# Spec — Track 6: `Uczelnia.objects.first()` sweep + rozszerzenie guarda

Audyt: `docs/superpowers/2026-06-04-audyt-uczelnia-coverage.md` (Klasa 1, druga
ślepa plamka). Gałąź `feature/multi-hosted-config`.

## Problem

Guard `test_multihosted_get_default_guard.py` pilnuje wyłącznie
`Uczelnia.objects.get_default()` / `Uczelnia.objects.default`. Wzorzec
**semantycznie równoważny** `Uczelnia.objects.first()` (zgaduje pierwszą-z-brzegu
uczelnię) jest niewidoczny dla guarda i występuje **28×** w runtime. W widoku z
requestem `Uczelnia.objects.first()` → operacja DLA PIERWSZEJ uczelni niezależnie
od hosta (ten sam klasa-bug co B1, tylko inny zapis).

## Inwentarz (28 wystąpień — do bezwzględnej weryfikacji)

| plik | liczność | klasa |
|---|---|---|
| `ewaluacja_optymalizacja/views/evaluation_browser/views.py` | 6 | 🔴 runtime view (request dostępny) |
| `ewaluacja_optymalizacja/views/{unpinning_list,pins,optimize_unpin,discipline_swap_list}.py` | 2 ea | 🔴 runtime view |
| `ewaluacja_optymalizacja/views/{unpinning_analysis,unpin_sensible,index,discipline_swap_analysis,bulk_optimization}.py` | 1 ea | 🔴 runtime view |
| `ewaluacja_optymalizacja/management/commands/{solve_uczelnia,solve_evaluation}.py` | 1 ea | 🟡 CLU → single-or-fail |
| `ewaluacja_optymalizacja/core/__init__.py` | 1 | weryfikować (runtime vs setup) |
| `bpp/models/{jednostka,autor}.py` | 1 ea | 🟡 warstwa modelu (display/sort) — prawdop. whitelist |
| `bpp/admin/core.py` | 1 | 🟡 form default UI (jak w whitelist get_default) |
| `bpp/management/commands/debug_setup_initial_data.py` | 1 | 🟡 debug — whitelist |
| `bpp/demo_data/generators/uczelnia.py` | 1 | 🟡 demo/seed — whitelist |
| `bpp_setup_wizard/tests.py` | 1 | test — poza zakresem (guard ignoruje `test_`) |

## Reguła rozstrzygania (per wystąpienie)

1. **Widok runtime z requestem** (`ewaluacja_optymalizacja/views/*`) → zamień na
   `Uczelnia.objects.get_for_request(self.request)` (write) lub
   `raport_slotow.uczelnia_helper.uczelnia_dla_odczytu(self.request)` (read).
   UWAGA: te widoki należą do **federacji optymalizacji** (świadomie olanej jako
   logika), więc samo użycie właściwej uczelni z requestu jest poprawne i NIE
   wymaga pełnego federacyjnego refaktoru — chodzi tylko o „nie pierwsza-z-brzegu".
2. **Management command** (`solve_uczelnia`, `solve_evaluation`) → wzorzec
   single-or-fail: `Uczelnia.objects.get(pk=uczelnia_id) if uczelnia_id else
   Uczelnia.objects.get()` + arg `--uczelnia` (jak `zbieraj_sloty`, B2).
3. **Warstwa modelu / display / demo / debug** → świadomy fallback; jeśli
   None-tolerant i bez requestu → **whitelist** w guardzie z uzasadnieniem.
4. **`core/__init__.py`** → przeczytać; jeśli woła go widok/task z dostępną
   uczelnią → przekazać argumentem; jeśli setup-time → whitelist.

## Rozszerzenie guarda

W `src/bpp/tests/test_multihosted_get_default_guard.py`:
- Dodać DRUGI wzorzec: `Uczelnia\.objects\.first\(\)`.
- Osobny słownik `APPROVED_FIRST` z whitelistą (demo/debug/warstwa modelu/UI
  default) + komentarz per wpis.
- Skan `_scan()` zliczający oba wzorce; asercja jak dla get_default.
- Rozważyć też `Uczelnia\.objects\.all\(\)\[0\]` (obecnie 0 wystąpień — dodać
  prewencyjnie do wzorca, koszt zerowy).

## Plan wykonania (TDD, per-grupa, subagent-driven jak R1/R3)

1. **Recon:** przeczytać KAŻDE z 28 wystąpień, sklasyfikować (🔴 fix / 🟡 whitelist),
   uzupełnić tabelę powyżej werdyktami `plik:linia`.
2. **Fix runtime views** (~17 w `ewaluacja_optymalizacja/views/`): per plik
   zamiana na `get_for_request`/`uczelnia_dla_odczytu`. Test: widok pod U2 operuje
   na U2, nie U1 (model `OptimizationRun`/`MetrykaAutora` ma FK uczelnia — asercja
   po `uczelnia_id`). Uwaga na enqueue tasków (`pins.py` przekazuje `uczelnia.pk`).
3. **Fix commands** (2): `--uczelnia` + single-or-fail; test CommandError przy >1
   bez flagi.
4. **Whitelist** reszty z uzasadnieniem.
5. **Guard:** rozszerzyć wzorzec, ustawić whitelistę; uruchomić — zielony.
6. Pełna regresja `ewaluacja_optymalizacja` + guard.

## Inwariant
Single-install: `get_for_request` zwraca tę jedną uczelnię = zachowanie jak
`first()`. Zero zmian liczb przy 1 uczelni.

## Zależność
Backlog C (globalne `.delete()` w tych samych widokach/taskach federacji) jest
ORTOGONALNY — ten spec dotyczy TYLKO rozstrzygania uczelni (`first()`), nie
scope'owania delete'ów. Można je domknąć osobno (lub przy okazji).
