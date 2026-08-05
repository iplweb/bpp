"""Strażnik commitowanego pliku `.test_durations`.

CI dzieli suite na 8 grup po ~rownym CZASIE przez pytest-split, czytajac
ten plik (`--splitting-algorithm least_duration`, mount read-only w
docker-compose.test.ci.yml). Gdy plik znika / jest uciety / uszkodzony,
pytest-split degraduje sie cicho do podzialu po liczbie testow — czyli
wracamy do starego problemu (jeden shard ~2x wolniejszy). „Cicho" jest tu
slowem kluczem: nic nie pada, gate dalej zielony, tylko wolniejszy. Ten
test zamienia te cicha degradacje w glosny FAIL.

Plik regenerujesz lokalnie: `make tests` albo `make test-durations`
(oba dopisuja czasy obu przebiegow — not-playwright + playwright — i
pytest-split je merge'uje). Potem `git commit .test_durations`. CI nigdy
go nie liczy ani nie nadpisuje.
"""

import json
from pathlib import Path

import pytest

# repo-root/.test_durations: __file__ = src/django_bpp/tests/<plik>
# parents[3] == repo root (lokalnie i w obrazie test-runner, gdzie WORKDIR
# = /src i plik jest montowany jako /src/.test_durations).
DURATIONS_PATH = Path(__file__).resolve().parents[3] / ".test_durations"

# Suite ma ~4100 testow (3960 non-playwright + ~140 playwright). Podloga
# wykrywa katastrofalne uciecie/nadpisanie podzbiorem, tolerujac normalny
# churn. Jesli suite kiedys realnie skurczy sie ponizej — obniz swiadomie.
MIN_DURATIONS_ENTRIES = 2000


@pytest.fixture(scope="module")
def durations():
    assert DURATIONS_PATH.is_file(), (
        f"Brak {DURATIONS_PATH.name} w korzeniu repo. CI nie zbalansuje "
        f"shardow po czasie. Wygeneruj: `make test-durations`, potem commit."
    )
    with DURATIONS_PATH.open() as f:
        return json.load(f)


def test_durations_is_a_nonempty_mapping(durations):
    assert isinstance(durations, dict)
    assert durations, ".test_durations jest puste"


def test_durations_has_enough_entries(durations):
    assert len(durations) >= MIN_DURATIONS_ENTRIES, (
        f".test_durations ma tylko {len(durations)} wpisow "
        f"(<{MIN_DURATIONS_ENTRIES}). Plik prawdopodobnie zapisany z "
        f"podzbioru testow (np. tylko `not playwright`) i nadpisal komplet. "
        f"Zregeneruj `make test-durations` (pelny przebieg, oba markery)."
    )


def test_durations_entries_are_well_formed(durations):
    # Klucze to pytest node-id (zawieraja `::`), wartosci to dodatnie czasy.
    bad_keys = [k for k in durations if "::" not in k][:5]
    assert not bad_keys, f"Klucze nie wygladaja na node-id pytest: {bad_keys}"

    bad_values = [
        (k, v)
        for k, v in durations.items()
        if not isinstance(v, (int, float)) or v < 0
    ][:5]
    assert not bad_values, f"Czasy musza byc nieujemnymi liczbami: {bad_values}"
