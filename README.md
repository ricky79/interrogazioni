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
- **Estrazione coordinata tra le materie**: l'algoritmo tiene conto delle interrogazioni
  già fissate nelle altre materie, con queste regole in ordine di importanza:
  1. mai due interrogazioni nello stesso giorno (se le date lo permettono; altrimenti
     il rappresentante vede un avviso con i casi rimasti)
  2. chi è già uscito il primo giorno in un'altra materia non è di nuovo il primo
  3. chi è stato interrogato presto nelle altre materie va più avanti, e viceversa
  4. se possibile, niente interrogazioni in giorni consecutivi
- **Link di invito** per i compagni: vedono i calendari in sola lettura senza registrarsi,
  e con "Quando tocca a me?" trovano subito le proprie date. Il link si può rigenerare
  per invalidare quello vecchio
- "Rifai estrazione", esportazione CSV (apribile in Excel), stampa
- Password salvate come hash, protezione CSRF sui form

## Privacy

- Suggerimento e pulsante per usare **nome e iniziale del cognome** ("Anna B.")
- **PIN della classe** facoltativo, richiesto oltre al link di invito (bloccato per 15 minuti
  dopo 10 tentativi errati)
- Pagine delle classi escluse dai motori di ricerca (`X-Robots-Tag`, `robots.txt`) e
  `Referrer-Policy: no-referrer`, così il link non trapela verso altri siti
- Registrazione con conferma di **almeno 14 anni** e accettazione dell'**informativa** (`/privacy`)
- **Eliminazione dell'account** con cancellazione di tutti i dati
- **Cancellazione automatica** delle classi il 31 agosto e degli account inattivi da oltre un anno
- Solo il cookie tecnico di sessione: nessun banner cookie necessario

## Avvio

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://127.0.0.1:5000
```

In produzione imposta queste variabili d'ambiente:

| Variabile | Contenuto |
|-----------|-----------|
| `SECRET_KEY` | stringa lunga e casuale |
| `TITOLARE_NOME` | chi gestisce il sito (mostrato nell'informativa) |
| `TITOLARE_EMAIL` | email per le richieste privacy |
| `HOSTING` | fornitore e paese dei server, es. "PythonAnywhere, server in UE" |

La pulizia dei dati scaduti parte da sola una volta al giorno; si può anche lanciare
a mano con `flask --app app pulizia`.

## Test

```bash
.venv/bin/python -m pytest
```

## Struttura

| File | Contenuto |
|------|-----------|
| `scheduler.py` | algoritmo di distribuzione: estrazione casuale + ricerca locale sulle regole tra materie |
| `app.py` | route Flask: area rappresentante, vista pubblica, validazione |
| `auth.py` | registrazione, login, eliminazione account, protezione CSRF |
| `privacy.py` | PIN, intestazioni anti-indicizzazione, cancellazione automatica, informativa |
| `db.py` | schema e connessione SQLite |
| `templates/`, `static/` | interfaccia HTML/CSS |
