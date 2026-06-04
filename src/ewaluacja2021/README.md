# ewaluacja2021 — apka wygaszana (husk, faza 1/2)

**Status: feature usunięty, kod usunięty. Pozostał minimalny szczątek
wymagany przez Django do zdjęcia tabel i do spójności grafu migracji.**

Apka obsługiwała raporty „ewaluacja 2021 → 3N" oraz import maksymalnych
slotów z XLSX. Cały feature był już wyłączony (URL-e i linki w UI
zakomentowane), a żywy kod systemu nie importował z niej niczego poza
zakresem lat `ROK_MIN`/`ROK_MAX` — te przeniesiono do
`ewaluacja_common/const.py`.

## Faza 1 (ten stan): tabele kasowane migracją 0020

- **Modele usunięte.** `migrations/0020_delete_ewaluacja2021_models.py`
  to „nagrobek" — `DeleteModel` na 5 tabel
  (`zamowienienaraport`, `liczbandlauczelni`, `iloscudzialowdlaautora`,
  `importmaksymalnychslotow`, `wierszimportumaksymalnychslotow`).
  Wykonuje się na `migrate` przy następnym deployu i fizycznie zdejmuje
  tabele z baz produkcyjnych.
- **Apka zostaje w `INSTALLED_APPS`** dopóki nagrobek nie zostanie
  wdrożony wszędzie — inaczej migracja 0020 nie miałaby jak się wykonać.

## Dlaczego te pliki nie zostały skasowane

Reguła projektu: **nigdy nie modyfikujemy istniejących migracji**.
Historyczne migracje (0001–0019) na sztywno importują poniższy kod, więc
musi on pozostać importowalny — inaczej *każde* `migrate` (także na
świeżej bazie, która odtwarza 0001→0020) wywali się `ImportError`:

| Plik | Trzymany bo… |
|---|---|
| `fields.py` (`LiczbaNField`) | używany w polach migracji 0001, 0002, 0003, 0012, 0013, 0014 |
| `validators.py` (`xlsx_header_validator`, `validate_xlsx`) | używany w 0003, 0005, 0018 |
| `util.py` (`find_header_row` i resztki) | importowany przez `validators.py` |
| `models.py` → tylko `dyscypliny_naukowe_w_bazie` | `limit_choices_to` w migracji 0007 |
| `apps.py`, `__init__.py`, `migrations/` | rejestracja apki + historia migracji |

To są **wyłącznie shimy migracyjne** — nie ma w nich już żadnej logiki
biznesowej i nikt spoza tej apki ich nie importuje.

## Faza 2 (osobny PR, PO wdrożeniu fazy 1)

Gdy migracja 0020 wykona się na wszystkich hostach (tabele zniknęły),
można usunąć apkę do końca:

1. `rm -rf src/ewaluacja2021/`
2. usunąć wpis `"ewaluacja2021"` z `INSTALLED_APPS`
   (`src/django_bpp/settings/base.py`),
3. usunąć wpis `"ewaluacja2021"` z `[tool.setuptools.packages.find]`
   w `pyproject.toml`.

Dopiero wtedy znikają też migracje i shimy. **Nie robić fazy 2 zanim
faza 1 nie jest wdrożona na produkcji** — usunięcie migracji 0020 przed
jej wykonaniem zostawiłoby osierocone tabele w bazach.
