import csv
import io
import os
from datetime import date

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)

from db import get_db, init_db
from scheduler import distribuisci, parse_date

MAX_STUDENTI = 200

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
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    init_db(app)
    app.jinja_env.filters["data_it"] = formatta_data

    @app.route("/")
    def index():
        materie = get_db().execute("""
            SELECT m.id, m.nome,
                   (SELECT COUNT(*) FROM studenti s WHERE s.materia_id = m.id) AS n_studenti,
                   (SELECT COUNT(*) FROM date_interrogazione d WHERE d.materia_id = m.id) AS n_date,
                   (SELECT MIN(giorno) FROM date_interrogazione d WHERE d.materia_id = m.id) AS prima,
                   (SELECT MAX(giorno) FROM date_interrogazione d WHERE d.materia_id = m.id) AS ultima
            FROM materie m ORDER BY m.id DESC
        """).fetchall()
        return render_template("index.html", materie=materie)

    @app.route("/materie/nuova", methods=["GET", "POST"])
    def nuova_materia():
        form = request.form
        if request.method == "POST":
            errori, dati = valida(form)
            if not errori:
                materia_id = salva_materia(**dati)
                flash("Calendario generato!")
                return redirect(url_for("materia", materia_id=materia_id))
            for e in errori:
                flash(e, "errore")
        return render_template("nuova.html", form=form,
                               date_inserite=form.getlist("date") or [""])

    @app.route("/materie/<int:materia_id>")
    def materia(materia_id):
        m, calendario = carica_calendario(materia_id)
        return render_template("materia.html", materia=m, calendario=calendario,
                               oggi=date.today().isoformat())

    @app.post("/materie/<int:materia_id>/rigenera")
    def rigenera(materia_id):
        carica_calendario(materia_id)  # 404 se non esiste
        assegna(materia_id)
        get_db().commit()
        flash("Nuova estrazione effettuata.")
        return redirect(url_for("materia", materia_id=materia_id))

    @app.post("/materie/<int:materia_id>/elimina")
    def elimina(materia_id):
        db = get_db()
        db.execute("DELETE FROM materie WHERE id = ?", (materia_id,))
        db.commit()
        flash("Materia eliminata.")
        return redirect(url_for("index"))

    @app.route("/materie/<int:materia_id>/calendario.csv")
    def esporta_csv(materia_id):
        m, calendario = carica_calendario(materia_id)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Data", "Ordine", "Studente"])
        for giorno, studenti in calendario:
            for i, s in enumerate(studenti, 1):
                w.writerow([giorno, i, s])
        nome_file = "".join(c if c.isalnum() else "_" for c in m["nome"]) or "calendario"
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{nome_file}.csv"'})

    return app


def valida(form):
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

    nomi = [r.strip() for r in form.get("nomi", "").splitlines() if r.strip()]
    if nomi:
        studenti = nomi
    else:
        try:
            n = int(form.get("numero", ""))
        except ValueError:
            n = 0
        if n < 1:
            errori.append("Il numero di studenti deve essere almeno 1.")
        studenti = [f"Studente {i}" for i in range(1, n + 1)]
    if len(studenti) > MAX_STUDENTI:
        errori.append(f"Massimo {MAX_STUDENTI} studenti.")

    return errori, {"nome": nome, "giorni": giorni, "studenti": studenti}


def salva_materia(nome, giorni, studenti):
    db = get_db()
    materia_id = db.execute("INSERT INTO materie (nome) VALUES (?)", (nome,)).lastrowid
    db.executemany("INSERT INTO date_interrogazione (materia_id, giorno) VALUES (?, ?)",
                   [(materia_id, g.isoformat()) for g in giorni])
    db.executemany("INSERT INTO studenti (materia_id, nome) VALUES (?, ?)",
                   [(materia_id, s) for s in studenti])
    assegna(materia_id)
    db.commit()
    return materia_id


def assegna(materia_id):
    """(Ri)estrae a sorte l'assegnazione studenti → date per una materia."""
    db = get_db()
    date_ids = {r["giorno"]: r["id"] for r in db.execute(
        "SELECT id, giorno FROM date_interrogazione WHERE materia_id = ?", (materia_id,))}
    studenti = [r["id"] for r in db.execute(
        "SELECT id FROM studenti WHERE materia_id = ?", (materia_id,))]
    piano = distribuisci(studenti, list(date_ids))
    db.executemany("UPDATE studenti SET data_id = ?, ordine = ? WHERE id = ?",
                   [(date_ids[giorno], i, s)
                    for giorno, ids in piano.items()
                    for i, s in enumerate(ids, 1)])


def carica_calendario(materia_id):
    db = get_db()
    m = db.execute("SELECT * FROM materie WHERE id = ?", (materia_id,)).fetchone()
    if m is None:
        abort(404)
    calendario = []
    for d in db.execute("SELECT id, giorno FROM date_interrogazione "
                        "WHERE materia_id = ? ORDER BY giorno", (materia_id,)).fetchall():
        nomi = [r["nome"] for r in db.execute(
            "SELECT nome FROM studenti WHERE data_id = ? ORDER BY ordine", (d["id"],))]
        calendario.append((d["giorno"], nomi))
    return m, calendario


if __name__ == "__main__":
    create_app().run(debug=True)
