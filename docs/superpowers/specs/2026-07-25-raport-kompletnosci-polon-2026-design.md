# Raport kompletności danych POL-on 2026 — projekt

**Zgłoszenie:** FD#437 · **Data:** 2026-07-25 · **Status:** projekt zaakceptowany, do implementacji

## Problem

Rozporządzenie Ministra Nauki i Szkolnictwa Wyższego z dnia 16 czerwca 2026 r.
w sprawie danych przetwarzanych w Zintegrowanym Systemie Informacji o Szkolnictwie
Wyższym i Nauce POL-on (Dz. U. 2026 poz. 811, w życie od 30 czerwca 2026 r.)
określa w § 2 ust. 10 zakres danych o osiągnięciach naukowych, jakie podmiot
wprowadza do **wykazu pracowników**.

Rozpoznanie wykazało, że **BPP w zdecydowanej większości nie wymaga nowych pól** —
zakres z § 2 ust. 10 pokrywa się z tym, czego wymaga eksport do PBN, a te pola
w BPP są. Problemem nie jest brak miejsca na dane, tylko **brak widoczności,
których danych brakuje** w konkretnych rekordach.

Rozporządzenie wyznacza przy tym twarde terminy (§ 9 ust. 3):

- osiągnięcia wprowadza się **do 31 grudnia roku następującego po roku zaistnienia zmiany**,
- osiągnięcia z roku poprzedzającego rok ewaluacji — **do 15 stycznia roku ewaluacji**.

## Cel

Raport roboczy, który dla bieżącego okna ewaluacyjnego pokazuje **przy którym
pracowniku, w którym rekordzie, jakiej danej brakuje** — z odnośnikiem do
paragrafu rozporządzenia i linkiem prosto do formularza edycji.

Raport **nie** wysyła niczego do POL-on. BPP nie jest zintegrowane z POL-on;
dane trafiają tam pośrednio (PBN/SEDN, sprawozdawczość uczelni). Raport jest
narzędziem przygotowania danych, nie kanałem sprawozdawczym.

### Poza zakresem

- blokowanie zapisu rekordu z brakami (walidacja u źródła) — ewentualny krok drugi,
- eksport do pliku sprawozdawczego POL-on,
- dane spoza § 2 ust. 10 (wykaz studentów, doktorantów, instytucji, dyplomy),
- ujednolicenie rozjechanych definicji okna ewaluacyjnego — patrz „Dług techniczny",
- **osiągnięcia artystyczne (pkt 7), wzory użytkowe (pkt 2), odmiany roślin (pkt 3)** —
  BPP nie ma dla nich modelu ani charakteru formalnego. Raport nie może zgłaszać
  braków w danych, dla których nie istnieje miejsce zapisu.

### Zakres ograniczony: patenty

Model `Patent` pokrywa z § 2 ust. 10 pkt 1 tylko litery a (tytuł), c (numer
patentu), g (data i numer zgłoszenia) oraz przez relacje k (dyscyplina) i m
(współtwórcy, ORCID).

Dla liter **b, d, e, f, h, i, j, l BPP nie ma pól**: nazwa uprawnionego podmiotu,
nazwa urzędu udzielającego, państwa ochrony, data ogłoszenia w „Wiadomościach
Urzędu Patentowego", uprzednie pierwszeństwo, streszczenie opisu, data złożenia
tłumaczenia patentu europejskiego.

Raport sprawdza więc dla patentów wyłącznie wymogi możliwe do wypełnienia.
Dołożenie brakujących pól to samodzielna zmiana — zbiega się z FD#449, gdzie
klientka niezależnie zgłosiła braki w modelu patentowym.

## Decyzje projektowe

### 1. Ziarno: (autor, dyscyplina, rekord)

Raport operuje na **parach autor–osiągnięcie**, nie na samych publikacjach.
Odwzorowuje to konstrukcję rozporządzenia: § 2 ust. 10 umieszcza osiągnięcia
w wykazie pracowników, a każde osiągnięcie niesie własną „dyscyplinę, o której
mowa w art. 265 ust. 13 ustawy". Ten sam artykuł u dwóch współautorów to
w POL-onie dwa wpisy, przy dwóch osobach, potencjalnie w dwóch dyscyplinach.

**Źródłem ziarna są konkretne modele powiązań** — `Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`, `Patent_Autor` — a **nie** widok
`Cache_Punktacja_Autora_Query`.

Powód jest twardy i wynika z kodu: widok `Rekord` (`bpp_rekord_mat`,
`managed = False`) dziedziczy tylko wybrane klasy abstrakcyjne (`RekordBase`,
`src/bpp/models/cache/rekord.py:192-211`). **Nie ma wśród nich**
`ModelZOplataZaPublikacje` ani `ModelZPolamiEwaluacjiPBN`, a `strony`, `tom`
i `nr_zeszytu` są jawnie wygaszone (`= None`, linie 258–260). Przez `Rekord`
**nie da się sprawdzić** wymogów dotyczących opłat APC (pkt 4 lit. m, pkt 5
lit. n), artykułu recenzyjnego (pkt 4 lit. f), projektów NCN/FNP/NPRH/UE
(pkt 5 lit. k), edycji naukowej (pkt 5 lit. j) ani tomu, zeszytu i stron
(pkt 4 lit. j, k).

Model konkretny wystawia wszystkie te pola, a jego through-model niesie komplet
danych potrzebnych do przypisania braku do osoby: `autor`, `jednostka`,
`dyscyplina_naukowa`, `przypieta`, `upowaznienie_pbn`, `typ_odpowiedzialnosci`
(`src/bpp/models/abstract/authors.py:19-90`). Dodatkowa korzyść: dane czytane są
na żywo, nie z cache'u, który bywa nieświeży.

Konsekwencja: widok składa wynik z trzech zapytań (ciągłe, zwarte, patenty).

### 2. Rejestr reguł jako dane

Nowa aplikacja `kompletnosc_polon`, moduł `reguly.py`:

```python
class Waga(models.TextChoices):
    WYMAGANE = "W", "Wymagane"        # rozporządzenie żąda bezwarunkowo
    WARUNKOWE = "C", "Warunkowe"      # „jeżeli posiada", „jeżeli są znane"

@dataclass(frozen=True)
class Regula:
    kod: str                 # stabilny identyfikator, np. "ART_DOI"
    dotyczy: Osiagniecie     # ARTYKUL | MONOGRAFIA | ROZDZIAL | PATENT
    warunek: Q               # PRAWDZIWY, gdy danej BRAKUJE
    opis: str                # komunikat dla użytkownika
    paragraf: str            # np. "§ 2 ust. 10 pkt 4 lit. a"
    waga: Waga = Waga.WYMAGANE
```

Warunek jest obiektem `Q`, więc jedna definicja obsługuje trzy zastosowania:
policzenie braków (`annotate`), zawężenie listy (`filter`) i test jednostkowy.
Dopisanie wymogu po nowelizacji to jeden wpis, bez dotykania widoku.

Pole `paragraf` trafia do interfejsu — użytkownik widzi podstawę prawną wymogu,
a nie samo „czerwone pole". Pole `waga` odwzorowuje warunkowość rozporządzenia:
wymogi opatrzone „jeżeli posiada" / „jeżeli są znane" **nie stają się
bezwarunkowe**; raport pokazuje je osobno i nie wlicza do licznika braków
krytycznych.

### 3. Rejestr reguł — treść

**Warunki zapisane są od strony through-modelu** (`Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`, `Patent_Autor`): pola powiązania autora bez prefiksu
(`dyscyplina_naukowa`, `przypieta`, `upowaznienie_pbn`, `autor__orcid`), pola
publikacji z prefiksem `rekord__`.

Pierwsza wersja tego projektu zapisywała warunki odwrotnie — od strony modelu
konkretnego, z `a__` jako skrótem na through-model. Było to **błędne
semantycznie**: `Q(autorzy_set__upowaznienie_pbn=False)` na querysecie
`Wydawnictwo_Ciagle` znaczy „istnieje *jakiś* autor bez upoważnienia", a nie
„*ten* autor go nie ma", a przy `annotate()` zwielokrotniałoby wiersze przez
JOIN. Ziarno raportu to jedna para (autor, rekord) — czyli dokładnie jeden
wiersz through-modelu. W tabelach niżej `a__` czytaj jako „pole powiązania
autora, zapisywane bez prefiksu".

#### Artykuł naukowy (§ 2 ust. 10 pkt 4) — `Wydawnictwo_Ciagle`

| Kod | Warunek braku | Lit. | Waga |
|---|---|---|---|
| `ART_DOI` | `doi` puste **i** `public_www` puste **i** `www` puste | a | W |
| `ART_DYSCYPLINA` | `a__dyscyplina_naukowa` NULL **lub** `a__przypieta=False` | c | W |
| `ART_UPOWAZNIENIE` | `a__upowaznienie_pbn=False` | d | W |
| `ART_ORCID` | `a__autor__orcid` puste | e | C |
| `ART_RECENZYJNY` | `pbn_czy_artykul_recenzyjny` NULL | f | W |
| `ART_ZRODLO` | `zrodlo` NULL | h | W |
| `ART_ISSN` | `zrodlo__issn`, `zrodlo__e_issn`, `issn`, `e_issn` — wszystkie puste | h | W |
| `ART_TOM` | `tom` puste **i** `informacje` puste | j | C |
| `ART_STRONY` | `strony` puste **i** `szczegoly` puste | k | C |
| `ART_OA_WERSJA` | `openaccess_tryb_dostepu` ustawione **i** `openaccess_wersja_tekstu` NULL | l | W |
| `ART_OA_LICENCJA` | `openaccess_tryb_dostepu` ustawione **i** `openaccess_licencja` NULL | l | W |
| `ART_OA_DATA` | `openaccess_tryb_dostepu` ustawione **i** `openaccess_data_opublikowania` NULL | l | W |
| `ART_OA_CZAS` | `openaccess_tryb_dostepu` ustawione **i** `openaccess_czas_publikacji` NULL | l | W |
| `ART_OA_MIESIACE` | `openaccess_czas_publikacji` = „po opublikowaniu" **i** `openaccess_ilosc_miesiecy` NULL | l | W |
| `ART_APC` | `opl_pub_cost_free` NULL **i** `opl_pub_amount` NULL **i** trzy flagi źródeł NULL | m | W |
| `ART_APC_ZRODLO` | `opl_pub_amount` > 0 **i** żadna flaga źródła nie jest `True` | m | W |

Reguły OA są **warunkowe względem trybu dostępu**: jeśli praca nie jest
oznaczona jako Open Access, rozporządzenie nie wymaga danych OA i raport milczy.
`ART_OA_MIESIACE` uruchamia się tylko dla udostępnienia po opublikowaniu — bo
tylko wtedy liczba miesięcy ma sens.

#### Monografia (§ 2 ust. 10 pkt 5) — `Wydawnictwo_Zwarte`, `charakter_sloty` = książka

| Kod | Warunek braku | Lit. | Waga |
|---|---|---|---|
| `MON_DOI` | `doi` puste **i** `public_www` puste **i** `www` puste | a | W |
| `MON_ISBN` | `isbn` puste **i** `e_isbn` puste | b | W |
| `MON_WYDAWCA` | `wydawca` NULL **i** `wydawca_opis` puste | e | W |
| `MON_DYSCYPLINA` | `a__dyscyplina_naukowa` NULL **lub** `a__przypieta=False` | g | W |
| `MON_UPOWAZNIENIE` | `a__upowaznienie_pbn=False` | h | W |
| `MON_ORCID` | `a__autor__orcid` puste | d | C |
| `MON_EDYCJA_NAUKOWA` | `pbn_czy_edycja_naukowa` NULL | j | W |
| `MON_PROJEKTY` | wszystkie cztery `pbn_czy_projekt_*` NULL | k | W |
| `MON_OA_*` | jak `ART_OA_*` | m | W |
| `MON_APC`, `MON_APC_ZRODLO` | jak `ART_APC*` | n | W |

#### Rozdział (§ 2 ust. 10 pkt 6) — `Wydawnictwo_Zwarte`, `charakter_sloty` = rozdział

| Kod | Warunek braku | Lit. | Waga |
|---|---|---|---|
| `ROZ_NADRZEDNE` | `wydawnictwo_nadrzedne` NULL **i** `wydawnictwo_nadrzedne_w_pbn` NULL | a | W |
| `ROZ_DYSCYPLINA` | jak `MON_DYSCYPLINA` | d | W |
| `ROZ_UPOWAZNIENIE` | jak `MON_UPOWAZNIENIE` | e | W |
| `ROZ_ORCID` | `a__autor__orcid` puste | c | C |

Rozdział dziedziczy wymogi monografii macierzystej (lit. a odsyła do pkt 5),
ale raport **nie duplikuje** ich na rozdziale — braki monografii pokazuje przy
monografii. Inaczej jedna niekompletna książka generowałaby braki przy każdym
z kilkunastu rozdziałów, zalewając listę.

#### Patent (§ 2 ust. 10 pkt 1) — `Patent`

| Kod | Warunek braku | Lit. | Waga |
|---|---|---|---|
| `PAT_NUMER` | `numer_prawa_wylacznego` puste | c | W |
| `PAT_ZGLOSZENIE` | `numer_zgloszenia` puste **lub** `data_zgloszenia` NULL | g | W |
| `PAT_DYSCYPLINA` | jak wyżej | k | W |
| `PAT_UPOWAZNIENIE` | jak wyżej | l | W |
| `PAT_ORCID` | `a__autor__orcid` puste | m | C |

### 4. Okno ewaluacyjne

Bieżące okno zaczyna się w **2026 r.** Stała `OKNO_EWALUACJI = (2026, 2029)`
w `ewaluacja_common/const.py` jako jedyne źródło prawdy dla nowej aplikacji.
Istniejących wywołań w `ewaluacja_metryki` nie ruszamy — patrz „Dług techniczny".

### 5. Liczenie na żywo, bez materializacji

Braki liczone przy każdym otwarciu widoku, przez `annotate()` warunkami reguł.
Nie powstaje tabela pochodna, nie ma migracji tworzącej model raportu.

Uzasadnienie: okno 2026+ dopiero się otwiera, więc zbiór jest dziś bliski pustemu
i przez pierwsze lata pozostanie mały. Materializacja (wzorem `MetrykaAutora`)
wprowadzałaby opóźnienie między poprawką a zniknięciem rekordu z listy — czyli
tarcie, które zabija adopcję narzędzia roboczego. Rejestr reguł jest niezależny
od sposobu liczenia, więc materializacja da się dołożyć bez przepisywania logiki.

## Architektura

```
src/kompletnosc_polon/
├── apps.py                 # KompletnoscPolonConfig
├── const.py                # Osiagniecie, Waga
├── reguly.py               # REGULY: tuple[Regula, ...] + pomocnicze selektory
├── selektory.py            # budowa querysetów per typ osiągnięcia
├── urls.py                 # app_name = "kompletnosc_polon"
├── views/
│   ├── __init__.py         # re-eksport + __all__
│   ├── lista.py            # widok zbiorczy: autor → liczba braków
│   └── szczegoly.py        # rozwinięcie: rekordy autora + konkretne braki
├── templates/kompletnosc_polon/
│   ├── lista.html
│   └── szczegoly.html
└── tests/
```

Wzorzec skopiowany z `ewaluacja_metryki` (pakiet `views/` z re-eksportem,
`uczelnia_scope.py`, szablony w `templates/<app_label>/`, dziedziczenie
po globalnym `base.html`).

**Rejestracja:** `"kompletnosc_polon"` w `INSTALLED_APPS`
(`src/django_bpp/settings/base.py`, blok aplikacji ewaluacyjnych, ok. linii 480);
`path("kompletnosc_polon/", include("kompletnosc_polon.urls"))`
w `src/django_bpp/urls.py`; link w `src/django_bpp/templates/top_bar.html`
w istniejącym podmenu „ewaluacja".

**Kontrola dostępu:** `EwaluacjaRequiredMixin` z
`ewaluacja_metryki.views.mixins`, ale widok wymaga **pełnych** uprawnień
(`ma_pelne_uprawnienia_ewaluacji`) — to narzędzie redaktorskie, nie widok dla
autora. Zawężenie do uczelni przez `uczelnia_dla_odczytu(request)`
(`raport_slotow.uczelnia_helper`) i `scope_*` z `bpp.util.uczelnia_scope`.

**Migracje:** brak. Aplikacja nie ma modeli.

## Przepływ danych

1. Widok ustala okno (`OKNO_EWALUACJI`) i uczelnię (`uczelnia_dla_odczytu`).
2. `selektory.py` buduje querysety through-modeli, zawężone do: roku w oknie,
   powiązania **przypiętego** (`przypieta=True`) oraz autora afiliowanego do
   jednostki tej uczelni (przez `scope_autorzy_do_uczelni`).

   Zawężenie celowo **nie** odsiewa powiązań bez dyscypliny. Pierwotna wersja
   projektu mówiła o „przypiętej dyscyplinie", co czytane dosłownie odsiałoby
   też `dyscyplina_naukowa IS NULL` — a wtedy reguły `*_DYSCYPLINA` stałyby się
   martwe i raport przemilczałby dokładnie ten brak, o który pyta. Powiązanie
   przypięte, ale bez dyscypliny, zostaje w raporcie i jest zgłaszane jako brak.
3. Dla każdego querysetu `annotate()` dokłada po jednym `BooleanField` na regułę
   pasującą do typu osiągnięcia (`Case/When` z `Regula.warunek`).
4. Widok zbiorczy agreguje po autorze: liczba rekordów z brakami, liczba braków
   wymaganych i warunkowych.
5. Widok szczegółów listuje rekordy jednego autora wraz z nazwami naruszonych
   reguł, opisami i paragrafami, każdy z linkiem do formularza edycji w adminie.

## Obsługa błędów

- **Brak przypiętych dyscyplin w całej bazie** (świeża instalacja, nieuruchomiona
  ewaluacja) → widok pokazuje komunikat wyjaśniający, że raport wymaga
  przypisanych dyscyplin, zamiast pustej tabeli sugerującej „wszystko w porządku".
- **Zero braków** → jawny komunikat „sprawdzono N rekordów, brak zastrzeżeń",
  z podaniem zakresu lat. Puste tabele bez kontekstu są mylące.
- **Charakter formalny bez `charakter_sloty`** (fixture instalacyjny zostawia
  `null` — ustalone w rozpoznaniu) → taki rekord nie daje się zaklasyfikować jako
  monografia ani rozdział. Trafia do osobnej sekcji „nierozpoznany typ
  osiągnięcia" zamiast zniknąć po cichu.
- Zgodnie z regułą repo: żadnego `except: pass`.

## Testy

- **Test per reguła** — dla każdej z reguł dwa rekordy przez `baker.make`: jeden
  spełniający wymóg, jeden z brakiem; asercja, że reguła łapie dokładnie ten drugi.
  To właściwa jednostka testowa, bo reguły są danymi. Test parametryzowany po
  `REGULY`, więc dopisanie reguły bez testu psuje suitę.
- **Test ziarna** — publikacja dwóch współautorów w dwóch dyscyplinach daje dwa
  wiersze, a brak przypisany jest właściwej osobie.
- **Test zakresu** — rekord spoza okna, rekord z odpiętą dyscypliną i rekord
  autora z innej uczelni nie pojawiają się w raporcie.
- **Test warunkowości** — praca bez oznaczenia OA nie generuje braków OA;
  praca z `openaccess_czas_publikacji` innym niż „po opublikowaniu" nie wymaga
  liczby miesięcy.
- **Test widoku** — dostęp odrzucony dla użytkownika bez pełnych uprawnień;
  dane zawężone do uczelni.

Konwencja repo: pytest, funkcje bez klas, `@pytest.mark.django_db`,
`model_bakery.baker`.

## Dług techniczny ujawniony przy okazji

Trzy niezgodne definicje okna ewaluacyjnego:

| Miejsce | Wartość |
|---|---|
| `ewaluacja_common/const.py` | `ROK_MIN = 2022`, `ROK_MAX = 2026` |
| `ewaluacja_metryki/models.py:114-120` | pola `rok_min`/`rok_max`, domyślnie `2022` / `2025` |
| `ewaluacja_metryki/tasks.py`, `utils.py` | `rok_min=2022, rok_max=2025` w ośmiu sygnaturach |

`ROK_MAX` mówi 2026, metryki liczą do 2025. Rozjazd siedzi w domyślnych
argumentach funkcji, nie we wspólnej stałej, więc jest niewidoczny. Wraz
z otwarciem okna 2026+ każde z tych miejsc jest błędne.

Świadomie **nie naprawiane w tym PR** — zmiana domyślnych lat zmieniłaby wyniki
liczenia metryk i slotów, czyli zachowanie niezwiązane z tym zgłoszeniem.
Do osobnego zgłoszenia.

## Braki modelu danych do osobnych zgłoszeń

Wymogi rozporządzenia bez odpowiednika w BPP:

| Wymóg | Paragraf | Stan |
|---|---|---|
| ISMN (druki muzyczne) | pkt 5 lit. b | brak pola |
| Czy monografia jest przekładem dzieła istotnego | pkt 5 lit. i | brak pola; kierunek tłumaczenia wyliczany dopiero w adapterze eksportu PBN, nieprzechowywany |
| Zgłoszenie do oceny eksperckiej KEN + wynik | pkt 5 lit. l | brak pola |
| Patenty: uprawniony, urząd, państwa ochrony, data ogłoszenia w WUP, pierwszeństwo, streszczenie, tłumaczenie patentu EP | pkt 1 lit. b, d, e, f, h, i, j | brak pól (por. FD#449) |
| Osiągnięcia artystyczne | pkt 7 | brak modelu |

## Ryzyka

| Ryzyko | Reakcja |
|---|---|
| Raport na starcie pusty (okno 2026 dopiero się otwiera) — użytkownik uzna, że nie działa | Widok jawnie komunikuje zakres lat i liczbę sprawdzonych rekordów, także przy zerze braków |
| Fałszywe braki tam, gdzie dana jest nieobowiązkowa | Pole `waga`; wymogi warunkowe liczone osobno i nieoznaczane jako krytyczne |
| Trzy zapytania zamiast jednego | Akceptowane — zbiór mały, a alternatywą jest rozszerzanie widoku `bpp_rekord`, co dotyka całego systemu |
| Instalacje bez ustawionego `charakter_sloty` klasyfikują się nijak | Osobna sekcja „nierozpoznany typ" zamiast cichego pominięcia |

## Errata — zmiany wprowadzone po recenzji adwersarialnej

Recenzja całości przed wystawieniem PR znalazła dwa błędy krytyczne, wyciek
danych w instalacji wielouczelnianej i pięć luk merytorycznych. Wszystkie
potwierdzone uruchomieniem kodu, nie domysłem. Rejestr urósł z **40 do 50+
reguł**. Zmiany względem treści powyżej:

### Wydawnictwa ciągłe wymagają filtra charakteru formalnego

Pierwotny projekt zakładał, że „wydawnictwo ciągłe jest zawsze pkt 4". To
nieprawda: `Wydawnictwo_Ciagle` obejmuje w BPP także streszczenia zjazdowe
(PSZ/ZSZ), listy do redakcji (L), recenzje (R) i komunikaty (KOM). Bez filtra
raport żądał od streszczenia konferencyjnego numeru DOI i informacji, czy jest
artykułem recenzyjnym.

Ziarno dla artykułów zawężone do
`rekord__charakter_formalny__rodzaj_pbn = RODZAJ_PBN_ARTYKUL` — idiom, którego
repo już używa w `pbn_integrator` i `komparator_pbn`.

### Monografia macierzysta rozdziału nie była sprawdzana wcale

Projekt zakładał, że braki monografii pokazujemy przy monografii, więc rozdział
ich nie duplikuje. Przesłanka była fałszywa: monografia trafia do raportu tylko
wtedy, gdy sama ma powiązanie autorskie z uczelni. Rozdział w monografii
zbiorowej pod obcą redakcją ma rodzica bez takich powiązań — więc § 2 ust. 10
pkt 6 lit. a nie był sprawdzany w najczęstszym przypadku.

Dodane reguły `ROZ_MON_ISBN`, `ROZ_MON_WYDAWCA`, `ROZ_MON_DOI` po ścieżce
`rekord__wydawnictwo_nadrzedne__…`, bramkowane wskazanym rodzicem. Świadomie
tylko trio identyfikujące, a nie cały pkt 5 — rodzic z autorami z uczelni jest
audytowany osobno, a pełne powielenie dawałoby podwójne zgłoszenia.

### Widok szczegółów przeciekał dane między uczelniami

`get_object_or_404(Autor, slug=…)` bez zawężenia zwracał HTTP 200 z imieniem
i nazwiskiem autora obcej uczelni. Slug jest przewidywalny (`nazwisko-imie`),
więc pozwalało to enumerować kadrę. Zawężone przez `scope_autor_do_uczelni` —
teraz 404.

### Reguły dołożone

| Kod | Wymóg | Paragraf |
|---|---|---|
| `ART_OA_TRYB`, `MON_OA_TRYB` | sposób udostępnienia OA — brakowało reguły na samą bramkę, więc rekord z datą OA, ale bez trybu, wersji i licencji nie dawał żadnego naruszenia | pkt 4 lit. l / pkt 5 lit. m |
| `ART_APC_KWOTA`, `MON_APC_KWOTA` | zadeklarowano niebezkosztowość, ale nie podano kwoty — luka między dwiema dotychczasowymi regułami APC | pkt 4 lit. m / pkt 5 lit. n |
| `ART_KONFERENCJA_NAZWA`, `_DATY`, `_MIEJSCE` | dane konferencji, gdy artykuł jest z materiałów konferencyjnych; wymóg całkiem pominięty, mimo że BPP ma pola | pkt 4 lit. g |
| `ROZ_MON_ISBN`, `ROZ_MON_WYDAWCA`, `ROZ_MON_DOI` | dane identyfikujące monografii macierzystej | pkt 6 lit. a |

### Pozostałe poprawki

- **Paginacja** widoku listy (25 autorów na stronę). Założenie „zbiór jest mały"
  nie przeżyje pierwszego roku okna: pola `pbn_czy_*` i `opl_pub_*` mają
  `default=None`, a `przypieta` `default=True`, więc w realnej instalacji prawie
  każde powiązanie ma co najmniej jeden brak wymagany.
- **Sekcja „nierozpoznany typ"** zawężona do rekordów, które naprawdę jadą do
  PBN — wcześniej ostrzegała o charakterach sklasyfikowanych poprawnie i celowo
  (fragment, tłumaczenie, skrypt), wysyłając redaktora do edycji słownika bez
  powodu. Rozszerzona symetrycznie na wydawnictwa ciągłe bez ustawionego
  `rodzaj_pbn`, żeby artykuły nie znikały po cichu na niedokonfigurowanej
  instalacji.
- **Testy**: dotychczasowy wzorzec zerował wszystkie człony koniunkcji naraz,
  więc dowolny człon poza pierwszym dawało się usunąć z kodu przy zielonej
  suicie. Dołożone testy „fallback ratuje" na każdy taki człon.
- `sa_przypiete_dyscypliny()` zawężone do uczelni — zdradzało boolean o stanie
  danych obcej instytucji.
