# Naprawy naruszeń WCAG stwierdzonych lekturą kodu

Data: 2026-08-06
Poprzednik: `2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md`

## Cel

Usunąć te naruszenia WCAG 2.2 AA, które specyfikacja z 2026-08-05
stwierdziła **na podstawie lektury kodu** — bez czekania na audyt, skan
szeroki ani infrastrukturę testową.

To krok 3 z sekcji „Kolejność prac i zależności" tamtego dokumentu,
wykonywany jako samodzielna iteracja. Reszta programu (bramka CI, baseline,
audyt ręczny, raport zgodności) **nie wchodzi** — czeka na moment, w którym
pojawi się odbiorca raportu. Dziś takiego odbiorcy nie ma.

Uzasadnienie takiego cięcia: naprawy stwierdzone poprawiają dostępność
realnie i natychmiast, nie wymagają żadnej infrastruktury i nie zależą od
pięciu otwartych decyzji, które blokują resztę programu. Budowanie bramki CI
i raportu bez odbiorcy byłoby produkcją artefaktu, którego nikt nie czyta.

## Zakres

**Wchodzi:**

- 1.1.1 — obraz bez `alt` w `504.html`
- 1.1.1 — martwy szablon z obrazem bez `alt` (usunięcie, nie łatanie)
- 3.1.2 — atrybuty `lang` na tytułach obcojęzycznych, **oba wektory**
- warunek konieczny dla 3.1.2: rozszerzenie allowlisty sanityzatora
- wykaz świadomie odroczonych niezgodności
- korekta błędnego uzasadnienia w specyfikacji z 2026-08-05

**Nie wchodzi (odroczone świadomie, wpis w wykazie):**

- 2.1.4 — skrót `/`
- 2.5.7 — nawigacja po grafie powiązań

**Nie wchodzi (poza tą iteracją):**

- bramka CI z axe-core, baseline, strona wzorników
- skan szeroki na dumpie, audyt ręczny WCAG-EM, raport zgodności
- hipotezy do zbadania (3.3.7, 3.3.8, CAPTCHA, 2.5.8)

## Naprawa 1 — 1.1.1, obraz bez `alt` w `504.html`

`src/bpp/templates/504.html:12` renderuje ikonę wewnątrz `<h1>`:

```html
<h1>
    <img src="/static/bpp/svg/database.svg" style="max-width: 2.8em;"
         align="absmiddle"/>
    Przekroczono dozwolony czas wykonywania zapytania
</h1>
```

Obok obrazu stoi pełny tekst komunikatu. Ikona nie niesie żadnej informacji,
której nie ma w tekście — jest dekoracją. Właściwą wartością jest `alt=""`
(pusty), nie opis: pusty `alt` każe czytnikowi **pominąć** element, podczas
gdy brak atrybutu każe mu odczytać nazwę pliku („database dot es vee gee").

Opis w rodzaju `alt="ikona bazy danych"` byłby błędem — powtarzałby
dekorację jako treść i wydłużał odczyt strony błędu.

## Naprawa 2 — 1.1.1, martwy szablon

`src/bpp/templates/user_navigation_autocomplete.html:7` zawiera `<img>` bez
`alt`. Szablon jest **nieużywany**: przeszukanie całego repozytorium (poza
`.git`, `node_modules`, `.venv`) znajduje jego nazwę wyłącznie w
specyfikacji z 2026-08-05. Żaden widok, tag ani `include` go nie renderuje.

Widok pod `bpp:navigation-autocomplete` (`src/bpp/urls.py:496`) to
`GlobalNavigationAutocomplete` (`src/bpp/views/autocomplete/navigation.py:91`)
— podklasa `Select2QuerySetSequenceView` z django-autocomplete-light. Zwraca
JSON; listę podpowiedzi rysuje Select2 po stronie klienta. Szablon jest
pozostałością po wcześniejszej implementacji.

**Decyzja: usuwamy plik**, nie dopisujemy `alt`.

Uzasadnienie: naruszenie w kodzie, którego nikt nie renderuje, nie jest
naruszeniem — użytkownik nigdy tej strony nie zobaczy. Dopisanie `alt`
utrwaliłoby martwy plik i przy następnym audycie znowu trafiłby na listę
jako „widok do zbadania". Usunięcie zamyka sprawę.

To zarazem korekta specyfikacji z 2026-08-05, która wymienia ten plik jako
jeden z dwóch widoków wymagających poprawki `alt`. Metoda (grep po `<img`)
nie odpowiadała na pytanie, czy plik jest renderowany.

## Naprawa 3 — 3.1.2, atrybuty `lang`

### Problem

Baza bibliograficzna zawiera w większości tytuły angielskie, na stronie
zadeklarowanej jako `lang="pl"`. Czytnik ekranu odczytuje angielski tytuł
polską fonetyką. Kryterium 3.1.2 (AA) wymaga oznaczenia fragmentu w innym
języku niż język strony.

Dane są już w modelu: `Jezyk.kod_bcp47`
(`src/bpp/models/system/__init__.py:81`) trzyma notację BCP 47 / RFC 5646,
czyli dokładnie to, czego wymaga atrybut `lang`. Pole dodano dla eksportu
CERIF/OpenAIRE.

### Źródło kodu językowego

Model publikacji (`src/bpp/models/abstract/publication_base.py:46-66`) ma
trzy pola językowe:

| pole | znaczenie | użycie tutaj |
|---|---|---|
| `jezyk` | Język (wymagany) | język `tytul_oryginalny` |
| `jezyk_alt` | Język alternatywny (opcjonalny) | język `tytul` (przekład) |
| `jezyk_orig` | Język oryginalny, dla tłumaczeń, eksport do PBN | nie używamy |

`jezyk_orig` jest jawnie udokumentowany jako pole dla tłumaczeń
eksportowane do PBN i nie opisuje języka żadnego z dwóch wyświetlanych
tytułów — pomijamy.

**Założenie do potwierdzenia:** `jezyk_alt` opisuje język tytułu
przełożonego (`tytul`). Pole nie ma `help_text`, a w kodzie występuje
wyłącznie jako pozycja w fieldsetach admina, serializerach API i eksporcie
CERIF — żadne z tych miejsc nie ujawnia semantyki. Jeżeli założenie jest
błędne, `tytul` po prostu nie dostaje atrybutu (patrz reguła niżej) i
poprawka pozostaje bezpieczna, tylko węższa.

### Reguła

Dla każdego z dwóch tytułów niezależnie:

- kod języka niepusty → owiń w `<span lang="...">`
- kod pusty, brak relacji, lub relacja bez `kod_bcp47` → **nie dodawaj
  atrybutu wcale**

`lang=""` jest gorsze niż brak atrybutu: pusta wartość jest w HTML
traktowana jako „język nieznany" i unieważnia dziedziczenie z `<html
lang="pl">`, czyli psuje odczyt fragmentu, który bez atrybutu byłby
odczytany poprawnie po polsku.

Oba tytuły wymagają **osobnych** znaczników. Wspólny `<span>` obejmujący
blok „tytuł oryginalny (przekład)" oznaczyłby jednym językiem dwa fragmenty
w różnych językach — gorzej niż nie oznaczyć nic.

### Wektor 1 — szablony stron szczegółowych

Trzy miejsca renderują tytuł bezpośrednio z pól modelu:

- `src/bpp/templates/browse/praca_tabela_mono.html:17-21`
- `src/bpp/templates/browse/praca_tabela.html:7-10`
- `src/bpp/templates/browse/praca.html:49` (breadcrumb)

Zmiana działa natychmiast po wdrożeniu — szablon renderuje się przy każdym
żądaniu z aktualnych danych relacyjnych.

Uwaga na filtry: tytuły przechodzą przez `|safe_tytul` (mono), `|safe`
(tabela) i `|truncatewords_html:15|safe_tytul` (breadcrumb). Znacznik
`<span>` dokładamy **wokół** wyniku filtra, w szablonie — nie wewnątrz
wartości pola. Sanityzator tytułu (`safe_tytul_html`) nie ma z nim
styczności.

### Wektor 2 — generator opisu bibliograficznego

Listy `browse`, wyniki multiseek i wydawnictwa powiązane (31 miejsc w
szablonach) nie renderują pól — wstawiają gotowy HTML z
`opis_bibliograficzny_cache`. Tytuł siedzi **wewnątrz** tego blobu,
wymieszany z polszczyzną:

```
Kowalski Jan, Nowak Anna. Effects of X on Y. Postępy Higieny
i Medycyny Doświadczalnej 2024, t. 78, s. 112-119.
```

Owinięcie całego blobu w `lang="en"` byłoby błędem — oznaczyłoby polskie
nazwiska i polską nazwę czasopisma jako angielskie. Wycinanie tytułu z blobu
przy renderowaniu odpada: dopasowanie stringu jest kruche przy tytułach
zawierających zamierzone `<i>`/`<sub>`.

Zostaje jedyna droga: **znacznik wstawia generator**, czyli trafia do środka
cache'owanego HTML-u w chwili jego powstawania.

Generator to szablon Django `src/bpp/templates/opis_bibliograficzny.html:7-11`,
renderowany przez `ModelZOpisemBibliograficznym.opis_bibliograficzny()`
(`src/bpp/models/util.py:91`). Zmiana jest tam symetryczna do wektora 1.

## Warunek konieczny — allowlista sanityzatora

`opis_bibliograficzny()` kończy się przepuszczeniem złożenia przez
`safe_opis_bibliograficzny_html` (`src/bpp/util/text.py:316`), czyli przez
nh3 z wąską allowlistą (`text.py:306-313`):

```python
class safe_opis_bibliograficzny_defaults:
    ALLOWED_TAGS = safe_tytul_defaults.ALLOWED_TAGS + ("a",)
    ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}
```

gdzie `safe_tytul_defaults.ALLOWED_TAGS == ("i", "em", "b", "strong",
"sub", "sup", "u")`.

`span` nie jest dozwolonym tagiem, a atrybuty ma wyłącznie `<a>`. Bez
zmiany allowlisty `<span lang="en">Tytuł</span>` zostałby zredukowany do
gołego `Tytuł` — poprawka wektora 2 cicho by nie zadziałała.

**Zmiana:** dopisać `"span"` do `ALLOWED_TAGS` i `"span": ["lang"]` do
`ALLOWED_ATTRIBUTES`.

Ocena ryzyka: `lang` jest atrybutem czysto deklaratywnym — nie wykonuje
kodu, nie ładuje zasobów, nie wpływa na układ. `span` bez `style` i bez
`class` nie pozwala na nadpisanie wyglądu. Rozszerzenie jest wąskie i nie
otwiera nowego wektora XSS.

Obie wartości są nadpisywalne przez `settings.OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`
i `..._ALLOWED_ATTRIBUTES`. Wdrożenie z własnym override'em dostanie starą,
wąską listę i straci znaczniki — to zachowanie akceptowalne (override jest
świadomą decyzją administratora), ale wymaga wzmianki w wykazie.

## Rollout wektora 2

`opis_bibliograficzny_cache` to **dane**, nie kod: w bazie leżą gotowe
stringi HTML wygenerowane wcześniejszą wersją generatora. Deploy podmienia
szablon, ale nie dotyka zapisanych wierszy.

Regeneracja dzieje się sama, w istniejącym cyklu nocnym — bez ręcznej
interwencji i bez okna serwisowego ponad to, które już istnieje:

1. **22:00** — Ofelia (`bpp-deploy/docker-compose.application.yml:117-118`)
   uruchamia `python src/manage.py denorm_rebuild --no-flush`. `rebuildall()`
   oznacza wszystkie wiersze jako brudne.
2. **w nocy** — kontener `denorm-queue` przekazuje LISTEN/NOTIFY do kolejki
   celery `denorm`; `flush_single` przelicza rekord i zapisuje nowy
   `opis_bibliograficzny_cache` w tabeli źródłowej.
3. **natychmiast po tym UPDATE** — trigger `bpp_refresh_cache()`
   (`src/bpp/migrations/107_cache_functions.sql:5`) robi `DELETE` +
   `INSERT ... SELECT` z widoku, więc `bpp_rekord_mat` (materializacja, z
   której czytają listy) dostaje nową treść.

Istotne: **`denorm_rebuild` (nie `denorm_flush`)**. Flush opróżnia tylko
kolejkę brudnych wierszy, a podmiana kodu Pythona nie brudzi żadnego —
harmonogram oparty na `flush` nie zmieniłby nic. Rebuild sam oznacza
wszystko.

Pierwsza noc po wdrożeniu jest cięższa niż zwykle: dziś rebuild zwykle
zastaje identyczne wartości, więc zapisów i strzałów triggera jest mało; po
zmianie generatora różni się każdy wiersz. Operacja mieści się w
istniejącym oknie (przed backupem o 2:30 —
`bpp-deploy/docker-compose.backup.yml:64`) i nie wymaga człowieka.

**Szablon jest na dysku, nie w bazie.** Migracja `0295_instaluj_szablony.py`
kiedyś kopiowała `opis_bibliograficzny.html` do `dbtemplates`, ale
`0473_szablon_nazwa_szablonu.py` to odwróciła: usunęła FK
`SzablonDlaOpisuBibliograficznego.template`, wprowadziła zwykłe
`nazwa_szablonu` z domyślnym `"opis_bibliograficzny.html"`, a
`purge_opis_dbtemplate` skasowała wiersze dbtemplate dla wszystkich
używanych nazw. Zmiana pliku w repozytorium dociera więc do każdego
wdrożenia zwykłym deployem — bez migracji danych i bez ryzyka skasowania
customizacji uczelni.

## Wpływ na konsumentów opisu

`opis_bibliograficzny_cache` nie służy wyłącznie do publicznego HTML-a.
Dodanie `<span lang>` zmienia to, co dostają:

| konsument | plik | ocena |
|---|---|---|
| REST API `/api/v1/` | `src/api_v1/serializers/szukaj.py:28` | zwraca string HTML; już zawiera `<i>`/`<sub>` |
| widget publikacji | `src/api_v1/viewsets/recent_publications_common.py:135` | jw. |
| wydruki PDF | `src/oswiadczenia/` (weasyprint) | `<span lang>` nieszkodliwy |
| DjangoQL | `src/bpp/djangoql_schema.py:105-108` | `strip_tags` — bez zmian |
| filtr kolejki PBN | `src/pbn_export_queue/views/list_views.py:81` | **do testu** |

Ostatnia pozycja to jedyna realna: `search_lower in
record.opis_bibliograficzny_cache.lower()` szuka podłańcucha w surowym
HTML-u, więc znacznik wstawiony między słowa może rozbić dopasowanie. Blob
już dziś zawiera znaczniki, więc klasa problemu nie jest nowa — ale wstawiamy
je w nowym miejscu (przed tytułem), co wymaga testu.

## Testy

Konwencja pytest (funkcje, `@pytest.mark.django_db`, `baker.make`).

**3.1.2, wektor 1** — dla każdego z trzech szablonów:
- tytuł oryginalny z `kod_bcp47="en"` → w wyjściu jest `lang="en"`
- `kod_bcp47=""` → w wyjściu **nie ma** `lang=` przy tytule
- tytuł oryginalny i przekład w różnych językach → dwa różne `lang`,
  nierozłączne (żaden nie obejmuje drugiego)

**3.1.2, wektor 2** — na `opis_bibliograficzny()`:
- te same trzy przypadki na wygenerowanym opisie
- **znacznik przeżywa sanityzację** — asercja wprost na wyniku
  `opis_bibliograficzny()`, nie na samym szablonie; to test broniący
  allowlisty przed cofnięciem

**Sanityzator** — regresja bezpieczeństwa na `safe_opis_bibliograficzny_html`:
- `<script>alert(1)</script>` nadal usuwany razem z treścią
- `<span onerror="...">` → atrybut zdarzenia usunięty, `span` zostaje
- `<span style="...">`, `<span class="...">` → atrybuty usunięte
- `<span lang="en">` → przechodzi w całości

**Filtr kolejki PBN** — wyszukiwanie frazy w opisie zawierającym `<span
lang>` nadal znajduje rekord dla frazy niesąsiadującej ze znacznikiem;
przypadek frazy przeciętej znacznikiem odnotowany asercją zgodną z
zastanym zachowaniem (dokumentuje stan, nie udaje naprawy).

**1.1.1** — asercja, że `504.html` renderuje `<img` z `alt=""`.

Weryfikacja braku regresji szablonowych: `make tests-without-playwright`
lokalnie przed PR-em.

## Wykaz odroczonych niezgodności

Nie istnieje dziś raport zgodności, w którym takie wpisy miałyby swoje
miejsce. Zapisujemy je w specyfikacji z 2026-08-05 (nowa sekcja
„Odroczone niezgodności"), bo to dokument, który przyszły audyt przeczyta
jako pierwszy; issue na GitHubie by zaginęło.

Każdy wpis zawiera kryterium, stan, uzasadnienie i datę decyzji.

**2.1.4 Character Key Shortcuts (A) — skrót `/`.**
Handler w `src/django_bpp/templates/base.html:39-49` wiąże `/` na
`document`, wykluczając jedynie `input`/`textarea`/`select`. Nie spełnia
żadnego z trzech warunków kryterium (wyłączalny, przemapowywalny, aktywny
tylko przy focusie). Stan: **niezgodne, świadomie odroczone**. Powód: brak
nacisku regulacyjnego i brak odbiorcy raportu; wszystkie trzy dopuszczone
wyjścia mają koszt produktowy (utrata skrótu globalnego albo zbudowanie
interfejsu preferencji dla użytkownika anonimowego). Do rozstrzygnięcia,
gdy audyt ruszy.

**2.5.7 Dragging Movements (AA) — graf powiązań.**
`src/powiazania_autorow/templates/powiazania_autorow/graf.html`, widok
publiczny bramkowany per uczelnia (`czy_pokazywac_siec_powiazan`,
`src/bpp/views/browse.py:245`). Nawigacja wyłącznie przez przeciąganie.
Stan: **niezgodne, świadomie odroczone**. Powód: koszt (przyciski
przesuwania i zoomu albo obsługa klawiaturą wizualizacji) nieproporcjonalny
do pozostałych napraw w tej iteracji, a funkcja jest opcjonalna i w części
wdrożeń wyłączona.

**3.1.2 — instalacje z niewypełnionym `kod_bcp47`.**
Stan: **spełnione warunkowo**. Pole jest `blank=True`; poprawka kodu
oznacza tytuł tylko tam, gdzie słownik języków ma wypełniony kod BCP 47.
Uzupełnienie słownika jest zadaniem uczelni i w raporcie musi być warunkiem,
nie faktem dokonanym.

**3.1.2 — instalacje z własnym `OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`.**
Stan: **spełnione warunkowo**. Override w settings zastępuje domyślną
allowlistę; wdrożenie, które go ustawiło przed tą zmianą, straci znaczniki
w opisie bibliograficznym do czasu dopisania `span`/`lang`.

## Korekta specyfikacji z 2026-08-05

Dwa miejsca tamtego dokumentu wymagają poprawki. Obie korekty idą w tym
samym PR — dokument opisuje stan kodu i milcząca rozbieżność mści się przy
następnym czytaniu.

**Wektor 2 nie wymaga liveops.** Sekcja „3.1.2 Language of Parts" i „Otwarte
decyzje" twierdzą, że domknięcie wektora 2 wymaga „przebudowy cache'u, czyli
migracji danych na produkcji" i „godzin przeliczania na dużych bazach" per
wdrożenie. Wniosek (odroczyć) był oparty na przesłance, która nie
uwzględniała nocnego `denorm_rebuild` z Ofelii — przeliczenie całej bazy
dzieje się co noc niezależnie od tej zmiany. Rzeczywistym warunkiem
koniecznym jest rozszerzenie allowlisty nh3, którego dokument nie wymienia.

**`user_navigation_autocomplete.html` nie jest widokiem w zakresie.**
Sekcje „Punkt wyjścia" (`:58`) i „1.1.1 Non-text Content" (`:601`)
wymieniają go jako jeden z dwóch widoków z obrazem bez `alt`. Szablon jest
martwy — usuwamy go, a inwentaryzacja traci jedną pozycję.

## Poza zakresem

- bramka CI z axe-core, baseline jako zapadka, strona wzorników
- skan szeroki na dumpie, próbka WCAG-EM, audyt ręczny bloków 1–6
- raport zgodności i deklaracja dostępności
- kryteria z listy hipotez (3.3.7, 3.3.8, CAPTCHA, 2.5.8)
- panel zalogowanego użytkownika i Django admin
- poziom AAA
