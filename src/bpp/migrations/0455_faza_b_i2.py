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


def rerun_konwersja_wydzialy(apps, schema_editor):
    """Idempotentna reimplementacja ``konwertuj_wydzialy_na_jednostki``
    (komenda Fazy A) na modelach historycznych.

    Dla każdego ``Wydzial`` bez odpowiadającego węzła (po ``legacy_wydzial_id``)
    tworzy ukrytą, nieaktualną ``Jednostka`` — ROOT drzewa MPTT
    (parent=None → pola drzewa trywialne: lft=1, rght=2, level=0,
    tree_id = kolejny wolny). Na świeżej bazie zwykle nic nie tworzy
    (Faza A skonwertowała już wszystko), ale MUSI być poprawne i idempotentne.
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
        Jednostka.objects.create(
            nazwa=w.nazwa,
            skrot=w.skrot,
            skrot_nazwy=w.skrot_nazwy,
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
