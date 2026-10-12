"""Algoritmo di distribuzione casuale degli studenti sulle date di interrogazione."""

import random
from datetime import date


def distribuisci(studenti, date_disponibili, rng=None):
    """Distribuisce casualmente gli studenti sulle date in modo equilibrato.

    Ogni data riceve n // d studenti; le n % d persone in eccesso vengono
    assegnate a date scelte a caso, così nessuna data è privilegiata.

    Restituisce un dict {data: [studenti nell'ordine di interrogazione]}
    con le date in ordine cronologico.
    """
    if not date_disponibili:
        raise ValueError("Serve almeno una data")

    rng = rng or random.Random()
    giorni = sorted(date_disponibili)
    mescolati = list(studenti)
    rng.shuffle(mescolati)

    base, extra = divmod(len(mescolati), len(giorni))
    con_extra = set(rng.sample(range(len(giorni)), extra))

    risultato = {}
    pos = 0
    for i, giorno in enumerate(giorni):
        quanti = base + (1 if i in con_extra else 0)
        risultato[giorno] = mescolati[pos:pos + quanti]
        pos += quanti
    return risultato


def parse_date(valori):
    """Converte stringhe ISO (YYYY-MM-DD) in date, ignorando vuoti e duplicati."""
    giorni = set()
    for v in valori:
        v = (v or "").strip()
        if v:
            giorni.add(date.fromisoformat(v))
    return sorted(giorni)
