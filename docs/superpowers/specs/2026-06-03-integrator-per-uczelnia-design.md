# Design — Integrator PBN per-uczelnia (mały wątek D)

Data: 2026-06-03
Gałąź: `feature/multi-hosted-config`
Kontekst: wątek D z `HANDOFF-multi-hosted.md`. Po R1 (slot read-side) i R2 (liczba_n).

## Cel i zakres

Import publikacji z PBN (`pbn_integrator`) porównuje afiliacje autorów z „naszą"
uczelnią przez `Uczelnia.objects.default` — w multi-install „nasza" uczelnia jest
niejednoznaczna. Import biegnie per-uczelnia (każda uczelnia ma własny token PBN
i własnego `BppPBNClient`, który ZNA swoją `uczelnia` — Wątek 1). R-integrator
przepina te porównania na **uczelnię klienta** (`client.uczelnia`).

**W zakresie:** 5 użyć `Uczelnia.objects.default` w
`pbn_integrator/importer/authors.py` (funkcja `_przetworz_afiliacje`) → parametr
`uczelnia` przekazany z `utworz_autorow` (ma `client`). Aktualizacja guard-whitelisty.

**Poza zakresem:** reszta `pbn_integrator` nie używa `objects.default` (guard
whitelist potwierdza: jedyny wpis to `authors.py: 5`). Drobne (§E) — osobno.

## Stan obecny (zmapowany)

- `BppPBNClient.__init__(self, transport, uczelnia)` → `self.uczelnia` (Wątek 1,
  `pbn_api/client/__init__.py:93-95`).
- Łańcuch: `importuj_publikacje_po_pbn_uid_id(pbn_uid_id, client, default_jednostka, …)`
  → `utworz_{ksiazke,rozdzial,artykul}` → `utworz_autorow(ret, pbn_json, client,
  default_jednostka, …)` → `_przetworz_afiliacje(...)`. **Każdy poziom ma `client`.**
- `_przetworz_afiliacje(ta_afiliacja, default_jednostka, typ_autor, typ_redaktor,
  default_typ_odpowiedzialnosci=None)` (authors.py:~70-141) używa
  `Uczelnia.objects.default` 5×: `.obca_jednostka` (l.93), `.pbn_uid_id`
  (l.106, 115, 121, 135).
- Guard: `src/bpp/tests/test_multihosted_get_default_guard.py` —
  `"pbn_integrator/importer/authors.py": 5`.

## Zmiana

1. `_przetworz_afiliacje(...)` zyskuje parametr `uczelnia` (dodany na końcu sygnatury,
   wymagany). Wewnątrz: `Uczelnia.objects.default` → `uczelnia`:
   - `jednostka = uczelnia.obca_jednostka`,
   - 3× porównanie `... == uczelnia.pbn_uid_id`,
   - `uczelnia.pbn_uid_id if jest_nasz else "123"`.
   Import `from bpp.models import Uczelnia` może zostać (jeśli nieużywany po zmianie
   — usuń, by ruff nie zgłaszał; sprawdź inne użycia w pliku).
2. `utworz_autorow(...)` woła `_przetworz_afiliacje(..., uczelnia=client.uczelnia)`.
3. Guard whitelist: usuń wpis `"pbn_integrator/importer/authors.py": 5` (po zmianie
   plik nie używa `objects.default`).

## Invariant single-install

`client.uczelnia` w jednouczelnianej instalacji = ta jedna uczelnia = dotychczasowy
`Uczelnia.objects.default` → import zachowuje się identycznie.

## Ryzyka / uwagi

- `client.uczelnia` MUSI być ustawione na wejściu integratora (jest — `get_client`
  buduje `BppPBNClient` z uczelnią; Wątek 1). Jeśli jakaś ścieżka testowa konstruuje
  klienta bez uczelni, test to wykaże.
- `default_jednostka` jest przekazywana niezależnie (z entry-pointu, per-uczelnia) —
  spójna z `client.uczelnia`. Nie ruszamy jej.

## Testy

- Test jednostkowy `_przetworz_afiliacje`: dla afiliacji z `institutionId ==
  uczelnia.pbn_uid_id` → `afiliuje=True`, `jednostka=default_jednostka`; dla obcej →
  `obca_jednostka`, `afiliuje=False`. Z DWIEMA uczelniami (różne `pbn_uid_id`):
  ta sama afiliacja jest „nasza" dla uczelni A, „obca" dla B.
- Guard test (`test_multihosted_get_default_guard.py`) zielony po usunięciu wpisu
  (plik nie ma już `objects.default`).
- Regresja: `uv run pytest src/pbn_integrator/ -q -p no:cacheprovider` (single-install
  identycznie).

## Komendy weryfikacji

- `uv run pytest src/pbn_integrator/ src/bpp/tests/test_multihosted_get_default_guard.py -q -p no:cacheprovider`
- Lint: `uv run ruff check src/pbn_integrator/importer/authors.py`.

## Po integratorze

Drobne (§E): usunięcie `get_default` z `adapters/wydawnictwo.py`. Federacja — olana.
