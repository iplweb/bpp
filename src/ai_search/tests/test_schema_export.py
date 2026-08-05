import pytest
from django.core.cache import cache

from ai_search import schema_export


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    # W ustawieniach testowych domyślny backend cache to DummyCache (nic nie
    # przechowuje) — podmieniamy na LocMemCache, żeby móc zweryfikować
    # rzeczywiste ponowne użycie z cache. Ten sam wzorzec co w test_fx.py.
    caches = dict(settings.CACHES)
    caches["default"] = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    settings.CACHES = caches
    from django.core.cache import cache as cache_module

    cache_module.clear()
    yield cache_module
    cache_module.clear()


@pytest.fixture(autouse=True)
def _clear():
    for k in ("rekord", "autor"):
        cache.delete(f"ai_search:schema:{k}")
    yield


@pytest.mark.django_db
def test_schema_shape_rekord():
    data = schema_export.schema_for_llm("rekord")
    assert isinstance(data, str)
    assert "# DjangoQL schema" in data
    assert "start model: bpp.rekord" in data


@pytest.mark.django_db
def test_schema_shape_autor():
    data = schema_export.schema_for_llm("autor")
    assert isinstance(data, str)
    assert data.strip()  # niepusty string
    assert "bpp.autor" in data


@pytest.mark.django_db
def test_schema_does_not_leak_password_field():
    data = schema_export.schema_for_llm("rekord")
    assert "password" not in data.lower()


@pytest.mark.django_db
def test_cache_reused(monkeypatch):
    calls = {"n": 0}
    real = schema_export._build

    def counting(model_key):
        calls["n"] += 1
        return real(model_key)

    monkeypatch.setattr(schema_export, "_build", counting)
    schema_export.schema_for_llm("rekord")
    schema_export.schema_for_llm("rekord")
    assert calls["n"] == 1


@pytest.mark.django_db
def test_unknown_model_key_raises():
    with pytest.raises(KeyError):
        schema_export.schema_for_llm("nieistnieje")
