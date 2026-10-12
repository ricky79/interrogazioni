import re

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})


def nuovo_client(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf_token"] = "tok"
    return c


def post(client, url, **dati):
    return client.post(url, data={"csrf_token": "tok", **dati})


def rappresentante(app, username="rapp", nomi="Anna\nLuca\nMarco\nSara", numero=""):
    c = nuovo_client(app)
    post(c, "/registrati", username=username, password="password1", conferma="password1",
         eta="1", privacy="1")
    post(c, "/classe/nuova", nome=f"Classe di {username}", nomi=nomi, numero=numero)
    return c


def crea_materia(client, nome="Storia"):
    r = post(client, "/classe/materie/nuova", nome=nome, date=["2026-11-03", "2026-11-05"])
    assert r.status_code == 302
    return r.headers["Location"]


def link_invito(client):
    pagina = client.get("/classe").get_data(as_text=True)
    return re.search(r'id="link" value="http://localhost(/c/[^"]+)"', pagina).group(1)


def test_csrf_obbligatorio(app):
    c = nuovo_client(app)
    r = c.post("/registrati", data={"username": "x", "password": "password1", "conferma": "password1"})
    assert r.status_code == 400


def test_registrazione_login_logout(app):
    c = rappresentante(app)
    post(c, "/esci")
    assert c.get("/classe").status_code == 302
    with c.session_transaction() as sess:  # il logout azzera anche il token CSRF
        sess["csrf_token"] = "tok"
    r = post(c, "/accedi", username="rapp", password="sbagliata")
    assert "errati" in r.get_data(as_text=True)
    assert post(c, "/accedi", username="RAPP", password="password1").status_code == 302
    assert c.get("/classe").status_code == 200


def test_username_duplicato(app):
    rappresentante(app)
    c = nuovo_client(app)
    r = post(c, "/registrati", username="rapp", password="password1", conferma="password1",
             eta="1", privacy="1")
    assert "già in uso" in r.get_data(as_text=True)


def test_una_classe_per_rappresentante(app):
    c = rappresentante(app)
    r = post(c, "/classe/nuova", nome="Seconda", nomi="X")
    assert r.headers["Location"].endswith("/classe")
    assert "Seconda" not in c.get("/classe").get_data(as_text=True)


def test_calendario_con_nomi(app):
    c = rappresentante(app)
    pagina = c.get(crea_materia(c)).get_data(as_text=True)
    assert "martedì 3 novembre 2026" in pagina
    for nome in ("Anna", "Luca", "Marco", "Sara"):
        assert f"<li>{nome}</li>" in pagina


def test_classe_con_numero_poi_rinomina(app):
    c = rappresentante(app, nomi="", numero="3")
    url = crea_materia(c)
    assert "<li>Alunno 1</li>" in c.get(url).get_data(as_text=True)
    alunni = re.findall(r'name="nome_(\d+)" value="Alunno 1"', c.get("/classe").get_data(as_text=True))
    post(c, "/classe/alunni", **{f"nome_{alunni[0]}": "Giulia Verdi"})
    pagina = c.get(url).get_data(as_text=True)
    assert "<li>Giulia Verdi</li>" in pagina and "Alunno 1" not in pagina


def test_aggiunta_e_rimozione_alunni(app):
    c = rappresentante(app)
    url = crea_materia(c)
    anna = re.search(r'name="nome_(\d+)" value="Anna"', c.get("/classe").get_data(as_text=True)).group(1)
    post(c, "/classe/alunni", elimina=anna, nomi="Nuovo")
    pagina = c.get(url).get_data(as_text=True)
    assert "<li>Anna</li>" not in pagina
    assert "Non ancora assegnati: Nuovo" in pagina
    post(c, url + "/rigenera")
    assert "<li>Nuovo</li>" in c.get(url).get_data(as_text=True)


def test_link_invito_sola_lettura(app):
    c = rappresentante(app)
    url_materia = crea_materia(c)
    link = link_invito(c)
    materia_id = url_materia.rsplit("/", 1)[1]

    ospite = nuovo_client(app)
    pagina = ospite.get(link).get_data(as_text=True)
    assert "Storia" in pagina and "Classe di rapp" in pagina
    pagina = ospite.get(f"{link}/materie/{materia_id}").get_data(as_text=True)
    assert "<li>Anna</li>" in pagina
    assert "Rifai estrazione" not in pagina and "Elimina" not in pagina
    assert ospite.get(f"{link}/materie/{materia_id}/calendario.csv").status_code == 200
    # l'ospite non può modificare
    assert post(ospite, f"/materie/{materia_id}/rigenera").status_code == 302
    assert ospite.get(f"/materie/{materia_id}").status_code == 302

    # quando tocca a me
    anna = re.search(r'<option value="(\d+)"\s*>Anna', ospite.get(link).get_data(as_text=True))
    mie = ospite.get(f"{link}?alunno={anna.group(1)}").get_data(as_text=True)
    assert "novembre 2026</strong> – Storia" in mie


def test_rigenera_invito_invalida_vecchio_link(app):
    c = rappresentante(app)
    vecchio = link_invito(c)
    post(c, "/classe/invito")
    assert c.get(vecchio).status_code == 404
    assert nuovo_client(app).get(link_invito(c)).status_code == 200


def test_classi_isolate(app):
    a = rappresentante(app, "rapp_a")
    url_a = crea_materia(a)
    b = rappresentante(app, "rapp_b", nomi="Zeno")
    materia_id = url_a.rsplit("/", 1)[1]
    assert b.get(url_a).status_code == 404
    assert post(b, f"/materie/{materia_id}/elimina").status_code == 404
    assert b.get(f"{link_invito(b)}/materie/{materia_id}").status_code == 404
    assert 'value="Anna"' not in b.get("/classe").get_data(as_text=True)


def test_validazione_materia(app):
    c = rappresentante(app)
    r = post(c, "/classe/materie/nuova", nome="", date=[""])
    testo = r.get_data(as_text=True)
    assert "nome della materia" in testo and "almeno una data" in testo


def test_csv_ed_eliminazioni(app):
    c = rappresentante(app)
    url = crea_materia(c)
    righe = c.get(url + "/calendario.csv").get_data(as_text=True).strip().splitlines()
    assert len(righe) == 5
    post(c, url + "/elimina")
    assert c.get(url).status_code == 404
    post(c, "/classe/elimina")
    assert c.get("/classe").headers["Location"].endswith("/classe/nuova")
