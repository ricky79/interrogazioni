import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    return app.test_client()


def crea(client, **extra):
    dati = {"nome": "Storia", "date": ["2026-11-03", "2026-11-05", "2026-11-10"], "numero": "10"}
    dati.update(extra)
    return client.post("/materie/nuova", data=dati)


def test_creazione_e_calendario(client):
    r = crea(client)
    assert r.status_code == 302
    pagina = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Storia" in pagina
    assert "martedì 3 novembre 2026" in pagina
    assert sum(pagina.count(f"<li>Studente {i}</li>") for i in range(1, 11)) == 10


def test_nomi_personalizzati(client):
    r = crea(client, nomi="Anna\nLuca\n\nMarco\n")
    pagina = client.get(r.headers["Location"]).get_data(as_text=True)
    for nome in ("Anna", "Luca", "Marco"):
        assert f"<li>{nome}</li>" in pagina
    assert "Studente 1" not in pagina


def test_validazione(client):
    r = crea(client, nome="", date=[""], numero="0")
    testo = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "nome della materia" in testo
    assert "almeno una data" in testo


def test_rigenera_csv_elimina(client):
    url = crea(client).headers["Location"]
    assert client.post(url + "/rigenera").status_code == 302
    csv = client.get(url + "/calendario.csv").get_data(as_text=True)
    assert len(csv.strip().splitlines()) == 11
    client.post(url + "/elimina")
    assert client.get(url).status_code == 404
