"""Algoritmo di distribuzione casuale degli studenti sulle date di interrogazione."""

import random
from collections import namedtuple
from datetime import date

# Un'interrogazione già fissata in un'altra materia: il giorno e la posizione
# relativa di quella data nel calendario della materia (0 = primo giorno, 1 = ultimo).
Impegno = namedtuple("Impegno", "giorno posizione")

# Pesi delle regole: più alto = regola più importante.
PESO_STESSO_GIORNO = 1000   # due interrogazioni lo stesso giorno
PESO_PRIMO_GIORNO = 50      # di nuovo il primo giorno
PESO_ANTICIPO = 10          # già interrogato presto nelle altre materie → ora più tardi
PESO_GIORNO_CONSECUTIVO = 3  # interrogazioni in giorni consecutivi

TENTATIVI = 4


def costo(impegni, giorno, posizione):
    """Quanto è sconveniente interrogare in `giorno` uno studente con questi impegni."""
    if not impegni:
        return 0
    c = 0
    for imp in impegni:
        distanza = abs((giorno - imp.giorno).days)
        if distanza == 0:
            c += PESO_STESSO_GIORNO
        elif distanza == 1:
            c += PESO_GIORNO_CONSECUTIVO
    if posizione == 0 and any(imp.posizione == 0 for imp in impegni):
        c += PESO_PRIMO_GIORNO
    anticipo_medio = sum(1 - imp.posizione for imp in impegni) / len(impegni)
    c += PESO_ANTICIPO * anticipo_medio * (1 - posizione)
    return c


def posizioni_relative(n_date):
    """Posizione di ogni data nel calendario: 0 = prima, 1 = ultima."""
    if n_date == 1:
        return [0.0]
    return [i / (n_date - 1) for i in range(n_date)]


def distribuisci(studenti, date_disponibili, rng=None, impegni=None):
    """Distribuisce casualmente gli studenti sulle date in modo equilibrato.

    Ogni data riceve n // d oppure n // d + 1 studenti. Se `impegni` è dato
    ({studente: [Impegno, ...]} con le interrogazioni nelle altre materie),
    tra tutte le distribuzioni equilibrate si cerca quella che rispetta meglio
    le regole pesate qui sopra, partendo da estrazioni casuali.

    Restituisce un dict {data: [studenti nell'ordine di interrogazione]}
    con le date in ordine cronologico.
    """
    if not date_disponibili:
        raise ValueError("Serve almeno una data")

    rng = rng or random.Random()
    impegni = impegni or {}
    giorni = sorted(date_disponibili)
    posizioni = posizioni_relative(len(giorni))
    studenti = list(studenti)
    costi = {s: [costo(impegni.get(s), g, p) for g, p in zip(giorni, posizioni)]
             for s in studenti}

    migliore, costo_migliore = None, None
    for _ in range(TENTATIVI if impegni else 1):
        gruppi = _estrazione_casuale(studenti, len(giorni), rng)
        _migliora(gruppi, costi, rng)
        totale = sum(costi[s][i] for i, gruppo in enumerate(gruppi) for s in gruppo)
        if costo_migliore is None or totale < costo_migliore:
            migliore, costo_migliore = gruppi, totale

    for gruppo in migliore:
        rng.shuffle(gruppo)  # ordine casuale all'interno della giornata
    return dict(zip(giorni, migliore))


def _estrazione_casuale(studenti, n_date, rng):
    mescolati = list(studenti)
    rng.shuffle(mescolati)
    base, extra = divmod(len(mescolati), n_date)
    con_extra = set(rng.sample(range(n_date), extra))
    gruppi, pos = [], 0
    for i in range(n_date):
        quanti = base + (1 if i in con_extra else 0)
        gruppi.append(mescolati[pos:pos + quanti])
        pos += quanti
    return gruppi


def _migliora(gruppi, costi, rng, max_passate=50):
    """Ricerca locale: scambia studenti tra date (o sposta verso una data con
    un posto in meno) finché il costo totale diminuisce. L'equilibrio tra le
    date è sempre mantenuto."""
    coppie = [(x, y) for x in range(len(gruppi)) for y in range(len(gruppi)) if x != y]
    for _ in range(max_passate):
        migliorato = False
        rng.shuffle(coppie)
        for x, y in coppie:
            gx, gy = gruppi[x], gruppi[y]
            # spostamento: possibile solo dalla data con un posto in più
            if len(gx) > len(gy):
                for i, a in enumerate(gx):
                    if costi[a][y] < costi[a][x]:
                        gy.append(gx.pop(i))
                        migliorato = True
                        break
            for i in range(len(gx)):
                for j in range(len(gy)):
                    a, b = gx[i], gy[j]
                    if costi[a][y] + costi[b][x] < costi[a][x] + costi[b][y]:
                        gx[i], gy[j] = b, a
                        migliorato = True
        if not migliorato:
            return


def parse_date(valori):
    """Converte stringhe ISO (YYYY-MM-DD) in date, ignorando vuoti e duplicati."""
    giorni = set()
    for v in valori:
        v = (v or "").strip()
        if v:
            giorni.add(date.fromisoformat(v))
    return sorted(giorni)
