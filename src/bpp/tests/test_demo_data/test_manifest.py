"""Testy dla Manifest z bpp.demo_data.manifest."""

import json

import pytest

from bpp.demo_data.manifest import Manifest


def test_empty_manifest_has_metadata(tmp_manifest_path):
    m = Manifest(
        path=tmp_manifest_path, database="testdb", command_args={"wydzialow": 3}
    )
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["database"] == "testdb"
    assert data["command_args"] == {"wydzialow": 3}
    assert data["objects"] == {}
    assert "created_at" in data


def test_append_pks(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1, 2, 3])
    m.append("bpp.Wydzial", [4, 5])
    m.append("bpp.Jednostka", [10, 11])
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["objects"]["bpp.Wydzial"]["pks"] == [1, 2, 3, 4, 5]
    assert data["objects"]["bpp.Jednostka"]["pks"] == [10, 11]


def test_append_with_extra(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Uczelnia", [1], extra={"created_by_demo": True})
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["objects"]["bpp.Uczelnia"]["pks"] == [1]
    assert data["objects"]["bpp.Uczelnia"]["created_by_demo"] is True


def test_atomic_write_no_tmp_left(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1])
    m.save()

    tmp = tmp_manifest_path.with_suffix(tmp_manifest_path.suffix + ".tmp")
    assert not tmp.exists()


def test_load_roundtrip(tmp_manifest_path):
    m1 = Manifest(path=tmp_manifest_path, database="db", command_args={"x": 1})
    m1.append("bpp.Wydzial", [1, 2])
    m1.append("bpp.Uczelnia", [9], extra={"created_by_demo": True})
    m1.save()

    m2 = Manifest.load(tmp_manifest_path)
    assert m2.database == "db"
    assert m2.command_args == {"x": 1}
    assert m2.objects_for("bpp.Wydzial") == [1, 2]
    assert m2.objects_for("bpp.Uczelnia") == [9]
    assert m2.extra_for("bpp.Uczelnia") == {"created_by_demo": True}


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Manifest.load(tmp_path / "nope.json")


def test_iter_phases_in_cleanup_order(tmp_manifest_path):
    """objects_in_cleanup_order zwraca pary (model_label, pks) w bezpiecznej
    kolejnosci usuwania."""
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1])
    m.append("bpp.Wydawnictwo_Ciagle_Autor", [2])
    m.append("bpp.Uczelnia", [3], extra={"created_by_demo": True})
    m.append("bpp.Wydawnictwo_Ciagle", [4])

    order = [label for label, _ in m.objects_in_cleanup_order()]
    # Wydawnictwo_Ciagle_Autor (M2M) przed Wydawnictwo_Ciagle (rekordem)
    # Wydzial przed Uczelnia
    assert order.index("bpp.Wydawnictwo_Ciagle_Autor") < order.index(
        "bpp.Wydawnictwo_Ciagle"
    )
    assert order.index("bpp.Wydzial") < order.index("bpp.Uczelnia")


def test_cleanup_order_skips_uczelnia_if_not_created_by_demo(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Uczelnia", [3])  # bez created_by_demo
    order = [label for label, _ in m.objects_in_cleanup_order()]
    assert "bpp.Uczelnia" not in order
