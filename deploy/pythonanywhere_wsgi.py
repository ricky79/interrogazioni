# File WSGI per PythonAnywhere (account "interrogazioni", server UE).
# Copialo in: Web → "WSGI configuration file" e sostituisci tutto il contenuto.

import os
import sys

PROGETTO = "/home/interrogazioni/interrogazioni"
if PROGETTO not in sys.path:
    sys.path.insert(0, PROGETTO)

# Chiave segreta per i login: incolla qui quella generata con
#   python3 -c "import secrets; print(secrets.token_hex(32))"
os.environ["SECRET_KEY"] = "INCOLLA-QUI-LA-CHIAVE-GENERATA"

# Dati mostrati nell'informativa privacy (/privacy)
os.environ["TITOLARE_NOME"] = "Il tuo nome e cognome"
os.environ["TITOLARE_EMAIL"] = "la-tua-email@esempio.it"
os.environ["HOSTING"] = "PythonAnywhere (Anaconda Inc.), server nell'Unione Europea"

if os.environ["SECRET_KEY"].startswith("INCOLLA"):
    raise RuntimeError("Imposta SECRET_KEY nel file WSGI prima di avviare il sito")

from app import create_app  # noqa: E402

application = create_app()
