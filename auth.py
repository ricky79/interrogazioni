"""Account dei rappresentanti: registrazione, login e protezione CSRF."""

import functools
import hmac
import secrets
import sqlite3
from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db

bp = Blueprint("auth", __name__)

MIN_PASSWORD = 8


@bp.before_app_request
def carica_utente():
    uid = session.get("utente_id")
    g.utente = None
    if uid is not None:
        db = get_db()
        g.utente = db.execute(
            "SELECT id, username, ultimo_accesso FROM utenti WHERE id = ?", (uid,)).fetchone()
        oggi = date.today().isoformat()
        if g.utente and g.utente["ultimo_accesso"] != oggi:
            db.execute("UPDATE utenti SET ultimo_accesso = ? WHERE id = ?", (oggi, uid))
            db.commit()


@bp.before_app_request
def verifica_csrf():
    if request.method == "POST":
        atteso = session.get("csrf_token", "")
        ricevuto = request.form.get("csrf_token", "")
        if not atteso or not hmac.compare_digest(atteso, ricevuto):
            abort(400, "Token CSRF non valido: ricarica la pagina e riprova.")


@bp.app_template_global()
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def login_required(view):
    @functools.wraps(view)
    def wrapper(**kwargs):
        if g.utente is None:
            flash("Accedi per continuare.", "errore")
            return redirect(url_for("auth.accedi"))
        return view(**kwargs)
    return wrapper


def _accedi_come(utente_id):
    token = session.get("csrf_token")
    session.clear()  # evita session fixation
    session["utente_id"] = utente_id
    if token:
        session["csrf_token"] = token


@bp.route("/registrati", methods=["GET", "POST"])
def registrati():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        errori = []
        if not 3 <= len(username) <= 40:
            errori.append("Il nome utente deve avere tra 3 e 40 caratteri.")
        if len(password) < MIN_PASSWORD:
            errori.append(f"La password deve avere almeno {MIN_PASSWORD} caratteri.")
        if password != request.form.get("conferma", ""):
            errori.append("Le due password non coincidono.")
        if not request.form.get("eta"):
            errori.append("Per registrarti devi avere almeno 14 anni.")
        if not request.form.get("privacy"):
            errori.append("Devi accettare l'informativa privacy.")
        if not errori:
            db = get_db()
            try:
                uid = db.execute(
                    "INSERT INTO utenti (username, password_hash, privacy_accettata_il) "
                    "VALUES (?, ?, datetime('now'))",
                    (username, generate_password_hash(password))).lastrowid
                db.commit()
            except sqlite3.IntegrityError:
                errori.append("Nome utente già in uso.")
            else:
                _accedi_come(uid)
                flash("Account creato! Ora crea la tua prima classe.")
                return redirect(url_for("index"))
        for e in errori:
            flash(e, "errore")
    return render_template("auth.html", registrazione=True, form=request.form)


@bp.route("/accedi", methods=["GET", "POST"])
def accedi():
    if request.method == "POST":
        utente = get_db().execute(
            "SELECT id, password_hash FROM utenti WHERE username = ?",
            (request.form.get("username", "").strip(),)).fetchone()
        if utente and check_password_hash(utente["password_hash"], request.form.get("password", "")):
            _accedi_come(utente["id"])
            return redirect(url_for("index"))
        flash("Nome utente o password errati.", "errore")
    return render_template("auth.html", registrazione=False, form=request.form)


@bp.post("/esci")
def esci():
    session.clear()
    return redirect(url_for("index"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        db = get_db()
        hash_ = db.execute("SELECT password_hash FROM utenti WHERE id = ?",
                           (g.utente["id"],)).fetchone()["password_hash"]
        if check_password_hash(hash_, request.form.get("password", "")):
            db.execute("DELETE FROM utenti WHERE id = ?", (g.utente["id"],))
            db.commit()
            session.clear()
            flash("Account e dati della classe cancellati definitivamente.")
            return redirect(url_for("index"))
        flash("Password errata: account non eliminato.", "errore")
    return render_template("account.html")
