# Prompt startowy — faza 04 soft-delete (guardy PROTECT)

Skopiuj treść między liniami do nowej sesji Claude Code, uruchomionej
w `~/Programowanie/bpp`.

---

Zrób fazę 04 soft-delete w BPP (guardy PROTECT).

**Worktree najpierw** — jeszcze nie istnieje, załóż go z `feat/soft-delete`
(tam wylądowały fazy 01–03, merge commit `774f1a72d`):

```bash
git worktree add ~/Programowanie/bpp-soft-delete-04 -b feat/soft-delete-04 feat/soft-delete
```

potem `EnterWorktree path=~/Programowanie/bpp-soft-delete-04`.

**Zacznij od dwóch dokumentów, w tej kolejności:**

1. `docs/superpowers/HANDOFF-soft-delete-faza-04.md` — stan, decyzje
   właściciela, dług. **Sekcja §4c jest obowiązkowa**: to lista rozjazdów
   między planem a kodem, sprawdzona w kodzie 2026-08-09.
2. `docs/superpowers/plans/2026-06-04-soft-delete-04-guardy-protect.md` —
   plan, 7 zadań. Powstał PRZED fazami 02 i 03, więc **czytaj go przez filtr
   §4c handoffu**. Nie odtwarzaj stanu z gita.

**Czego NIE rób:** nie ufaj numerom linii w planie (wszystkie nieaktualne,
tabela w §4c/R5); nie wstawiaj guarda na rozdziały do
`BppPublikacjaSoftDeleteMixin` (§4c/R3); nie zakładaj, że
`Praca_Habilitacyjna.autor` to `OneToOneField` (§4c/R2).

**Bloker, o którym trzeba wiedzieć zanim napiszesz Zadanie 3:** miękkie
`Autor.delete()` psuje scalanie autorów w przypadku „kolizja autorstw
w koszu", a Zadanie 6 planu tego nie wykryje. Mechanizm i miejsce poprawki:
§4c/R1. Poprawkę pisz RAZEM z Zadaniem 3, nie po nim.

**Zasady (te same, które sprawdziły się w fazie 03):**

- TDD: każda zmiana najpierw czerwonym testem, potem implementacja.
  Czerwień z `ImportError` nie liczy się jako dowód — **zweryfikuj mutacyjnie**,
  że asercje pilnują tego, co mają. Mutacja, która PRZESZŁA, znaczy albo słaby
  test, albo zbędny kod — rozstrzygnij który, zanim cokolwiek dopiszesz.
- Do mutacji rób **kopię pliku**, nie `git checkout` (cofa do HEAD i kasuje
  niezacommitowaną implementację).
- `ruff format` i `ruff check` tylko na własnych plikach.
- Testy uruchamiaj lokalnie. Czytaj podsumowanie pytest, **nie kod wyjścia
  `make`** (zwraca 0 mimo porażek). `make tests` przerywa się na pierwszym
  błędnym kroku — dokończ `tests-only-playwright` i `js-tests` osobno.
- Słowniki w testach bierz z fixture'ów (`jezyki`, `charaktery_formalne`,
  `typy_kbn`, `statusy_korekt`, `typy_odpowiedzialnosci`), nie z baseline —
  testy transakcyjne potrafią wyczyścić dane referencyjne. Zanim uznasz
  porażkę za regresję, powtórz na świeżych kontenerach (bez
  `PYTEST_TESTCONTAINERS_REUSE=1`).
- Przy zmianie typu pola albo typu zwracanego: sprawdź nie tylko KTO to woła,
  ale CO robi z wynikiem. Szablony Django połykają brak atrybutu bez wyjątku.
- **CI nie biegnie na PR-ach do `feat/soft-delete`** (workflow `Tests` ma
  `pull_request: branches: [dev]`). Zielony check na takim PR-ze nie jest
  dowodem — jedyną weryfikacją jest przebieg lokalny.
- Newsfragment (`src/bpp/newsfragments/<slug>.{feature,bugfix}.rst`) do każdej
  zmiany widocznej dla użytkownika.
- **Nie odświeżaj baseline** (`make baseline-update`) — stoi na `bpp/0487`
  i tak ma zostać do czasu scalania całego `feat/soft-delete` do `dev`.

**Na koniec:** pełne `make tests` (wszystkie trzy kroki), `pre-commit` na
plikach fazy, PR do `feat/soft-delete` z opisem mówiącym też, czego faza NIE
domyka, i handoff dla fazy 05.

Zacznij od Zadania 1 z planu — ale dopiero po przeczytaniu §4c.

---
