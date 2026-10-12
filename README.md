# interrogazioni

Web application per gestire le **interrogazioni programmate** di una classe: il
rappresentante configura alunni, materie e date e il sistema distribuisce a sorte
gli alunni sulle date in modo equilibrato.

## Funzionalità

- **Account da rappresentante** (nome utente + password): ogni rappresentante crea
  e gestisce **la propria classe** e vede solo quella
- **Alunni con nome** (uno per riga) oppure solo il numero, con nomi da completare in
  seguito; i nomi si possono modificare, aggiungere o rimuovere in qualsiasi momento
- **Materie** con le relative date: gli alunni della classe vengono estratti a sorte in
  modo equilibrato (differenza massima di 1 persona tra le date), con l'ordine del giorno
- **Link di invito** per i compagni: vedono i calendari in sola lettura senza registrarsi,
  e con "Quando tocca a me?" trovano subito le proprie date. Il link si può rigenerare
  per invalidare quello vecchio
- "Rifai estrazione", esportazione CSV (apribile in Excel), stampa
- Password salvate come hash, protezione CSRF sui form

## Avvio

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://127.0.0.1:5000
```

In produzione imposta la variabile d'ambiente `SECRET_KEY` con una stringa lunga e casuale.

## Test

```bash
.venv/bin/python -m pytest
```

## Struttura

| File | Contenuto |
|------|-----------|
| `scheduler.py` | algoritmo di distribuzione casuale (puro, testabile) |
| `app.py` | route Flask: area rappresentante, vista pubblica, validazione |
| `auth.py` | registrazione, login, protezione CSRF |
| `db.py` | schema e connessione SQLite |
| `templates/`, `static/` | interfaccia HTML/CSS |
