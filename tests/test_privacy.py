import re
from datetime import date

from privacy import pulisci_dati_scaduti, scadenza_anno_scolastico
from test_app import app, crea_materia, link_invito, nuovo_client, post, rappresentante  # noqa: F401


def test_registrazione_richiede_eta_e_privacy(app):
    c = nuovo_client(app)
    r = post(c, "/registrati", username="rapp", password="password1", conferma="password1")
    testo = r.get_data(as_text=True)
    assert "almeno 14 anni" in testo and "informativa" in testo
    assert c.get("/classe").status_code == 302  # non loggato


def test_intestazioni_e_robots(app):
    c = rappresentante(app)
    r = nuovo_client(app).get(link_invito(c))
    assert r.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "X-Robots-Tag" not in nuovo_client(app).get("/").headers
    assert "Disallow: /c/" in nuovo_client(app).get("/robots.txt").get_data(as_text=True)


def test_informativa(app):
    app.config["TITOLARE_EMAIL"] = "privacy@esempio.it"
    testo = nuovo_client(app).get("/privacy").get_data(as_text=True)
    assert "privacy@esempio.it" in testo and "31 agosto" in testo


def test_pin(app):
    c = rappresentante(app)
    url = crea_materia(c)
    link = link_invito(c)
    materia = f"{link}/materie/{url.rsplit('/', 1)[1]}"
    post(c, "/classe/pin", pin="12")  # troppo corto: ignorato
    assert nuovo_client(app).get(link).status_code == 200
    post(c, "/classe/pin", pin="4321")

    ospite = nuovo_client(app)
    for pagina in (link, materia, materia + "/calendario.csv"):
        r = ospite.get(pagina)
        assert r.status_code == 302 and r.headers["Location"].endswith("/pin")
    assert "PIN errato" in post(ospite, link + "/pin", pin="0000").get_data(as_text=True)
    assert post(ospite, link + "/pin", pin="4321").status_code == 302
    assert "<li>Anna</li>" in ospite.get(materia).get_data(as_text=True)

    # cambiando PIN, chi era entrato con quello vecchio deve reinserirlo
    post(c, "/classe/pin", pin="9999")
    assert ospite.get(link).status_code == 302
    post(c, "/classe/pin", rimuovi="1")
    assert ospite.get(link).status_code == 200


def test_pin_bloccato_dopo_troppi_errori(app):
    c = rappresentante(app)
    post(c, "/classe/pin", pin="4321")
    link = link_invito(c)
    ospite = nuovo_client(app)
    for _ in range(10):
        post(ospite, link + "/pin", pin="0000")
    r = post(ospite, link + "/pin", pin="4321")
    assert "Troppi tentativi" in r.get_data(as_text=True)


def test_elimina_account(app):
    c = rappresentante(app)
    link = link_invito(c)
    assert "non eliminato" in post(c, "/account", password="sbagliata").get_data(as_text=True)
    assert post(c, "/account", password="password1").status_code == 302
    assert nuovo_client(app).get(link).status_code == 404
    with c.session_transaction() as s:
        s["csrf_token"] = "tok"
    assert "errati" in post(c, "/accedi", username="rapp", password="password1").get_data(as_text=True)


def test_scadenza_anno_scolastico():
    assert scadenza_anno_scolastico(date(2026, 10, 12)) == date(2027, 8, 31)
    assert scadenza_anno_scolastico(date(2027, 3, 1)) == date(2027, 8, 31)
    assert scadenza_anno_scolastico(date(2027, 7, 15)) == date(2028, 8, 31)  # troppo vicina


def test_pulizia_dati_scaduti(app):
    c = rappresentante(app)
    link = link_invito(c)
    pagina = c.get("/classe").get_data(as_text=True)
    assert re.search(r"cancellati automaticamente il \w+ 31 agosto", pagina)
    with app.app_context():
        assert pulisci_dati_scaduti(date(2026, 9, 1)) == (0, 0)
        assert pulisci_dati_scaduti(date(2100, 1, 1)) == (1, 1)
    assert nuovo_client(app).get(link).status_code == 404
