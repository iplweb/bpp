import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from djangoql.exceptions import DjangoQLParserError
from djangoql.parser import DjangoQLParser
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.views.zapytanie import EXAMPLES, user_can_use_query_editor

URL = "bpp:zapytanie"


def _all_examples():
    """Splaszcza EXAMPLES do listy (level, model, desc, query)."""
    for level in EXAMPLES:
        for group in level["groups"]:
            for desc, query in group["items"]:
                yield (level["level"], group["model"], desc, query)


@pytest.fixture
def wprowadzanie_user(test_user):
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    test_user.groups.add(group)
    test_user.is_staff = True
    test_user.save()
    return test_user


@pytest.fixture
def wprowadzanie_client(client, wprowadzanie_user):
    client.force_login(wprowadzanie_user)
    return client


@pytest.mark.django_db
def test_zapytanie_view_anonymous_redirected(client):
    response = client.get(reverse(URL))
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_zapytanie_view_logged_in_non_staff_forbidden(client, test_user):
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_staff_without_group_forbidden(client, test_user):
    test_user.is_staff = True
    test_user.save()
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_group_without_staff_forbidden(client, test_user):
    """Staff jest wymagany oprocz przynaleznosci do grupy."""
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    test_user.groups.add(group)
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_wprowadzanie_user_allowed(wprowadzanie_client):
    response = wprowadzanie_client.get(reverse(URL))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_zapytanie_view_superuser_allowed(superuser_client):
    response = superuser_client.get(reverse(URL))
    assert response.status_code == 200


@pytest.mark.django_db
def test_zapytanie_view_renders_radio_buttons(superuser_client):
    response = superuser_client.get(reverse(URL))
    html = response.content.decode("utf-8")
    assert 'type="radio"' in html
    assert 'value="rekord"' in html
    assert 'value="autor"' in html


@pytest.mark.django_db
def test_zapytanie_query_autor_matches(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski"'},
    )
    assert response.status_code == 200
    assert response.context["count"] == 1
    assert response.context["error"] is None
    results = list(response.context["results"])
    assert len(results) == 1
    assert results[0].nazwisko == "Kowalski"


@pytest.mark.django_db
def test_zapytanie_query_autor_no_matches(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski")

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Nieistnieje"'},
    )
    assert response.status_code == 200
    assert response.context["count"] == 0
    assert response.context["error"] is None


@pytest.mark.django_db
def test_zapytanie_query_invalid_syntax_shows_error(superuser_client):
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": "this is not valid djangoql !!!"},
    )
    assert response.status_code == 200
    assert response.context["error"]
    assert response.context["count"] is None


@pytest.mark.django_db
def test_zapytanie_query_unknown_field_shows_error(superuser_client):
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nieistniejace_pole = "x"'},
    )
    assert response.status_code == 200
    assert response.context["error"]


@pytest.mark.django_db
def test_zapytanie_empty_query_renders_form_without_results(superuser_client):
    response = superuser_client.get(reverse(URL), {"model": "autor", "query": ""})
    assert response.status_code == 200
    assert response.context.get("results") is None


@pytest.mark.django_db
def test_zapytanie_query_rekord_uses_correct_model(superuser_client):
    """Radio 'rekord' przelacza queryset na model Rekord, nie Autor."""
    response = superuser_client.get(
        reverse(URL),
        {"model": "rekord", "query": "rok = 1900"},
    )
    assert response.status_code == 200
    assert response.context["error"] is None
    assert response.context["model_key"] == "rekord"
    assert response.context["count"] == 0


@pytest.mark.django_db
def test_zapytanie_default_model_is_rekord(superuser_client):
    response = superuser_client.get(reverse(URL))
    assert response.status_code == 200
    form = response.context["form"]
    assert form.fields["model"].initial == "rekord"


@pytest.mark.parametrize(
    "level,model,desc,query",
    list(_all_examples()),
    ids=lambda v: str(v)[:50] if isinstance(v, str) else str(v),
)
def test_zapytanie_examples_are_valid_djangoql(level, model, desc, query):
    """Kazdy przyklad w EXAMPLES MUSI byc poprawnym DjangoQL.

    DjangoQL grammar (parser.py) nie wspiera unary `not (expr)`; do negacji
    uzywaj `!=`, `!~`, `not in`, `not startswith`, `not endswith`.
    Ten test parsuje skladniowo (bez resolvowania pol — to dziedzina schemy).
    """
    parser = DjangoQLParser()
    try:
        parser.parse(query)
    except DjangoQLParserError as exc:
        pytest.fail(
            f"Bledna skladnia DjangoQL w przykladzie "
            f"(level={level}, model={model}, desc={desc!r}): "
            f"{query!r}\n -> {exc}"
        )


def test_zapytanie_examples_cover_both_models():
    """Sanity check: kazdy poziom ma przyklady dla obu modeli."""
    for level in EXAMPLES:
        models = {g["model"] for g in level["groups"]}
        assert models == {"rekord", "autor"}, (
            f"Level {level['level']} ma niekompletne pokrycie: {models}"
        )
        for group in level["groups"]:
            assert group["items"], (
                f"Level {level['level']} {group['model']}: brak przykladow"
            )


def test_zapytanie_examples_no_unary_not():
    """DjangoQL NIE WSPIERA unary `not (expr)` — wykryjmy regresje."""
    import re

    pattern = re.compile(r"\bnot\s*\(")
    for level, model, desc, query in _all_examples():
        assert not pattern.search(query), (
            f"Unary 'not (...)' znaleziono w przykladzie "
            f"(level={level}, model={model}, desc={desc!r}): {query!r}"
        )


@pytest.mark.django_db
def test_tytul_rel_picker_filters_by_pk():
    from djangoql.queryset import apply_search

    from bpp.models import Autor
    from bpp.models.autor import Tytul
    from bpp.views.zapytanie import BppZapytanieSchema

    # Baseline DB may already contain these titles (tytul.json fixture).
    prof, _ = Tytul.objects.get_or_create(nazwa="profesor", defaults={"skrot": "prof."})
    dr, _ = Tytul.objects.get_or_create(nazwa="doktor", defaults={"skrot": "dr"})
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)
    baker.make("bpp.Autor", nazwisko="Nowak", tytul=dr)

    qs = apply_search(
        Autor.objects.all(),
        f'tytul__rel = "profesor [{prof.pk}]"',
        schema=BppZapytanieSchema,
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_tytul_dot_traversal_still_works():
    from djangoql.queryset import apply_search

    from bpp.models import Autor
    from bpp.models.autor import Tytul
    from bpp.views.zapytanie import BppZapytanieSchema

    # Baseline DB may already contain this title (tytul.json fixture).
    prof, _ = Tytul.objects.get_or_create(nazwa="profesor", defaults={"skrot": "prof."})
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)

    qs = apply_search(
        Autor.objects.all(), 'tytul.skrot = "prof."', schema=BppZapytanieSchema
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_aktualna_jednostka_rel_picker_filters_by_pk():
    from djangoql.queryset import apply_search

    from bpp.models import Autor, Jednostka
    from bpp.views.zapytanie import BppZapytanieSchema

    j = baker.make(Jednostka, nazwa="Katedra X")
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", aktualna_jednostka=j)
    baker.make("bpp.Autor", nazwisko="Nowak")

    qs = apply_search(
        Autor.objects.all(),
        f'aktualna_jednostka__rel = "Katedra X [{j.pk}]"',
        schema=BppZapytanieSchema,
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_autor_schema_has_rel_fields_and_keeps_relations():
    from bpp.models import Autor
    from bpp.views.zapytanie import BppZapytanieSchema

    schema = BppZapytanieSchema(Autor)
    fields = schema.models["bpp.autor"]
    assert "tytul__rel" in fields
    assert "aktualna_jednostka__rel" in fields
    assert fields["tytul"].type == "relation"  # trawersacja zachowana


@pytest.mark.django_db
def test_rekord_schema_has_autorzy_rel_pickers():
    from bpp.models.cache import Autorzy, Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    schema = BppZapytanieSchema(Rekord)
    autorzy_fields = schema.models[schema.model_label(Autorzy)]
    assert "autor__rel" in autorzy_fields
    assert "jednostka__rel" in autorzy_fields
    assert autorzy_fields["autor"].type == "relation"


@pytest.mark.django_db
def test_user_can_use_query_editor_superuser():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=False)
    assert user_can_use_query_editor(u) is True


@pytest.mark.django_db
def test_user_can_use_query_editor_staff_in_group():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True)
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grp)
    assert user_can_use_query_editor(u) is True


@pytest.mark.django_db
def test_user_can_use_query_editor_plain_logged_in():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    assert user_can_use_query_editor(u) is False


def test_user_can_use_query_editor_anonymous():
    from django.contrib.auth.models import AnonymousUser

    assert user_can_use_query_editor(AnonymousUser()) is False


@pytest.mark.django_db
def test_rekord_autorzy_autor_rel_filters_real_fk():
    from djangoql.queryset import apply_search

    from bpp.models.cache import Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    qs = apply_search(
        Rekord.objects.all(),
        'autorzy.autor__rel = "X [1]"',
        schema=BppZapytanieSchema,
    )
    sql = str(qs.query).lower()
    assert "autor__rel" not in sql  # remap zadziałał (nie filtruje alt-nazwy)
    assert "autor_id" in sql


@pytest.mark.django_db
def test_zapytanie_view_tytul_rel_picker(superuser_client):
    from bpp.models.autor import Tytul

    prof, _ = Tytul.objects.get_or_create(nazwa="profesor", defaults={"skrot": "prof."})
    baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": f'tytul__rel = "profesor [{prof.pk}]"'},
    )
    assert response.status_code == 200
    assert response.context["error"] is None
    assert response.context["count"] == 1


@pytest.mark.django_db
def test_zapytanie_suggestions_tytul_rel_returns_options(superuser_client):
    from bpp.models.autor import Tytul

    prof, _ = Tytul.objects.get_or_create(nazwa="profesor", defaults={"skrot": "prof."})
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "autor"})
    response = superuser_client.get(url, {"field": "tytul__rel", "search": "profesor"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(f"#{prof.pk}" in item for item in items)


@pytest.mark.django_db
def test_zapytanie_suggestions_autor_rel_dal_smoke(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "rekord"})
    response = superuser_client.get(
        url, {"field": "autorzy.autor__rel", "search": "Kowal"}
    )
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)


def _breakdown_leaves(node):
    if not node["children"]:
        yield node
    for ch in node["children"]:
        yield from _breakdown_leaves(ch)


@pytest.mark.django_db
def test_zapytanie_breakdown_explains_zero(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski" and imiona = "asdfo"'},
    )
    assert response.status_code == 200
    assert response.context["count"] == 0
    breakdown = response.context["breakdown"]
    assert breakdown is not None
    assert breakdown["count"] == 0
    leaves = {leaf["text"]: leaf["count"] for leaf in _breakdown_leaves(breakdown)}
    assert any("asdfo" in t and c == 0 for t, c in leaves.items())


@pytest.mark.django_db
def test_zapytanie_no_breakdown_when_results(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski")
    response = superuser_client.get(
        reverse(URL), {"model": "autor", "query": 'nazwisko = "Kowalski"'}
    )
    assert response.context["count"] == 1
    assert response.context["breakdown"] is None


@pytest.mark.django_db
def test_zapytanie_breakdown_rendered_in_html(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski" and imiona = "asdfo"'},
    )
    html = response.content.decode("utf-8")
    assert "Dlaczego 0 wyników" in html
    assert "ten warunek nie pasuje do żadnego rekordu" in html
    assert "asdfo" in html
    # warunek z 0 trafień (poza korzeniem) ma czerwoną liczbę
    assert "zapytanie-breakdown-count--zero" in html


@pytest.mark.django_db
def test_zapytanie_breakdown_culprit_on_leaf_not_root(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski" and imiona = "asdfo"'},
    )
    breakdown = response.context["breakdown"]
    assert breakdown["label"] is None  # korzeń (główne zapytanie) bez etykiety
    leaves = list(_breakdown_leaves(breakdown))
    culprit = next(leaf for leaf in leaves if "asdfo" in leaf["text"])
    assert culprit["count"] == 0
    assert culprit["label"] == "ten warunek nie pasuje do żadnego rekordu"
    other = next(leaf for leaf in leaves if "Kowalski" in leaf["text"])
    assert other["label"] is None  # warunek z trafieniami nie jest winowajcą


@pytest.mark.django_db
def test_zapytanie_breakdown_root_intersection_not_labeled(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski" and imiona = "Anna"'},
    )
    breakdown = response.context["breakdown"]
    assert breakdown["count"] == 0
    assert breakdown["label"] is None  # głównego zapytania nie etykietujemy
    # każdy warunek z osobna coś zwraca (>=1), więc żaden liść nie jest winowajcą
    for leaf in _breakdown_leaves(breakdown):
        assert leaf["count"] >= 1
        assert leaf["label"] is None


@pytest.mark.django_db
def test_zapytanie_breakdown_no_label_on_dead_or_branch(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {
            "model": "autor",
            "query": (
                '(nazwisko = "Kowalski" or nazwisko = "Xyz") and imiona = "asdfo"'
            ),
        },
    )
    breakdown = response.context["breakdown"]
    assert breakdown["count"] == 0
    leaves = list(_breakdown_leaves(breakdown))
    # martwa gałąź w NIEPUSTYM OR — nie winowajca, bez etykiety (koniec z szumem)
    xyz = next(leaf for leaf in leaves if "Xyz" in leaf["text"])
    assert xyz["count"] == 0
    assert xyz["label"] is None
    # realny winowajca: warunek z 0 trafień połączony AND-em
    asdfo = next(leaf for leaf in leaves if "asdfo" in leaf["text"])
    assert asdfo["count"] == 0
    assert asdfo["label"] == "ten warunek nie pasuje do żadnego rekordu"


@pytest.mark.django_db
def test_rekord_zrodlo_rel_filters_real_fk():
    from djangoql.queryset import apply_search

    from bpp.models.cache import Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    qs = apply_search(
        Rekord.objects.all(), 'zrodlo__rel = "X [1]"', schema=BppZapytanieSchema
    )
    sql = str(qs.query).lower()
    assert "zrodlo__rel" not in sql  # remap na realny FK
    assert "zrodlo_id" in sql


@pytest.mark.django_db
def test_rekord_and_autorzy_have_extended_pickers():
    from bpp.models.cache import Autorzy, Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    schema = BppZapytanieSchema(Rekord)
    rekord_fields = schema.models[schema.model_label(Rekord)]
    for name in (
        "zrodlo__rel",
        "wydawca__rel",
        "konferencja__rel",
        "wydawnictwo_nadrzedne__rel",
        "charakter_formalny__rel",
        "jezyk__rel",
        "typ_kbn__rel",
        "status_korekty__rel",
        "openaccess_licencja__rel",
    ):
        assert name in rekord_fields, name
    assert rekord_fields["zrodlo"].type == "relation"  # trawersacja zachowana

    autorzy_fields = schema.models[schema.model_label(Autorzy)]
    for name in (
        "dyscyplina_naukowa__rel",
        "kierunek_studiow__rel",
        "typ_odpowiedzialnosci__rel",
    ):
        assert name in autorzy_fields, name


@pytest.mark.django_db
def test_zapytanie_suggestions_zrodlo_rel(superuser_client):
    from bpp.models import Zrodlo

    z = baker.make(Zrodlo, nazwa="Nature Reviews Cardiology")
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "rekord"})
    response = superuser_client.get(url, {"field": "zrodlo__rel", "search": "Nature"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(f"#{z.pk}" in item for item in items)


@pytest.mark.django_db
def test_picker_excludes_hidden_records(superuser_client):
    from bpp.models import Jezyk

    widoczny = baker.make(Jezyk, nazwa="ZZTESTwidoczny", widoczny=True)
    ukryty = baker.make(Jezyk, nazwa="ZZTESTukryty", widoczny=False)
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "rekord"})
    response = superuser_client.get(url, {"field": "jezyk__rel", "search": "ZZTEST"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(f"#{widoczny.pk}" in item for item in items)
    assert not any(f"#{ukryty.pk}" in item for item in items)


@pytest.mark.django_db
def test_schema_publication_models_have_pickers():
    """Wspólny BppQLSchema auto-generuje pickery dla modeli publikacji
    (admin Patent/doktorat/habilitacja korzysta z tego samego schematu)."""
    from bpp.djangoql_schema import BppQLSchema
    from bpp.models import Patent, Praca_Doktorska, Praca_Habilitacyjna

    cases = {
        Patent: ["status_korekty__rel", "wydzial__rel"],
        Praca_Doktorska: [
            "autor__rel",
            "promotor__rel",
            "wydawca__rel",
            "jednostka__rel",
        ],
        Praca_Habilitacyjna: ["jednostka__rel", "wydawca__rel", "typ_kbn__rel"],
    }
    for model, expected in cases.items():
        schema = BppQLSchema(model)
        fields = schema.models[schema.model_label(model)]
        for name in expected:
            assert name in fields, f"{model.__name__}: brak {name}"


def test_publication_admins_use_bpp_ql_schema():
    """Adminy publikacji (w tym nowo włączone) mają djangoql_schema = BppQLSchema."""
    from bpp.admin.patent import Patent_Admin
    from bpp.admin.praca_doktorska import Praca_DoktorskaAdmin
    from bpp.admin.praca_habilitacyjna import Praca_HabilitacyjnaAdmin
    from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
    from bpp.admin.wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin
    from bpp.djangoql_schema import BppQLSchema

    for admin_cls in (
        Patent_Admin,
        Praca_DoktorskaAdmin,
        Praca_HabilitacyjnaAdmin,
        Wydawnictwo_CiagleAdmin,
        Wydawnictwo_ZwarteAdmin,
    ):
        assert admin_cls.djangoql_schema is BppQLSchema, admin_cls.__name__
