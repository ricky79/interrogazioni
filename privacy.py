"""Misure privacy: PIN della classe, intestazioni anti-indicizzazione,
cancellazione automatica dei dati e informativa."""

import hmac
from datetime import date, datetime, timedelta

import click
from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

from db import get_db

bp = Blueprint("privacy", __name__, cli_group=None)

MAX_ERRORI_PIN = 10
BLOCCO_PIN = timedelta(minutes=15)
INATTIVITA_MAX = timedelta(days=400)  # account mai più usati da oltre un anno


# --- Scadenza dei dati --------------------------------------------------------

def scadenza_anno_scolastico(oggi=None):
    """31 agosto della fine dell'anno scolastico in corso (almeno 60 giorni da oggi)."""
    oggi = oggi or date.today()
    scadenza = date(oggi.year + (1 if oggi.month >= 9 else 0), 8, 31)
    if scadenza - oggi < timedelta(days=60):
        scadenza = scadenza.replace(year=scadenza.year + 1)
    return scadenza


def pulisci_dati_scaduti(oggi=None):
    """Cancella le classi scadute e gli account inattivi da più di un anno."""
    oggi = oggi or date.today()
    db = get_db()
    classi = db.execute("DELETE FROM classi WHERE scade_il < ?", (oggi.isoformat(),)).rowcount
    utenti = db.execute("DELETE FROM utenti WHERE ultimo_accesso < ?",
                        ((oggi - INATTIVITA_MAX).isoformat(),)).rowcount
    db.commit()
    return classi, utenti


@bp.before_app_request
def pulizia_periodica():
    """Esegue la pulizia al massimo una volta al giorno, alla prima richiesta."""
    oggi = date.today()
    if current_app.config.get("_ULTIMA_PULIZIA") != oggi:
        current_app.config["_ULTIMA_PULIZIA"] = oggi
        pulisci_dati_scaduti(oggi)


@bp.cli.command("pulizia")
def comando_pulizia():
    """Cancella subito i dati scaduti (utile come attività pianificata)."""
    classi, utenti = pulisci_dati_scaduti()
    click.echo(f"Classi cancellate: {classi}, account cancellati: {utenti}")


# --- Intestazioni HTTP --------------------------------------------------------

PAGINE_INDICIZZABILI = {"/", "/privacy"}


@bp.after_app_request
def intestazioni_privacy(risposta):
    risposta.headers["Referrer-Policy"] = "no-referrer"
    risposta.headers["X-Content-Type-Options"] = "nosniff"
    risposta.headers["X-Frame-Options"] = "DENY"
    if request.path not in PAGINE_INDICIZZABILI:
        risposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    return risposta


@bp.route("/robots.txt")
def robots():
    return current_app.response_class("User-agent: *\nDisallow: /c/\n", mimetype="text/plain")


# --- PIN della classe ---------------------------------------------------------

def _impronta_pin(classe):
    # cambia quando il rappresentante cambia PIN, così gli sblocchi vecchi decadono
    return classe["pin_hash"][-16:]


def richiedi_pin(classe):
    """Interrompe la richiesta con la pagina del PIN se la classe è protetta e non sbloccata."""
    if not classe["pin_hash"]:
        return
    sbloccate = session.get("pin_ok", {})
    if hmac.compare_digest(sbloccate.get(str(classe["id"]), ""), _impronta_pin(classe)):
        return
    abort(redirect(url_for("privacy.inserisci_pin", token=classe["token_invito"])))


@bp.route("/c/<token>/pin", methods=["GET", "POST"])
def inserisci_pin(token):
    db = get_db()
    classe = db.execute("SELECT * FROM classi WHERE token_invito = ?", (token,)).fetchone()
    if classe is None:
        abort(404)
    if not classe["pin_hash"]:
        return redirect(url_for("pubblica", token=token))

    if request.method == "POST":
        adesso = datetime.now()
        bloccata = classe["pin_bloccato_fino"] and datetime.fromisoformat(classe["pin_bloccato_fino"]) > adesso
        if bloccata:
            flash("Troppi tentativi errati: riprova tra qualche minuto.", "errore")
        elif check_password_hash(classe["pin_hash"], request.form.get("pin", "").strip()):
            db.execute("UPDATE classi SET pin_errori = 0, pin_bloccato_fino = NULL WHERE id = ?",
                       (classe["id"],))
            db.commit()
            session["pin_ok"] = {**session.get("pin_ok", {}), str(classe["id"]): _impronta_pin(classe)}
            return redirect(url_for("pubblica", token=token))
        else:
            errori = classe["pin_errori"] + 1
            blocco = (adesso + BLOCCO_PIN).isoformat() if errori >= MAX_ERRORI_PIN else None
            db.execute("UPDATE classi SET pin_errori = ?, pin_bloccato_fino = ? WHERE id = ?",
                       (0 if blocco else errori, blocco, classe["id"]))
            db.commit()
            flash("PIN errato.", "errore")
    return render_template("pin.html", classe=classe, pubblica=True)


# --- Informativa --------------------------------------------------------------

@bp.route("/privacy")
def informativa():
    cfg = current_app.config
    return render_template("privacy.html",
                           titolare=cfg.get("TITOLARE_NOME") or "[nome del titolare da completare]",
                           contatto=cfg.get("TITOLARE_EMAIL") or "[email di contatto da completare]",
                           hosting=cfg.get("HOSTING") or "[fornitore di hosting e paese da completare]")
