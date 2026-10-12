import random
from datetime import date

import pytest

from scheduler import distribuisci, parse_date


def test_tutti_assegnati_una_volta():
    studenti = list(range(25))
    giorni = [date(2026, 11, d) for d in (3, 5, 10, 12)]
    piano = distribuisci(studenti, giorni, random.Random(1))
    assegnati = [s for gruppo in piano.values() for s in gruppo]
    assert sorted(assegnati) == studenti


def test_distribuzione_equilibrata():
    giorni = [date(2026, 11, d) for d in range(1, 8)]
    for seed in range(50):
        piano = distribuisci(range(23), giorni, random.Random(seed))
        dimensioni = [len(g) for g in piano.values()]
        assert max(dimensioni) - min(dimensioni) <= 1


def test_date_in_ordine_cronologico():
    giorni = [date(2026, 12, 1), date(2026, 11, 1), date(2026, 11, 15)]
    piano = distribuisci(range(5), giorni)
    assert list(piano) == sorted(giorni)


def test_piu_date_che_studenti():
    piano = distribuisci(["a", "b"], [date(2026, 11, d) for d in range(1, 6)])
    assert sum(len(g) for g in piano.values()) == 2


def test_senza_date():
    with pytest.raises(ValueError):
        distribuisci(["a"], [])


def test_parse_date_ignora_vuoti_e_duplicati():
    assert parse_date(["2026-11-05", "", "2026-11-03", "2026-11-05"]) == [
        date(2026, 11, 3), date(2026, 11, 5)]


# --- Regole tra materie diverse -------------------------------------------------

from scheduler import Impegno, posizioni_relative  # noqa: E402


def impegni_da(piano):
    """Converte un calendario già estratto negli impegni per la materia successiva."""
    giorni = sorted(piano)
    pos = posizioni_relative(len(giorni))
    return {s: [Impegno(g, pos[i])] for i, g in enumerate(giorni) for s in piano[g]}


def test_mai_due_interrogazioni_lo_stesso_giorno():
    giorni = [date(2026, 11, d) for d in (3, 5, 10, 12)]
    for seed in range(30):
        rng = random.Random(seed)
        storia = distribuisci(range(22), giorni, rng)
        matematica = distribuisci(range(22), giorni, rng, impegni=impegni_da(storia))
        for g in giorni:
            assert not set(storia[g]) & set(matematica[g])
        dimensioni = [len(v) for v in matematica.values()]
        assert max(dimensioni) - min(dimensioni) <= 1


def test_chi_era_primo_non_e_di_nuovo_primo():
    storia_giorni = [date(2026, 10, d) for d in (20, 22, 27, 29)]
    mate_giorni = [date(2026, 11, d) for d in (3, 10, 17, 24)]
    for seed in range(30):
        rng = random.Random(seed)
        storia = distribuisci(range(20), storia_giorni, rng)
        mate = distribuisci(range(20), mate_giorni, rng, impegni=impegni_da(storia))
        assert not set(storia[storia_giorni[0]]) & set(mate[mate_giorni[0]])


def test_chi_era_presto_va_piu_tardi():
    storia_giorni = [date(2026, 10, d) for d in (20, 22, 27, 29)]
    mate_giorni = [date(2026, 11, d) for d in (3, 10, 17, 24)]
    rng = random.Random(7)
    storia = distribuisci(range(20), storia_giorni, rng)
    mate = distribuisci(range(20), mate_giorni, rng, impegni=impegni_da(storia))
    # chi era nelle prime due date di storia ora è nelle ultime due di matematica
    primi_storia = set(storia[storia_giorni[0]]) | set(storia[storia_giorni[1]])
    ultimi_mate = set(mate[mate_giorni[2]]) | set(mate[mate_giorni[3]])
    assert primi_storia == ultimi_mate


def test_tre_materie_stesse_date_senza_doppioni():
    giorni = [date(2026, 11, d) for d in (2, 4, 6, 9, 11, 13)]
    rng = random.Random(3)
    impegni = {}
    for _ in range(3):
        piano = distribuisci(range(24), giorni, rng, impegni=impegni)
        for s, imp in impegni_da(piano).items():
            impegni.setdefault(s, []).extend(imp)
    for s, imp in impegni.items():
        assert len({i.giorno for i in imp}) == 3


def test_sovrapposizione_inevitabile_assegna_comunque():
    giorno = [date(2026, 11, 3)]
    storia = distribuisci(range(5), giorno)
    mate = distribuisci(range(5), giorno, impegni=impegni_da(storia))
    assert sorted(mate[giorno[0]]) == list(range(5))
