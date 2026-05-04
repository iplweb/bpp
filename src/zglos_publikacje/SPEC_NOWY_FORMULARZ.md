# Specyfikacja: nowy formularz zgłaszania publikacji

## Przegląd zmian

Obecny formularz jednoetapowy zastępujemy wielokrokowym wizardem z dwoma
krokami wstępnymi (kafelki wyboru) oraz formularzem danych zależnym od
dokonanych wyborów.

---

## Krok 1 — Rodzaj publikacji (kafelki)

Użytkownik wybiera jeden z czterech kafelków:

| Kafelek       | Wartość wewnętrzna |
|---------------|--------------------|
| Artykuł       | `ARTYKUL`          |
| Monografia    | `MONOGRAFIA`       |
| Rozdział      | `ROZDZIAL`         |
| Inne          | `POZOSTALE`        |

Wybór zastępuje dotychczasowe pole `rodzaj_zglaszanej_publikacji` w formularzu.
Pole `rodzaj_zglaszanej_publikacji` w modelu pozostaje (kompatybilność),
ale jest ustawiane automatycznie na podstawie wybranego kafelka.

---

## Krok 2 — Forma dostępu (kafelki)

Użytkownik wybiera jeden z dwóch kafelków:

| Kafelek              | Znaczenie                                                  |
|----------------------|------------------------------------------------------------|
| Otwarty dostęp       | Pełny tekst jest dostępny online (link lub DOI)            |
| Dostęp ograniczony   | Pełny tekst nie jest swobodnie dostępny w internecie       |

Ten krok dotyczy wszystkich czterech typów publikacji jednakowo.

---

## Krok 3 — Formularz danych o publikacji

Pola formularza zależą od kombinacji wyboru z kroków 1 i 2.

### Pola wspólne (zawsze obecne, niezależnie od wyborów)

| Pole                                         | Typ           | Wymagane | Uwagi                                                       |
|----------------------------------------------|---------------|----------|--------------------------------------------------------------|
| `tytul_oryginalny`                           | textarea      | tak      | Tytuł pracy                                                  |
| `rok`                                        | integer       | tak      | Rok publikacji                                                |
| `email`                                      | email         | tak      | E-mail zgłaszającego; prefill jeśli user zalogowany           |
| `zgoda_na_publikacje_pelnego_tekstu`         | choice (tak/nie) | tak*  | *Pole widoczne tylko gdy uczelnia ma włączone ustawienie `pytaj_o_zgode_na_publikacje_pelnego_tekstu`. Opis: "Zgoda na publikację pełnego tekstu w lokalnym repozytorium". Help text wyjaśnia, że dotyczy lokalnego repozytorium uczelni, niezależnie od formy dostępu do publikacji w internecie. |

### Pola zależne od kroku 2 (forma dostępu)

#### Wariant: Otwarty dostęp

| Pole          | Typ       | Wymagane | Uwagi                                                                 |
|---------------|-----------|----------|-----------------------------------------------------------------------|
| `strona_www`  | URL/text  | tak      | Link do pełnego tekstu lub identyfikator DOI. Jedno pole; system sam wykrywa, czy podano DOI czy URL. |

Pliki PDF: **nie są wymagane, pole nie pojawia się**.

#### Wariant: Dostęp ograniczony

| Pole          | Typ       | Wymagane | Uwagi                                                        |
|---------------|-----------|----------|--------------------------------------------------------------|
| `strona_www`  | URL/text  | nie      | Opcjonalny link (np. zajawka na stronie wydawcy)             |
| `pliki`       | file/PDF (wiele) | tak | Pliki PDF z pełnym tekstem pracy; wymagany min. 1 plik; możliwość dodania wielu plików |

### Pola zależne od kroku 1 (rodzaj publikacji)

#### Artykuł

Brak dodatkowych pól ponad pola wspólne + pola z kroku 2.

#### Monografia

| Pole      | Typ                          | Wymagane | Uwagi                                                                   |
|-----------|------------------------------|----------|-------------------------------------------------------------------------|
| `wydawca` | autocomplete + freetext      | nie      | Autocomplete z tabeli wydawców BPP. Jeśli brak pasującego — freetext.   |

#### Rozdział

| Pole                       | Typ                          | Wymagane | Uwagi                                                                                                                 |
|----------------------------|------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------|
| `wydawnictwo_nadrzedne`    | autocomplete + freetext      | tak      | Tytuł monografii, w której jest rozdział. Autocomplete z wydawnictw zwartych BPP i/lub wydawnictw nadrzędnych PBN. Jeśli brak pasującego — freetext. |
| `wydawca`                  | autocomplete + freetext      | nie      | Nazwa wydawcy/oficyny. Autocomplete z tabeli wydawców BPP. Jeśli brak — freetext.                                     |

#### Inne

Brak dodatkowych pól ponad pola wspólne + pola z kroku 2.

---

## Podsumowanie: macierz pól na formularzu (krok 3)

Legenda: **W** = wymagane, **O** = opcjonalne, **—** = nie pojawia się

| Pole                                 | Artykuł OA | Artykuł ogr. | Monografia OA | Monografia ogr. | Rozdział OA | Rozdział ogr. | Inne OA | Inne ogr. |
|--------------------------------------|:----------:|:------------:|:-------------:|:---------------:|:-----------:|:-------------:|:-------:|:---------:|
| `tytul_oryginalny`                   | W          | W            | W             | W               | W           | W             | W       | W         |
| `rok`                                | W          | W            | W             | W               | W           | W             | W       | W         |
| `email`                              | W          | W            | W             | W               | W           | W             | W       | W         |
| `zgoda_na_publikacje_pelnego_tekstu` | O*         | O*           | O*            | O*              | O*          | O*            | O*      | O*        |
| `strona_www` (link/DOI)              | W          | W            | W             | W               | W           | W             | O       | O         |
| `pliki` (PDF, wiele)                 | —          | W            | —             | W               | —           | W             | —       | W         |
| `wydawca`                            | —          | —            | O             | O               | O           | O             | —       | —         |
| `wydawnictwo_nadrzedne`              | —          | —            | —             | —               | W           | W             | —       | —         |

*O\* = widoczne tylko gdy uczelnia ma włączone ustawienie*

---

## Kolejne kroki wizarda (bez zmian)

- **Krok 4 — Autorzy**: bez zmian względem obecnego formularza.
- **Krok 5 — Opłaty za publikację**: bez zmian; wyświetlany warunkowo
  w zależności od ustawień uczelni i rodzaju publikacji.

---

## Uwagi techniczne

1. Pole `rodzaj_zglaszanej_publikacji` w modelu `Zgloszenie_Publikacji`
   wymaga rozszerzenia wartości enum `Rodzaje` — rozdzielenie
   `ARTYKUL_LUB_MONOGRAFIA` na `ARTYKUL` i `MONOGRAFIA`.
2. Migracja danych: istniejące rekordy `ARTYKUL_LUB_MONOGRAFIA` mogą
   wymagać decyzji, jak je przeklasyfikować (lub zostawić z obecną wartością
   jako legacy).
3. Pola `wydawca` i `wydawnictwo_nadrzedne` to nowe pola na modelu
   `Zgloszenie_Publikacji`.
4. Autocomplete z możliwością freetext: implementacja przez
   django-autocomplete-light z opcją `create` lub analogiczny mechanizm
   pozwalający wpisać wartość spoza listy.
5. Wizardy (django-formtools SessionWizard) pozostają jako mechanizm
   nawigacji między krokami.
