# Przełączniki konfiguracyjne REST API `/api/v1/`

Data: 2026-08-05
Stan wyjściowy: `dev` @ `2bf58407d`
Gałąź: `feat/api-v1-przelaczniki`
(worktree: `~/Programowanie/bpp-api-v1-przelaczniki`)
Poprzednia specyfikacja dotykająca tematu:
`docs/superpowers/specs/2026-08-03-cerif-export-design.md` (wprowadziła
`Uczelnia.api_v1_wlaczone`)

## Cel

Dać administratorowi instalacji BPP realną konfigurację REST API zamiast
jednego przełącznika „wszystko albo nic", **nie zmuszając nikogo do
używania czegokolwiek**. Domyślnie po wdrożeniu tej zmiany nic się nie
zmienia: każda funkcja, która działała, działa dalej.

Zasada nadrzędna: **wszystkie nowe pola mają default oznaczający „jak
dotychczas"**. Jedyne pole domyślnie wyłączone (`api_v1_tylko_zalogowani`)
jest wyłączone właśnie dlatego, że jego włączenie zmieniłoby zachowanie.

## Zakres

W zakresie:

- pięć nowych pól `BooleanField` na `Uczelnia` (ograniczenie dostępu do
  zalogowanych + cztery grupy endpointów);
- rozbudowa bramki `api_v1/permissions.py` o grupy, ograniczenie do
  zalogowanych i czytelne komunikaty;
- filtrowanie listingu `/api/v1/` (root) do grup faktycznie włączonych;
- przeniesienie i przemianowanie fieldsetu „REST API" w adminie `Uczelnia`;
- uwarunkowanie linków do API w stopce wyników multiseek;
- ciche zachowanie widgetu `embed/bpp-publikacje.js` przy 404 **wynikającym
  z decyzji administratora** (odpowiedź z kluczem `powod`); pozostałe 404
  nadal pokazują ramkę błędu;
- nagłówki CORS na odpowiedziach **błędów** endpointów kafelkowych — bez
  nich widget cross-origin w ogóle nie zobaczy treści odpowiedzi;
- testy, migracja, odświeżenie baseline, dokumentacja administratora,
  newsfragment.

Poza zakresem (świadomie):

- zmiany w throttlingu (`api_v1/throttling.py`) — to osobne narzędzie,
  rozwiązujące problem obciążenia, nie ekspozycji danych;
- przełączniki dla `/oai/` i `/cerif-oai/` — już istnieją
  (`oai_pmh_aktywny`, `eksport_cerif_wlaczony`);
- jakakolwiek zmiana zakresu danych zwracanych przez endpointy
  (`ukryte_statusy("api")`, `nie_eksportuj_przez_api` zostają nietknięte);
- wersjonowanie API, `/api/v2/`.

## Model danych

### Enum grup

W `src/bpp/models/uczelnia.py` (zależność aplikacji idzie w stronę
`api_v1` → `bpp`, więc enum nie może mieszkać w `api_v1`):

```python
class GrupaApiV1(models.TextChoices):
    DANE_BIBLIOGRAFICZNE = "dane_bibliograficzne", "dane bibliograficzne"
    WYSZUKIWANIE = "wyszukiwanie", "wyszukiwanie"
    KAFELKI = "kafelki", "kafelki do osadzania"
    NARZEDZIA_REDAKTORSKIE = "narzedzia_redaktorskie", "narzędzia redaktorskie"
```

Wartość enuma jest **jednocześnie sufiksem nazwy pola** na `Uczelnia`.
Kontrakt egzekwuje metoda i test (patrz niżej):

```python
def api_v1_grupa_wlaczona(self, grupa: GrupaApiV1) -> bool:
    return getattr(self, f"api_v1_{grupa.value}")
```

### Pola na `Uczelnia`

| Pole | Etykieta | Default | Nowe? |
|---|---|---|---|
| `api_v1_wlaczone` | Włącz REST API (/api/v1/) | `True` | nie |
| `api_v1_tylko_zalogowani` | REST API tylko dla zalogowanych | `False` | tak |
| `api_v1_dane_bibliograficzne` | Udostępniaj dane bibliograficzne | `True` | tak |
| `api_v1_wyszukiwanie` | Udostępniaj wyszukiwanie | `True` | tak |
| `api_v1_kafelki` | Udostępniaj kafelki do osadzania | `True` | tak |
| `api_v1_narzedzia_redaktorskie` | Udostępniaj narzędzia redaktorskie | `True` | tak |

`help_text` pola `api_v1_wlaczone` wymaga aktualizacji — musi powiedzieć
wprost, że **nie dotyczy kafelków**, bo to jedyne złamanie hierarchii
(patrz „Semantyka").

Rozważone i odrzucone sposoby przechowywania:

- **`ArrayField`/JSON z listą włączonych grup** — jedno pole zamiast pięciu,
  ale admin wymagałby ręcznego `MultipleChoiceField`, a kod zamiast
  `uczelnia.api_v1_kafelki` robiłby testy przynależności do listy;
- **osobny model z `OneToOne`** — sensowny przy 20+ przełącznikach; przy
  sześciu to zbędna tabela i join.

Płaskie `BooleanField`-y są idiomem całego modelu `Uczelnia` (kilkadziesiąt
pól `pokazuj_*`), dają checkboxy w adminie za darmo i trywialną migrację.

## Przypisanie endpointów do grup

| Grupa | Prefiksy w routerze |
|---|---|
| `DANE_BIBLIOGRAFICZNE` | `konferencja`, `seria_wydawnicza`, `czas_udostepnienia_openaccess`, `nagroda`, `charakter_formalny`, `typ_kbn`, `jezyk`, `dyscyplina_naukowa`, `poziom_wydawcy`, `wydawca`, `wydawnictwo_zwarte`, `wydawnictwo_zwarte_autor`, `wydawnictwo_zwarte_streszczenie`, `patent`, `patent_autor`, `wydawnictwo_ciagle`, `wydawnictwo_ciagle_autor`, `wydawnictwo_ciagle_zewnetrzna_baza_danych`, `wydawnictwo_ciagle_streszczenie`, `praca_doktorska`, `praca_habilitacyjna`, `rodzaj_zrodla`, `zrodlo`, `jednostka`, `uczelnia`, `autor`, `funkcja_autora`, `tytul`, `autor_jednostka` |
| `WYSZUKIWANIE` | `szukaj` |
| `KAFELKI` | `recent_author_publications`, `recent_unit_publications` |
| `NARZEDZIA_REDAKTORSKIE` | `zapytanie/rekord`, `zapytanie/autor`, `zapytanie/autorzy`, `raport_slotow_uczelnia`, `raport_slotow_uczelnia_wiersz` |

Poza grupami:

- **root `/api/v1/`** (`CustomAPIRootView`) — `grupa=None`;
- **`whoami/`** (tożsamość klienta OAuth/MCP) — `grupa=None`.

Oba podlegają wyłącznie głównemu wyłącznikowi i ograniczeniu do
zalogowanych.

## Semantyka

Kolejność rozstrzygania w bramce:

1. **Uczelnia nierozstrzygnięta** (`get_for_request` → `None`: pusta baza,
   kreator konfiguracji, brak mapowania Site→Uczelnia) → **przepuszczamy**.
   Zachowanie odziedziczone po obecnej bramce; fail-closed zabiłby świeżą
   instalację.
2. **Grupa `KAFELKI`** → rozstrzyga wyłącznie `api_v1_kafelki`.
   Nie zależy od `api_v1_wlaczone` ani od `api_v1_tylko_zalogowani`.
3. **`api_v1_wlaczone == False`** → 404 z komunikatem głównym.
4. **Grupa wyłączona** → 404 z komunikatem o grupie.
5. **`api_v1_tylko_zalogowani == True` i użytkownik anonimowy** → 401.

Krok 2 jest **świadomym złamaniem hierarchii**: widget
`embed/bpp-publikacje.js` wisi na publicznych stronach WWW jednostek,
których administrator BPP nie kontroluje. Wyłączenie API nie może po cichu
psuć cudzych stron; kto chce zamknąć również kafelki, odznacza ich własne
pole. W kodzie jest to pierwszy test **przełączników** (zaraz po
rozstrzygnięciu tenanta) i kończy się wcześnie właśnie po to, by wyjątek
był widoczny w jednym miejscu, a nie rozproszony po warunkach.

Kolejność kroków 4 → 5 jest celowa. Skutek uboczny: przy
`api_v1_tylko_zalogowani == True` anonim odróżni grupę wyłączoną (404) od
włączonej (401), czyli pozna konfigurację grup. Przyjmujemy to świadomie —
stan grup nie jest tajemnicą, a odwrotna kolejność byłaby myląca: anonim
dostawałby „zaloguj się" pod adresem, który po zalogowaniu i tak zwraca
404, bo grupa jest wyłączona dla wszystkich. 404 jest prawdziwe dla
każdego, 401 tylko dla niezalogowanych.

### Kody odpowiedzi i komunikaty

| Sytuacja | Wyjątek | Kod | `detail` |
|---|---|---|---|
| Główny wyłącznik odznaczony | `NotFound` | 404 | „REST API tego serwisu zostało wyłączone przez administratora." |
| Grupa odznaczona | `NotFound` | 404 | „Ta część REST API została wyłączona przez administratora tego serwisu." |
| Tylko zalogowani + anonim | `NotAuthenticated` | 401 | „REST API tego serwisu jest dostępne wyłącznie dla zalogowanych użytkowników." |

Rozróżnienie 404 / 401 jest celowe. 404 znaczy „tego tu nie ma"; 401 —
„to istnieje, ale się uwierzytelnij". Przy ograniczeniu do zalogowanych
404 wprowadzałby w błąd, bo po zalogowaniu zasób jednak jest.

**Dlaczego `NotAuthenticated`, a nie `PermissionDenied`.** Gdyby bramka
rzucała `PermissionDenied`, wynikiem byłoby zawsze 403 — bo rzucając
wyjątek wprost, omijamy `APIView.permission_denied()`, które normalnie
zamienia odmowę na `NotAuthenticated` dla klientów bez uwierzytelnienia.
Zepsułoby to kontrakt `whoami/`, który wg swojego docstringu (spec bpp-mcp
§5.4d) ma na brak tokenu odpowiadać **401**, mapowalnym przez klienta MCP
na ponowne logowanie; 403 nie wywołałoby re-auth.

`NotAuthenticated` oddaje tę decyzję DRF-owi: `handle_exception` dokłada
nagłówek `WWW-Authenticate`, jeśli pierwszy authenticator go dostarcza,
a w przeciwnym razie sam degraduje odpowiedź do 403. W tej instalacji
pierwszy w `DEFAULT_AUTHENTICATION_CLASSES` jest
`oauth_mcp.authentication.StrictOAuth2Authentication`, który zwraca
challenge `Bearer`, więc **efektywnym kodem jest 401 na całym `/api/v1/`** —
spójnie z tym, co ten stack już robi dla `IsAuthenticated`. Żadnego
specjalnego traktowania `whoami/` nie potrzeba.

**Root `/api/v1/` i `whoami/`** (obie z `grupa=None`) zachowują się
jednakowo i niezależnie od stanu czterech grup:
`api_v1_wlaczone == False` → 404; `api_v1_tylko_zalogowani == True`
i anonim → 401. Root przy włączonym API, ale wszystkich czterech grupach
odznaczonych, zwraca 200 z samą sekcją `info` — pustą listą zasobów.

Komunikaty przekazujemy **w słowniku** `{"detail": …, "powod": …}` jako
argument `NotFound(...)` / `NotAuthenticated(...)` — patrz sekcja niżej.
Nigdy jako goły string, bo wtedy `powod` przepada. DRF negocjuje typ
treści: `curl` dostanie JSON, przeglądarka — stronę błędu browsable API.
Nie potrzeba własnego widoku ani szablonu. `return False` dałby generyczny
komunikat bez możliwości wyjaśnienia przyczyny.

### Pole `powod` — odróżnialność maszynowa

Sam `detail` nie wystarczy: klient (widget do osadzania) musi odróżnić
„administrator to wyłączył" od „nie ma takiego autora", a oba są 404.
Porównywanie tekstu komunikatu byłoby kruche.

`exception_handler` DRF renderuje `exc.detail` **bezpośrednio**, gdy jest
listą albo słownikiem, a opakowuje w `{"detail": …}` dopiero gdy nie jest.
Wystarczy więc podać słownik — bez własnego handlera i bez nagłówków:

```python
raise NotFound({"detail": KOMUNIKAT_GRUPA,
                "powod": "grupa_wylaczona",
                "grupa": grupa.value})
```

| Sytuacja | Kod | `powod` | Dodatkowo |
|---|---|---|---|
| Główny wyłącznik odznaczony | 404 | `api_wylaczone` | — |
| Grupa odznaczona | 404 | `grupa_wylaczona` | `grupa`: wartość enuma |
| Tylko zalogowani + anonim | 401 | `wymagane_zalogowanie` | — |

**Kontrakt dla klientów: obecność klucza `powod` znaczy „to decyzja
konfiguracyjna administratora, nie błąd".** Odpowiedzi 404 spoza bramki
(`pobierz_encje_lub_404` — nieistniejąca lub ukryta encja) tego klucza nie
mają i nie będą miały. Dzięki temu widget rozstrzyga jednym testem
obecności klucza, nie listą znanych wartości — dołożenie w przyszłości
czwartego powodu niczego nie popsuje.

## Implementacja bramki

`src/api_v1/permissions.py`:

```python
class BramkaApiV1(BasePermission):
    def __init__(self, grupa: GrupaApiV1 | None = None):
        self.grupa = grupa

    def has_permission(self, request, view):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is None:
            return True

        if self.grupa is GrupaApiV1.KAFELKI:
            if not uczelnia.api_v1_kafelki:
                raise self._grupa_wylaczona()
            return True

        if not uczelnia.api_v1_wlaczone:
            raise NotFound({"detail": KOMUNIKAT_GLOWNY,
                            "powod": "api_wylaczone"})
        if self.grupa and not uczelnia.api_v1_grupa_wlaczona(self.grupa):
            raise self._grupa_wylaczona()
        if uczelnia.api_v1_tylko_zalogowani and not request.user.is_authenticated:
            raise NotAuthenticated({"detail": KOMUNIKAT_ZALOGOWANI,
                                    "powod": "wymagane_zalogowanie"})
        return True

    def _grupa_wylaczona(self) -> NotFound:
        return NotFound({"detail": KOMUNIKAT_GRUPA,
                         "powod": "grupa_wylaczona",
                         "grupa": self.grupa.value})
```

Bramka wchodzi przez `get_permissions()` (zwraca **instancje**), a nie przez
`permission_classes` (DRF instancjonowałby klasę bezargumentowo, więc nie
dałoby się przekazać grupy). `BramkaApiV1Mixin` przechowuje grupę
w atrybucie klasy `bramka_api_v1_grupa` — nazwa z prefiksem, bo mixin
owija także klasy z innych aplikacji (`WhoAmIView` z `oauth_mcp`) i gołe
`grupa` mogłoby się z czymś zderzyć.

`z_bramka_api_v1(view_cls, grupa)` przyjmuje `grupa` jako argument
**wymagany**, tak samo jak `register()`. Inaczej furtka wraca piętro niżej:
root i `whoami/` są owijane bezpośrednio, z pominięciem routera, więc
domyślne `None` na tym poziomie przepuściłoby po cichu każdy przyszły widok
owinięty ręcznie. Root i `whoami/` przekazują `grupa=None` **jawnie**.

### Router

`grupa` jest **wymaganym** argumentem `CustomRouter.register()`:

```python
router.register(r"szukaj", SzukajViewSet, basename="szukaj",
                grupa=GrupaApiV1.WYSZUKIWANIE)
```

Bez wartości domyślnej. Rejestracja nowego viewsetu bez wskazania grupy
kończy się `TypeError` przy imporcie `urls.py`, czyli przy starcie
aplikacji. Wartość domyślna po cichu odtwarzałaby furtkę, przed którą
ostrzega istniejący docstring `CustomRouter` („pozostawienie furtki przy
każdym nowym viewsecie").

Router zapamiętuje mapę `prefiks → grupa` i udostępnia ją widokowi root.

### Root `/api/v1/`

`CustomAPIRootView.get()` już przebudowuje `response.data` na kategorie.
Przed kategoryzacją dochodzi filtr: endpointy należące do wyłączonych grup
znikają z listingu. Mapa `prefiks → grupa` trafia do widoku przez
`initkwargs` w `CustomRouter.get_api_root_view()`; klasa deklaruje atrybut
o wartości domyślnej `{}`, bo `View.as_view()` przyjmuje wyłącznie
`initkwargs` odpowiadające istniejącym atrybutom.

**Konsekwencja przyjęta świadomie:** przy `api_v1_wlaczone == False` root
zwraca 404, a kafelki odpowiadają dalej. Widget woła je bezpośrednio, nie
przez listing, więc działa — po prostu nie da się ich odkryć, przeglądając
API.

## CORS na odpowiedziach błędów — warunek konieczny

Bez tego punktu cały mechanizm `powod` jest martwy dokładnie tam, gdzie
ma działać.

Dziś nagłówki CORS ustawia wyłącznie `_ustaw_cors()` w
`odpowiedz_z_publikacjami` (`viewsets/recent_publications_common.py:103`),
czyli **tylko na odpowiedzi sukcesu**. W projekcie nie ma
`django-cors-headers` ani żadnego middleware CORS. Tymczasem:

- bramka rzuca wyjątek w `has_permission`, czyli w `initial()`, **przed**
  wejściem do metody widoku — odpowiedź buduje `exception_handler` DRF,
  bez `_ustaw_cors()`;
- `pobierz_encje_lub_404` rzuca `Http404` — tak samo.

Widget siedzi na cudzej domenie, więc `fetch` idzie w trybie `cors`. Brak
`Access-Control-Allow-Origin` na odpowiedzi błędu oznacza, że
**przeglądarka nie poda jej skryptowi w ogóle**: promise odrzuca się
`TypeError`-em, bez statusu i bez treści. Widget wpada w `.catch` i nie ma
jak odróżnić 404 od 500, a tym bardziej odczytać `powod`.

To jest zarazem **istniejący błąd**, nie tylko przeszkoda dla nowej
funkcji: dziś literówka w `data-autor` na cross-originowym osadzeniu daje
w konsoli mglisty błąd sieciowy zamiast czytelnego 404.

**Rozwiązanie:** wspólny mixin dla `RecentAuthorPublicationsViewSet`
i `RecentUnitPublicationsViewSet`, nadpisujący `finalize_response()`
i wołający tam `_ustaw_cors()`. `finalize_response` wykonuje się w
`APIView.dispatch()` **zawsze** — także dla odpowiedzi zbudowanej przez
`handle_exception()` — więc jedno miejsce pokrywa sukces i wszystkie
błędy. Wywołanie `_ustaw_cors()` z `odpowiedz_z_publikacjami` znika,
żeby polityka CORS została w jednym miejscu.

Zakres celowo wąski: nagłówki dostają **tylko endpointy kafelkowe**,
bo tylko one są projektowane do wołania cross-origin. Reszta `/api/v1/`
zostaje bez CORS, tak jak dziś.

**Testu JS to nie złapie** — stub `fetch` w vitest omija politykę
pochodzenia. Dlatego potrzebny jest test pytest asertujący
`Access-Control-Allow-Origin` na odpowiedziach błędu (patrz „Testy").

## Admin

`src/bpp/admin/uczelnia.py`: fieldset „REST API" przenosi się sprzed
„Deklaracji dostępności" na miejsce **przed** „OAI-PMH dla Primo (/oai/)"
i zmienia nazwę na `REST API (/api/v1/)`. Powstaje spójny blok interfejsów
wyjściowych:

```
PBN API
REST API (/api/v1/)
OAI-PMH dla Primo (/oai/)
Eksport CERIF / OpenAIRE (/cerif-oai/)
```

Kolejność pól: `api_v1_wlaczone`, `api_v1_tylko_zalogowani`, następnie
cztery grupy w kolejności deklaracji enuma — `api_v1_dane_bibliograficzne`,
`api_v1_wyszukiwanie`, `api_v1_kafelki`, `api_v1_narzedzia_redaktorskie`.
Fieldset pozostaje zwinięty (`grp-collapse grp-closed`).

## Frontend

### Stopka wyników multiseek

`src/django_bpp/templates/multiseek/common-results.html`, linie 22–23 —
akapit widoczny przy wyniku > 25 000 rekordów, dziś linkujący bezwarunkowo
do `/api/v1/` i `/bpp/oai/?verb=ListSets`.

Po zmianie akapit wymienia wyłącznie interfejsy, którymi **da się pobrać
rekordy**, a gdy nie ma żadnego — nie pojawia się wcale. Warunki:

- link JSON-REST: `uczelnia.api_v1_wlaczone and uczelnia.api_v1_dane_bibliograficzne`
  — sam `api_v1_wlaczone` nie wystarczy, bo przy odznaczonych danych
  bibliograficznych root wprawdzie odpowiada, ale rekordów za nim nie ma,
  a akapit obiecuje właśnie rekordy;
- link OAI-PMH: `uczelnia.oai_pmh_aktywny`.

Komentarze Django w tym pliku muszą być jednoliniowe (`{# ... #}` z
otwarciem i zamknięciem w tej samej linii) — reguła projektu.

### Widget do osadzania

`src/bpp/static/embed/bpp-publikacje.js`: dziś **każdy** błąd, w tym 404,
kończy się `renderBlad()` — ramką z komunikatem o błędzie na cudzej stronie
WWW. To jest złe w jedną stronę. Wyciszenie każdego 404 byłoby złe
w drugą, bo `RecentAuthorPublicationsViewSet` i
`RecentUnitPublicationsViewSet` wołają `pobierz_encje_lub_404`
(`viewsets/recent_publications_common.py`), więc 404 zwraca również
literówka w `data-autor`/`data-jednostka`, autor z `pokazuj=False` i encja
skasowana — czyli zwykłe pomyłki, o których ktoś musi się dowiedzieć.

Rozstrzyga **obecność klucza `powod`** w treści odpowiedzi:

| Odpowiedź | Na stronie | W kontenerze | W konsoli |
|---|---|---|---|
| 404 **z** `powod` (decyzja administratora) | nic | komentarz HTML z `detail` | `console.warn` z URL-em i `powod` |
| 404 **bez** `powod` (encja nieosiągalna) | dotychczasowa ramka błędu | — | `console.warn` z URL-em |
| 404 z treścią nie-JSON (proxy, strona błędu) | dotychczasowa ramka błędu | — | `console.warn` z URL-em |
| Inny błąd (500, sieć) | dotychczasowa ramka błędu | — | `console.warn` z URL-em |

Dziś widget w ogóle nie czyta treści błędnej odpowiedzi
(`if (!resp.ok) throw new Error("HTTP " + resp.status)`), więc przy 404
dochodzi krok `resp.json()`. Musi być odporny: **każde niepowodzenie
parsowania degraduje do wiersza „bez `powod`"**, czyli do ramki błędu.
Cisza jest zarezerwowana dla przypadku, w którym serwer wprost
powiedział, że to decyzja administratora.

Komentarz HTML wstrzykiwany do kontenera:

```html
<div id="bpp-publikacje-…">
  <!-- BPP: kafelki do osadzania zostały wyłączone przez administratora serwisu -->
</div>
```

Niewidoczny dla czytelnika strony, widoczny w „pokaż źródło" — czyli
osoba, która wkleiła widget, dowie się, dlaczego nic nie ma, bez
otwierania DevToolsów. Treść bierzemy z `detail` i wstawiamy przez
`document.createComment`, które nie interpretuje HTML-a; jedynym realnym
wektorem jest sekwencja zamykająca, więc zwijamy `--`. Istniejąca funkcja
`sanitize` **nie** ma tu zastosowania — czyści HTML w kontekście
elementu, a to inny kontekst.

Podział ról jest tu celowy: strona ma wyglądać normalnie po świadomej
decyzji administratora, ale nie ma ukrywać cudzej literówki.

`bpp-publikacje.js` jest **celowo poza bundlem** (adnotacja w nagłówku
pliku; `Gruntfile.js` go nie referencjuje). Nie wymaga więc
`grunt build` — trafia do produkcji przez `collectstatic` przy budowie
obrazu, a lokalnie `runserver` serwuje go wprost.

## Testy

Nowy plik `src/api_v1/tests/test_przelaczniki.py`.

| Test | Uzasadnienie |
|---|---|
| Defaulty pięciu nowych pól (`tylko_zalogowani=False`, reszta `True`) | „realnie wszystko ma działać" jako wykonywalny warunek |
| Każda grupa osobno: wyłączenie gasi swoje endpointy i **nie rusza cudzych** | regresja w mapowaniu prefiks→grupa inaczej przejdzie niezauważona |
| Kafelki odpowiadają przy `api_v1_wlaczone=False` | jedyne złamanie hierarchii — przybite testem, nie komentarzem |
| Kafelki odpowiadają anonimowi przy `tylko_zalogowani=True` | j.w. |
| `tylko_zalogowani`: 401 dla anonima, 200 dla zalogowanego | rozróżnienie 401/404 |
| `tylko_zalogowani`: anonim dostaje 401 (nie 403) i nagłówek `WWW-Authenticate` | kontrakt `whoami/` dla bpp-mcp; `PermissionDenied` dałoby 403 i zabiło re-auth |
| `Access-Control-Allow-Origin` na 404 z bramki **i** na 404 z `pobierz_encje_lub_404` | test JS tego nie złapie (stub `fetch` omija politykę pochodzenia); bez nagłówka widget nie przeczyta `powod` |
| Treść `detail` w każdym z trzech komunikatów | wymaganie jawne; bez testu pierwszy refaktor `NotFound(KOMUNIKAT)` → `NotFound()` przejdzie zielono i zabierze informację |
| `powod` w każdej z trzech odpowiedzi bramki (+ `grupa` przy `grupa_wylaczona`) | kontrakt maszynowy dla widgetu; łatwo go zgubić refaktorem, bo `detail` sam z siebie wygląda na wystarczający |
| 404 z `pobierz_encje_lub_404` (nieistniejący autor, `pokazuj=False`) **nie ma** klucza `powod` | druga połowa tego samego kontraktu — bez niej widget wyciszyłby także literówki |
| Root ukrywa endpointy wyłączonych grup | bez tego filtr w `CustomAPIRootView.get()` można usunąć bez czerwonego testu, a listing pokazywałby linki prowadzące w 404 |
| Root i `whoami/`: 404 przy wyłączonym API, 401 dla anonima przy `tylko_zalogowani`, obojętność na stan grup | jedyne dwa widoki bez grupy — łatwo je pominąć przy refaktorze bramki |
| Kontrakt enum↔pola: dla każdej `GrupaApiV1` istnieje `api_v1_<value>` na `Uczelnia` | wiązanie przez `getattr` nie ma kontroli statycznej; literówka wybuchłaby dopiero na produkcji |
| Rejestracja viewsetu bez `grupa=` podnosi `TypeError` | pilnuje, by domyślna wartość nie wróciła |

Istniejące testy `/api/v1/` z `src/cerif_export/tests/test_przelaczniki.py`
przenoszą się do nowego pliku (mieszkają w aplikacji eksportu CERIF
z przyczyn historycznych). Część CERIF-owa zostaje na miejscu.

### Test JS widgetu

Nowy `tests/js/embed-publikacje.test.js` (vitest + jsdom, tak jak
istniejące `tests/js/*.test.js`): w DOM-ie stawiamy tag
`<script src="…/embed/bpp-publikacje.js" data-autor="…">`, podmieniamy
`globalThis.fetch` na stub i sprawdzamy trzy przypadki:

1. **404 z `powod`** — kontener bez widocznej treści, w środku komentarz
   HTML zawierający `detail`;
2. **404 bez `powod`** — dotychczasowa ramka błędu, brak komentarza;
3. **404 z treścią nie-JSON** — dotychczasowa ramka błędu;
4. **500** — dotychczasowa ramka błędu.

We wszystkich czterech przypadkach asertujemy `console.warn` — tabela
w sekcji „Frontend" wymaga go bezwarunkowo.

Przypadki 2 i 3 są tu najważniejsze: pilnują, żeby wyciszenie nie rozlało
się na zwykłe pomyłki w `data-autor` ani na awarie infrastruktury.

Widget jest IIFE odpalanym przy załadowaniu i wymaga
`document.currentScript`, więc test importuje plik dopiero po
przygotowaniu DOM-u.

### Uruchamianie

Lokalnie, obowiązkowo: `uv run pytest src/api_v1/`, potem
`make tests-without-playwright`, potem `make js-tests`. Pełne `make tests`
przerywa się na pierwszym błędnym kroku — po naprawie Pythona trzeba
dokończyć pozostałe kroki, a nie uznać je za pominięte.

## Migracja i baseline

Jedna migracja `AddField` × 5. Wszystkie pola mają wartość domyślną, więc
Django wypełni istniejące wiersze bez data-migracji i bez ryzyka regresji
na wdrożeniach.

Po migracji: **`make baseline-update`** (delta), nie `make rebuild-baseline`.
Commitujemy `baseline-sql/baseline.sql` **oraz** `baseline-sql/baseline.meta.json`.

Goły `manage.py baseline_update` jest zabroniony — pomija
`fix-baseline-search-path`, przez co triggery denorm na `hstore` nie
widzą operatora przy `CREATE TRIGGER`, ładowanie baseline pod
`ON_ERROR_STOP=1` wywala się w całości, a kontener testowej bazy nie wstaje.

## Dokumentacja

- nowa strona `docs/administrator/rest-api.md`: sześć przełączników, co
  konkretnie gaśnie przy każdym, wyjątek kafelków, ostrzeżenie że
  wyłączenie grupy „Kafelki" psuje widgety wklejone na stronach WWW
  jednostek;
- wpis w `mkdocs.yml` bezpośrednio przed „Eksport CERIF / OpenAIRE"
  (strony o OAI-PMH w nawigacji nie ma, więc pełnej symetrii z adminem
  i tak się nie da uzyskać);
- aktualizacja docstringów `CustomRouter` i `permissions.py` o grupy;
- newsfragment `src/bpp/newsfragments/api-v1-przelaczniki.feature.rst`.

## Ryzyka

| Ryzyko | Ograniczenie |
|---|---|
| Administrator wyłącza grupę „Kafelki" nie wiedząc, że psuje widgety na stronach jednostek | `help_text` pola + ostrzeżenie w dokumentacji + widget milczy zamiast pokazywać błąd |
| Nowy viewset trafia do routera bez grupy | `grupa` jako wymagany kwarg → `TypeError` przy starcie + test |
| Literówka w `GrupaApiV1.value` rozjeżdża enum z nazwą pola | test kontraktu iterujący po enumie |
| Wyłączenie API zostawia martwy link w stopce multiseek | warunki w szablonie + akapit znika, gdy nie ma czynnego interfejsu |
| Brak CORS na odpowiedziach błędów czyni `powod` nieczytelnym cross-origin — czyli w jedynym scenariuszu, w jakim widget działa | `_ustaw_cors()` przeniesione do `finalize_response()` obu viewsetów kafelkowych + test pytest na nagłówek przy 404 (test JS tego nie wykryje) |
| Bramka rzucająca `PermissionDenied` zamienia 401 na 403 i zabija re-auth w bpp-mcp | `NotAuthenticated` + test asertujący 401 i `WWW-Authenticate` |
| Refaktor bramki gubi klucz `powod` — widget zaczyna wyciszać zwykłe pomyłki w `data-autor` | testy z obu stron kontraktu: `powod` jest w odpowiedziach bramki i **nie ma** go w 404 z `pobierz_encje_lub_404` |
| Zmiana bramki psuje istniejące uprawnienia viewsetów (`MoznaUzywacZapytania`, `IsGrupaRaportyWyswietlanie`) | bramka wchodzi przez `get_permissions()` przed istniejącymi, nie zastępując ich — mechanizm już działa i jest testowany |
