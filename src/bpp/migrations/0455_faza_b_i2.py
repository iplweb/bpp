"""Faza B / issue #438 — I-2.

Zdejmuje 3 triggery bazodanowe pilnujące struktury Jednostka/Wydzial
i zastępuje je sygnałami Pythona (patrz ``bpp.models.jednostka``):

* ``bpp_jednostka_ustaw_wydzial_aktualna_trigger`` — zastąpiony sygnałem
  post_save/post_delute na ``Jednostka_Wydzial``,
* ``bpp_jednostka_wydzial_sprawdz_uczelnia_id_trigger`` — walidacja uczelni,
  zdjęty BEZ zamiennika (Zasada #4 federacji),
* ``bpp_jednostka_sprawdz_uczelnia_id_trigger`` — j.w.

Następnie idempotentnie ponawia konwersję ``Wydzial`` → ukryty węzeł
``Jednostka`` (Faza A). DROP wykonujemy PRZED konwersją, bo trigger
walidacyjny na ``bpp_jednostka`` odpaliłby się przy INSERT-cie węzłów.
"""

from django.db import migrations, models

DROP_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS bpp_jednostka_ustaw_wydzial_aktualna_trigger
    ON bpp_jednostka_wydzial;
DROP TRIGGER IF EXISTS bpp_jednostka_wydzial_sprawdz_uczelnia_id_trigger
    ON bpp_jednostka_wydzial;
DROP TRIGGER IF EXISTS bpp_jednostka_sprawdz_uczelnia_id_trigger
    ON bpp_jednostka;
DROP FUNCTION IF EXISTS bpp_jednostka_ustaw_wydzial_aktualna();
DROP FUNCTION IF EXISTS bpp_jednostka_wydzial_sprawdz_uczelnia_id();
DROP FUNCTION IF EXISTS bpp_jednostka_sprawdz_uczelnia_id();
"""


def _bez_kolizji(Jednostka, field, value, w_id, max_length, suffix):
    """Zwraca ``value`` jeśli nie koliduje z istniejącą ``Jednostka`` na
    ``field``; w przeciwnym razie dokleja deterministyczny ``suffix``
    wyprowadzony ze stabilnego ``Wydzial.id`` (tego samego, który ląduje
    w ``legacy_wydzial_id``), tak by wynik zmieścił się w ``max_length``.

    ``Jednostka.nazwa`` i ``Jednostka.skrot`` są ``unique=True`` — stara
    Faza A (okno A→B) mogła utworzyć ``Wydzial`` o nazwie/skrócie kolidującym
    z istniejącą ``Jednostka``. Bez tego przy INSERT-cie węzła leciałby
    ``IntegrityError`` w trakcie nienadzorowanego auto-deployu (brak operatora,
    by rozwiązać kolizję w locie — spec A2/A3 wymaga deterministycznego
    auto-suffiksu). Puste/None zostawiamy bez zmian (nie ma po czym kolidować,
    a ``skrot_nazwy`` bywa puste). Suffiksujemy TYLKO pole, które faktycznie
    koliduje — reszta pól kopiowana verbatim. Gdyby po suffiksie nadal był
    konflikt (skrajnie nieprawdopodobne: legacy id jest unikalne), świadomie
    pozwalamy paść — NIE pętlimy w nieskończoność.
    """
    if not value:
        return value
    if not Jednostka.objects.filter(**{field: value}).exists():
        return value
    base = value
    if len(base) + len(suffix) > max_length:
        base = base[: max_length - len(suffix)]
    return f"{base}{suffix}"


def rerun_konwersja_wydzialy(apps, schema_editor):
    """Idempotentna reimplementacja ``konwertuj_wydzialy_na_jednostki``
    (komenda Fazy A) na modelach historycznych.

    Dla każdego ``Wydzial`` bez odpowiadającego węzła (po ``legacy_wydzial_id``)
    tworzy ukrytą, nieaktualną ``Jednostka`` — ROOT drzewa MPTT
    (parent=None → pola drzewa trywialne: lft=1, rght=2, level=0,
    tree_id = kolejny wolny). Na świeżej bazie zwykle nic nie tworzy
    (Faza A skonwertowała już wszystko), ale MUSI być poprawne i idempotentne.

    Idempotencja: węzły już utworzone (dopasowane po ``legacy_wydzial_id``)
    są pomijane na wejściu pętli, więc ponowny przebieg nigdy nie suffiksuje
    powtórnie ani nie tworzy duplikatu.
    """
    Wydzial = apps.get_model("bpp", "Wydzial")
    Jednostka = apps.get_model("bpp", "Jednostka")
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")

    wydzialy = list(Wydzial.objects.all())
    if not wydzialy:
        return

    rodzaj_wydzial, _ = RodzajJednostki.objects.get_or_create(nazwa="Wydział")

    next_tree_id = (Jednostka.objects.aggregate(m=models.Max("tree_id"))["m"] or 0) + 1

    for w in wydzialy:
        if Jednostka.objects.filter(legacy_wydzial_id=w.id).exists():
            continue
        # Deterministyczny auto-suffiks per pole unikalne (spec A2/A3).
        nazwa = _bez_kolizji(Jednostka, "nazwa", w.nazwa, w.id, 512, f" [W{w.id}]")
        skrot = _bez_kolizji(Jednostka, "skrot", w.skrot, w.id, 128, f"-W{w.id}")
        skrot_nazwy = _bez_kolizji(
            Jednostka, "skrot_nazwy", w.skrot_nazwy, w.id, 250, f"-W{w.id}"
        )
        Jednostka.objects.create(
            nazwa=nazwa,
            skrot=skrot,
            skrot_nazwy=skrot_nazwy,
            opis=w.opis,
            adnotacje=w.adnotacje,
            poprzednie_nazwy=w.poprzednie_nazwy,
            pbn_id=w.pbn_id,
            uczelnia=w.uczelnia,
            rodzaj=rodzaj_wydzial,
            rodzaj_jednostki="normalna",
            legacy_wydzial_id=w.id,
            parent=None,
            widoczna=False,
            aktualna=False,
            zezwalaj_na_ranking_autorow=w.zezwalaj_na_ranking_autorow,
            pokazuj_opis=w.pokazuj_opis,
            zarzadzaj_automatycznie=w.zarzadzaj_automatycznie,
            kolejnosc=max(0, w.kolejnosc),
            tree_id=next_tree_id,
            lft=1,
            rght=2,
            level=0,
        )
        next_tree_id += 1


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0454_faza_b_i1"),
    ]

    operations = [
        migrations.RunSQL(DROP_TRIGGERS_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunPython(
            rerun_konwersja_wydzialy, reverse_code=migrations.RunPython.noop
        ),
    ]
