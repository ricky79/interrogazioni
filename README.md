# interrogazioni

Web application per gestire le **interrogazioni programmate**: si configura una materia
(nome, date, numero di studenti o elenco nomi) e il sistema distribuisce casualmente
gli studenti sulle date in modo equilibrato.

## Funzionalità

- Configurazione materia: nome, date (aggiungibili una alla volta), numero di studenti
  oppure elenco nomi (uno per riga)
- Estrazione casuale equilibrata: ogni data riceve `n ÷ d` studenti, gli eventuali
  resti sono assegnati a date scelte a sorte (differenza massima di 1 persona tra le date)
- Ordine di interrogazione all'interno di ogni giornata
- "Rifai estrazione", esportazione CSV (apribile in Excel), stampa
- Più materie salvate in un database SQLite locale

## Avvio

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://127.0.0.1:5000
```

## Test

```bash
.venv/bin/python -m pytest
```

## Struttura

| File | Contenuto |
|------|-----------|
| `scheduler.py` | algoritmo di distribuzione casuale (puro, testabile) |
| `app.py` | route Flask e validazione del form |
| `db.py` | schema e connessione SQLite |
| `templates/`, `static/` | interfaccia HTML/CSS |
