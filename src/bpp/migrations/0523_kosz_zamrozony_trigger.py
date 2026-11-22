"""Zbiorcza blokada kosza w bazie: rekord w koszu jest ZAMROŻONY.

Jeden trigger ``BEFORE UPDATE OR DELETE`` (``bpp_kosz_straznik``) na każdej
tabeli modelu z koszem. Bez flagi transakcji ``bpp.kosz_operacja = 'on'``
(ustawia ją wyłącznie ``bpp.models.soft_delete.operacja_kosza()`` —
``delete()``/``restore()``/``hard_delete()``):

- zmiana ``deleted_at`` (w którąkolwiek stronę) jest odrzucana — kosz
  i przywrócenie idą wyłącznie przez ``delete()``/``restore()``;
- każdy ``UPDATE`` wiersza w koszu (``OLD.deleted_at IS NOT NULL``) jest
  odrzucany — m.in. pełny ``save()`` nieaktualnej instancji, która
  „wskrzesiłaby" rekord, ``deleted_objects.update()``, surowy SQL;
- fizyczny ``DELETE`` wiersza w koszu jest odrzucany.

Wyjątek: zmiany robione przez INNE triggery (``pg_trigger_depth() > 1``,
np. ``aktualna_jednostka`` autora liczona triggerem z ``bpp_autor_jednostka``)
— to dane wyliczane, nie edycja, i nie dotykają ``deleted_at``.

Błąd ma komunikat zaczynający się od ``BPP_KOSZ:`` — admin tłumaczy go na
czytelny komunikat. UWAGA dla przyszłych migracji danych: ``UPDATE`` na tych
tabelach, który ma objąć rekordy z kosza, musi ustawić flagę
(``SELECT set_config('bpp.kosz_operacja', 'on', true)``).

NIEODWRACALNA (brak ``reverse_sql``) — jak cały łańcuch soft-delete
``0511``–``0523``; powrót wyłącznie z kopii bazy.
"""

from django.db import migrations

TABELE = [
    "bpp_wydawnictwo_ciagle",
    "bpp_wydawnictwo_zwarte",
    "bpp_patent",
    "bpp_praca_doktorska",
    "bpp_praca_habilitacyjna",
    "bpp_autor",
    "bpp_uczelnia",
    "bpp_zrodlo",
    "bpp_wydawca",
    "bpp_konferencja",
    "bpp_seria_wydawnicza",
]

FUNKCJA = """
CREATE OR REPLACE FUNCTION bpp_kosz_straznik() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
BEGIN
    IF coalesce(current_setting('bpp.kosz_operacja', true), '') = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.deleted_at IS NOT NULL THEN
            RAISE EXCEPTION 'BPP_KOSZ: rekord %.% jest w koszu — nie można go '
                'usunąć fizycznie poza operacją kosza', TG_TABLE_NAME, OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.deleted_at IS DISTINCT FROM NEW.deleted_at THEN
        RAISE EXCEPTION 'BPP_KOSZ: zmiana deleted_at w %.% tylko przez '
            'delete()/restore()', TG_TABLE_NAME, OLD.id;
    END IF;
    IF OLD.deleted_at IS NOT NULL AND pg_trigger_depth() <= 1 THEN
        RAISE EXCEPTION 'BPP_KOSZ: rekord %.% jest w koszu — najpierw go '
            'przywróć', TG_TABLE_NAME, OLD.id;
    END IF;
    RETURN NEW;
END $bpp_body$;
"""


def _sql_forward():
    sql = [FUNKCJA]
    for t in TABELE:
        sql.append(
            f"DROP TRIGGER IF EXISTS {t}_kosz_straznik ON {t}; "
            f"CREATE TRIGGER {t}_kosz_straznik BEFORE UPDATE OR DELETE ON {t} "
            f"FOR EACH ROW EXECUTE FUNCTION bpp_kosz_straznik();"
        )
    return "\n".join(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0522_kasowanie_prac_dyplomowych_z_autorzy_mat"),
    ]

    operations = [
        migrations.RunSQL(_sql_forward()),
    ]
