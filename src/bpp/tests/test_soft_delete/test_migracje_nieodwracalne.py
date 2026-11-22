"""Migracje soft-delete są NIEODWRACALNE (decyzja właściciela).

Cofnięcie łańcucha kosza rozjechałoby dane (rekordy w koszu, wycofania
z PBN, sprzątnięte ``_mat``) z kodem, więc ``migrate`` w tył ma rzucić
``IrreversibleError`` ZANIM cokolwiek zmieni. Powrót — tylko z kopii bazy.

Test jest statyczny (graf z dysku): Django sprawdza ``reversible`` każdej
operacji w ``Migration.unapply`` przed pierwszym DDL-em, więc obecność
nieodwracalnej operacji jest dokładnie tym, co blokuje rollback.
"""

import pytest
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.loader import MigrationLoader

NIEODWRACALNE = [
    ("bpp", "0511_publikacje_soft_delete_fields"),
    ("bpp", "0512_soft_delete_rekord_views"),
    ("bpp", "0513_soft_delete_autorzy_przez_publikacje"),
    ("bpp", "0514_nowe_sumy_bez_skasowanych_publikacji"),
    ("bpp", "0515_drop_kronika_views"),
    ("bpp", "0516_praca_habilitacyjna_warunkowy_unique_autora"),
    ("bpp", "0517_soft_delete_protect_fk"),
    ("bpp", "0518_autor_soft_delete"),
    ("bpp", "0519_softdeletelog"),
    ("bpp", "0520_soft_delete_struktura_i_slowniki"),
    ("bpp", "0521_slug_unikalny_razem_z_koszem"),
    ("bpp", "0522_kasowanie_prac_dyplomowych_z_autorzy_mat"),
    ("bpp", "0523_kosz_zamrozony_trigger"),
    ("cerif_export", "0001_odpieta_przynaleznosc"),
    ("pbn_api", "0080_sentdata_withdrawn_at"),
    ("pbn_export_queue", "0011_pbn_export_queue_operacja"),
    ("pbn_export_queue", "0012_zamowil_protect"),
    ("pbn_import", "0013_alter_importinconsistency_inconsistency_type"),
    ("pbn_integrator", "0001_initial"),
    ("rozbieznosci_dyscyplin", "0022_rozbieznosci_zrodel_bez_skasowanych_publikacji"),
    ("zglos_publikacje", "0030_zgloszenie_autor_protect"),
    ("zglos_publikacje", "0031_zgloszenie_kosz_zamrozony_trigger"),
]


@pytest.fixture(scope="module")
def graf():
    return MigrationLoader(None, ignore_no_migrations=True).graph


@pytest.mark.parametrize("klucz", NIEODWRACALNE, ids="/".join)
def test_migracja_soft_delete_jest_nieodwracalna(graf, klucz):
    migracja = graf.nodes[klucz]
    assert any(not op.reversible for op in migracja.operations), (
        f"{klucz} da się cofnąć — łańcuch soft-delete ma być nieodwracalny"
    )


def test_cofniecie_ponizej_0510_blokuje_juz_najwyzsza_migracja(graf):
    """Każda droga w tył przez ``bpp/0511``–``0523`` zaczyna się od
    ``0523`` (najwyższej w łańcuchu) — i tam od razu staje."""
    migracja = graf.nodes[("bpp", "0523_kosz_zamrozony_trigger")]
    with pytest.raises(IrreversibleError):
        migracja.unapply(project_state=None, schema_editor=None)
