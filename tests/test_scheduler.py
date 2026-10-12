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
