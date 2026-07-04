# Likwidacja pustych jednostek uczelni → jednostki domyślne per wydział

Data: 2026-06-30
Status: zaimplementowane

## Problem

Dla uczelni (np. UAFM, `Uczelnia.skrot == "UAFM"`) należy zlikwidować
jednostki organizacyjne w wydziałach i zostawić w każdym wydziale jedną
„jednostkę domyślną". **Założenie biznesowe: likwidowane jednostki są PUSTE**
(nie ma w nich zatrudnień, publikacji, patentów ani prac doktorskich). Jeżeli
któraś nie jest pusta — operacja ma się NIE wykonać i zgłosić błąd.

Dzięki założeniu o pustości NIE ma scalania / przepinania danych — to zwykłe
„skasuj puste, załóż domyślne".

## Pułapka: CASCADE

`bpp.Jednostka` jest celem FK z `on_delete=CASCADE` z wielu modeli. „Pusta"
musi więc oznaczać brak referencji w KAŻDYM kanale, który przy `DELETE`
kasuje realne dane:

- `Autor_Jednostka` (zatrudnienia) — `autor.py:562`
- `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor`
  (przez `BazaModeluOdpowiedzialnosciAutorow.jednostka`, `abstract/authors.py:23`)
- `Praca_Doktorska.jednostka` — `praca_doktorska.py:27`
- **`Autor.aktualna_jednostka`** — `autor.py:105` (`CASCADE`!): gdyby jednostka
  była czyjąś „aktualną", jej skasowanie skasowałoby autora. Przy braku
  zatrudnień nie powinno wystąpić (pole pochodzi z triggera `0046`), ale jest
  sprawdzane jako tani bezpiecznik.

`Jednostka_Wydzial` (historia) jest też CASCADE, ale to czysta metadana —
ginie razem z jednostką i nie blokuje usunięcia.

## Decyzje

- Jednostka docelowa: NOWA, jedna per wydział.
- Nazwa: `"Jednostka Domyślna - {wydzial.nazwa}"` (BEZ odmiany — nazwy
  wydziałów już zawierają słowo „Wydział", np. → `Jednostka Domyślna -
  Wydział Medyczny`). Skrót: `"JD-{wydzial.skrot}"`.
- Niepuste jednostki → `CommandError`, nic nie kasujemy (wszystko-albo-nic).
- Jednostki bez wydziału (w tym `Uczelnia.obca_jednostka`) — nietknięte
  (filtr `wydzial__in=wydzialy`; dodatkowy explicit exclude na
  `obca_jednostka`).

## Rozwiązanie

Komenda: `src/bpp/management/commands/zaloz_jednostki_domyslne.py`

```
uv run python src/manage.py zaloz_jednostki_domyslne UAFM --dry-run
uv run python src/manage.py zaloz_jednostki_domyslne UAFM
```

Algorytm (cały w `@transaction.atomic`):

1. `Uczelnia.objects.get(skrot=...)` (multi-hosted → po skrócie, nigdy
   `get_default`).
2. `wydzialy = Wydzial.objects.filter(uczelnia=...)`; brak wydziałów → błąd.
3. `likwidowane` = jednostki tej uczelni z `wydzial__in=wydzialy`, minus
   `obca_jednostka`.
4. **Walidacja pustości**: dla każdej liczone są powiązania CASCADE; jeśli
   jakieś niepuste → wypisz listę z licznikami i `CommandError` (nic nie
   skasowane).
5. Dla każdego wydziału `get_or_create` jednostki domyślnej (idempotentne).
6. **Bezpiecznik hierarchii**: jeśli któraś usuwana jednostka jest rodzicem
   jednostki spoza zakresu (parent CASCADE) → `CommandError`.
7. `do_usuniecia.delete()` (stare, poza świeżo założonymi domyślnymi).
8. `--dry-run` → `transaction.set_rollback(True)` na końcu (zmiany wykonują się
   naprawdę w transakcji i są wycofywane → wierny podgląd).

Co działa samo: `Autor.aktualna_jednostka`/`aktualna_funkcja` (trigger SQL
`0046`); hierarchia MPTT (wszystkie stare kasowane, domyślne mają `parent=None`).

## Testy

`src/bpp/tests/test_zaloz_jednostki_domyslne.py`:

1. happy path — puste jednostki znikają, zostaje 1 domyślna z poprawną nazwą,
2. niepusta (z `Autor_Jednostka`) → `CommandError`, stan nietknięty,
3. `--dry-run` niczego nie zmienia,
4. uczelnia bez wydziałów → `CommandError`.

## Poza zakresem komendy

- Przeniesienie danych z NIEpustych jednostek — od tego jest istniejące
  `remap_jednostka` (przepina FK z detekcją konfliktów). Tę komendę uruchamia
  się ręcznie PRZED `zaloz_jednostki_domyslne`, jeśli walidacja pustości
  zgłosi niepuste jednostki.
- Przeliczenie `Cache_Punktacja_*` — niepotrzebne, bo kasujemy tylko puste
  jednostki (cache i tak ich nie dotyczy).
