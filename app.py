import csv
import io
import os
import secrets
from datetime import date

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, url_for)

from werkzeug.security import generate_password_hash

import auth
import privacy
from auth import login_required
from db import get_db, init_db
from privacy import richiedi_pin, scadenza_anno_scolastico
from scheduler import distribuisci, parse_date

MAX_ALUNNI = 200

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def formatta_data(iso):
    d = date.fromisoformat(iso)
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE=os.path.join(app.instance_path, "interrogazioni.sqlite"),
        SESSION_COOKIE_SAMESITE="Lax",
        # dati mostrati nell'informativa privacy
        TITOLARE_NOME=os.environ.get("TITOLARE_NOME"),
        TITOLARE_EMAIL=os.environ.get("TITOLARE_EMAIL"),
        HOSTING=os.environ.get("HOSTING"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    init_db(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(privacy.bp)
    app.jinja_env.filters["data_it"] = formatta_data

    # --- Area del rappresentante -------------------------------------------

    @app.route("/")
    def index():
        if g.utente is None:
            return render_template("home.html")
        if classe_utente() is None:
            return redirect(url_for("nuova_classe"))
        return redirect(url_for("classe"))

    @app.route("/classe/nuova", methods=["GET", "POST"])
    @login_required
    def nuova_classe():
        if classe_utente() is not None:
            return redirect(url_for("classe"))
        form = request.form
        if request.method == "POST":
            nome = form.get("nome", "").strip()
            errori, alunni = valida_alunni(form, obbligatori=True)
            if not nome:
                errori.insert(0, "Inserisci il nome della classe.")
            if not errori:
                db = get_db()
                classe_id = db.execute(
                    "INSERT INTO classi (utente_id, nome, token_invito, scade_il) VALUES (?, ?, ?, ?)",
                    (g.utente["id"], nome, secrets.token_urlsafe(16),
                     scadenza_anno_scolastico().isoformat())).lastrowid
                aggiungi_alunni(classe_id, alunni)
                db.commit()
                flash("Classe creata! Ora aggiungi la prima materia.")
                return redirect(url_for("classe"))
            for e in errori:
                flash(e, "errore")
        return render_template("classe_nuova.html", form=form)

    @app.route("/classe")
    @login_required
    def classe():
        c = classe_richiesta()
        return render_template("classe.html", classe=c, materie=elenco_materie(c["id"]),
                               alunni=elenco_alunni(c["id"]),
                               link_invito=url_for("pubblica", token=c["token_invito"], _external=True))

    @app.post("/classe/alunni")
    @login_required
    def modifica_alunni():
        c = classe_richiesta()
        db = get_db()
        ids_validi = {a["id"] for a in elenco_alunni(c["id"])}
        da_eliminare = {int(i) for i in request.form.getlist("elimina") if i.isdigit()} & ids_validi
        for alunno_id in ids_validi - da_eliminare:
            nome = request.form.get(f"nome_{alunno_id}", "").strip()
            if nome:
                db.execute("UPDATE alunni SET nome = ? WHERE id = ?", (nome, alunno_id))
        db.executemany("DELETE FROM alunni WHERE id = ?", [(i,) for i in da_eliminare])

        errori, nuovi = valida_alunni(request.form, obbligatori=False)
        if len(ids_validi) - len(da_eliminare) + len(nuovi) > MAX_ALUNNI:
            errori.append(f"Massimo {MAX_ALUNNI} alunni.")
        if errori:
            db.rollback()
            for e in errori:
                flash(e, "errore")
        else:
            aggiungi_alunni(c["id"], nuovi)
            db.commit()
            flash("Elenco alunni aggiornato.")
        return redirect(url_for("classe") + "#alunni")

    @app.post("/classe/invito")
    @login_required
    def rigenera_invito():
        c = classe_richiesta()
        db = get_db()
        db.execute("UPDATE classi SET token_invito = ? WHERE id = ?",
                   (secrets.token_urlsafe(16), c["id"]))
        db.commit()
        flash("Nuovo link di invito creato: quello vecchio non funziona più.")
        return redirect(url_for("classe"))

    @app.post("/classe/pin")
    @login_required
    def imposta_pin():
        c = classe_richiesta()
        db = get_db()
        if request.form.get("rimuovi"):
            db.execute("UPDATE classi SET pin_hash = NULL WHERE id = ?", (c["id"],))
            flash("PIN rimosso: basta il link per vedere i calendari.")
        else:
            pin = request.form.get("pin", "").strip()
            if not 4 <= len(pin) <= 12:
                flash("Il PIN deve avere tra 4 e 12 caratteri.", "errore")
                return redirect(url_for("classe") + "#pin")
            db.execute("UPDATE classi SET pin_hash = ?, pin_errori = 0, pin_bloccato_fino = NULL "
                       "WHERE id = ?", (generate_password_hash(pin), c["id"]))
            flash("PIN impostato: comunicalo ai compagni separatamente dal link.")
        db.commit()
        return redirect(url_for("classe") + "#pin")

    @app.post("/classe/elimina")
    @login_required
    def elimina_classe():
        c = classe_richiesta()
        db = get_db()
        db.execute("DELETE FROM classi WHERE id = ?", (c["id"],))
        db.commit()
        flash("Classe eliminata.")
        return redirect(url_for("index"))

    @app.route("/classe/materie/nuova", methods=["GET", "POST"])
    @login_required
    def nuova_materia():
        c = classe_richiesta()
        form = request.form
        if request.method == "POST":
            errori, nome, giorni = valida_materia(form)
            if not elenco_alunni(c["id"]):
                errori.append("Aggiungi prima gli alunni della classe.")
            if not errori:
                materia_id = salva_materia(c["id"], nome, giorni)
                flash("Calendario generato!")
                return redirect(url_for("materia", materia_id=materia_id))
            for e in errori:
                flash(e, "errore")
        return render_template("materia_nuova.html", form=form, n_alunni=len(elenco_alunni(c["id"])),
                               date_inserite=form.getlist("date") or [""])

    @app.route("/materie/<int:materia_id>")
    @login_required
    def materia(materia_id):
        m = materia_richiesta(materia_id)
        return mostra_materia(m, admin=True)

    @app.post("/materie/<int:materia_id>/rigenera")
    @login_required
    def rigenera(materia_id):
        m = materia_richiesta(materia_id)
        assegna(m["id"])
        get_db().commit()
        flash("Nuova estrazione effettuata.")
        return redirect(url_for("materia", materia_id=materia_id))

    @app.post("/materie/<int:materia_id>/elimina")
    @login_required
    def elimina_materia(materia_id):
        m = materia_richiesta(materia_id)
        db = get_db()
        db.execute("DELETE FROM materie WHERE id = ?", (m["id"],))
        db.commit()
        flash("Materia eliminata.")
        return redirect(url_for("classe"))

    @app.route("/materie/<int:materia_id>/calendario.csv")
    @login_required
    def esporta_csv(materia_id):
        return csv_materia(materia_richiesta(materia_id))

    # --- Vista in sola lettura per i compagni (link di invito) ---------------

    @app.route("/c/<token>")
    def pubblica(token):
        c = classe_da_token(token)
        alunni = elenco_alunni(c["id"])
        scelto = request.args.get("alunno", type=int)
        mie = None
        if scelto in {a["id"] for a in alunni}:
            mie = get_db().execute("""
                SELECT m.nome AS materia, d.giorno, a.ordine
                FROM assegnazioni a
                JOIN materie m ON m.id = a.materia_id
                JOIN date_interrogazione d ON d.id = a.data_id
                WHERE a.alunno_id = ? ORDER BY d.giorno, m.nome
            """, (scelto,)).fetchall()
        return render_template("classe_pubblica.html", classe=c, materie=elenco_materie(c["id"]),
                               alunni=alunni, scelto=scelto, mie=mie, pubblica=True,
                               oggi=date.today().isoformat())

    @app.route("/c/<token>/materie/<int:materia_id>")
    def materia_pubblica(token, materia_id):
        return mostra_materia(materia_da_token(token, materia_id), admin=False)

    @app.route("/c/<token>/materie/<int:materia_id>/calendario.csv")
    def csv_pubblico(token, materia_id):
        return csv_materia(materia_da_token(token, materia_id))

    return app


# --- Accesso ai dati (con controllo dei permessi) ----------------------------

def classe_utente():
    return get_db().execute("SELECT * FROM classi WHERE utente_id = ?",
                            (g.utente["id"],)).fetchone()


def classe_richiesta():
    c = classe_utente()
    if c is None:
        abort(redirect(url_for("nuova_classe")))
    return c


def materia_richiesta(materia_id):
    """Materia della classe del rappresentante loggato, altrimenti 404."""
    m = get_db().execute("""
        SELECT m.*, c.token_invito FROM materie m JOIN classi c ON c.id = m.classe_id
        WHERE m.id = ? AND c.utente_id = ?
    """, (materia_id, g.utente["id"])).fetchone()
    if m is None:
        abort(404)
    return m


def classe_da_token(token):
    c = get_db().execute("SELECT * FROM classi WHERE token_invito = ?", (token,)).fetchone()
    if c is None:
        abort(404)
    richiedi_pin(c)
    return c


def materia_da_token(token, materia_id):
    c = classe_da_token(token)
    m = get_db().execute("""
        SELECT m.*, c.token_invito FROM materie m JOIN classi c ON c.id = m.classe_id
        WHERE m.id = ? AND c.id = ?
    """, (materia_id, c["id"])).fetchone()
    if m is None:
        abort(404)
    return m


def elenco_alunni(classe_id):
    return get_db().execute("SELECT id, nome FROM alunni WHERE classe_id = ? ORDER BY posizione, id",
                            (classe_id,)).fetchall()


def elenco_materie(classe_id):
    return get_db().execute("""
        SELECT m.id, m.nome,
               (SELECT COUNT(*) FROM date_interrogazione d WHERE d.materia_id = m.id) AS n_date,
               (SELECT MIN(giorno) FROM date_interrogazione d WHERE d.materia_id = m.id) AS prima,
               (SELECT MAX(giorno) FROM date_interrogazione d WHERE d.materia_id = m.id) AS ultima
        FROM materie m WHERE m.classe_id = ? ORDER BY m.nome
    """, (classe_id,)).fetchall()


def aggiungi_alunni(classe_id, nomi):
    db = get_db()
    inizio = db.execute("SELECT COALESCE(MAX(posizione), 0) FROM alunni WHERE classe_id = ?",
                        (classe_id,)).fetchone()[0]
    db.executemany("INSERT INTO alunni (classe_id, nome, posizione) VALUES (?, ?, ?)",
                   [(classe_id, n, inizio + i) for i, n in enumerate(nomi, 1)])


# --- Validazione --------------------------------------------------------------

def valida_alunni(form, obbligatori):
    """Legge i nomi (uno per riga) o, in alternativa, un numero di alunni anonimi."""
    errori = []
    nomi = [r.strip() for r in form.get("nomi", "").splitlines() if r.strip()]
    if not nomi and form.get("numero", "").strip():
        try:
            n = int(form["numero"])
        except ValueError:
            n = 0
        if n < 1:
            errori.append("Il numero di alunni deve essere almeno 1.")
        nomi = [f"Alunno {i}" for i in range(1, n + 1)]
    if obbligatori and not nomi and not errori:
        errori.append("Inserisci i nomi degli alunni oppure il loro numero.")
    if len(nomi) > MAX_ALUNNI:
        errori.append(f"Massimo {MAX_ALUNNI} alunni.")
    if any(len(n) > 80 for n in nomi):
        errori.append("Un nome è troppo lungo (massimo 80 caratteri).")
    return errori, nomi


def valida_materia(form):
    errori = []
    nome = form.get("nome", "").strip()
    if not nome:
        errori.append("Inserisci il nome della materia.")
    try:
        giorni = parse_date(form.getlist("date"))
    except ValueError:
        giorni = []
        errori.append("Una delle date non è valida.")
    else:
        if not giorni:
            errori.append("Inserisci almeno una data.")
    return errori, nome, giorni


# --- Calendari ----------------------------------------------------------------

def salva_materia(classe_id, nome, giorni):
    db = get_db()
    materia_id = db.execute("INSERT INTO materie (classe_id, nome) VALUES (?, ?)",
                            (classe_id, nome)).lastrowid
    db.executemany("INSERT INTO date_interrogazione (materia_id, giorno) VALUES (?, ?)",
                   [(materia_id, g.isoformat()) for g in giorni])
    assegna(materia_id)
    db.commit()
    return materia_id


def assegna(materia_id):
    """(Ri)estrae a sorte l'assegnazione alunni → date per una materia."""
    db = get_db()
    date_ids = {r["giorno"]: r["id"] for r in db.execute(
        "SELECT id, giorno FROM date_interrogazione WHERE materia_id = ?", (materia_id,))}
    alunni = [r["id"] for r in db.execute(
        "SELECT a.id FROM alunni a JOIN materie m ON m.classe_id = a.classe_id WHERE m.id = ?",
        (materia_id,))]
    piano = distribuisci(alunni, list(date_ids))
    db.execute("DELETE FROM assegnazioni WHERE materia_id = ?", (materia_id,))
    db.executemany("INSERT INTO assegnazioni (materia_id, alunno_id, data_id, ordine) VALUES (?, ?, ?, ?)",
                   [(materia_id, a, date_ids[giorno], i)
                    for giorno, ids in piano.items()
                    for i, a in enumerate(ids, 1)])


def carica_calendario(materia_id):
    db = get_db()
    calendario = []
    for d in db.execute("SELECT id, giorno FROM date_interrogazione "
                        "WHERE materia_id = ? ORDER BY giorno", (materia_id,)).fetchall():
        nomi = [r["nome"] for r in db.execute(
            "SELECT al.nome FROM assegnazioni a JOIN alunni al ON al.id = a.alunno_id "
            "WHERE a.data_id = ? ORDER BY a.ordine", (d["id"],))]
        calendario.append((d["giorno"], nomi))
    return calendario


def non_assegnati(materia_id):
    """Alunni aggiunti alla classe dopo l'ultima estrazione di questa materia."""
    return get_db().execute("""
        SELECT al.nome FROM alunni al JOIN materie m ON m.classe_id = al.classe_id
        WHERE m.id = ? AND al.id NOT IN (SELECT alunno_id FROM assegnazioni WHERE materia_id = ?)
        ORDER BY al.posizione
    """, (materia_id, materia_id)).fetchall()


def mostra_materia(m, admin):
    return render_template("materia.html", materia=m, admin=admin, pubblica=not admin,
                           calendario=carica_calendario(m["id"]),
                           non_assegnati=non_assegnati(m["id"]),
                           oggi=date.today().isoformat())


def csv_materia(m):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Data", "Ordine", "Alunno"])
    for giorno, alunni in carica_calendario(m["id"]):
        for i, nome in enumerate(alunni, 1):
            # evita che Excel interpreti un nome come formula
            w.writerow([giorno, i, "'" + nome if nome[:1] in "=+-@" else nome])
    nome_file = "".join(c if c.isalnum() else "_" for c in m["nome"]) or "calendario"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{nome_file}.csv"'})


if __name__ == "__main__":
    create_app().run(debug=True)
