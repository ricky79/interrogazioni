"""Account dei rappresentanti: registrazione, login e protezione CSRF."""

import functools
import hmac
import secrets
import sqlite3

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
        g.utente = get_db().execute(
            "SELECT id, username FROM utenti WHERE id = ?", (uid,)).fetchone()


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
        if not errori:
            db = get_db()
            try:
                uid = db.execute(
                    "INSERT INTO utenti (username, password_hash) VALUES (?, ?)",
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
