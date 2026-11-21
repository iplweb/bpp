import json

from fixtures import xdist_bench


def _zapisz(tmp_path, **nadpisz):
    data = {
        "version": xdist_bench.VERSION,
        "fingerprint": xdist_bench.fingerprint(),
        "suites": {
            "not playwright": {"best": 16, "measured_at": "2026-11-12 22:00:00"}
        },
    }
    data.update(nadpisz)
    (tmp_path / xdist_bench.BENCH_FILENAME).write_text(json.dumps(data))


def test_xdist_bench_brak_pliku(tmp_path):
    assert xdist_bench.best_workers(tmp_path, "not playwright") == (None, "")


def test_xdist_bench_zwraca_najlepsze_dla_markera(tmp_path):
    _zapisz(tmp_path)
    best, note = xdist_bench.best_workers(tmp_path, " not playwright ")
    assert best == 16
    assert "2026-11-12" in note


def test_xdist_bench_inny_marker_bez_limitu(tmp_path):
    _zapisz(tmp_path)
    assert xdist_bench.best_workers(tmp_path, "playwright") == (None, "")


def test_xdist_bench_plik_z_innej_maszyny_ignorowany(tmp_path):
    fp = xdist_bench.fingerprint() | {"hostname": "inna-maszyna"}
    _zapisz(tmp_path, fingerprint=fp)
    best, note = xdist_bench.best_workers(tmp_path, "not playwright")
    assert best is None
    assert "innej maszyny" in note


def test_xdist_bench_uszkodzony_plik(tmp_path):
    (tmp_path / xdist_bench.BENCH_FILENAME).write_text("{nie json")
    best, note = xdist_bench.best_workers(tmp_path, "not playwright")
    assert best is None
    assert "nieczytelny" in note


def test_dopasuj_pamiec_liniowo():
    # 4 GB stałe + 1 GB na workera
    punkty = [(n, 4096 + 1024 * n) for n in (4, 8, 16)]
    stala, na_workera = xdist_bench.dopasuj_pamiec(punkty)
    assert round(stala) == 4096
    assert round(na_workera) == 1024


def test_dopasuj_pamiec_jeden_punkt_i_brak():
    assert xdist_bench.dopasuj_pamiec([(8, 8192)]) == (0.0, 1024.0)
    assert xdist_bench.dopasuj_pamiec([]) is None


def test_max_workers_dla_ram():
    model = (4096.0, 1024.0)
    # 16 GB - 2 GB zapasu - 4 GB stałe = 10 GB → 10 workerów
    assert xdist_bench.max_workers_dla_ram(16 * 1024, model) == 10
    assert xdist_bench.max_workers_dla_ram(4 * 1024, model) == 0


def test_rekomendacje_z_pomiaru():
    suite = {
        "best": 16,
        "table": [
            {"n": n, "ok": True, "median_wall_s": t, "peak_ram_mb": 4096 + 1024 * n}
            for n, t in ((8, 80.0), (16, 45.0), (24, 44.0))
        ],
    }
    fp = {"physical_cpus": 16, "logical_cpus": 32}
    tekst = "\n".join(xdist_bench.rekomendacje(suite, fp))
    assert "-n 16" in tekst
    assert "więcej workerów już nie przyspiesza" in tekst
    assert "wymaga ~22 GB RAM" in tekst  # 4 + 16 GB szczyt + 2 GB zapasu
    assert "16 GB RAM: -n 10, ~80 s lub dłużej" in tekst
    assert "32 GB RAM: -n 16, ~45 s" in tekst  # limit = najszybsze -n
    assert "8 GB RAM: -n 2" in tekst


def test_rekomendacje_stary_plik_bez_pamieci():
    suite = {"best": 8, "table": [{"n": 8, "ok": True, "median_wall_s": 50.0}]}
    tekst = xdist_bench.rekomendacje(suite, {"physical_cpus": 8, "logical_cpus": 16})
    assert "brak pomiaru pamięci" in tekst[0]


def test_rekomendacje_best_to_najwieksze_zmierzone():
    suite = {
        "best": 8,
        "table": [
            {"n": n, "ok": True, "median_wall_s": t, "peak_ram_mb": 1024 * n}
            for n, t in ((4, 80.0), (8, 45.0))
        ],
    }
    tekst = "\n".join(
        xdist_bench.rekomendacje(suite, {"physical_cpus": 16, "logical_cpus": 32})
    )
    assert "zmierz większe" in tekst
