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

**KOREKTA zakresu (2026-06-03):** pierwotny spec błędnie twierdził „jedyny wpis to
authors.py: 5" (truncated grep). Guard whitelist ma w istocie TRZY wpisy integratora
(zgodnie z handoff §D). Pełny zakres:
- `importer/authors.py` (5) — ZROBIONE (`68959b629` + `3ca65a740`).
- `management/commands/pbn_integrator.py:221` (`_handle_people`): `pbn_uid_id =
  Uczelnia.objects.default.pbn_uid_id`. `handle()` ma już `client` i `uczelnia`;
  `_handle_people(opts, client, s, e)` → użyj `client.uczelnia.pbn_uid_id`.
- `utils/scientists.py:438` (matcher `matchuj_autora_po_stronie_pbn`): porównanie
  `pos["institutionId"] == Uczelnia.objects.default.pbn_uid_id`. Jedyny caller:
  `integruj_wszystkich_niezintegrowanych_autorow()` (globalny, iteruje wszystkich
  autorów bez pbn_uid). **Reguła (jak R2):** matcher dostaje uczelnię AUTORA
  (`autor.aktualna_jednostka.uczelnia`); gdy `None` (brak/obca jednostka) →
  matcher nie potrafi potwierdzić „pracuje u nas", `can_be_set` zostaje False
  (autor i tak bez home-uczelni — nie integrujemy go agresywnie). Sygnatura
  `matchuj_autora_po_stronie_pbn(imiona, nazwisko, orcid, uczelnia)`; przy `438`
  porównanie tylko gdy `uczelnia is not None` (`uczelnia.pbn_uid_id`).

**Poza zakresem:** reszta `pbn_integrator` nie używa `objects.default`. Drobne (§E) — osobno.

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
