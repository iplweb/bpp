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
- 3.1.2 — atrybuty `lang` na tytułach oryginalnych, **oba wektory**
- warunek konieczny dla 3.1.2: rozszerzenie allowlisty sanityzatora
- wykaz świadomie odroczonych niezgodności
- korekta błędnych ustaleń w specyfikacji z 2026-08-05

**Nie wchodzi (odroczone świadomie, wpis w wykazie):**

- 2.1.4 — skrót `/`
- 2.5.7 — nawigacja po grafie powiązań
- 3.1.2 dla tytułu przełożonego (`tytul`) — patrz „Decyzja o polu `jezyk_alt`"

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

### Decyzja o polu `jezyk_alt`

Model publikacji (`src/bpp/models/abstract/publication_base.py:46-66`) ma
trzy pola językowe:

| pole | znaczenie | użycie tutaj |
|---|---|---|
| `jezyk` | Język (wymagany) | **język `tytul_oryginalny`** |
| `jezyk_alt` | Język alternatywny (opcjonalny) | nie używamy — patrz niżej |
| `jezyk_orig` | Język oryginalny, dla tłumaczeń, eksport do PBN | nie używamy |

`jezyk_orig` jest udokumentowany jako pole dla tłumaczeń eksportowane do
PBN i nie opisuje języka żadnego z dwóch wyświetlanych tytułów.

Semantyka `jezyk_alt` jest **nieustalona**. Pole nie ma `help_text`, a w
kodzie występuje wyłącznie jako pozycja w fieldsetach admina
(`src/bpp/admin/helpers/fieldsets.py:104`), w serializerach API, w eksporcie
XLSX (`src/bpp/admin/xlsx_export/resources.py:82`) i w komendzie
`ukryj_nieuzywane_jezyki` — żadne z tych miejsc nie ujawnia, co pole
oznacza. Fakt osłabiający hipotezę „to język przekładu": eksport CERIF
oznacza tytuły językami z `jezyk` i `dodatkowe_tytuly.jezyk`, a `jezyk_alt`
bierze wyłącznie do `select_related` — gdyby opisywał język tytułu
przełożonego, byłby tam użyty.

**Decyzja: w tej iteracji oznaczamy wyłącznie `tytul_oryginalny`, językiem
z `jezyk`. Tytuł przełożony (`tytul`) nie dostaje atrybutu.**

Uzasadnienie: przy **wypełnionym** `jezyk_alt` o innej semantyce
oznaczylibyśmy tytuł błędnym językiem, a błędne oznaczenie jest gorsze niż
brak (patrz „Reguła"). Bez atrybutu tytuł przełożony dziedziczy `lang="pl"`
ze strony, co dla polskiego przekładu — przypadek dominujący w polskiej
bibliografii — jest prawdą.

Koszt tej ostrożności: rekordy, w których przekład jest obcojęzyczny (tytuł
oryginalny polski, `tytul` angielski), pozostają nieoznaczone. Trafia to do
wykazu jako niezgodność częściowa, do domknięcia po ustaleniu semantyki
`jezyk_alt` z osobą znającą historię modelu.

### Reguła

Dla `tytul_oryginalny`:

- `kod_bcp47` niepusty → owiń w `<span lang="...">`
- kod pusty, brak relacji `jezyk`, lub relacja bez `kod_bcp47` → **nie
  dodawaj atrybutu wcale**

`lang=""` jest gorsze niż brak atrybutu: pusta wartość jest w HTML
traktowana jako „język nieznany" i unieważnia dziedziczenie z `<html
lang="pl">`, czyli psuje odczyt fragmentu, który bez atrybutu byłby
odczytany poprawnie po polsku. Z tego samego powodu nie zgadujemy języka,
gdy danych brak.

Znacznik obejmuje **wyłącznie** tytuł oryginalny — nigdy bloku „tytuł
oryginalny (przekład)" w całości. Wspólny `<span>` oznaczyłby jednym
językiem dwa fragmenty w różnych językach.

### Wektor 1 — szablony stron szczegółowych

Dwa żywe miejsca renderują tytuł bezpośrednio z pól modelu:

- `src/bpp/templates/browse/praca_tabela_mono.html:17-21` — treść strony
  szczegółów publikacji
- `src/bpp/templates/browse/praca.html:49` — breadcrumb

Zmiana działa natychmiast po wdrożeniu — szablon renderuje się przy każdym
żądaniu z aktualnych danych relacyjnych.

Uwaga na filtry: tytuły przechodzą przez `|safe_tytul` (mono) i
`|truncatewords_html:15|safe_tytul` (breadcrumb). Znacznik `<span>`
dokładamy **wokół** wyniku filtra, w szablonie — nie wewnątrz wartości pola.
Sanityzator tytułu (`safe_tytul_html`) nie ma z nim styczności.

Breadcrumb operuje na `Rekord` (materializacja), nie na modelu źródłowym.
`RekordBase` dziedziczy `ModelTypowany` (`src/bpp/models/cache/rekord.py:204`),
więc `jezyk` jest dostępne. `jezyk_alt` i `jezyk_orig` są tam ustawione na
sztywno na `None` (`rekord.py:262-263`) — bez znaczenia, skoro ich nie
używamy.

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

Generator to szablon Django renderowany przez
`ModelZOpisemBibliograficznym.opis_bibliograficzny()`
(`src/bpp/models/util.py:91`). Nazwę szablonu wskazuje
`SzablonDlaOpisuBibliograficznego.nazwa_szablonu`, domyślnie
`opis_bibliograficzny.html`.

**Dwa szablony do edycji**, oba są wariantami generatora opisu:

- `src/bpp/templates/opis_bibliograficzny.html:7-11` — domyślny
- `src/bpp/templates/browse/praca_tabela.html:7-10` — wariant alternatywny

Drugi bywa mylony ze stroną szczegółów, bo leży w katalogu `browse/`. Nie
jest stroną: `praca.html:54` włącza wyłącznie `praca_tabela_mono.html`, a
jedyne odwołanie do `praca_tabela.html` w repozytorium to migracja
`0295_instaluj_szablony.py:25`, która instalowała go do `dbtemplates` obok
`opis_bibliograficzny.html` — czyli jako drugi oferowany format opisu.
Wdrożenie, które ustawiło na niego `nazwa_szablonu`, renderuje przez niego
opisy; edytujemy go, żeby takie wdrożenia też dostały znaczniki.

Ten plik przechodzi więc ścieżką wektora 2 (post-processing stringowy +
sanityzator + cache), nie wektora 1.

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
wąską listę i straci znaczniki — zachowanie akceptowalne (override jest
świadomą decyzją administratora), ale wymaga wpisu w wykazie.

Post-processing stringowy w `opis_bibliograficzny()` (`util.py:106-121` —
kolaps spacji i normalizacja interpunkcji: `" , "`, `" . "`, `". . "`,
`". , "`, `" ."`, `".</b>["`) nie zawiera wzorca mogącego rozciąć
`<span lang="…">`. Znacznik przechodzi bez uszczerbku.

## Rollout wektora 2

`opis_bibliograficzny_cache` to **dane**, nie kod: w bazie leżą gotowe
stringi HTML wygenerowane wcześniejszą wersją generatora. Deploy podmienia
szablon, ale nie dotyka zapisanych wierszy.

Regeneracja dzieje się sama, w istniejącym cyklu nocnym — bez ręcznej
interwencji i bez okna serwisowego ponad to, które już istnieje:

1. **22:00** — Ofelia (`bpp-deploy/docker-compose.application.yml:117-118`)
   uruchamia `python src/manage.py denorm_rebuild --no-flush`. `rebuildall()`
   oznacza wszystkie wiersze jako brudne, bez synchronicznego przeliczania.
2. **w nocy** — kontener `denorm-queue`
   (`bpp-deploy/docker-compose.workers.yml:69`) przekazuje PostgreSQL
   LISTEN/NOTIFY do kolejki celery `denorm`; zadanie przelicza rekord i
   zapisuje nowy `opis_bibliograficzny_cache` w tabeli źródłowej.
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

**Zastrzeżenie:** powyższe zweryfikowano dla stacka `bpp-deploy`.
Harmonogram żyje w labelach Ofelii, nie w `CELERY_BEAT_SCHEDULE`, więc
wdrożenie prowadzone inaczej może go nie mieć — tam cache nie odświeży się
samo i wymaga jednorazowego `manage.py denorm_rebuild`.

**Szablon jest na dysku, nie w bazie.** Migracja `0295_instaluj_szablony.py`
kiedyś kopiowała szablony opisu do `dbtemplates`, ale
`0473_szablon_nazwa_szablonu.py` to odwróciła: usunęła FK
`SzablonDlaOpisuBibliograficznego.template`, wprowadziła zwykłe
`nazwa_szablonu` z domyślnym `"opis_bibliograficzny.html"`, a
`purge_opis_dbtemplate` skasowała wiersze dbtemplate dla wszystkich
używanych nazw. Zmiana pliku w repozytorium dociera więc do każdego
wdrożenia zwykłym deployem — bez migracji danych i bez ryzyka skasowania
customizacji uczelni.

## Wpływ na konsumentów opisu

`opis_bibliograficzny_cache` nie służy wyłącznie do publicznego HTML-a.
Poniżej pełna lista konsumentów z oceną wpływu `<span lang>` wstawionego
przed tytułem.

**Neutralizują znacznik (usuwają HTML) — bez wpływu:**

| konsument | plik | mechanizm |
|---|---|---|
| eksport multiseek XLSX/DOCX | `src/bpp/views/multiseek_export.py:113,149` | konwersja HTML → czysty tekst |
| raporty DOCX | `src/nowe_raporty/docx_export.py:15-35` | nh3 z własną allowlistą bez `span` |
| DjangoQL | `src/bpp/djangoql_schema.py:105-108` | `strip_tags` |
| indeks pełnotekstowy | `src/bpp/management/commands/rebuild_search_index.py:84`, `0428_weighted_publication_fulltext.sql` | SQL-owy `strip_tags` |

**Przekazują HTML dalej — znacznik trafia do odbiorcy:**

| konsument | plik | ocena |
|---|---|---|
| REST API `/api/v1/` | `src/api_v1/serializers/szukaj.py:28` | string HTML; już zawiera `<i>`/`<sub>` |
| widget publikacji | `src/api_v1/viewsets/recent_publications_common.py:135` | jw. |
| modal globalnego wyszukiwania | `src/bpp/views/autocomplete/navigation.py:111` | etykieta renderowana jako HTML — znacznik **pomaga** 3.1.2 |
| eksport XLSX oświadczeń | `src/oswiadczenia/views.py:446` | surowy HTML w komórce arkusza (stan zastany, nie pogarszamy) |
| szablony przeglądania i admina | `bpp/zapytanie.html`, `deduplikator_autorow`, `rozbieznosci`, `przemapuj_zrodla_pbn/views.py:492` | renderowane `|safe` |

**Wyszukiwanie po podłańcuchu w surowym HTML — wymaga testu:**

| miejsce | plik | uwaga |
|---|---|---|
| filtr kolejki PBN (lista) | `src/pbn_export_queue/views/list_views.py:76-83` | gałąź `elif` — działa **tylko gdy rekord nie ma `tytul_oryginalny`** |
| filtr kolejki PBN (akcje) | `src/pbn_export_queue/views/action_views.py:383-386` | ten sam wzorzec |
| pomocnik tytułu | `src/pbn_export_queue/views/utils.py:188-200` | fallback na opis |
| **rekordy powiązane (publiczne)** | `src/bpp/templates/browse/praca_tabela_mono.html:676,914` | `data-records` z `\|safe\|escapejs`; JS szuka po surowym HTML i podświetla przez `replace` |

Ostatnia pozycja jest najistotniejsza, bo leży w **zakresie audytu** — to
wyszukiwarka na publicznej stronie szczegółów, a nie narzędzie
administracyjne. Znacznik wstawiony przed tytułem może rozciąć frazę
szukaną przez użytkownika i zaburzyć podświetlanie.

Blob już dziś zawiera znaczniki, więc klasa problemu nie jest nowa — ale
wstawiamy je w nowym miejscu, więc każda z czterech pozycji dostaje test.

## Testy

Konwencja pytest (funkcje, `@pytest.mark.django_db`, `baker.make`).

**3.1.2, wektor 1 — `praca_tabela_mono.html`:**
- `jezyk.kod_bcp47="en"` → w wyjściu `lang="en"` obejmujący tytuł oryginalny
- `kod_bcp47=""` → w wyjściu **nie ma** `lang=` przy tytule
- rekord z wypełnionym `tytul` (przekład) → znacznik obejmuje wyłącznie
  tytuł oryginalny, przekład zostaje poza nim

**3.1.2, wektor 1 — `praca.html` (breadcrumb):**
- dwa pierwsze przypadki jak wyżej. Breadcrumb renderuje wyłącznie
  `tytul_oryginalny`, więc przypadek z przekładem go nie dotyczy.

**3.1.2, wektor 2** — na `opis_bibliograficzny()`, dla obu szablonów
(`opis_bibliograficzny.html` i `browse/praca_tabela.html`, przełączane
przez `SzablonDlaOpisuBibliograficznego.nazwa_szablonu`):
- te same przypadki na wygenerowanym opisie
- **znacznik przeżywa sanityzację** — asercja wprost na wyniku
  `opis_bibliograficzny()`, nie na renderze samego szablonu; to test
  broniący allowlisty przed cofnięciem
- post-processing nie uszkadza znacznika (opis z tytułem sąsiadującym z
  interpunkcją normalizowaną w `util.py:106-121`)

**Sanityzator** — regresja bezpieczeństwa na `safe_opis_bibliograficzny_html`:
- `<script>alert(1)</script>` nadal usuwany razem z treścią
- `<span onerror="...">` → atrybut zdarzenia usunięty, `span` zostaje
- `<span style="...">`, `<span class="...">` → atrybuty usunięte
- `<span lang="en">` → przechodzi w całości

**Wyszukiwanie po podłańcuchu** — po jednym teście na każdą z czterech
pozycji z tabeli:
- `list_views.py` i `action_views.py`: rekord **bez** `tytul_oryginalny`
  (inaczej test nie trafi w gałąź `elif`), fraza z opisu niesąsiadująca ze
  znacznikiem → rekord nadal znajdowany
- `utils.py`: fallback zwraca opis ze znacznikiem
- rekordy powiązane: test szablonowy sprawdzający, że `data-records`
  zawiera znacznik, plus test JS (vitest) na wyszukiwanie i podświetlanie
  w tekście ze znacznikiem

Przypadek frazy przeciętej znacznikiem odnotowujemy asercją zgodną z
zastanym zachowaniem — dokumentuje stan, nie udaje naprawy.

**1.1.1** — asercja, że `504.html` renderuje `<img` z `alt=""`.

Weryfikacja braku regresji: `make tests-without-playwright` oraz `make
js-tests` lokalnie przed PR-em.

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
interfejsu preferencji dla użytkownika anonimowego).

**2.5.7 Dragging Movements (AA) — graf powiązań.**
`src/powiazania_autorow/templates/powiazania_autorow/graf.html`, widok
publiczny bramkowany per uczelnia (`czy_pokazywac_siec_powiazan`,
`src/bpp/views/browse.py:245`). Nawigacja wyłącznie przez przeciąganie.
Stan: **niezgodne, świadomie odroczone**. Powód: koszt nieproporcjonalny do
pozostałych napraw w tej iteracji, a funkcja jest opcjonalna i w części
wdrożeń wyłączona.

**3.1.2 — tytuł przełożony (`tytul`).**
Stan: **spełnione częściowo**. Oznaczamy tytuł oryginalny; przekład zostaje
bez atrybutu i dziedziczy `lang="pl"`. Dla rekordów, w których przekład jest
obcojęzyczny, kryterium pozostaje niespełnione. Powód: semantyka pola
`jezyk_alt` jest nieustalona, a błędne oznaczenie byłoby gorsze niż brak. Do
domknięcia po potwierdzeniu, co pole oznacza.

**3.1.2 — instalacje z niewypełnionym `kod_bcp47`.**
Stan: **spełnione warunkowo**. Pole jest `blank=True`; poprawka oznacza
tytuł tylko tam, gdzie słownik języków ma wypełniony kod BCP 47.
Uzupełnienie słownika jest zadaniem uczelni. Dodatkowo: `@depend_on_related`
przy `opis_bibliograficzny_cache`
(`src/bpp/models/wydawnictwo_ciagle.py:218-226`) **nie obejmuje**
`bpp.Jezyk`, więc uzupełnienie kodu w słowniku nie zabrudzi cache'ów —
opisy złapią nowy kod dopiero po najbliższym nocnym rebuildzie (do 24 h).

**3.1.2 — instalacje z własnym szablonem opisu.**
Stan: **spełnione warunkowo**. Edytujemy dwa szablony z repozytorium; jeśli
`SzablonDlaOpisuBibliograficznego.nazwa_szablonu` wskazuje na inny plik,
opisy nie dostaną znaczników mimo poprawnej allowlisty.

**3.1.2 — instalacje z własnym `OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`.**
Stan: **spełnione warunkowo**. Override w settings zastępuje domyślną
allowlistę; wdrożenie, które go ustawiło przed tą zmianą, straci znaczniki
w opisie do czasu dopisania `span`/`lang`.

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
