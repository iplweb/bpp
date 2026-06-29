# Historia zmian

<!-- towncrier release notes start -->

## bpp 202606.1393 (2026-06-24)

### Naprawione

- Wydruk PDF raportu slotów - autor zawiera teraz wszystkie rekordy autora, a
  nie tylko pierwszą stronę (wcześniej, przy więcej niż 25 pracach, PDF urywał
  się na pierwszej stronie i zostawała namiastka pagera). Dodatkowo każda tabela
  (osobna dla każdej dyscypliny autora) ma nagłówek z nazwą dyscypliny, dzięki
  czemu przy autorze z kilkoma dyscyplinami wiadomo, której tabela dotyczy, a
  stopka tabeli z sumą punktów i slotów pokazuje się tylko raz, na końcu tabeli,
  zamiast powtarzać się na każdej podstronie wielostronicowego wydruku (FD#405).


## bpp 202606.1392 (2026-06-24)

### Naprawione

- Eksport raportu slotów - autor do PDF zawiera teraz wyłącznie sam raport.
  Wcześniej do pliku PDF potrafiło wyciec menu serwisu, surowy szablon
  powiadomień (`{{#clickURL}}`) i stopka strony — działo się tak, gdy serwer
  nie zdążył dociągnąć stylów do wydruku. PDF jest teraz generowany z
  dedykowanego, samowystarczalnego szablonu, więc wygląda poprawnie niezależnie
  od stanu plików statycznych (FD#405).

### Usprawnienie

- Zgłoszenia błędów w Rollbarze zawierają teraz w polu ``custom`` login
  zalogowanego użytkownika (a dla ruchu niezalogowanego — wyraźne oznaczenie
  użytkownika anonimowego), co ułatwia powiązanie błędu z konkretną osobą.


## bpp 202606.1391 (2026-06-20)

No significant changes.


## bpp 202606.1390 (2026-06-17)

### Naprawione

- Zaktualizowano trzy zależności tranzytywne do wersji łatających
  podatności zgłoszone w audycie ``pip-audit``: ``bleach`` do 6.4.0
  (GHSA-8rfp-98v4-mmr6, GHSA-gj48-438w-jh9v), ``daphne`` do 4.2.2
  (PYSEC-2026-213, PYSEC-2026-214) oraz ``pypdf`` do 6.13.2
  (CVE-2026-48735, CVE-2026-49460, CVE-2026-49461, CVE-2026-54530,
  CVE-2026-54531). Minimalne wersje są od teraz egzekwowane przez
  ``constraint-dependencies`` w ``pyproject.toml``, dzięki czemu
  przyszłe przeliczenie ``uv.lock`` nie cofnie się poniżej
  załatanego wydania.


## bpp 202606.1389 (2026-06-17)

No significant changes.


## bpp 202606.1388 (2026-06-13)

No significant changes.


## bpp 202606.1387 (2026-06-13)

### Naprawione

- Triggery denormalizacji (``django-denorm-iplweb``, bump do ``1.12.1``)
  rozwiązują teraz identyfikator typu treści (``content_type_id``)
  dynamicznie w momencie zadziałania triggera, zamiast mieć go zaszytego
  na stałe w treści triggera. Dzięki temu znikają błędy
  ``ForeignKeyViolation`` na tabeli ``denorm_dirtyinstance``, gdy
  identyfikatory w ``django_content_type`` zmienią numerację po stronie
  triggerów — np. po odtworzeniu bazy z innego zrzutu albo po przebudowie
  typów treści. ``drop_triggers`` poprawnie usuwa też osierocone triggery
  po wcześniejszych wersjach biblioteki (pełny ``drop`` + ``install``).

### Usprawnienie

- Arkusze CSS motywów są mniejsze (−5%, ok. 16 KB na motyw) po
  usunięciu dziewięciu nieużywanych komponentów Foundation (m.in.
  karuzela orbit, suwak slider, przełącznik switch, menu off-canvas).
  Lista komponentów jest teraz wspólna dla wszystkich sześciu motywów
  (jeden plik zamiast sześciu kopii), z udokumentowanym audytem użycia.
- Mniej zbędnych zapytań SQL na często odwiedzanych stronach: wyniki
  multiwyszukiwarki dla raportów tabelarycznych liczą rekordy i sumy
  punktacji jednym skanem zamiast dwóch; przeglądanie lat nie wykonuje
  ponownie tych samych COUNT-ów; eksport multiseek nie odpytuje bazy
  o typ rekordu dla każdego wiersza z osobna (procesowy cache
  ``ContentType``); API ostatnich publikacji autora nie pobiera ~40
  zbędnych kolumn i nie duplikuje publikacji, gdy autor występuje na
  rekordzie wielokrotnie.
- Przeglądanie autorów działa szybciej i poprawniej ukrywa autorów
  obcych: lista nie buduje już GROUP BY po wszystkich przypisaniach
  autorów, filtr „autorzy bez prac" korzysta ze zmaterializowanej tabeli
  cache zamiast skanować pięć tabel źródłowych, a autor przypisany
  wyłącznie do jednostki sztucznej (Obca / „Błędna") jest teraz ukrywany
  także wtedy, gdy figuruje tylko w jednej z nich.
- Przeglądanie kolejnych stron wyników multiwyszukiwarki jest szybsze:
  liczba rekordów i sumy punktacji są liczone raz na zapytanie
  (cache 30 min), a nie od nowa przy każdej stronie. Zmiana formularza,
  wyrzucenie rekordu z wyników lub zalogowanie przelicza od razu.
- Strona pojedynczego rekordu (adres ze slugiem) ładuje się szybciej:
  kolumna ``slug`` w tabeli cache ``bpp_rekord_mat`` dostała indeks —
  wcześniej każde wejście na stronę rekordu skanowało całą tabelę.
  Dodatkowo sprawdzenie „czy rekord ma punktację/sloty" na stronie
  szczegółów kosztuje jedno zapytanie zamiast dwóch.
- Strony ładują się szybciej: główny pakiet JavaScript (``bundle.js``)
  schudł o ~600 KB (−39%) po usunięciu nieużywanej biblioteki Tone.js
  (dźwięki powiadomień nigdy nie były włączone), a start kontenera nie
  traci już czasu na ponowną minifikację zminifikowanego wcześniej
  JavaScriptu (``COMPRESS_JS_FILTERS``).
- Trigger odświeżający tabele cache (``bpp_rekord_mat`` /
  ``bpp_autorzy_mat``) działa wydajniej i poprawniej: edycja publikacji
  nie kasuje już i nie wstawia od nowa wszystkich wierszy autorów
  (czysty upsert zamiast DELETE z kaskadą FK), masowe operacje nie
  zużywają subtransakcji per wiersz, zmiana autora wpisu „in-place"
  poprawnie aktualizuje cache, a usunięcie jednej z dwóch ról tego
  samego autora (np. autor + redaktor) nie usuwa już obu wierszy
  z cache autorów.
- Wyszukiwanie pełnotekstowe działa szybciej: indeks pełnotekstowy
  tabeli cache rekordów zmienił typ z GiST na GIN. Na danych
  produkcyjnych typowe kształty zapytań przyspieszają od 1,7× do
  prawie 20× (zapytania z dwoma słowami), bez zauważalnego kosztu
  przy zapisie.


## bpp 202606.1386 (2026-06-12)

### Naprawione

- Wydruki (m.in. raporty z multiseek) nie zajmują już niepotrzebnie
  dodatkowej, prawie pustej strony. Stopka „Dokument wygenerowano przy
  pomocy systemu…” była spychana na kolejną stronę, ponieważ kontenery
  treści miały na ekranie ustawione ``min-height: 100vh`` (przyklejenie
  stopki do dołu okna). W druku ``100vh`` oznacza całą wysokość kartki,
  więc treść była rozciągana na pełną stronę. Reguły te są teraz
  neutralizowane w ``@media print``.


## bpp 202606.1385 (2026-06-10)

### Naprawione

- Naprawiono błąd serwera (HTTP 500) przy zgłaszaniu publikacji z
  załącznikiem PDF większym niż 2,5 MB. W kreatorze „Zgłoś publikację"
  dodanie takiego pliku w kroku z danymi przerywało wysyłkę z błędem —
  plik tymczasowy był zapisywany dwukrotnie, a drugi zapis trafiał na
  już przeniesiony plik. Pliki dowolnej wielkości są teraz przyjmowane
  poprawnie.


## bpp 202606.1384 (2026-06-09)

No significant changes.


## bpp 202606.1383 (2026-06-09)

No significant changes.


## bpp 202606.1382 (2026-06-09)

### Naprawione

- Deduplikator autorów uruchamia skanowanie mimo nieaktualnych danych PBN,
  pokazując ostrzeżenie, oraz normalizuje Unicode'owe myślniki w nazwiskach
  przed bucketowaniem kandydatów.
- Dodano brakujące polskie tłumaczenia komunikatów ``django-mptt`` używanych w
  drzewiastym panelu administracyjnym.
- Poprawiono kolejność i blokadę kolumn w eksporcie tabeli Jednostka z modułu redagowania.

### Usprawnienie

- Dodano eksport tabel Jednostka i Wydział z modułu redagowania w Django adminie.
- Dodano eksport wyników Multiseek do CSV i XLSX z limitem 5000 rekordów,
  linkami BPP/PBN, nazwami plików i arkuszy opartymi o tytuł raportu oraz
  ochroną komórek arkusza przed interpretacją jako formuły.
- Ulepszono pełnotekstowe wyszukiwanie publikacji przez ważenie tytułów,
  autorów, DOI, roku oraz opisu bibliograficznego w cache'owanym indeksie.


## bpp 202606.1381 (2026-06-08)

No significant changes.


## bpp 202606.1380 (2026-06-05)

### Naprawione

- Lista (changelist) w panelu administracyjnym dla modeli z eksportem
  XLSX (m.in. wydawnictwa, autorzy, dyscypliny autorów) wykonywała
  zapytanie filtrujące i wyszukujące **dwukrotnie** przy każdym
  wyświetleniu — raz przy sprawdzaniu uprawnień do eksportu
  (``has_export_permission`` budowało własny ``ChangeList`` tylko po to,
  by policzyć rekordy), a drugi raz przy renderowaniu listy. Teraz
  ``ChangeList`` jest budowany raz na żądanie, więc kosztowne zapytanie
  nie powtarza się. Przy okazji znika zdublowany komunikat o błędzie
  składni w wyszukiwarce DjangoQL.

### Usprawnienie

- Widok „Szukaj zapytaniem" oraz wyszukiwarki DjangoQL w panelu
  administracyjnym zyskują wygodniejszy edytor zapytań (dzięki
  nowej wersji ``djangoql-iplweb``):

  * **Podświetlanie składni** w polu zapytania, a w razie błędu —
    czerwona falka pod miejscem, które trzeba poprawić (nieznane
    pole albo błąd składni).
  * **Zapytania wieloliniowe** — ``Shift+Enter`` wstawia nową linię,
    zwykły ``Enter`` nadal wykonuje wyszukiwanie.
  * **Przycisk „Sformatuj"** — czytelnie wcina i łamie długie
    zapytanie na wiele linii.
  * **Panel „Wyjaśnij liczby"** — na żądanie pokazuje, ile rekordów
    pasuje do każdej gałęzi zapytania (czerwone = tu wynik schodzi do
    zera, bursztynowe = martwa gałąź ``or``). Uzupełnia dotychczasowe
    rozbicie „dlaczego 0 wyników".
  * **Podpowiedzi wartości w listach** ``pole in ( … )`` — autocomplete
    działa też wewnątrz nawiasów listy, nie tylko po operatorze.

  W panelu administracyjnym podświetlanie składni jest włączone dla
  wszystkich wyszukiwarek DjangoQL.


## bpp 202606.1379 (2026-06-05)

No significant changes.


## bpp 202606.1378 (2026-06-04)

### Naprawione

- Wyszukiwarka zapytań DjangoQL (``/bpp/zapytanie/``) nie zwraca już
  zduplikowanych wyników. Filtrowanie po relacji „do wielu" (np.
  ``autorzy.autor.nazwisko ~ "Kowalski"``) tworzyło złączenie, które
  powielało ten sam rekord raz na każdy pasujący wiersz powiązany —
  przez co lista i licznik wyników były zawyżone. Wyniki są teraz
  zwracane jako lista unikalnych obiektów.

### Usprawnienie

- Na stronie rekordu prace z bardzo długą listą autorów (powyżej 25)
  domyślnie pokazują widok skrócony: pierwszych pięciu autorów, a po
  wielokropku autorów z jednostek uczelni (z numerem ich pozycji na
  liście, np. ``(264.)``). Przycisk „Pokaż wszystkich (N)" rozwija pełną
  listę, a „Zwiń listę autorów" wraca do skróconej. Autorzy z naszej
  uczelni są wyróżnieni także na pełnej liście. Pełna lista pozostaje w
  treści strony, więc kopiowanie, wydruk i indeksowanie obejmują
  wszystkich autorów.

  Długi opis bibliograficzny jest dodatkowo zwijany do kilku linii z
  przyciskiem „rozwiń" (pojawia się tylko gdy opis faktycznie się nie
  mieści).
- Usprawnienia integracji z DSpace w panelu redagowania:

  - W mapowaniach DSpace pole „Uczelnia" jest teraz podstawiane domyślnie
    (jedyna uczelnia w systemie, a przy wielu — uczelnia bieżącego
    serwisu).
  - Pole „UUID kolekcji DSpace" zamienia się w listę kolekcji pobieraną na
    żywo z DSpace wybranej uczelni — nie trzeba już przepisywać UUID
    ręcznie. Gdy DSpace jest nieosiągalny, pole wraca do ręcznego
    wpisania identyfikatora.
  - Dla rekordów wysłanych do repozytorium pojawia się link „zobacz
    w repozytorium" — na stronie edycji rekordu, w dzienniku wysyłek oraz
    na publicznej stronie szczegółów rekordu (karta „Linki zewnętrzne").
- Widok „Szukaj zapytaniem": pola ``<fk>__rel`` z autocomplete (wybór autora,
  jednostki, tytułu naukowego z podpowiedzi i filtrowanie po wybranym obiekcie),
  obok dotychczasowej składni z kropką. Gdy zapytanie zwróci 0 rekordów, widok
  pokazuje teraz rozbicie wyjaśniające, który warunek wyzerował wynik.
- Wyszukiwarka DjangoQL w adminie (Źródło, Autor, Wydawca, Jednostka,
  Autor-Dyscyplina, Wydawnictwo ciągłe/zwarte oraz nowo włączone Patent, Praca
  doktorska i habilitacyjna) używa teraz wspólnego schematu ``BppQLSchema``:
  pickery ``<fk>__rel`` z autocomplete wyboru obiektu (po widocznych pozycjach),
  agregaty relacji, części dat oraz rozbicie „dlaczego 0 wyników". Publikacje są
  opisywane/szukane przez opis bibliograficzny.
- Wyszukiwarka zapytań DjangoQL (``/bpp/zapytanie/``) obsługuje teraz
  agregaty relacji oraz części dat. W zapytaniu można odwołać się do
  liczby powiązanych obiektów przez ``<relacja>__count`` (np.
  ``autorzy__count > 5`` zwraca rekordy z więcej niż pięcioma autorami)
  oraz do sum, średnich, minimów i maksimów pól liczbowych powiązanych
  modeli przez ``<relacja>__<pole>__sum`` / ``__avg`` / ``__min`` /
  ``__max``.

  Pola dat i czasu można porównywać po wyodrębnionych częściach —
  ``<pole>__year``, ``__month``, ``__day``, ``__quarter`` itd., a dla
  pól ze znacznikiem czasu dodatkowo ``__hour``, ``__minute``,
  ``__second``.

  Nowe pola pojawiają się również w podpowiedziach (autouzupełnianiu)
  edytora zapytań.


## bpp 202606.1377 (2026-06-02)

### Naprawione

- Dodano exponential backoff (5 prób, max ~30 sekund) przy pobieraniu
  ``PublikacjaInstytucji_V2`` (UUID publikacji z PBN API v2). Poprzednio
  jedna próba kończyła się warningiem "nie jest błędem", co myliło użytkowników
  — brak V2 oznacza brak możliwości generowania linków do PBN Interfejs
  i wysyłki oświadczeń (wymagany UUID). Teraz system automatycznie ponawia
  z rosnącym czasem oczekiwania (2s, 4s, 8s, 16s, 32s).

  Jeśli po wszystkich próbach nadal nie ma V2 — wyświetlany jest BŁĄD (czerwony)
  z sugestią użycia wysyłki w tle (PBN Export Queue) zamiast interaktywnej.

  **Ważne dla deploymentu**: przy interaktywnej wysyłce z admina może być potrzebne
  zwiększenie timeoutu nginx/gunicorn dla ścieżek ``/admin/`` do minimum 90-120 sekund
  (domyślne 30-60s może być za mało przy 5 próbach z opóźnieniami).
- Poprawka w ``sync_publication``: POST oświadczeń publikacji w trybie
  selektywnym (``Uczelnia.pbn_kasuj_dyscypliny_selektywnie=True``, default)
  wysyła teraz TYLKO oświadczenia brakujące w PBN (``only_in_intended``),
  nie pełen zestaw lokalnych. Wcześniej kod wywoływał
  ``WydawnictwoPBNAdapter.pbn_get_api_statements()`` zwracające wszystkie
  lokalne statements i POST-ował kompletny zestaw — także te oświadczenia,
  które już były w PBN. Przy założeniu że API PBN może nie być
  idempotentne (odrzucić duplikaty, utworzyć zduplikowane rekordy albo
  zachowywać się nieprzewidywalnie), wysyłanie tylko brakujących jest
  bezpieczniejsze — nie dublujemy żądań dla już istniejących oświadczeń,
  co zachowuje ich metadata w PBN (``addedTimestamp`` itp.).

  Krok 3 algorytmu (PBN puste + BPP ma) nadal wysyła wszystkie oświadczenia
  publikacji, bo w tym scenariuszu ``only_in_intended`` = wszystkie klucze
  lokalne. Krok 5 (tryb batch, ``pbn_kasuj_dyscypliny_selektywnie=False``)
  pozostaje bez zmian — po ``delete_all`` PBN jest puste, więc POST wysyła
  pełen zestaw BPP (wipe+rewrite).
- Poprawka w narzędziu CLI ``pbn_test_wysylka_interaktywna``:

  - krok porównania oświadczeń (KROK 6/8) używał lokalnego cache'a
    ``OswiadczenieInstytucji`` (snapshot z poprzedniej synchronizacji
    PBN) jako reprezentanta „stanu BPP", co powodowało fałszywą
    identyczność po zmianach w rekordzie — skasowaniu autora,
    zmianie/wypięciu dyscypliny lub innej edycji ``Wydawnictwo_*_Autor``
    (cache nie był re-synchronizowany, pokazywał stare 3 oświadczenia
    nawet po faktycznym zmniejszeniu intencji BPP do 2). Narzędzie
    teraz porównuje **intencję BPP na żywo** — to co by wygenerował
    ``WydawnictwoPBNAdapter.pbn_get_api_statements()`` gdyby wysyłać
    teraz — z aktualnym stanem PBN. Dodatkowo KROK 1/8 pokazuje zarówno
    cache jak i intencję żywą, żeby od razu widać było rozjazd.
  - narzędzie zawsze pyta osobno o DELETE oświadczeń i osobno o POST
    oświadczeń, także gdy porównanie zwróciło identyczność —
    użytkownik może wymusić operację np. dla empirycznego sprawdzenia
    reakcji PBN (wcześniej flow kończył się wczesnym ``return`` po
    identyczności bez opcji kontynuacji). Domyślna wartość pytania
    zależy od wyniku porównania: „identyczne" → default ``n``,
    „różnice" → default ``t``.
- Refaktoryzacja wysyłki publikacji do PBN (``sync_publication``): publikacja
  jest zawsze wysyłana przez endpoint repozytoryjny
  ``POST /api/v1/repositorium/publications`` (bez oświadczeń w body), a
  dyscypliny/oświadczenia synchronizowane są w osobnym kroku przez
  ``/api/v2/institution-profile/statements`` dopiero po potwierdzeniu
  wysyłki publikacji. Dzięki temu nieudana wysyłka publikacji (np. HTTP
  423 Locked albo inna przejściowa awaria PBN) nie kasuje już istniejących
  oświadczeń w profilu instytucji — wcześniej kasowanie działo się przed
  POST i tracono dane przy każdym niepowodzeniu.

  Algorytm synchronizacji oświadczeń: GET aktualnego stanu PBN, porównanie
  z intencją BPP (``WydawnictwoPBNAdapter.pbn_get_json_statements()``)
  przez klucz ``(personId, disciplineId)``, selektywne DELETE (per-osoba
  przez ``delete_publication_statement(personId, role)``) brakujących w
  BPP + POST dodatkowych. Tryb kasowania sterowany nową flagą
  ``Uczelnia.pbn_kasuj_dyscypliny_selektywnie`` (domyślnie ``True``;
  ``False`` używa ``delete_all`` + POST batch).

  Nowy wyjątek ``StatementsResendFailedException`` (w
  ``pbn_api.exceptions``) jest podnoszony gdy retry x3 z exponential
  backoff (2s/4s/8s) na GET/DELETE/POST /v2/statements się wyczerpie.
  Klasyfikowany w ``pbn_export_queue`` jako ``RETRY_LATER`` — kolejka
  ponowi wysyłkę za kilka minut.

  Usunięto pole ``Uczelnia.pbn_api_kasuj_przed_wysylka`` (obsolete —
  stary pre-upload DELETE zastąpiony nowym algorytmem diff po wysyłce).
  Flaga ``Uczelnia.pbn_wysylaj_bez_oswiadczen`` pozostaje z dotychczasową
  semantyką (odmawia wysyłki publikacji bez oświadczeń).

### Usprawnienie

- Dodano interaktywne narzędzie CLI
  ``pbn_test_wysylka_interaktywna`` (Django management command) do
  eksperymentalnego testowania flow wysyłki publikacji i oświadczeń do PBN
  krok po kroku. Narzędzie prowadzi użytkownika przez kolejne fazy —
  generowanie JSON publikacji, wybór endpointa (``/api/v1/publications``
  all-in-one albo ``/api/v1/repositorium/publications`` bez oświadczeń),
  POST publikacji, GET i porównanie oświadczeń lokalnych z tym co jest w
  PBN, DELETE oświadczeń i POST przez ``/api/v2/institution-profile/statements``
  — pokazując dla każdego kroku metodę HTTP, URL, body i odpowiedź
  serwera. Narzędzie nie modyfikuje lokalnej bazy BPP i posiada tryb
  ``--dry-run``. Służy jako baza do audytu zachowania PBN API i
  projektowania bezpieczniejszej kolejności operacji wysyłki (scenariusz:
  nieudana wysyłka publikacji kasowała wcześniej istniejące oświadczenia).


## bpp 202606.1376 (2026-06-01)

### Naprawione

- Na formularzach nowych raportów (np. „Raport autorów”) sekcja
  „Opcje zaawansowane” jest teraz rozwijanym akordeonem (z markerem
  ``+``/``−``) umieszczonym wewnątrz ramki „Wybierz parametry”, spójnym
  wizualnie z filtrami na stronie „Ranking autorów”.

  Pola zakresów od/do (Punkty MNiSW, Impact Factor, Punktacja
  wewnętrzna) wyświetlają się obok siebie — analogicznie do pól
  „Od roku”/„Do roku” — zamiast jedno pod drugim.
- Spolszczono okno ostrzeżenia o wygasającej sesji
  (``django-session-security``) — wcześniej wyświetlało się po angielsku
  zarówno na stronie publicznej, jak i w panelu administracyjnym.
  Pakiet nie dostarcza skompilowanych tłumaczeń dla języka polskiego,
  więc komunikaty („Your session is about to expire”, „seconds”,
  „Click or type to extend your session.”) zostały przetłumaczone
  w katalogu tłumaczeń projektu.


## bpp 202606.1375 (2026-06-01)

### Naprawione

- Naprawiono rozbijanie dwukolumnowego układu strony rekordu przez
  treść streszczenia. Streszczenia importowane z zewnętrznych źródeł
  zawierają operatory porównania wpisane wprost w tekst (np.
  ``<30 IU/dL``, ``ct<or ≥15K``, ``>= 1%``). Pojedynczy znak ``<`` bez
  zamykającego ``>`` był traktowany przez minifikator HTML jak otwarcie
  znacznika, który połykał dalszy markup (w tym zamykające znaczniki
  prawej kolumny) — cała strona zlewała się do jednej kolumny, a tekst
  streszczenia wyświetlał się jako posortowana sieczka słów.

  Streszczenia są teraz renderowane przez filtr ``|safe_streszczenie``,
  który escape'uje gołe operatory ``<``/``>`` i sanityzuje pozostały
  markup (usuwa m.in. znaczniki JATS z importu Crossref oraz ewentualny
  kod XSS), oddając poprawny, zbalansowany HTML. Dotyczy to widoku
  rekordu oraz listy najnowszych streszczeń na stronie uczelni.


## bpp 202606.1374 (2026-06-01)

No significant changes.


## bpp 202606.1373 (2026-06-01)

### Naprawione

- Cztery widoki wykonujące mutacje danych zostały przerobione z metody
  HTTP ``GET`` na ``POST`` z ekranem potwierdzenia. Wcześniej kliknięcie
  zwykłego linku (lub np. prefetch w przeglądarce) mogło wykonać ciężką
  operację bez świadomej akcji użytkownika i bez ochrony CSRF. Teraz
  ``GET`` wyświetla ekran potwierdzenia z formularzem ``POST``,
  zabezpieczonym tokenem CSRF, a sama mutacja wykonywana jest dopiero
  po akceptacji.

  Dotyczy widoków:

  - ``komparator_pbn_udzialy:rebuild`` — przebudowa rozbieżności PBN
    (uruchamia zadanie Celery z ``clear_existing=True``).
  - ``rozbieznosci_if:ustaw_wszystkie`` — masowe ustawienie IF
    z punktacji źródła dla przefiltrowanych rekordów.
  - ``rozbieznosci_pk:ustaw_wszystkie`` — masowe ustawienie punktów
    MNiSW z punktacji źródła dla przefiltrowanych rekordów.
  - ``snapshot_odpiec:nowy`` — utworzenie nowego snapshotu odpięć.
  - ``snapshot_odpiec:aplikuj`` — zaaplikowanie snapshotu na bazę.
- Eksporty XLSX (porównanie publikacji BPP–PBN, lista publikacji
  do wysyłki oświadczeń) sanityzują teraz wartości komórek przed
  zapisem. Wartości tekstowe zaczynające się od ``=``, ``+``, ``-``,
  ``@`` lub białego separatora są poprzedzane apostrofem,
  co powstrzymuje Excela / LibreOffice'a przed interpretacją ich
  jako formuł (CSV/Formula Injection wg OWASP). Pomocnicza funkcja
  ``bpp.util.sanitize_xlsx_cell`` / ``sanitize_xlsx_row`` jest
  dostępna do wykorzystania w kolejnych eksportach.
- Klient PBN-API wykonuje teraz wszystkie zapytania HTTP (``GET``,
  ``POST``, ``DELETE``, autoryzacja OAuth) z jawnymi limitami czasu
  łączenia i odpowiedzi. Wcześniej brak ``timeout`` powodował, że
  zawieszony serwer PBN mógł zablokować w nieskończoność proces web
  albo workera Celery. Wartość można nadpisać przez ``settings``
  lub zmienną środowiskową ``PBN_CLIENT_HTTP_TIMEOUT`` (sekundy
  jako liczba albo ``connect,read``); domyślnie 30 s connect / 120 s
  read.
- Naprawiono błąd w ``docker/appserver/entrypoint-appserver.sh`` powodujący
  że nowsze pliki staticów (np. CSS po dodaniu nowego SCSS-a) nie trafiały
  na produkcję mimo zredeployowania nowego obrazu.

  Poprzednio entrypoint kopiował ``cp -ru /app/staticroot.baked/. "$STATIC_ROOT/"``
  — flaga ``-u`` (update only if newer) porównywała mtime źródła z mtime
  docelowym. mtime w ``.baked`` pochodzi z czasu ``grunt build`` w trakcie
  buildu obrazu, podczas gdy mtime na named volume z czasu ``cp`` przy
  poprzednim restarcie kontenera. Jeśli poprzedni restart nastąpił później
  niż grunt build w nowym obrazie (typowy scenariusz przy deployach jeden
  po drugim), ``cp -u`` cicho skipował kopiowanie i volume utrzymywał stare
  pliki — a ``django-compressor`` produkował bundle z tych przestarzałych
  źródeł.

  Teraz używamy ``cp -rf`` — zawsze nadpisuje pliki istniejące w ``.baked``,
  bez sprawdzania mtime. Ochrona tenant-specific zmian (custom branding
  wgrany post-deploy do podkatalogów spoza ``.baked``) jest zachowana,
  ponieważ ``cp`` i tak nie kasuje plików spoza źródła.

  **Symptom dla użytkowników poprzedniego zachowania**: po dodaniu nowych
  reguł CSS (np. nowych klas SCSS) i zredeployowaniu obrazu, na produkcji
  nadal widoczny jest stary styl. Workaround manualny:
  ``docker compose exec appserver cp -rf /app/staticroot.baked/. "$STATIC_ROOT/" && docker compose exec appserver python src/manage.py compress -v0 --force``.
  Po tym fixie nie jest już potrzebny.
- Publiczny autocomplete w ``zglos_publikacje`` (wybór wydawcy
  i wydawnictwa nadrzędnego) escape'uje teraz nazwy z bazy BPP
  oraz dane pobrane z PBN przy budowie etykiet w wynikach. Wcześniej
  ``mark_safe(f"...")`` interpolował wartości bez sanityzacji,
  przez co tytuł lub nazwa wydawcy zawierające znaczniki HTML
  mogły wstrzyknąć skrypt na publicznej stronie zgłoszenia.
- Tworzenie zadań w tle dla pobrań z PBN
  (``pbn_downloader_app.tasks.create_task_with_lock``) oraz wysyłki
  oświadczeń (``pbn_wysylka_oswiadczen`` widok startu zadania) jest
  teraz chronione przez Postgresowy advisory lock. Wcześniej sprawdzenie
  ``filter(status="running").exists()`` wewnątrz ``transaction.atomic()``
  nie gwarantowało wzajemnego wykluczenia — dwa równoczesne żądania
  mogły obydwa nie znaleźć aktywnego zadania i obydwa założyć kolejne,
  przez co dwóch workerów mogło naraz wykonywać tę samą operację.
- Widoki listy problemów PBN, szczegółów rozbieżności dyscyplin
  oraz szczegółów brakującego autora w module
  ``komparator_pbn_udzialy`` wymagają teraz członkostwa w grupie
  „wprowadzanie danych”. Wcześniej te trzy widoki były dostępne
  publicznie, mimo że pokazują dane synchronizowane z PBN i wewnętrzne
  identyfikatory BPP.

### Usprawnienie

- Aplikacja ``formdefaults``, dotychczas utrzymywana w drzewie BPP,
  została wymieniona na zewnętrzny pakiet ``django-formdefaults``
  (PyPI). Dane (``FormRepresentation``, ``FormFieldRepresentation``,
  ``FormFieldDefaultValue``) i utrwalone wartości domyślne pozostają
  nietknięte — Django zastosuje pięć nowych migracji przyrostowo
  (``pre_registered``, ``is_auto_snapshot`` plus dwa unique constraints).

  Każdy formularz frontendowy zalogowanego użytkownika dostał teraz
  przycisk **„Moje wartości domyślne”** w prawym górnym rogu,
  otwierający popup do edycji własnych ustawień startowych pola
  po polu. Użytkownicy z flagą ``is_staff`` widzą obok drugi
  przycisk **„Systemowe wartości domyślne”** — edytuje on
  wartość systemową, którą widzą wszyscy. Domyślne uprawnienie pakietu
  (``is_superuser``) zostało rozszerzone na ``is_staff`` przez ustawienie
  ``FORMDEFAULTS_CAN_EDIT_SYSTEM_WIDE``.

  Przyciski pojawiają się m.in. w nowych raportach, raporcie slotów,
  rankingu autorów, importerze publikacji, importach (POLON, dyscypliny,
  lista IF, lista ministerialna, pracownicy, udziały) oraz w wizardzie
  zgłoszenia publikacji. Stary admin ``/admin/formdefaults/...`` nadal
  działa.
- Wizard importera publikacji (CrossRef): gdy dopasowanie autora trafia
  na **wielu** kandydatów (np. dwóch autorów o tym samym nazwisku — z
  diakrytykiem i bez), system pre-zaznacza najlepszego (więcej publikacji,
  ORCID), zapisuje pełną listę z metadanymi i wyświetla rozwijaną listę
  alternatyw z badge'ami `pewność` / `liczba publikacji` / `ORCID`.
  Kliknięcie kandydata przepina dopasowanie jednym requestem.

### Usunięto

- Aplikacja ``dynamic_columns`` została wydzielona do osobnego pakietu
  ``django-dynamic-columns`` (publikacja na PyPI, repo
  ``iplweb/django-dynamic-columns``). Z perspektywy BPP nic się nie
  zmienia: konfiguracja w ``settings.DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS``
  oraz ``settings.DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES`` pozostaje
  identyczna, a wszystkie zapisane przez użytkowników wybory kolumn w
  adminie nadal działają — pakiet zachowuje te same tabele i migracje
  co poprzednia, wbudowana w BPP aplikacja.
- Usunięto martwą aplikację ``create_test_db`` wraz z jej jedynym
  poleceniem ``manage.py create_test_db``. Komenda wykorzystywała
  sztuczkę z ``manage.py test --keepdb`` do utworzenia bazy testowej
  i nie była już używana przez CI ani lokalny workflow. Aktualnie
  funkcjonalność pokrywają ``pytest-testcontainers`` (testy
  integracyjne na ulotnym kontenerze PostgreSQL) oraz
  ``run-site --from-dump`` (odtworzenie bazy z dumpa).


## bpp 202605.1372 (2026-05-04)

### Naprawione

- Naprawiono healthcheck lekkiego `authserver`-a, który zwracał
  `503 Service Unavailable` przez `AttributeError` na nieistniejącym
  `settings.CELERY_BROKER_URL`. Sonda Redis jest teraz pomijana, gdy
  ustawienia nie konfigurują brokera Celery — `authserver` nie używa
  kolejki zadań, więc jego stan zdrowia nie zależy od Redis-a. Sonda
  PostgreSQL działa bez zmian.

## bpp 202605.1371 (2026-05-04)

### Naprawione

- Batchowe enqueueowanie do PBN
  (`queue_pbn_export_batch`) raportuje teraz nieoczekiwane
  błędy do Rollbara i logów zamiast cicho je połykać.
  Wcześniej blok `except Exception: pass` w pętli po
  rekordach pochłaniał wszystkie wyjątki (DB error,
  integrity error, programmer error) — pojedynczy zły
  rekord nie zatrzymywał batcha, ale operator nie miał
  żadnej widoczności co poszło nie tak. Brakujące rekordy
  (`DoesNotExist`) i już-w-kolejce
  (`AlreadyEnqueuedError`) nadal są pomijane bez alertu —
  to nie są błędy.
- Endpoint `/health/` faktycznie sprawdza teraz dostępność
  PostgreSQL (`SELECT 1`) i Redisa (`PING` z 2-sekundowym
  timeoutem) i zwraca `503` z listą niedostępnych komponentów
  zamiast bezwarunkowego `200 OK`. Docker healthcheck
  serwisów `appserver` / `authserver` wykrywa teraz awarię
  bazy lub brokera — wcześniej kontener pozostawał oznaczony
  jako „healthy” mimo że strona nie była w stanie obsłużyć
  żadnego requestu.
- Endpointy `/bpp/api/upload-punktacja-zrodla/`,
  `/bpp/api/punktacja-zrodla/`, `/bpp/api/rok-habilitacji/`,
  `/bpp/api/ostatnia-jednostka-i-dyscyplina/` oraz
  `/bpp/api/pubmed-id/` wymagają teraz zalogowania.
  Wcześniej były `csrf_exempt` bez sprawdzania
  uwierzytelnienia — w szczególności
  `upload-punktacja-zrodla` przyjmował anonimowe POST-y
  i tworzył wpisy `Punktacja_Zrodla` w bazie. Adminowy JS
  nadal działa bez zmian (sesja zalogowanego użytkownika);
  zmiana blokuje wyłącznie wywołania nieautoryzowane.
- Naprawiono auto-uzupełnianie jednostki i dyscypliny przy dodawaniu
  autora w publicznym formularzu „Zgłoś publikację”. Skrypt
  `autorform_dependant.js` wysyłał POST do
  `/bpp/api/ostatnia-jednostka-i-dyscyplina/` bez tokenu CSRF —
  publiczne `base.html` (w przeciwieństwie do admin-owego) nie ma
  globalnego `$.ajaxSetup` dodającego nagłówek `X-CSRFToken`,
  więc żądanie kończyło się odpowiedzią 403 i pola nie były
  wypełniane. Skrypt czyta teraz `csrfmiddlewaretoken` z ukrytego
  pola formularza i dokleja go do danych żądania.
- Strony przeglądania `/bpp/browse/autorzy/`,
  `/bpp/browse/zrodla/` i `/bpp/browse/jednostki/`
  generują listę aktywnych literek alfabetu jednym zapytaniem
  `SELECT DISTINCT` zamiast 26+ osobnych `EXISTS`-ów
  (po jednym na każdą literkę z osobnym matchingiem dla
  polskich znaków). Polskie diakrytyki nadal mapują się na
  kanoniczne litery (`Ą` → `A`, `Ł` → `L` itd.).
- Task `pbn_downloader_app.tasks.download_institution_publications`
  nie wykonuje już redundantnego sprawdzenia stanu
  „running” poza transakcją. Atomowy check-and-create
  w `create_task_with_lock` nadal zapobiega duplikatom;
  usunięcie wcześniejszego, nie-atomowego check-a likwiduje
  race-window, w którym dwa workery przechodziły check, oba
  otrzymywały `ValueError` w wyścigu o lock i jeden niepotrzebnie
  failował zamiast po prostu czekać.
- Taski importu dyscyplin (`stworz_kolumny`,
  `przeanalizuj_import_dyscyplin`,
  `integruj_import_dyscyplin`) faktycznie ryglują rekord
  `Import_Dyscyplin` przez `SELECT ... FOR UPDATE`.
  Wcześniej wywołanie `select_for_update().filter(pk=pk)`
  zwracało leniwy `QuerySet`, który nigdy nie był ewaluowany —
  SQL z klauzulą `FOR UPDATE` nie szedł do bazy, a lock
  realnie nie istniał. Przy równoczesnym przetwarzaniu tego
  samego importu (np. user kliknie „Przeanalizuj” dwa razy
  pod rząd) workery mogły deptać sobie po polach FSM.
- `test_health_check_returns_503_when_db_down` zatruwał blocker
  `pytest-django` dla całego workera xdist (`monkeypatch.setattr` na
  `ConnectionProxy` wstrzykiwał bound `_blocking_wrapper` do
  `connections[default].__dict__`, co nadpisywało class-level patch
  i czyniło `django_db_blocker.unblock()` bezskutecznym). Multiseek
  testy padały deterministycznie 50 errors w `setup_databases`.
  Patch zmieniony na `health._check_db` (symetrycznie do testu
  redis-down). Dodatkowo middleware `test_logging_*` w
  `test_page_validation.py` zyskały autouse fixture wpinający
  `caplog.handler` bezpośrednio do loggera `django.request` —
  po zmianie `propagate=False` z commita audytu caplog nie widział
  WARNING-ów o zablokowanych żądaniach.

### Usprawnienie

- Admin interface dla aplikacji `importer_publikacji`: superuser może
  przeglądać historię importu publikacji (model `ImportSession` z
  oryginalnym tekstem BibTeX w polu `raw_data`) oraz dopasowanych
  autorów (model `ImportedAuthor`). Obie klasy zarejestrowane w
  Django adminie jako read-only (bez możliwości ręcznego tworzenia
  lub edycji, podgląd tylko). Lista sesji wspiera filtrowanie po statusie,
  dostawcy, dacie i autorach; wyszukiwanie po identyfikatorze, tytule,
  DOI; szczegóły sesji pokazują sformatowane JSON `raw_data`,
  `normalized_data`, `matched_data` oraz tabelę autorów z
  linkami do dopasowanych obiektów BPP.

- Deduplikator autorów: gruntowna przebudowa UI. Tytuł i pozycje
  menu uproszczone z "Deduplikator autorów PBN" na "Deduplikator
  autorów" (bez znacznika BETA), wpis dodany dodatkowo do podmenu
  "Operacje". Tryb skanowania (PBN/ogólny) prezentowany jest jako
  kolorowy badge przy "Główny rekord autora", filtr "Pokaż wyniki"
  zmieniony z radio-buttonów na poziomy button-group.

  Przyciski na karcie każdego potencjalnego duplikatu pogrupowane
  w trzy logiczne sekcje: Podgląd (otwórz wyd. ciągłe/zwarte,
  redagowanie, stronę główną, PBN), Decyzja ("Nie jest duplikatem
  głównego autora", usuń autora bez publikacji), Scalanie (cztery
  warianty scalania). Przyciski "Scal + ustaw dyscyplinę" oraz
  "Scal + ustaw subdyscyplinę" są ukryte, gdy główny autor nie ma
  żadnej dyscypliny.

  Powody podobieństwa renderowane są jako kolorowe chipy z ikonami
  Foundation, z tonami match/info/weak/warn dobranymi do siły
  przesłanki. Procent pewności jest sklampowany do zakresu 0–100%
  (wcześniej widoczne były wartości typu 140% wynikające z surowego
  score).

  Naprawione: oznaczenie autora jako nie-duplikat (przycisk
  "Nie jest duplikatem głównego autora") wykonuje się teraz przez
  AJAX z fadeOut karty, zamiast przeładowywać widok i przeskakiwać
  do kolejnego głównego autora. Naprawiono też "Scal wszystkie",
  który dla kandydatów z trybu ogólnego zwracał błąd 400 (JS
  wysyłał `main_scientist_id` zamiast `main_autor_id`); brakujące
  parametry trafiają teraz dodatkowo do Rollbara.

- Deduplikator autorów: nowy tryb "ogólny" znajdujący duplikaty wśród
  autorów spoza listy pracowników instytucji w PBN. Jeden przycisk
  "Skanuj duplikaty" uruchamia obie fazy (PBN + ogólna) sekwencyjnie.
  Widok pozwala filtrować wyniki radio-button-em (PBN/Ogólny/Oba),
  eksport XLSX zawiera kolumnę "Tryb". Anulowanie fazy ogólnej skutkuje
  statusem "Częściowo zakończone" — wyniki PBN pozostają dostępne.

- Formularz zgłaszania publikacji: pomocniczy tekst pola „Link do publikacji
  lub DOI" jest teraz dobierany w zależności od kombinacji rodzaju publikacji
  i formy dostępu — m.in. fragment o katalogach BN/NUKAT pojawia się tylko
  przy monografii i rozdziale w dostępie ograniczonym, a wzmianka o PBN
  znika dla publikacji typu „Inne". Dla rodzaju „Inne" pole nie jest
  wymagane (ponieważ tych publikacji nie wysyłamy do PBN); dla dostępu
  ograniczonego pozostaje wymagany plik PDF.

- Logi backendu Django zawierają teraz timestamp w formacie
  ISO oraz nazwę loggera, co pozwala korelować zdarzenia
  między równoczesnymi workerami w produkcji bez polegania
  wyłącznie na timestampach z `systemd` / Celery. Domyślnie
  skonfigurowane są też loggery `django.security`
  (SuspiciousOperation, DisallowedHost, niewłaściwy CSRF token),
  `django.request` (4xx/5xx requestów) i `celery`
  (retry, ack, errors). Dotychczasowy logger `pbn_import`
  zachowuje swój dawny czysty format (bez timestampu) na
  potrzeby UI pełnotekstowego importu.

- Polecenie `manage.py run_site` strumieniuje teraz logi
  runservera, celery i PostgreSQL równocześnie do jednego
  terminala z kolorowymi prefiksami (`web`, `celery`, `pg`)
  — jak `docker compose up`. Linie z różnych procesów są
  serializowane przez wątkowy multiplekser, więc się nie sklejają.
  Dodatkowo na lokalnym dev-stacku z `run_site` cookie banner
  jest automatycznie ukrywany — endpoint auto-loginu ustawia
  cookie `cookielaw_accepted=1` w odpowiedzi z przekierowaniem,
  co przy zwyczajowym workflow (uruchom `run_site` → przeglądarka
  otwiera autologin → przekierowanie na `/`) eliminuje banner.

- Task `zaktualizuj_liczbe_cytowan` (pobieranie liczby
  cytowań z Web of Science) używa teraz
  `celery_singleton.Singleton` z 2-godzinnym lockiem
  w Redisie i `time_limit=2h`. Dwa równoczesne uruchomienia
  (np. ręczne kliknięcie + zaplanowany cron) nie odpytają już
  zewnętrznego API podwójnie, a zawieszony WoS request
  nie zablokuje workera w nieskończoność.

- `manage.py run_site` zapisuje teraz numer portu runservera do
  gitignored pliku `.run_site_port` (analogicznie do
  `.run_site_token`). Agent kodujący nie musi już parsować bannera
  ani logów — składa URL z `cat .run_site_port` + `cat .run_site_token`. Plik jest ulotny: kasowany na exit run_site.

- `manage.py run_site` zapisuje teraz porty PostgreSQL i Redis-a
  (testcontainers) do gitignored plików `.run_site_pg_port` i
  `.run_site_redis_port` (analogicznie do `.run_site_port`). Agent
  kodujący może podpiąć `psql` / `redis-cli` bez parsowania bannera
  — w stdoucie banner zawiera teraz gotowe snippety dla obu narzędzi.
  Pliki są ulotne: kasowane na exit run_site.

### Usunięto

- Usunięto pozostałości po niezainstalowanej integracji
  Sentry: moduł `django_bpp.sentry_support`, jego test,
  endpoint `/sentry_test/` oraz sekcja `SENTRYSDK_*`
  w `.env.example`. Projekt używa Rollbara — żadne
  ustawienie Sentry nie było aktywne, a artefakty wprowadzały
  w błąd. Endpointy `/test_403/`, `/test_500/`
  i `/test_exception/` (do podglądu stron błędów i
  weryfikacji integracji Rollbara) pozostają.

  Z `package.json` usunięto pakiet `font-awesome 4.1.0`
  (nie był importowany przez bundle ani template'y; biblioteka
  po EOL z dostępnymi CVE). Aktywnie używany `jqueryui 1.11.1`
  zostaje — wymiana wymaga osobnej, większej zmiany.

  Z `bpp/tasks.py` usunięto martwą funkcję `my_limit()`
  i moduł-globalny słownik `task_limits` — funkcja nie była
  nigdzie wywoływana, a per-procesowy słownik nie miał szans
  działać poprawnie z wieloma workerami.

## bpp 202605.1370 (2026-05-02)

### Naprawione

- Importer publikacji wywalał się z `TypeError: '>' not supported between instances of 'NoneType' and 'int'` przy próbie utworzenia rekordu, gdy
  dane źródłowe (np. BibTeX) nie zawierały roku publikacji. Po stronie
  `ISlot` dodano obsługę `rok=None` (zwracane jest `CannotAdapt`,
  sloty nie są liczone), a w samym imporcie `_create_publication`
  waliduje obecność roku i zgłasza czytelny komunikat zamiast pełnego
  tracebacku.
- Naprawa testów Playwright (Chromium) padających na CI od commit-a `bafd8f209` (session-scoped `channels_live_server`). Daphne subprocess fork-uje z pytest worker process-u i dziedziczy monkey-patch `pytest_django._blocking_wrapper` na `BaseDatabaseWrapper.ensure_connection`, przez co każde zapytanie do DB w middleware (`django_countdown`, `bpp_setup_wizard`) crashowało z `RuntimeError: Database access not allowed` → 500 → puste strony → timeout-y Playwright. Fix: `set_database_connection` w subprocesie Daphne przywraca oryginalną implementację `ensure_connection`.

### Usprawnienie

- Dodano polecenia `dump_pbn_token` i `load_pbn_token` do
  przenoszenia tokenu PBN użytkownika między instancjami BPP — bez
  zrzutu całej bazy. `dump_pbn_token --user=<nazwa>` wypisuje JSON
  z tokenem i datą jego ostatniej aktualizacji na stdout, a
  `load_pbn_token --user=<nazwa>` czyta ten JSON ze stdin i ustawia
  te same wartości lokalnemu użytkownikowi.

  W `run_site` dodano flagę `--get-pbn-token-from USERNAME@SSH-HOST`, która automatyzuje ten transfer — łączy się po
  SSH ze wskazanym hostem (alias z `~/.ssh/config`), uruchamia
  `dump_pbn_token` w kontenerze `appserver` z katalogu
  `bpp-deploy` i wynik wgrywa do lokalnej bazy. Domyślne ścieżki i
  nazwę serwisu można nadpisać flagami `--remote-deploy-path` i
  `--remote-compose-service`.

- Nowa komenda `manage.py run_site` — uruchamia dev stack BPP w testcontainerach
  na losowych portach (PG + Redis), opcjonalnie odtwarza dump bazy
  (`--from-dump path`, autodetect `.sql` / `.sql.gz` / `.dump`), tworzy
  superusera `admin/admin`, odpala `runserver` i otwiera przeglądarkę.
  Eliminuje konflikty portów przy wielu konfiguracjach BPP na jednym serwerze.

## bpp 202604.1369 (2026-04-28)

### Naprawione

- Naprawiono generowanie `src/baseline-sql/baseline.sql`: komenda
  `baseline_rebuild` uruchamia teraz `pg_dump` *wewnątrz*
  testcontenera (`docker exec`) zamiast używać klienta z hosta.
  Gdy host miał nowszy major PostgreSQL niż obraz bazowy
  (`iplweb/bpp_dbserver:psql-16.13`), `pg_dump` w wersji 17
  wstawiał do dumpa dyrektywę `SET transaction_timeout = 0;`,
  której PostgreSQL 16 nie zna — przez co odtworzenie baseline'u
  na docelowej wersji się wywalało. Klient i serwer są teraz
  zawsze w tym samym majorze. Dodatkowo scrubber wycina takie
  linie jako safety net na wypadek przyszłych nowych dyrektyw.
- Naprawiono komunikat o przeterminowanym haśle, który pojawiał się
  użytkownikom zalogowanym przez Microsoft (`microsoft_auth`) lub
  ORCID (`orcid_integration`) bez formularza zmiany hasła. Hasłem
  takich kont zarządza zewnętrzny IdP, więc polityka wygasania nie
  powinna ich w ogóle obejmować — middleware
  `ConditionalPasswordChangeMiddleware` już to respektował, ale
  context processor `password_status` z `django-password-policies`
  nadal sprawdzał wiek hasła w bazie i ustawiał
  `password_change_required = True` w kontekście szablonu, przez co
  `base.html` renderował callout bez formularza (zmienna `form`
  istnieje tylko w widoku zmiany hasła, do którego middleware słusznie
  nie przekierowywał). Dodano
  `django_bpp.context_processors.conditional_password_status`,
  który symetrycznie pomija sprawdzenie dla backendów OAuth z
  `EXTERNAL_AUTH_BACKENDS` i deleguje do oryginalnego context
  processora wyłącznie dla zwykłego logowania `ModelBackend`.

### Usprawnienie

- CI: shardy `pytest` w workflow `Tests` nie odpalają już `make assets` przy starcie. Obraz `test-runner` ma zapieczone CSS i `.mo`
  z buildu obrazu (stage `test-runner` w `docker/bpp_base/Dockerfile`),
  więc `conftest.py` honoruje teraz zmienną `BPP_SKIP_ASSETS_BUILD=1`
  ustawioną w `docker-compose.test.ci.yml`.

  Wcześniej każdy z ośmiu równoległych shardów wpadał w
  `pytest_configure` i — z powodu braku sentinela
  `node_modules/.installed` w obrazie — odpalał pełny `yarn install` +
  `grunt build` przed pierwszym testem. Lokalny dev nie jest zmieniony:
  bez tej zmiennej `conftest.py` nadal uruchamia `make assets` jako
  safety net.

- Pipeline release-u (`make new-release` oraz `make release`)
  weryfikuje teraz zaleznosci pod katem znanych CVE PRZED zbumpieniem
  wersji i wystartowaniem builda. Nowy target `make scan-deps`
  generuje SBOM (CycloneDX) z `uv.lock` przez `uv export --no-dev`
  i puszcza go przez OSV-Scanner, Grype oraz Trivy. Jezeli ktorykolwiek
  skaner znajdzie HIGH/CRITICAL CVE, `make` zatrzyma sie z exit 1 i
  release nie ruszy — zeby pominac (na wlasna odpowiedzialnosc), uzyj
  `./bin/scan-deps.sh --no-gate`. Wymagane narzedzia: `brew install osv-scanner grype trivy`.

  Workflow `dependency-audit.yml` rozszerzony o drugi job
  `multi-scanner`, ktory na CI generuje ten sam SBOM i odpala te
  same trzy skanery jako defense-in-depth obok istniejacego gate-u
  `uv-secure`. Nowe skanery sa report-only (zapisuja markdown do
  `GITHUB_STEP_SUMMARY`, nie blokuja merga) — chodzi o widocznosc
  findings, ktorych nie wykryla baza `uv-secure`, bez ryzyka
  zablokowania PR-a falszywym pozytywem z innej bazy CVE.

## bpp 202604.1368 (2026-04-28)

### Naprawione

- Naprawiono migrację `0413_bppuser_autor_onetoone`, która kończyła
  się błędem `cannot ALTER TABLE "bpp_bppuser" because it has pending trigger events` na bazach z istniejącymi danymi. Migracja została
  oznaczona jako nieatomowa, dzięki czemu deferred triggery (`denorm`)
  odpalane przez `RunPython` wystrzeliwują przed kolejnymi
  `ALTER TABLE` na tej samej tabeli.

## bpp 202604.1367 (2026-04-28)

### Naprawione

- `MaliciousRequestBlockingMiddleware` blokował legalne żądania
  DataTables AJAX, jeśli tabela miała wiele kolumn — biblioteka
  serializuje per-kolumnowe metadane (`columns[N][data]`,
  `[search][value]`, …) do query stringu, który łatwo przekraczał
  limit 2048 znaków. Konsekwencja: kontrolki DataTables na widokach
  `/api/...` zwracały HTTP 444 zamiast danych, a integracyjne testy
  Playwright (m.in. `import_dyscyplin`) timeout'owały się czekając
  na dane, których serwer odmówił.

  Dwie zmiany:

  - Limit `MAX_FULL_PATH_LENGTH` podniesiony 2048 → 4096 znaków
    (mieści typowy DataTables-payload bez otwierania drzwi rekurencyjnym
    `?next=` od skanerów, bo te i tak obsługuje osobny check).
  - Ścieżki zawierające `/api/` są zwolnione z check'u długości pełnego
    URL — endpointy API legalnie generują wzdęte query stringi, a
    scanner-boty z rekurencyjnymi przekierowaniami i tak nie kierują
    swoich łańcuchów na `/api/`. (middleware-api-whitelist)

- Pełen suite testów Playwright zostaje przyspieszony z ~3:50 do ~2:24
  (−85 s, −38 %) bez utraty pokrycia.

  Główne źródło zysku — naprawa ukrytego buga w
  `django_bpp.playwright_util.select_select2_autocomplete`: pierwszy
  `wait_for_selector` na `#select2-{id}-container` trafiał w pełen
  30-sekundowy timeout w testach gdzie ten wariant markupu nie istnieje
  (formularze inline django-grappelli admin), zanim wpadał do bloku
  `except` z fallbackowym selektorem siostrzanym. Helper jest używany
  w 64 miejscach — każde wywołanie traciło ~30 s. Najwolniejsze testy
  jak `test_changeform_add_full_flow` (3 wywołania select2) traciły
  ~90 s na samych timeoutach.

  Naprawa: race obu selektorów przez listę `", "` w jednym
  `wait_for_selector` — zwracamy się do `.select2-selection` (zawsze
  klikalny element) zamiast container'a. Efekt:

  - `test_changeform_add_full_flow`: 97 s → 8 s
  - `test_admin_wydawnictwo_ciagle_dowolnie_zapisane_nazwisko`:
    67 s → 8 s
  - `test_procent_odpowiedzialnosci_*_dwoch_autorow` cluster:
    37–48 s → 12–18 s

  Drugi front — eliminacja antywzorców `wait_for_load_state(networkidle)`
  i sztywnych `wait_for_timeout()` w testach Playwright, zastępowane
  warunkowymi waitami (`expect(...).to_have_value()`,
  `page.expect_navigation`, polling DB/listy dialogów):

  - `test_integracyjny` (import dyscyplin): 75 s → 13 s — usunięte
    sztywne sleepy i `networkidle` na stronie z otwartym WebSocketem
  - `test_multiseek_*` (6 testów): 30+ s → ~2 s — `expect_navigation`
    zamiast `networkidle` po klikach search
  - `test_smoke` crawler: usunięty `networkidle` w pętli (zawsze
    trafiał w 10 s timeout bo strony BPP mają long-polling)
  - `test_toz_tamze`, `test_admin_forms`, `test_clarivate`,
    `test_change_form_pbn_isbn_doi_etc`, `test_change_form_pubmed`,
    `test_crossref_api_sync_playwright` — sztywne `wait_for_timeout`
    zamienione na polling licznika rekordów / listy dialogów / wartości
    pól; w przypadku dialog handlerów polling musi pompować event loop
    przez `page.wait_for_timeout` (a nie `time.sleep`), bo handler
    odpala się tylko gdy Playwright przetwarza eventy. (playwright-suite-speedup)

- Naprawiono blokowanie zapytań AJAX widgetów DataTables przez
  `MaliciousRequestBlockingMiddleware`. Limit długości pełnego URL-a
  (`MAX_FULL_PATH_LENGTH`) został podniesiony z 2048 na 8192 — DataTables
  przy ~10 kolumnach generuje query string z percent-encoded metadanymi
  kolumn (`columns%5B0%5D%5Bdata%5D=…`) przekraczający 2 KB, ale dobrze
  mieszczący się w 8 KB (zgodnie z domyślnym `large_client_header_buffers`
  nginxa i `LimitRequestLine` Apacha). Eksponencjalnie rosnące łańcuchy
  `?next=` produkowane przez bot-skannery nadal są łapane — albo przez
  nowy próg, albo przez detektor zagnieżdżonego `?next=`.

- Naprawiono błąd teardown testów `TransactionTestCase` (m.in. testów
  Playwright z `transaction=True`) — `TRUNCATE` Django flush'a wywalał
  się na FK z niezarządzanej tabeli `bpp_rekord_mat` do zarządzanej
  `bpp_charakter_formalny`. Monkey-patch `_fixture_teardown` (dodający
  `allow_cascade=True` i retry przy deadlocku) został przeniesiony z
  `src/fixtures/conftest.py` do `src/conftest.py`: ten pierwszy plik
  jest siostrzanym katalogiem względem testów i pytest go automatycznie
  NIE ładuje dla testów spoza `src/fixtures/`, więc patch nigdy nie
  zaczepiał się dla większości testów transakcyjnych.

- Naprawiono losowe failowanie kilku testów Playwrighta uruchamianych
  równolegle z `-n auto`. Testy używające session-scoped fixture
  `channels_live_server` (jeden Daphne na worker, reuse między
  testami) były wrażliwe na pollution stanu w shared ASGI procesie:
  wycieki konekcji DB i race między test'em a serwerem na widoczność
  commitowanych danych.

  Dodano function-scoped warianty `admin_page_per_test` i
  `preauth_asgi_page_per_test` (oparte o istniejący
  `channels_live_server_per_test`) — każdy test dostaje świeży
  proces Daphne. Przepięto na nie testy:

  - `test_bpp_notifications`
  - `test_global_search_logged_in`
  - `test_procent_odpowiedzialnosci_baseModel_AutorFormset_jeden_autor`
  - `test_procent_odpowiedzialnosci_baseModel_AutorFormset_dwoch_autorow`
  - `test_procent_odpowiedzialnosci_baseModel_AutorFormset_dobrze_potem_zle_dwoch_autorow`

  Pozostałe testy (~67) nadal używają szybkiego session-scoped
  `channels_live_server` — bez regresji wydajności.

## bpp 202604.1366 (2026-04-27)

### Naprawione

- Rozszerzono `MaliciousRequestBlockingMiddleware` o dwie dodatkowe
  heurystyki ograniczające szum w logach od skanerów bezpieczeństwa:

  - Pełny URL (ścieżka + query string) dłuższy niż 2048 znaków zwraca
    HTTP 444. Dotychczasowy limit 1024 znaków obejmował tylko
    `request.path` i przepuszczał wzdęte query stringi.
  - Parametr `next=` zawierający kolejne `?next=` (po dekodowaniu
    query stringu przez Django) jest blokowany jako odcisk bota
    podążającego za przekierowaniami logowania bez cookies — typowy
    wzorzec rekurencyjnie zakodowanych łańcuchów krążących między
    `/accounts/login/` a `/admin/login/`.

  Pojedynczy, prawidłowy `next=` (np. po nieautoryzowanej próbie
  wejścia do widoku `toz`) pozostaje dozwolony. (blokada-zagnezdzonych-next)

- Naprawiono renderowanie paginacji w widokach z HTMX (np. `/pbn_export_queue/`),
  gdzie stopka strony lądowała pomiędzy pagerem a tabelą. Przyczyną była
  minifikacja HTML aplikowana do fragmentów ładowanych przez
  `hx-swap="innerHTML"` — `minify-html` zaprojektowany dla pełnych
  dokumentów restrukturyzował niezamknięte/puste tagi (m.in. pusty
  `<li class="ellipsis">`) w partial-ach, rozjeżdżając DOM po wstawieniu.

  Wprowadzono prewencję systemową przeciwko regresjom tej klasy:

  - `BppMinifyHtmlMiddleware` omija minifikację gdy żądanie ma nagłówek
    `HX-Request: true` (wszystkie HTMX-owe partial-e bypassują minifier).
  - Linter `djlint` dodany do pre-commit z aktywnymi regułami
    strukturalnymi (H020 puste-tag-pair, H025 orphan-tag) — wykrywa
    podobne pułapki przed merge-em.
  - Test integralności `test_html_minify_integrity.py` weryfikuje że
    typowe trefne wzorce (puste `<li>`, `<p/>`, `<span/>`) po
    minifikacji nie rozjeżdżają struktury DOM, plus że HTMX-owe requesty
    są właściwie bypassowane.

  Dodatkowo style paginacji `pagination_with_anchor.html` przeniesione z
  inline `<style>` (re-injektowanego przy każdym HTMX-swap-ie) do
  osobnego SCSS partial-a `_pagination.scss` importowanego z głównych
  schematów (blue/orange/green). (htmx-minify-paginacja)

### Usprawnienie

- Broker Celery przeniesiony z RabbitMQ na Redis (baza `DB 1`,
  zmienna `DJANGO_BPP_REDIS_DB_BROKER`). Result backend (Redis `DB 2`)
  i routing tasków bez zmian — migracja jest neutralna funkcjonalnie.

  Usunięte zostały:

  - serwis `rabbitmq` z `docker-compose.yml` i
    `docker-compose.test.yml`,
  - zmienne `DJANGO_BPP_RABBITMQ_*` z konfiguracji oraz
    `.env.docker` / `.env.example`,
  - zależność pakietu `amqp` z `pyproject.toml`,
  - start kontenera RabbitMQ w plugin-ie `testcontainers_bpp`,
  - pozycja „RabbitMQ" z menu admina (DOCKER_SERVICES_MENU).

  Po pull-u wymagany jest `uv lock` / rebuild obrazów (zniknie
  biblioteka `amqp`); istniejące deploye po przepięciu wymagają
  `stop workers → up -d → start workers`. Zadania zalegające
  w kolejce RabbitMQ przy migracji zostaną porzucone.

  Lokalne `docker compose up` startuje teraz znacząco szybciej —
  RabbitMQ pod emulacją amd64 na arm64 potrafił rozgrzewać się
  ~3 minuty, Redis w sekundę.

  Dla deploymentów: zmiany w `bpp-deploy` (compose, init-configs,
  prometheus job, nginx routing `/rabbitmq/`) muszą zostać
  wdrożone razem z tą wersją obrazu — szczegóły w `CHANGELOG` repo
  `iplweb/bpp-deploy`.

  Dodano `CELERY_BROKER_TRANSPORT_OPTIONS` z `visibility_timeout`
  ustawionym na 6 godzin — Redis re-deliveruje zadanie po tym
  timeout-cie jeśli worker padł, więc wartość musi przekraczać
  najdłuższy realny task (PBN export, import POLON). (celery-broker-redis)

## bpp 202604.1365 (2026-04-27)

### Usprawnienie

- Uproszczono healthcheck kontenera `celerybeat` — sprawdza on teraz
  wyłącznie dostępność brokera (RabbitMQ) przez świeże połączenie AMQP,
  bez wcześniejszego dwustopniowego badania pidfile + brokera.

  Sprawdzenie żywotności procesu beata przez `/celerybeat.pid` było
  redundantne, ponieważ `celery beat` jest procesem PID 1 kontenera —
  gdy padnie, kontener wychodzi i healthcheck nie jest wtedy nawet
  uruchamiany. Pozostawienie wyłącznie sondy brokera daje to, czego
  healthcheck nie wie z samego faktu, że kontener jeszcze biegnie.

  Dodatkowo usunięto pośredni skrypt `docker/beatserver/healthcheck.sh`
  — `HEALTHCHECK` w `docker/beatserver/Dockerfile` woła teraz
  bezpośrednio `python /app/healthcheck_broker.py`.

## bpp 202604.1364 (2026-04-27)

### Naprawione

- Naprawiono renderowanie formularza zgłaszania publikacji
  (`/zglos_publikacje/`) — stopka strony była "wciągana" do
  wnętrza przycisku "następny krok" / "zakończ i wyślij do akceptacji".
  Przyczyną były XHTML-owe samozamykające się `<span class="fi-..."/>`
  przy ikonach Foundation: minifier `minify-html` (zgodnie ze
  specyfikacją HTML5) ignoruje `/` na elementach nie-void, więc span
  pozostawał otwarty, a wraz z nim zjadał także zamykający `</button>`,
  co powodowało, że dalsza zawartość strony — łącznie ze stopką — stawała
  się dzieckiem przycisku. Spany ikon zamieniono na pełną parę
  `<span></span>`.
- Przypięto wersję `sass` do `~1.99.0` w `package.json` zamiast
  `^1.91.0`. Powód: blokada przed niekontrolowanym podniesieniem do
  Sass 2.0 (które przerobi `@import` z deprecation warning na twardy
  błąd kompilacji) oraz przed minor bumps (np. 1.100.x), które mogą
  eskalować nowe kategorie deprecation warnings. Świadomy upgrade
  wymaga teraz ręcznej zmiany pinu i przeglądu konsekwencji.
- Wszystkie `uses:` w workflowach GitHub Actions zostały przepięte z ruchomych tagów (`@v6`, `@v4` itd.) na pełne 40-znakowe SHA z komentarzem wersji. Chroni przed atakami typu tag-promotion (np. atakujący przejmuje konto utrzymującego akcję i przepina tag `@v4` na złośliwy commit). Dodano także `zizmor` jako pre-commit hook by wyłapywać regresje + plik konfiguracyjny `zizmor.yml` z udokumentowanymi pre-existing tech-debt findings (osobne follow-up PR-y).
- Wyciszono `if-function` w Dart Sass podczas `make assets` — wewnętrzne
  ostrzeżenia z foundation-sites 6.9.0 (util/\_value.scss, <span id="breakpoint.scss">breakpoint.scss</span>,
  <span id="color.scss">color.scss</span>, <span id="flex.scss">flex.scss</span>, <span id="math.scss">math.scss</span>), nieusuwalne z poziomu naszego repo,
  ponieważ Foundation jest w trybie maintenance. Komentarz w
  `Gruntfile.js` wyjaśnia, dlaczego każda z trzech kategorii
  (`global-builtin`, `if-function`, `import`) jest na liście
  `silenceDeprecations`. Liczba ostrzeżeń budowy spadła z 50 do 0.

### Dokumentacja

- Audyt potwierdził, że wszystkie ścieżki instalacji w CI i Docker buildzie używają `uv sync --frozen` (deterministic install z hashami SHA-256 z `uv.lock`). Dodano `--frozen` do targetów `prepare-developer-machine-*` w Makefile (pierwsze setup deweloperskie). Powstał `docs/SECURITY_PRACTICES.md` agregujący polityki bezpieczeństwa BPP.
- Dodano `SECURITY.md` z polityką zgłaszania luk bezpieczeństwa (preferowany kanał: GitHub Security Advisory) oraz SLA dla łat. README odsyła do polityki zamiast publicznego issue trackera.
- Jawnie zadeklarowano PyPI jako jedyny domyślny indeks `uv` w `pyproject.toml`. Chroni przed dependency confusion (publikacją zlosliwego pakietu na PyPI o tej samej nazwie co przyszly prywatny pakiet).

### Usprawnienie

- BPP nie jest już instalowany jako Python package — wszystkie `uv sync` używają `--no-install-project`. Usunięto `[project.scripts]` (`bpp-manage.py` był dead code) i `[project.entry-points."pytest11"]` (workspace install nie jest potrzebny). Plugin `testcontainers_bpp` ładowany teraz przez `-p testcontainers_bpp.plugin` w `pytest.ini` addopts. Udokumentowano politykę wheel-only z 11 pre-existing sdist-only deps jako accepted exceptions w `pyproject.toml` `[tool.uv]` komentarzu.

- Dodano `cooldown` do `.github/dependabot.yml` dla wszystkich trzech ekosystemów (Python/uv, GitHub Actions, Docker). Aktualizacje czekają 3 dni (major: 7) zanim Dependabot otworzy PR — chroni przed wciąganiem swieżo skompromitowanych wersji (np. atak typu LiteLLM 2.5h przed quarantine). Aktualizacje security (CVE) automatycznie omijają cooldown.

- Dodano `make uv-lock-cooldown` jako defense-in-depth do Dependabot cooldown — ręczne wywołanie `uv lock` z 3-dniowym oknem ostygania (pakiety opublikowane w ostatnich 3 dniach są wykluczane). Pakiety in-house (`*-iplweb`) zwolnione z cooldownu (atak na konto teamu uderzylby je tak czy tak). Override `CUTOFF` przez env var.

- Dodano workflow `Dependency vulnerability scan` (`.github/workflows/dependency-audit.yml`) używający `uv-secure` do skanowania `uv.lock` pod kątem znanych CVE. Triggers: zmiany w `uv.lock`/`pyproject.toml`, weekly cron poniedziałek 6:00 UTC, manualny `workflow_dispatch`. Gate: HIGH/CRITICAL z dostępnym fix-em failuje workflow; LOW/MEDIUM raportowane w job summary. Przy okazji wprowadzania bumpniety `jaraco.context` z 6.0.1 do 6.1.2 (GHSA-58pv-8j8x-9vj2 — ReDoS w transitive zależności).

- Uruchamianie testów na świeżej maszynie nie wymaga już hostowego klienta
  `psql`. Plugin `testcontainers_bpp` mountuje `baseline.sql` jako
  `/docker-entrypoint-initdb.d/01-baseline.sql` w kontenerze Postgresa,
  więc wbudowany entrypoint obrazu sam ładuje dump przy starcie — wewnątrz
  kontenera, bez udziału hosta. Plugin ustawia też
  `DJANGO_BPP_TEST_TEMPLATE=bpp`, dzięki czemu Django tworzy `test_bpp`
  przez natywne `CREATE DATABASE … WITH TEMPLATE bpp` (instant clone w
  silniku), zamiast ponownie odgrywać dump przez `psql`. Hostowy `psql`
  pozostaje wymagany tylko dla `manage.py baseline_load` i scenariusza
  `--no-testcontainers` (gdzie usługi dostarcza docker-compose).

  Konwencja lokalizacji baseline: `src/baseline-sql/baseline.sql`;
  override przez `BPP_BASELINE_SQL_PATH`. Patch w
  `django_pg_baseline.patches` dodatkowo zamyka połączenie Django i
  ubija pozostałe sesje na bazie-szablonie (`pg_terminate_backend`)
  przed CREATE, żeby Postgres pozwolił na clone.

## bpp 202604.1363 (2026-04-27)

### Usprawnienie

- Workerzy Celery emituja teraz eventy lifecycle (`worker-online`,
  `worker-heartbeat`, `worker-offline`) oraz eventy zadan
  (`task-received`, `task-started`, `task-succeeded`,
  `task-failed`) na RabbitMQ. Dzieki temu Flower poprawnie pokazuje
  status workerow (online/offline) oraz historie wykonywanych zadan.
  Wczesniej workerzy startowali z `task events: OFF` i Flower nie
  widzial ich w ogole.

## bpp 202604.1362 (2026-04-26)

### Naprawione

- Zaktualizowano zależności bezpieczeństwa wskazane przez Dependabot:
  `werkzeug` `3.1.3` → `3.1.8` (naprawa `safe_join()` dla
  nazw urządzeń specjalnych Windows; transient dep przez
  `pytest-httpserver`) oraz `sqlparse` `0.5.3` → `0.5.5`
  (DoS przy formatowaniu list krotek; transient dep przez Django).

### Usunięto

- Usunięto nieużywaną zależność deweloperską `PyPDF2` z
  `pyproject.toml`. Testy PDF korzystają z pakietu `pypdf`,
  który trafia do środowiska jako zależność tranzytywna
  `xhtml2pdf`. `PyPDF2` jest nieutrzymywany i posiadał alert
  bezpieczeństwa Dependabot bez dostępnej poprawki.

## bpp 202604.1361 (2026-04-21)

### Usprawnienie

- Autorzy powiązani z kontami użytkowników mogą teraz przeglądać swoje
  własne metryki ewaluacyjne. Dodano dwupoziomowy system uprawnień: pełny
  dostęp (administratorzy i grupa "wprowadzanie danych") oraz dostęp
  autorski (tylko podgląd własnych metryk). Dodano pole BppUser.autor
  (OneToOneField) łączące konta użytkowników z rekordami autorów,
  automatyczne dopasowywanie po adresie e-mail, stronę profilu użytkownika
  oraz link "Mój profil" w menu nawigacji. (freshdesk-308)

## bpp 202604.1360 (2026-04-20)

### Usprawnienie

- Zmniejszono rozmiar obrazów Docker o ~25% (z ~1.67 GB do ~1.25 GB
  rozpakowanego `iplweb/bpp_appserver`). Zmiany w `docker/bpp_base`:
  - `collectstatic` uruchamiany w builder stage — `node_modules`
    (~327 MB) nie trafia już do runtime, shipowany jest tylko pre-
    populowany `/app/staticroot`.
  - `uv` usunięty ze stage `runtime` — entrypointy używają
    `python`/`celery`/`uvicorn`/`gunicorn` wprost z `.venv/bin`.
  - Poprawiono błąd w zmiennej `PATH` (wskazywała `/.venv/bin`
    zamiast `/app/.venv/bin`) — działało to tylko dzięki `uv run`.
  - `pygad` instalowany bez `matplotlib` (biblioteka używana wyłącznie
    dla nieużywanych funkcji plotowania zbieżności algorytmu genetycznego).
  - `uv sync` ograniczony do realnych extras produkcyjnych
    (`--extra ldap --extra office365`) zamiast `--all-extras`;
    `testcontainers` oraz pakiety z grupy dev nie trafiają już do
    obrazu.
  - `gunicorn` oraz `watchdog` przeniesione do głównych zależności
    w `pyproject.toml` — wcześniej były doinstalowywane runtime'owo
    przez `uv pip install`.
  - Katalogi `tests` na poziomie aplikacji oraz `src/integration_tests`
    nie są już kopiowane do obrazów produkcyjnych.

## bpp 202604.1359 (2026-04-20)

### Naprawione

- Stopka na stronie głównej potrafiła wyświetlić się wewnątrz prawej
  kolumny (sekcja „Najnowsze rekordy ze streszczeniem") zamiast na
  dole jako pełnoszerokościowy pasek. Przyczyną było użycie filtra
  `truncatewords` (który nie zna się na HTML) na streszczeniach
  publikacji zawierających znaczniki z bazy (np. `<jats:p>`).
  Truncate obcinał tekst w środku znacznika, pozostawiając niedomknięte
  tagi, przez co przeglądarka dopasowywała zamknięcia dopiero na
  stopce. Przełączono na `truncatewords_html`, który zamyka otwarte
  tagi w punkcie obcięcia i utrzymuje poprawne drzewo DOM.

## bpp 202604.1358 (2026-04-20)

### Naprawione

- Pole „Nazwa użytkownika" na stronie `/accounts/login/` było
  wyświetlane bez stylu Foundation — wąskie, niskie, wyraźnie inne
  niż pole „Hasło". Przyczyną była agresywna minifikacja HTML przez
  `django-minify-html` usuwająca atrybut `type="text"` (domyślny
  w HTML5), do którego odwołuje się Foundation 6 przez selektor
  `input[type="text"]`. Po skonfigurowaniu middleware z opcją
  `keep_input_type_text_attr=True` atrybut jest zachowywany i pole
  wygląda tak samo jak pozostałe pola tekstowe w systemie.

  Dodatkowo włączono `keep_closing_tags=True` — treści z bazy
  (np. znacznik `<jats:p>` w abstraktach publikacji) po zrzuceniu
  opcjonalnych `</li>`/`</p>` potrafiły rozjechać drzewo DOM
  i przesłaniać stopkę na stronie głównej.

  Zaktualizowano rok w stopce na 2026.

### Usprawnienie

- Zastąpiono nieutrzymywany pakiet `django-fsm` jego aktywnie
  rozwijanym forkiem `django-fsm-2`. API pozostało niezmienione
  (`from django_fsm import FSMField, transition, GET_STATE`),
  więc zmiana jest przezroczysta dla kodu i migracji bazy danych.
  Dzięki temu znika ostrzeżenie `UserWarning` o braku wsparcia
  dla `django-fsm`.

## bpp 202604.1357 (2026-04-19)

### Naprawione

- Context processor `bpp.context_processors.constance_config` używa
  teraz `constance.utils.get_values_for_keys` zamiast
  `getattr(config, key)`. Od django-constance 4.x
  `Config.__getattr__` wykrywa aktywną pętlę `asyncio` i zwraca
  `AsyncValueProxy` zamiast bezpośredniej wartości. Django test
  client w nowszych wersjach startuje pętlę wewnętrznie, więc w
  testach (i faktycznie w ASGI-runtime) szablony renderujące
  `{{ WYDRUK_MARGINES_GORA|default:"2cm" }}` emitowały
  `RuntimeWarning: Synchronous access to Constance setting 'WYDRUK_MARGINES_*' inside an async loop`.
  `get_values_for_keys` idzie prosto do backendu, bez detekcji
  pętli, więc działa identycznie w obu kontekstach i nie odpala
  warningu.

- Dodano filtr w `pytest.ini` wygłuszający `DeprecationWarning: pkg_resources is deprecated` pochodzący z `oaipmh/common.py`
  (pyoai 2.5.0). Kod jest upstream-owy, nie mamy forku — filtr jest
  adekwatny do istniejącego już wpisu dla `oaipmh.server`.

- Dodano stabilne `order_by` do QuerySetów, które były stronicowane
  bez jawnego sortowania. Django emitowało wtedy
  `UnorderedObjectListWarning: Pagination may yield inconsistent results with an unordered object_list`, a kolejne strony mogły
  zwracać zduplikowane lub pominięte rekordy.

  Poprawione miejsca:

  - Autocomplete w `bpp.views.autocomplete`: `Dyscyplina_Naukowa`
    (`kod`), `Wydawnictwo_Zwarte` dla wydawnictwa nadrzędnego i
    wariantów admina (`tytul_oryginalny`), `Wydawnictwo_Ciagle`
    admin (`tytul_oryginalny`), `Zrodlo` (`nazwa` — zarówno
    bazowy queryset jak i `QuerySetSequence` z priorytetami PBN).
  - `pbn_wysylka_oswiadczen.views.PublicationListView` — combined
    `QuerySetSequence` sortowany `-rok, tytul_oryginalny, pk`.
  - `RaportSlotowUczelnia.get_details_set()` — sortowanie po
    `autor__nazwisko, autor__imiona, pk` dla stabilnej paginacji
    szczegółów raportu.
  - `RozbieznosciView` — dodano `Meta.ordering = ["id"]` (bazowy
    abstrakcyjny model już miał tę opcję, ale lokalne `Meta` ją
    nadpisywało). Migracja `0021` to wyłącznie `AlterModelOptions`
    (model jest `managed = False`, brak DDL).

- Mocki danych testowych PBN dla endpointów paginowanych są teraz
  owinięte w `fixtures.pbn_api.pbn_pageable_json` — zgodnie z
  rzeczywistym kształtem odpowiedzi PBN (`{content, pageable, number, totalElements, totalPages, ...}`). Wcześniej mocki zwracały
  płaską listę / pustą listę, co w
  `PBNClient._pages` triggerowało
  `RuntimeWarning: PBNClient.{get,post}_page request for ... did not return a paged resource, maybe use PBNClient.{get,post} (without 'page') instead`. Produkcyjne wywołania
  (`search_publications`, `get_institution_publication_v2`,
  `get_institution_statements_of_single_publication`) pozostają bez
  zmian — to są paginowane endpointy PBN, więc `get_pages` /
  `post_pages` są poprawne; problem był tylko w mockach.

  Poprawione pliki testowe:

  - `src/pbn_api/tests/test_client_sync.py`
  - `src/pbn_api/tests/test_client_helpers.py`
  - `src/pbn_api/tests/test_bpp_admin_helpers.py`
  - `src/bpp/tests/test_views/test_api.py`

- Naprawiono `ValueError: Plugin already registered under a different name` przy zbieraniu testów — `fixtures.conftest` został usunięty
  z listy `pytest_plugins` w `src/conftest.py`. Plik `conftest.py`
  jest auto-rejestrowany przez pytest pod pełną ścieżką, więc
  równoległa rejestracja pod nazwą moduły powodowała kolizję.

- Naprawiono `fixture 'kierunek_studiow' not found` w testach
  `test_KierunekStudiowQueryObject` — fixture przeniesiony z
  `src/fixtures/conftest.py` do `src/fixtures/conftest_models.py`,
  który jest zarejestrowany w `pytest_plugins` i tym samym widoczny
  globalnie. Fixture w zwykłym `conftest.py` był dostępny tylko dla
  testów w podrzędnych katalogach.

- Naprawiono błąd testów VCR (`AttributeError: property '_get_version_string' of 'VCRHTTPResponse' object has no setter`)
  występujący po podniesieniu `vcrpy` do 8.1.1. W `conftest.py`
  usunięto workaround rejestrujący `version_string` jako
  read-only `property` — nowa wersja `vcrpy` ustawia ten atrybut
  natywnie w `VCRHTTPResponse.__init__`, a stary shim kolidował
  z tą inicjalizacją.

- Naprawiono zapis naive datetime do pól `DateTimeField` w kilku
  miejscach kodu produkcyjnego, które używały `datetime.now()`
  zamiast `django.utils.timezone.now()`. Przy `USE_TZ=True` Django
  wywoływało `RuntimeWarning: received a naive datetime while time zone support is active` i interpretowało wartość w lokalnej strefie
  czasowej — co przy zmianach DST mogło prowadzić do niespójności
  dat w bazie.

  Zasięg zmian:

  - `OptimizationRun.finished_at` — zapisywane w
    `ewaluacja_optymalizacja.tasks.optimization` oraz w komendach
    `solve_uczelnia` i `solve_evaluation`.
  - `remove_old_objects` (`bpp.util`) — filtr wieku plików
    używany m.in. przez `remove_old_oswiadczenia_export_files`
    i `remove_old_integrator_files`.
  - `TemplateAdmin.template_updated` — filtr rekordów do
    przebudowy cache opisu bibliograficznego.

- Podniesiono zależność `MOAI-iplweb` do 2.0.2. Nowa wersja forka
  zastępuje przestarzałe `pkg_resources` (`iter_entry_points`,
  `working_set`) przez standardowe `importlib.metadata` — eliminuje
  16 ostrzeżeń `DeprecationWarning: pkg_resources is deprecated as an API` pojawiających się przy uruchamianiu testów i zbieraniu pluginów
  OAI.

- Przeniesiono rejestrację generatorów `model_bakery` dla
  `ArrayField` i `SearchVectorField` z imperatywnego
  `setup_model_bakery()` do deklaratywnego
  `BAKER_CUSTOM_FIELDS_GEN` w `django_bpp.settings.base`. Dzięki
  temu generatory są znane od startu Django, niezależnie od kolejności
  ładowania plików `conftest.py` — eliminuje sporadyczne
  `TypeError: field search type <SearchVectorField> is not supported by baker` w testach uruchamianych bez załadowanego
  `src/fixtures/conftest.py`.

- Pytest nie emituje już ostrzeżeń `PytestAssertRewriteWarning: Module already imported so cannot be rewritten; fixtures.conftest_*`
  (85 wystąpień w poprzednim runie). Przywrócono deklarację
  `pytest_plugins = [...]` w top-level `src/conftest.py` — pytest
  rejestruje `fixtures.conftest_{models,publications,system,browser, disciplines}` jako pluginy z aplikowanym assert-rewritingiem
  przed ich pierwszym importem.

  Jednocześnie `fixtures/__init__.py` przestał eager-importować
  `conftest_*` — wcześniejsze `from .conftest_X import *`
  pociągało te moduły przez łańcuch
  `from fixtures.playwright_fixtures import ...` → `fixtures/ __init__.py` PRZED rejestracją jako plugin, co właśnie generowało
  ostrzeżenia.

  Stałe (`NORMAL_DJANGO_USER_LOGIN/PASSWORD`, `JEDNOSTKA_UCZELNI`,
  `JEDNOSTKA_PODRZEDNA`) przeniesione do nowego modułu
  `fixtures.const`, żeby `from fixtures import X` mogło je
  re-eksportować bez ściągania modułów-pluginów.

- Usunięto `RuntimeWarning: Model 'long_running.testreport' was already registered` w testach `long_running`. Testowy model
  `TestReport` został przeniesiony z inline'owej definicji we
  fixturze do `test_bpp.models` wraz z migracją, dzięki czemu
  model jest rejestrowany w `apps` tylko raz, a nie przy każdym
  wywołaniu fixture'a.

- Usunięto redundantne dekoratory `@pytest.mark.django_db` nałożone
  na fixtury w plikach `conftest.py`. Pytest 8 ostrzegał
  `PytestRemovedIn9Warning: Marks applied to fixtures have no effect`, a sam marker i tak nie miał efektu — dostęp do bazy
  danych w fixturach jest dziedziczony z testu wywołującego. W pytest 9
  stosowanie markerów na fixturach będzie błędem.

- Wyciszono `RemovedInDjango60Warning: The FORMS_URLFIELD_ASSUME_HTTPS transitional setting is deprecated` w konfiguracji pytest
  (`pytest.ini`). Ustawienie zostaje, bo jest intencjonalnym opt-in
  na domyślne zachowanie Django 6.0 — jego usunięcie w 5.x przywróci
  warningi z `forms.URLField` dla URL-i bez schematu. Filter do
  zdjęcia razem z samym ustawieniem podczas upgrade na Django 6.0.

- Wyrównano `class Meta: model = ...` w tabelach `django-tables2`
  do faktycznego typu wierszy w QuerySecie. Dotychczas wyświetlane były
  ostrzeżenia `UserWarning: Table data is of type <X> but <Y> is specified in Table.Meta.model`:

  - `RankingAutorowTable` — `model = Autor` → `model = Sumy`
    (dane pochodzą z `Nowe_Sumy_View` / `Sumy`, nie bezpośrednio
    z `Autor`).
  - `RaportSlotowUczelniaTable` — `model = Cache_Punktacja_Autora_Query` → `model = RaportSlotowUczelniaWiersz` (widok listy iteruje po rekordach
    `RaportSlotowUczelnia.raportslotowuczelniawiersz_set`).

  `Meta.model` w `django-tables2` służy tylko do introspekcji pól;
  poza zniknięciem samego ostrzeżenia zachowanie tabel nie uległo
  zmianie.

- Zamieniono zależność `django-dbtemplates` na utrzymywany przez IPLweb
  fork `django-dbtemplates-iplweb` (\>=4.3.2). Fork używa
  `importlib.metadata` zamiast przestarzałego `pkg_resources`, co
  likwiduje `DeprecationWarning: pkg_resources is deprecated as an API`
  podczas uruchamiania testów i serwera. Nazwa importu (`dbtemplates`)
  nie zmienia się — kod aplikacji nie wymaga modyfikacji.

- Zbumpowano `MOAI-iplweb` z `==2.0.0` do `>=2.0.1` (release
  2.0.1 zawiera fix `datetime.utcnow()` → `datetime.now(UTC)`).
  Zniknęły ostrzeżenia `DeprecationWarning` z `moai/oai.py`.

  Dodano dwa targetowane filtry w `pytest.ini` dla pozostałych
  zewnętrznych warningów, których nie mamy gdzie naprawić w bpp:

  - `oaipmh.server` (paczka `pyoai` 2.5.0) — wywołuje
    `datetime.utcnow()`; nie mamy forka, zgłoszenie upstream
    w toku.
  - `webtest.forms` (paczka `webtest` 3.0.7) — używa
    `bs4.findAll` zamiast `find_all`; nie mamy forka, zgłoszenie
    do `Pylons/webtest` w toku.

  Zmienione zależności tranzytywne (uv downgrade wymuszone przez
  moai-iplweb `sqlalchemy<2` i `setuptools<80`): `sqlalchemy 2.0.44 → 1.4.54`, `setuptools 80.9 → 79.0`.

- Zbumpowano `django-denorm-iplweb` z `>=1.10.1` do `>=1.10.2`.
  Release 1.10.2 dodaje `get_joining_fields()` do inline'owej
  klasy `JoinField` w `TriggerFilterQuery` (`denorm/ denorms.py`), dzięki czemu Django 6.0 już nie emituje
  `RemovedInDjango60Warning: The usage of get_joining_columns() in Join is deprecated`.

- `import_polon` zapisuje teraz pola `Autor_Dyscyplina.zatrudnienie_od`
  i `zatrudnienie_do` jako tz-aware `datetime`. Wcześniej
  `normalize_date()` zwracał naiwny `datetime` (z `dateutil.parser`),
  przez co Django przy `USE_TZ=True` emitowało `RuntimeWarning: received a naive datetime` i interpretowało wartość w lokalnej strefie
  czasowej, co przy DST mogło powodować niespójności.

- `long_running.util.wait_for_object` nie blokuje już workera
  `time.sleep`-em. W razie `DoesNotExist` woła
  `current_task.retry(countdown=1, max_retries=no_tries)` — celery
  planuje ponowne uruchomienie tego samego zadania za sekundę, a worker
  obsługuje w tym czasie inne zadania. Po wyczerpaniu prób celery
  podnosi oryginalny `DoesNotExist`. Zniknął też
  `DeprecationWarning` emitowany przy każdym wywołaniu.

  Kontrakt: funkcję wywołujemy wyłącznie z kontekstu zadania celery
  (`task.delay(...)`, `.apply_async(...)`, `.apply(...)`).
  Wywołanie funkcji-zadania wprost jako zwykłej funkcji
  (`task_func(pk)`) nie ustawia `current_task` i omija mechanizm
  retry. Testy, które wcześniej wołały `analyze_file` i
  `task_sprobuj_wyslac_do_pbn` bezpośrednio, zostały przerobione
  na wywołanie przez celery (`.delay(...).get()` albo
  `.apply(args=..., ...).get()` — `.apply()` potrzebne tam, gdzie
  test mockuje `task.apply_async` do weryfikacji re-schedulowania
  i wtedy `.delay()` trafiłoby w mock zamiast uruchomić body
  zadania).

### Dokumentacja

- Workflow `Docker - oficjalne obrazy`
  (`.github/workflows/build-docker-images.yml`) buduje i publikuje
  obrazy docker automatycznie tylko przy pushu na `master`. Dla
  branchy `feature/**`, `fix/**`, `hotfix/**` build odpala się
  tylko wtedy, gdy w root repo istnieje pusty plik flaga
  `.docker-build` — zmiana oszczędza Docker Cloud Build minuty
  zużywane przez każdy push na długie feature-branche. Ręczne
  uruchomienie niezależnie od flagi: `gh workflow run build-docker-images.yml --ref <branch>` (lub GUI GitHub Actions).

  Aby włączyć auto-build na branchu:

      touch .docker-build
      git add .docker-build && git commit -m "ci: enable docker auto-build"

  Aby wyłączyć:

      git rm .docker-build && git commit -m "ci: disable docker auto-build"

### Usprawnienie

- Migracja do Django 5.2 LTS. System korzysta teraz z Django w wersji
  5.2.x zamiast 4.2.x; 4.2 LTS wchodzi w fazę EOL w kwietniu 2026 i
  traci wsparcie bezpieczeństwa.

  W ramach migracji zaktualizowano pakiety zależne do wersji
  kompatybilnych z Django 5.2: `django-crispy-forms`, `django-mptt`,
  `django-tables2`, `django-taggit`, `django-filter`,
  `django-import-export` (z 3.x na 4.x), `django-grappelli` (z 3.x
  na 4.x), `django-fsm`, `django-reversion`, oraz `Unidecode`.

  Porzucone `django-htmlmin` (brak wydań od 2019 r.) zastąpione przez
  utrzymywane `django-minify-html` — minyfikator HTML oparty o
  rust-owy `minify-html`. Middleware jest aktywne tylko w środowisku
  produkcyjnym, tak jak dotychczas.

  Nie wymaga interwencji administratora — wszystkie zmiany są
  transparentne na poziomie interfejsu użytkownika i panelu admina.

## bpp 202604.1356 (2026-04-17)

### Usunięto

- Wydzielono budowanie obrazu `iplweb/bpp_dbserver` z tego
  repozytorium do osobnego projektu
  ([github.com/iplweb/bpp-dbserver](https://github.com/iplweb/bpp-dbserver)).
  Usunięty został katalog `docker/dbserver/` oraz target `dbserver`
  z `docker-bake.hcl`; `docker-compose.yml`, `docker-compose.test.yml`,
  workflowy GitHub Actions i konfiguracja testcontainers pullują teraz
  wersjonowany tag `iplweb/bpp_dbserver:psql-16.13` zamiast budować
  obraz lokalnie. Cel: niezależny release cycle obrazu bazy (bump
  Postgresa nie wymaga release'u BPP) i eliminacja tagu `:latest`
  po stronie konsumentów.

## bpp 202604.1355 (2026-04-17)

No significant changes.

## bpp 202604.1354 (2026-04-17)

No significant changes.

## bpp 202604.1353 (2026-04-17)

### Naprawione

- Naprawiono czyszczenie kontenerów tworzonych przez plugin
  `testcontainers_bpp`. Jawny cleanup w `pytest_unconfigure`
  bywał pomijany przy abrupt-exit procesu pytest (`sys.exit` z
  fixture, nieprzechwycony wyjątek), a Ryuk jako fallback również
  zawodził przy restarcie Docker Desktop, pozostawiając osierocone
  kontenery PostgreSQL / Redis / RabbitMQ. Dodano safety net przez
  `atexit`, który zatrzymuje kontenery przy każdym normalnym
  zakończeniu procesu pytest (szanuje `BPP_TESTCONTAINERS_REUSE`).

  Dodano też target `make clean-testcontainers`, który jednym
  poleceniem usuwa wszystkie kontenery oznaczone etykietą
  `org.testcontainers=true` oraz stałonazwane `bpp-tc-*` —
  ratunek gdy cleanup mimo wszystko padnie (np. `SIGKILL` na
  pytest albo restart demona Docker).

- Naprawiono kolizję nazw URL-i w panelu administracyjnym: trzy widoki
  "toż" (dla `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte` oraz `Patent`)
  były zarejestrowane pod tą samą nazwą `admin_bpp_wydawnictwo_ciagle_toz`,
  przez co `reverse()` zawsze zwracał adres widoku patentu. Nazwy zostały
  rozdzielone na `admin_bpp_wydawnictwo_ciagle_toz`,
  `admin_bpp_wydawnictwo_zwarte_toz` i `admin_bpp_patent_toz`, oraz
  dodano test regresyjny.

- Uporządkowano konfigurację DevOps: usunięto martwy hook
  `pre-commit-circleci` (projekt używa GitHub Actions), skrócono
  `start_period` healthchecka serwisu `appserver` z 1800s do 120s,
  dodano raportujący (non-blocking) skan obrazów Docker przez Trivy
  w workflow `build-docker-images.yml` oraz zastąpiono
  `filterwarnings = ignore` w `pytest.ini` trybem `default`
  z wąskimi wyjątkami dla znanego szumu z bibliotek zewnętrznych,
  tak aby realne ostrzeżenia (np. `USE_L10N` z Django) były widoczne.

- Usunięto nadpisanie `SESSION_COOKIE_SECURE` i `CSRF_COOKIE_SECURE`
  w `production.py`, które wyłączało bezpieczne flagi ciasteczek sesji
  i CSRF. Wartości z `base.py` (`True`) są teraz poprawnie dziedziczone
  — ciasteczka są wysyłane wyłącznie przez HTTPS. Rozpoznawanie połączeń
  szyfrowanych za nginx-em działa dzięki już ustawionemu
  `SECURE_PROXY_SSL_HEADER`.

- Zoptymalizowano widok listy lat publikacji (`/lata/`) — zamiast
  wykonywać osobne zapytanie `COUNT` dla każdego rocznika, widok
  pobiera liczby publikacji jednym zapytaniem `GROUP BY`. Na
  uczelniach z szerokim zakresem lat publikacji strona ładuje się
  wyraźnie szybciej.

### Usprawnienie

- Dodano testy jednostkowe dla aplikacji `django_pg_baseline`
  pokrywające ładowanie konfiguracji, obliczanie świeżości migracji,
  generowanie metadanych, monkey-patch tworzenia bazy testowej,
  regenerację dumpu oraz komendy zarządzające (`baseline_check`,
  `baseline_info`, `baseline_load`, `baseline_rebuild`).

- Logika szybkiego bootstrapu bazy testowej z `pg_dump` (dotychczas
  rozproszona po `baseline/`, `src/conftest.py`, `Makefile`,
  `docker-compose.baseline.yml` i entrypoincie kontenera) została
  wyodrębniona do reusable Django app `django_pg_baseline` w
  `src/django_pg_baseline/`.

  Pakiet udostępnia cztery komendy zarządzania: `baseline_rebuild`
  (regeneruje dump przez `testcontainers`, bez potrzeby oddzielnego
  `docker-compose.baseline.yml`), `baseline_load` (ładuje dump do
  wskazanej bazy, no-op gdy baza nie jest pusta), `baseline_check`
  (gate CI sprawdzający deltę migracji) oraz `baseline_info`
  (czytelny raport o stanie baseline).

  Monkey-patch na `_create_test_db`, wcześniej wklejony inline w
  `src/conftest.py`, jest teraz instalowany automatycznie z
  `AppConfig.ready()` gdy pakiet jest w `INSTALLED_APPS`.

  Katalog z dumpem został przeniesiony z `baseline/` do
  `src/baseline-sql/` — `baseline.sql` i `baseline.meta.json`
  dalej żyją w repo, ale jako wyraźny data sidecar obok kodu pakietu.
  Konfiguracja w `settings.PG_BASELINE` została skrócona z ~25 linii
  do kilku kluczy; defaulty (lista argumentów `pg_dump`, zamrażane
  kolumny timestampów, alias bazy, próg freshness) żyją teraz w samym
  pakiecie, a projekt-konsument ustawia tylko `BASELINE_DIR` plus
  ewentualne nadpisania.

  Zależność `testcontainers[postgres]` jest opcjonalna
  (`uv sync --extra baseline-rebuild`) — wymagana tylko dla
  `baseline_rebuild`, pozostałe komendy jej nie potrzebują.

- Zmienna `DJANGO_SETTINGS_MODULE` została przeniesiona z sekcji
  `environment:` kontenerów (`appserver`, `celerybeat`,
  `workerserver-*`, `denorm-queue`) do plików `.env` / `.env.docker`
  / `.env.example`. Devowy docker-compose konsekwentnie używa ustawień
  `django_bpp.settings.local`; serwis `authserver` pozostaje bez
  zmian (korzysta z własnego modułu `django_bpp.settings.auth_server`).

### Usunięto

- Usunięto dev-only serwis `webserver` (nginx) z `docker-compose.yml`
  oraz katalog `docker/webserver/`. Produkcyjny nginx żyje w osobnym
  repozytorium `bpp-deploy` (`defaults/webserver/`) i znacząco
  różni się od dotychczasowej wersji lokalnej (HTTP/3 QUIC, nagłówki
  bezpieczeństwa, resolver Dockera, `/healthz`). Trzymanie dwóch
  rozjechanych kopii w dwóch repo powodowało dryf konfiguracji
  i fałszywe poczucie testowania prod-ready stacka lokalnie.

  Lokalny development używa `runserver` razem z infrastrukturą
  podnoszoną przez `docker compose up db redis rabbitmq`, więc
  nginx przed appserverem był nadmiarowy. Jeśli potrzebujesz
  przetestować pełny stack za nginxem zgodny z produkcją, użyj
  `bpp-deploy`.

- Usunięto mechanizm automatycznych offsetów portów per-worktree: skrypt
  `bin/prepare-worktree.sh`, targety `make new-worktree` /
  `make clean-worktree` oraz sekcję „Docker exposed ports (with worktree
  offset)” w `.env.example`. Równoległa izolacja testów jest realizowana
  przez `testcontainers_bpp` (losowe porty), więc dev-stack może
  spokojnie jeździć na jednej kopii usług na maszynę na domyślnych
  portach (`5432` / `6379` / `5672` / `8000` …).

## bpp 202604.1352 (2026-04-08)

No significant changes.

## bpp 202603.1351 (2026-03-03)

### Naprawione

- Przywrócono brakujący przycisk "Zmień hasło" na stronie zmiany hasła. (password-change-submit)

### Usprawnienie

- Przycisk "Tamże" w wydawnictwie zwartym kopiuje teraz również pola
  "Wydawnictwo nadrzędne" oraz "Wydawnictwo nadrzędne w PBN". (tamze-wydawnictwo-nadrzedne)

## bpp 202602.1349 (2026-02-03)

No significant changes.

## bpp 202602.1347 (2026-02-03)

No significant changes.

## bpp 202602.1346 (2026-02-03)

No significant changes.

## bpp 202602.1345 (2026-02-03)

No significant changes.

## bpp 202602.1344 (2026-02-02)

### Usprawnienie

- Dodano możliwość konfiguracji marginesów wydruku przez panel administracyjny
  (Ustawienia → Wydruk). Nowe opcje: WYDRUK_MARGINES_GORA, WYDRUK_MARGINES_DOL,
  WYDRUK_MARGINES_LEWO, WYDRUK_MARGINES_PRAWO. Domyślna wartość: 2cm.
  Naprawiono również błąd powodujący wyświetlanie uciętej linii na górze
  wydrukowanych stron (ukryto element skip-link w widoku wydruku). (konfigurowalne-marginesy-wydruku)

## bpp 202602.1343 (2026-02-02)

No significant changes.

## bpp 202601.1342 (2026-01-28)

No significant changes.

## bpp 202601.1341 (2026-01-28)

### Naprawione

- Naprawiono błąd podwójnego potwierdzenia w modułach ewaluacja_optymalizacja,
  multiseek oraz import_dyscyplin. Kliknięcie przycisków z atrybutem
  `data-confirm` wyświetlało dwa okna dialogowe potwierdzenia. Przyczyną były
  zduplikowane handlery - globalny w `event-handlers.js` i lokalne w szablonach.
  Usunięto duplikaty z szablonów, pozostawiając obsługę w globalnym handlerze. (double-confirm-fix)
- Naprawiono błąd importu książek z PBN, gdzie redaktorzy (EDITOR) byli importowani
  jako autorzy gdy brakowało danych afiliacji. Dodano komendę
  `fix_pbn_import_oswiadczen_ksiazki` do naprawy istniejących rekordów. (fix_pbn_editor_import)

### Usprawnienie

- Podczas importu oświadczeń z PBN, pole `data_oswiadczenia` na rekordach autorów publikacji jest teraz automatycznie ustawiane na podstawie pola `statedTimestamp` z oświadczenia PBN. (data_oswiadczenia_import)
- Dodano nowy moduł Deduplikator Publikacji umożliwiający automatyczne wykrywanie potencjalnych duplikatów publikacji w bazie danych. Funkcje modułu obejmują: skanowanie publikacji w zadanym zakresie lat, wykrywanie duplikatów na podstawie DOI, WWW, ISBN, źródła i podobieństwa tytułów, prezentację wyników z oceną podobieństwa oraz możliwość oznaczania rekordów jako duplikaty lub nie-duplikaty. (deduplikator_publikacji)
- Ulepszono metodę wyszukiwania autora przy integracji oświadczeń z PBN. Teraz oprócz wyszukiwania po pbn_uid_id, system próbuje również znaleźć autora po ORCID, a następnie po imieniu i nazwisku (case-insensitive). Dzięki temu autorzy bez przypisanego pbn_uid_id będą poprawnie dopasowywani podczas importu dyscyplin z oświadczeń PBN. (get_bpp_autor_fallback)
- Komparator PBN: połączono widoki rozbieżności dyscyplin i brakujących autorów w jedną stronę "Problemy PBN". Nowa tabela wyświetla wszystkie typy problemów z kolorowymi etykietami: różne dyscypliny (niebieski), brak autora w BPP (czerwony), brak powiązania (pomarańczowy), brak publikacji (szary). Dodano pogrupowane filtry i rozbudowane statystyki dla każdego typu problemu. Na stronach szczegółów dodano BPP ID dla autorów i publikacji. (komparator_pbn_udzialy_unified_view)
- Komenda `pbn_import` zawiera teraz krok "Konfiguracja jednostek" w menu interaktywnym oraz flagę `--disable-institutions` dla trybu batch. (pbn_import_institutions)

## bpp 202601.1340 (2026-01-23)

No significant changes.

## bpp 202601.1339 (2026-01-22)

No significant changes.

## bpp 202601.1338 (2026-01-22)

### Naprawione

- Naprawiono filtr "dyscyplina nieprzypisana" w przeglądarce ewaluacji. Filtr
  teraz prawidłowo znajduje tylko publikacje autorów dwudyscyplinowców, którzy
  mieli możliwość użycia dyscypliny X, ale przypisali dyscyplinę Y. Wcześniej
  filtr zwracał wszystkie publikacje autorów z daną dyscypliną, niezależnie od
  tego czy była ona przypisana do publikacji i czy autor był dwudyscyplinowcem. (filtr-dyscyplina-nieprzypisana)
- usunięto techniczne odniesienia do nazwy "Celery" z interfejsu użytkownika;
  użytkownik końcowy nie powinien widzieć szczegółów implementacyjnych systemu kolejkowania zadań (remove-celery-ui-references)

### Usprawnienie

- Zoptymalizowano czas startu serwera aplikacji. Migracje bazy danych wykonywane są synchronicznie,
  natomiast zadania collectstatic, compress i generate_500_page uruchamiane są w tle równolegle
  ze startem serwera uvicorn. Skraca to czas do dostępności serwera o ~15-90 sekund. (appserver-startup-optimization)
- Przeglądarka ewaluacji: dodano nowy filtr "Dyscyplina nieprzypisana", który pozwala wyszukiwać publikacje autorów posiadających daną dyscyplinę (główną lub subdyscyplinę) w swoim profilu, niezależnie od tego jaką dyscyplinę mają przypisaną do konkretnej publikacji. Zmieniono również układ panelu filtrów na 2 wiersze po 3 elementy dla lepszej czytelności. (dyscyplina-nieprzypisana-filter)
- Uproszczono kryteria doboru publikacji do wysyłki oświadczeń PBN. Publikacje są teraz
  wybierane tylko na podstawie roku wydania i obecności PBN UID, bez dodatkowych wymagań
  dotyczących autorów (dyscyplina, zatrudnienie, afiliacja, jednostka). Dzięki temu możliwe
  jest "wyczyszczenie" błędnie wysłanych oświadczeń - gdy autor miał przypisaną dyscyplinę,
  a następnie została ona usunięta, system nadal podejmie ponowną wysyłkę tej publikacji
  w celu usunięcia starych oświadczeń z PBN. (simplify-pbn-publication-criteria)

## bpp 202601.1337 (2026-01-22)

### Naprawione

- Naprawiono błąd AttributeError w imporcie POLON gdy pole rodzaj_autora
  w rekordzie Autor_Dyscyplina było puste. (import_polon_rodzaj_autora_none)
- Naprawiono problem z drukowaniem tabel z wyszukiwarki multiseek w przeglądarce
  Edge (formaty "Tabela" oraz "tabela z punktacją wewnętrzną"). Przyczyną był
  atrybut CSS `overflow: hidden`, który powodował ukrycie zawartości podczas
  drukowania w starszych wersjach Edge. (multiseek-table-print-edge)

### Usprawnienie

- Dodano raportowanie błędów do Rollbar w module importu danych z POLON.
  Błędy podczas wczytywania plików Excel/CSV są teraz automatycznie
  zgłaszane do systemu monitoringu wraz z kontekstem operacji. (rollbar-import-polon)

## bpp 202601.1336 (2026-01-21)

### Naprawione

- Naprawiono błąd IntegrityError przy edycji zgłoszenia publikacji - pole przyczyna_zwrotu było ustawiane na None zamiast pusty ciąg znaków. (przyczyna_zwrotu_fix)

## bpp 202601.1335 (2026-01-19)

### Naprawione

- Naprawiono błąd "NOT NULL constraint" dla pola `error_traceback` w tabeli
  `pbn_import_importsession`, który występował podczas automatycznego anulowania
  utraconej sesji importu PBN. Metoda `auto_cancel_if_lost()` używa teraz
  `mark_failed()` zamiast ręcznego ustawiania pól, co zapewnia poprawne
  wypełnienie wszystkich wymaganych pól (w tym `error_traceback` i `completed_at`). (auto-cancel-null-traceback)
- Naprawiono błąd naruszenia klucza obcego podczas importu publikacji instytucji z PBN. Funkcja <span class="title-ref">zapisz_publikacje_instytucji</span> nie sprawdzała istnienia rekordów Scientist i Institution przed utworzeniem PublikacjaInstytucji, co powodowało IntegrityError gdy osoba lub instytucja nie istniała lokalnie w bazie danych. (fix-fk-publikacja-instytucji)

### Usprawnienie

- Moduł importu oświadczeń (StatementImporter) teraz prawidłowo zapisuje nieścisłości wykryte podczas integracji oświadczeń do bazy danych (model ImportInconsistency). Wcześniej nieścisłości były jedynie wypisywane na konsolę i tracone. (statement_import_inconsistency)

## bpp 202601.1334 (2026-01-18)

No significant changes.

## bpp 202601.1333 (2026-01-18)

No significant changes.

## bpp 202601.1332 (2026-01-18)

No significant changes.

## bpp 202601.1331 (2026-01-18)

No significant changes.

## bpp 202601.1330 (2026-01-16)

No significant changes.

## bpp 202601.1329 (2026-01-16)

No significant changes.

## bpp 202601.1328 (2026-01-16)

No significant changes.

## bpp 202601.1327 (2026-01-15)

No significant changes.

## bpp 202601.1326 (2026-01-15)

No significant changes.

## bpp 202601.1325 (2026-01-14)

No significant changes.

## bpp 202601.1324 (2026-01-14)

No significant changes.

## bpp 202601.1323 (2026-01-14)

No significant changes.

## bpp 202601.1322 (2026-01-14)

No significant changes.

## bpp 202601.1321 (2026-01-14)

No significant changes.

## bpp 202601.1320 (2026-01-14)

No significant changes.

## bpp 202601.1319 (2026-01-14)

No significant changes.

## bpp 202601.1318 (2026-01-14)

No significant changes.

## bpp 202601.1317 (2026-01-14)

No significant changes.

## bpp 202601.1316 (2026-01-14)

No significant changes.

## bpp 202601.1315 (2026-01-14)

No significant changes.

## bpp 202601.1314 (2026-01-13)

No significant changes.

## bpp 202601.1313 (2026-01-13)

### Usprawnienie

- Dodano możliwość zmiany ustawień technicznych systemu w czasie działania
  przez panel administracyjny (django-constance). Nowy link "Ustawienia systemu"
  w menu "Administracja" dostępny wyłącznie dla superużytkowników. Początkowe
  ustawienia: punktacja wewnętrzna, oświadczenie KEN, struktura wydziałowa,
  integracja z Google Analytics. Dodano również możliwość globalnego wyłączenia
  pól punktacji (Index Copernicus, SNIP) - wyłączone pola znikają zarówno z
  modelu Uczelnia jak i z formularzy edycji publikacji. (constance)
- Dodano pola ewaluacji PBN/SEDN dla wydawnictw ciągłych i zwartych. Nowe pola
  pozwalają oznaczyć publikacje jako powstałe w ramach projektów FNP, NCN, NPRH
  lub UE, oraz jako indeksowane w czasopismach, artykuły recenzyjne lub edycje
  naukowe. Pola tłumaczeń i konferencji WoS są obliczane automatycznie podczas
  eksportu. Detekcja języka polskiego obsługuje różne warianty skrótów: pol, pl,
  POL, PL, pol., pl., POL., PL. itp. (pbn-evaluation-fields)

## bpp 202601.1312 (2026-01-12)

### Usprawnienie

- Dodano endpoint autoryzacyjny <span class="title-ref">/\_\_external_auth/is_superuser/</span> dla superużytkowników oraz konfigurację nginx proxy dla zewnętrznych usług monitoringu (Grafana, Dozzle, Beszel) z uwierzytelnianiem SSO przez BPP. (external-auth)

## bpp 202601.1311 (2026-01-06)

No significant changes.

## bpp 202601.1310 (2026-01-06)

No significant changes.

## bpp 202601.1309 (2026-01-06)

No significant changes.

## bpp 202601.1308 (2026-01-06)

No significant changes.

## bpp 202601.1307 (2026-01-06)

### Usprawnienie

- Dodano nowy widok "Przegladarka ewaluacji" umozliwiajacy przegladanie wszystkich publikacji z raportowanych dyscyplin. Widok wyswietla pozioma tabele z punktacja dyscyplin, filtrowanie po roku, tytule, dyscyplinie i nazwisku autora, oraz pozwala na przypinanie/odpinanie dyscyplin i zamiane dyscypliny na druga dla autorow dwudyscyplinowych. (przegladarka-ewaluacji)
- Optymalizacja odpinania slotów pomija teraz prace jednoautorskie - nie ma sensu ich odpinać, bo nie ma alternatywnego autora do przypisania slotu. (unpinning-skip-single-author)
- Dodano funkcję analizy możliwości zamiany dyscyplin w module optymalizacji ewaluacji. Funkcja wyszukuje publikacje wieloautorskie, gdzie zamiana dyscypliny autora (główna \<-\> subdyscyplina) zwiększa całkowitą punktację za publikację. Analiza wykorzystuje równoległe przetwarzanie z Celery chord dla przyspieszenia obliczeń (2.5-6x szybciej). (zamiana-dyscyplin)

## bpp 202601.1306 (2026-01-04)

### Usprawnienie

- Dodano bonus +1 slot dla autorów z dwoma dyscyplinami, gdy jedna z nich jest nieraportowana. Bonus jest doliczany po obliczeniu średniej liczby N, więc nie wpływa na wartość liczby N dla uczelni. (bonus-nieraportowana)
- Kolejka eksportu PBN: dodano nowy status "Wykluczone" dla publikacji, które z przyczyn projektowych nie mogą być eksportowane (nieobsługiwany charakter formalny, brak mapowania PBN dla typu, wyłączony eksport prac bez punktów). Status ten odróżnia świadome wykluczenia od prawdziwych błędów - wyświetlany jest szarą ikoną i nie pozwala na ponowną wysyłkę. (wykluczone-status)

## bpp 202512.1305 (2025-12-29)

No significant changes.

## bpp 202512.1304 (2025-12-29)

### Usprawnienie

- Ulepszono obsługę błędów w funkcji wyslij_informacje_o_platnosciach: dodano sprawdzanie wartości zwracanej przez upload_publication_fee (success=True), re-raise dla nieobsłużonych HttpException oraz NeedsPBNAuthorisationException. Komunikaty błędów wyświetlają się teraz czytelnie nad paskiem postępu (tqdm.write). (pbn_integrator_sync)
- Dodano dwa nowe raporty XLSX w module optymalizacji ewaluacji: "Raport SEDN \#1" (szczegółowy per-autor) oraz "Raport SEDN \#2" (zagregowany per-publikacja). Raporty zawierają dane o publikacjach z lat 2022-2025 wraz z informacją o wskazaniu przez algorytm optymalizacji. Przycisk "Pobierz wszystkie XLS (ZIP)" przeniesiono do nowej, trzeciej linii przycisków. (sedn-reports)

## bpp 202512.1303 (2025-12-23)

No significant changes.

## bpp 202512.1302 (2025-12-22)

No significant changes.

## bpp 202512.1301 (2025-12-22)

No significant changes.

## bpp 202512.1300 (2025-12-22)

No significant changes.

## bpp 202512.1299 (2025-12-22)

No significant changes.

## bpp 202512.1298 (2025-12-22)

No significant changes.

## bpp 202512.1297 (2025-12-22)

No significant changes.

## bpp 202512.1296 (2025-12-17)

No significant changes.

## bpp 202512.1295 (2025-12-17)

No significant changes.

## bpp 202512.1294 (2025-12-17)

No significant changes.

## bpp 202512.1293 (2025-12-17)

No significant changes.

## bpp 202512.1292 (2025-12-15)

### Usprawnienie

- Aktualizacja aplikacji do analizy rozbieżności Impact Factor - usunięto nieużywaną funkcjonalność wysyłki do PBN. (rozbieznosci_if_update)
- Nowa aplikacja do analizy rozbieżności punktów MNiSW pomiędzy rekordami a źródłami. (rozbieznosci_pk)
- Nowa aplikacja do wydruku oświadczeń pracowników. (wydruki_oswiadczen)

## bpp 202512.1291 (2025-12-03)

No significant changes.

## bpp 202512.1290 (2025-12-03)

### Usprawnienie

- Deduplikator autorów: rozbudowa przycisków scalania - dodano opcje "Scal + ustaw dyscyplinę" i "Scal + ustaw subdyscyplinę" dla automatycznego przypisywania dyscyplin do prac bez dyscypliny. Dodano przyciski "Pokaż wyd. ciągłe" i "Pokaż wyd. zwarte" otwierające moduł redagowania z filtrem DjangoQL. Poprawiono wykrywanie zamiany imienia z nazwiskiem (teraz obie strony muszą się zgadzać). Zmieniono kolor przycisku "Nie są duplikatami" na czerwony. (deduplikator-przyciski)
- Możliwość ręcznego wpisania sankcji dla każdej z dyscyplin w module Liczba N. Sankcje zmniejszają limit slotów (3N - sankcje) używany w optymalizacji ewaluacji. (sankcje)

## bpp 202512.1289 (2025-12-03)

No significant changes.

## bpp 202511.1288 (2025-11-30)

### Usprawnienie

- Dodano możliwość anulowania długo trwających zadań w module optymalizacji ewaluacji. Przyciski anulowania są dostępne na stronach statusu zadań optymalizacji z odpinaniem oraz analizy możliwości odpinania. (anulowanie-zadan-optymalizacji)
- Plik ZIP z wynikami optymalizacji bulk jest teraz cache'owany w bazie danych, co przyspiesza ponowne pobieranie wyników bez konieczności regenerowania pliku. (cache-zip-optymalizacji)
- Poprawiono obsługę wygaśnięcia sesji podczas żądań HTMX - zamiast wstrzykiwania strony logowania w miejsce elementu, użytkownik jest teraz przekierowywany na stronę logowania z zachowaniem pierwotnego adresu URL. (htmx-login-redirect)
- Rozszerzono moduł optymalizacji ewaluacji o widok szczegółów prac autora z możliwością eksportu do XLSX: prace nazbierane, prace nienazbierane, prace odpięte, wszystkie prace. Dodano również eksport ZIP ze wszystkimi dyscyplinami. (prace-autora-eksporty)
- Refaktoryzacja wewnętrzna: rozbito duże pliki na mniejsze moduły tematyczne w aplikacjach ewaluacja_optymalizacja, ewaluacja_metryki, pbn_api, pbn_integrator i bpp. Poprawa czytelności i łatwości utrzymania kodu. (refaktoryzacja-modulow)
- Ulepszono wyświetlanie statusów długo działających zadań w module optymalizacji ewaluacji. Dodano automatyczne odświeżanie stanu co 5 sekund, wyraźne komunikaty o etapach przetwarzania oraz globalne śledzenie stanu zadań analizy odpinania. (statusy-zadan-optymalizacji)

## bpp 202511.1285 (2025-11-27)

No significant changes.

## bpp 202511.1284 (2025-11-27)

No significant changes.

## bpp 202511.1283 (2025-11-25)

No significant changes.

## bpp 202511.1282 (2025-11-24)

No significant changes.

## bpp 202511.1280 (2025-11-13)

No significant changes.

## bpp 202511.1279 (2025-11-13)

No significant changes.

## bpp 202511.1278 (2025-11-13)

No significant changes.

## bpp 202511.1277 (2025-11-13)

No significant changes.

## bpp 202511.1276 (2025-11-13)

No significant changes.

## bpp 202511.1275 (2025-11-13)

### Naprawione

- Uszczelnienie warunków uczelni w module optymalizacji ewaluacji (ewaluacja-optymalizacja-warunki)
- Poprawiono liczenie liczby N dla uczelni - usunięto błąd prowadzący do niedokładności w przypadku wielu autorów z mniej niż całym etatem (liczba-n-czesc-etatu)

### Usprawnienie

- Dodano funkcję przemapowania publikacji z jednego źródła do drugiego. Funkcja dostępna dla administratorów na stronie źródła, umożliwia przeniesienie wszystkich publikacji do innego źródła z zachowaniem historii i możliwością cofnięcia operacji. (przemapuj-zrodlo)
- Zmieniono tekst przycisku na stronie głównej: "Dodaj ją do bazy" → "Zgłoś ją do bazy!" dla lepszej komunikacji procesu zgłaszania publikacji (przycisk-zglos-publikacje)
- Przejście na RabbitMQ jako broker komunikatów dla zadań Celery (rabbitmq-broker)

## bpp 202510.1274 (2025-10-22)

No significant changes.

## bpp 202510.1273 (2025-10-22)

No significant changes.

## bpp 202510.1272 (2025-10-21)

No significant changes.

## bpp 202510.1271 (2025-10-21)

### Naprawione

- Poprawiono błąd w module optymalizacji ewaluacji, gdzie komunikat o zakończeniu zadania wyświetlał się przedwcześnie, zanim wszystkie dane zostały zapisane do bazy danych. Teraz system czeka na rzeczywiste zakończenie wszystkich procesów i zapisanie wszystkich wyników przed wyświetleniem komunikatu o sukcesie. (optymalizacja-completion-fix)
- Poprawiono błąd w module optymalizacji ewaluacji dla funkcji "Optymalizuj, odpinając sloty", gdzie komunikat o zakończeniu zadania wyświetlał się przedwcześnie, zanim wszystkie procesy optymalizacji poszczególnych dyscyplin zakończyły się i zapisały dane do bazy. System teraz prawidłowo czeka na zakończenie wszystkich procesów Celery, weryfikuje zapisanie danych do bazy i wyświetla stan "finalizowania" przed pokazaniem komunikatu o sukcesie. (optymalizacja-unpin-completion-fix)
- Zmieniono sposób monitorowania postępu przeliczania optymalizacji w funkcji "Optymalizuj, odpinając sloty". System teraz nie używa zadań Celery do śledzenia postępu, tylko bezpośrednio monitoruje bazę danych. Przed rozpoczęciem przeliczania usuwa wszystkie istniejące OptimizationRun dla uczelni, następnie uruchamia zadania optymalizacji i wyświetla postęp jako procent ukończonych dyscyplin względem wszystkich raportowanych dyscyplin uczelni. (optymalizacja-unpin-no-celery-tracking)
- Naprawiono przedwczesne pokazywanie komunikatu "zadanie zakończone" w funkcji "Optymalizuj, odpinając sloty":
  - Naprawiono status "Zakończono" pokazujący się od razu po wejściu na stronę statusu zadania. Status teraz zawsze pokazuje "W trakcie" dopóki <span class="title-ref">task.ready() == False</span>, bez względu na stan bazy danych (która może zawierać stare rekordy z poprzedniego uruchomienia przed ich skasowaniem przez zadanie Celery).
  - System teraz czeka aż zadanie Celery faktycznie zakończy się (<span class="title-ref">task.ready() == True</span>) zanim pokaże komunikat o sukcesie w sekcji postępu, zamiast wyświetlać sukces gdy <span class="title-ref">completed_count == discipline_count == 0</span> na samym początku procesu. (optymalizacja-unpin-premature-success)
- Poprawiono wyświetlanie postępu w funkcji "Optymalizuj, odpinając sloty":
  - Faza denormalizacji teraz pokazuje liczbę rekordów do przeliczenia zamiast ogólnego komunikatu "Sprawdzanie kolejki przeliczania"
  - Procent postępu w pasku jest teraz zaokrąglony do liczby całkowitej (zamiast wielu miejsc po przecinku)
  - Po zakończeniu zadania system teraz poprawnie przekierowuje do strony głównej z komunikatem o sukcesie zamiast wyświetlać stronę z "zadaniem w trakcie wykonywania"
  - Monitorowanie postępu odbywa się przez bazę danych (dla fazy optymalizacji) i task.info (dla fazy denormalizacji) (optymalizacja-unpin-progress-fix)

### Usprawnienie

- Zrównoleglono obliczanie metryk ewaluacyjnych - teraz każdy autor-dyscyplina jest przetwarzany jako osobny task Celery, co pozwala wykorzystać wiele workerów jednocześnie i znacznie przyspieszyć generowanie metryk (3-7x szybciej przy 4-8 workerach). Postęp jest aktualizowany w czasie rzeczywistym - każdy zakończony task atomowo zwiększa licznik przetworzonych pozycji w bazie danych (metryki-parallel)
- W module optymalizacji publikacji dodano możliwość szybkiej zmiany dyscypliny autora bezpośrednio z interfejsu optymalizacji. Dla autorów posiadających dwie dyscypliny (dyscyplina_naukowa i subdyscyplina_naukowa) wyświetlany jest przycisk "Zmień dyscyplinę na: \[nazwa dyscypliny\] (\[kod\])" umożliwiający natychmiastową zmianę. Alternatywne dyscypliny niezgodne z dyscyplinami źródła publikacji są oznaczone przekreśleniem dla łatwiejszej identyfikacji potencjalnych problemów. Po zmianie dyscypliny następuje automatyczne przeliczenie punktacji, slotów oraz metryk ewaluacyjnych dla wszystkich autorów publikacji (optymalizuj-publikacje-zmiana-dyscypliny)
- Kolejka eksportu PBN: dodano możliwość pobierania i kopiowania wysłanych danych JSON bezpośrednio z widoku szczegółów kolejki. Dla błędnych eksportów dostępne są narzędzia diagnostyczne: automatyczne generowanie e-maila do helpdesku PBN oraz tworzenie promptu dla AI zgodnego z dokumentacją API PBN (<https://pbn.nauka.gov.pl/api/>) (pbn-export-queue-json-download)
- W module optymalizacji ewaluacji zmieniono nazwę tabeli "Ostatnie optymalizacje" na "Ostatnie kalkulacje".
  Dodano przycisk "Resetuj przypięcia" w wierszu RAZEM, który resetuje przypięcia dla wszystkich rekordów
  z lat 2022-2025, gdzie autor ma dyscyplinę, jest zatrudniony i afiliuje. Operacja działa asynchronicznie
  przez zadanie Celery, tworzy snapshot przed zmianami i automatycznie przelicza punktację. (reset-all-pins)
- Panel przypięć dyscyplin w module optymalizacji ewaluacji - możliwość podglądu statystyk przypięć/odpięć dla lat 2022-2025 oraz resetowania przypięć dla każdej dyscypliny osobno (z automatycznym tworzeniem snapshotu). (reset-discipline-pins)

## bpp 202510.1270 (2025-10-19)

### Naprawione

- Poprawiono generowanie linków w wykresach na panelu administracyjnym - kliknięcie na wykres charakteru formalnego teraz poprawnie przekierowuje do listy rekordów z filtrem `?charakter_formalny__id__exact=ID` zamiast nieprawidłowego `?charakter_formalny=ID` (admin-dashboard-charakter-filter-fix)

### Usprawnienie

- Dodano DynamicAdminFilterMixin do 24 klas administracyjnych posiadających 2 lub więcej filtrów w list_filter, co znacząco poprawia wydajność i użyteczność filtrowania w panelu administracyjnym Django dla dużych zbiorów danych. Zmiany dotyczą następujących modułów: deduplikator_autorow, rozbieznosci_dyscyplin, bpp (Autor_Dyscyplina, Wydawnictwo_Autor_Base, BppMultiseekVisibility, Wydawca), zglos_publikacje, ewaluacja_metryki, przemapuj_prace_autora, ewaluacja_liczba_n, dynamic_columns, admin_dashboard, django_countdown, importer_autorow_pbn, pbn_import, pbn_downloader_app oraz pbn_api. (dynamic-admin-filter-mixin)
- Dodano możliwość warunkowego włączania liczników w filtrach panelu administracyjnego. Liczniki wyświetlają się tylko gdy zarówno ustawienie `settings.DYNAMIC_FILTER_COUNTS_ENABLE` jak i atrybut `dynamic_filter_counts_enable` klasy admina są ustawione na `True`. Ustawienie globalne ma priorytet. Gdy liczniki są wyłączone, nie wyświetlają się placeholdery `(…)` ani nie są wykonywane żądania HTMx do pobierania liczników. (dynamic-filter-counts-conditional)
- PBN API: dodano automatyczne logowanie niepożądanych odpowiedzi z serwera PBN. System zapisuje w bazie danych sytuacje, gdy serwer PBN zmienia UID publikacji która już posiadała PBN UID, lub gdy odpowiada numerem UID który już istnieje w bazie danych. Wszystkie zarejestrowane zdarzenia są dostępne w panelu administracyjnym w menu "PBN API" -\> "Niepożądane odpowiedzi PBN", gdzie można przeglądać szczegóły każdego zdarzenia (wysłane dane JSON, odpowiedź serwera, użytkownik, czas wystąpienia) (pbn-niepozadane-odpowiedzi)
- Ulepszone wyszukiwanie w rekordach powiązanych na stronie szczegółów publikacji: pole wyszukiwania pojawia się tylko gdy jest więcej niż 2 rekordy powiązane, przepisano funkcjonalność JavaScript na prostszy i bardziej niezawodny mechanizm wykorzystujący zapisane dane w atrybucie data-records zamiast manipulacji DOM, dodano podświetlanie znalezionych fraz. Przeniesiono sekcję "Informacje dodatkowe" poza układ dwukolumnowy, dzięki czemu zajmuje ona teraz pełną szerokość ekranu dla lepszej czytelności. (wyszukiwanie-rekordow-powiazanych)

## bpp 202510.1269 (2025-10-19)

No significant changes.

## bpp 202510.1268 (2025-10-19)

No significant changes.

## bpp 202510.1267 (2025-10-19)

No significant changes.

## bpp 202510.1266 (2025-10-19)

### Naprawione

- Naprawiono błąd Internal Server Error przy próbie użycia akcji adminowej "Wyślij do PBN w tle". Problem był spowodowany brakiem funkcji top_contributors_view w module admin_dashboard oraz błędnym formatowaniem HTML w linku do kolejki eksportu. (admin_action_pbn_fix)

### Usprawnienie

- Dodano trzy wykresy donut (pierścieniowe) pokazujące hierarchiczny rozkład charakterów formalnych w bazie danych w środkowej kolumnie panelu administracyjnego. Pierwszy wykres przedstawia charaktery stanowiące kumulatywnie 90% wszystkich publikacji plus kategoria "Inne" (10%). Drugi wykres dzieli te 10% na kolejne 90% (9% całości) plus "Inne" (1% całości). Trzeci wykres szczegółowo pokazuje rozbicie ostatniego 1% najmniej popularnych charakterów. (admin_dashboard_charakter_formalny_pie_charts)
- Po kliknięciu w wykres typu donut dla charakteru formalnego użytkownik zostaje przekierowany do admina z przefiltrowaną listą publikacji dla danego charakteru formalnego. (admin_dashboard_charakter_formalny_pie_charts_clickable)
- Dodano płynne przejścia kolorów (animacje CSS) przy przełączaniu pomiędzy schematami kolorystycznymi w panelu administracyjnym oraz dla efektów hover w menu. Przejścia trwają 0,2 sekundy i obejmują kolory tła, tekstu oraz ramek. (admin_theme_smooth_transitions)
- Dodano cache dla strony głównej uczelni (uczelnia.html) - funkcja get_uczelnia_context_data() jest teraz cachowana przez 1 godzinę. Dodatkowo rozszerzono konfigurację CACHEOPS o modele: Uczelnia, Wydzial, Jednostka oraz Wydawnictwo_Ciagle_Streszczenie, co zapewnia automatyczną invalidację cache przy zmianach w panelu administracyjnym. (cache_uczelnia_page)
- Dodano interaktywny dashboard administracyjny jako główną stronę Django Admin. Dashboard zawiera:
  - Statystyki podstawowe (publikacje, autorzy, jednostki, użytkownicy)
  - Tabelę ostatnich logowań z automatycznym odświeżaniem (HTMX)
  - Wykresy aktywności użytkowników z podziałem na dzień/tydzień/miesiąc (Plotly)
  - Wykres nowych publikacji w różnych okresach czasowych (Plotly)
  - Wyszukiwarkę aplikacji i modeli z dynamicznym filtrowaniem (JavaScript)
  - Integrację z systemem easyaudit do śledzenia logowań (dashboard_admin)
- Dodano polską lokalizację dla wszystkich wykresów Plotly.js - wykresy wyświetlają teraz polskie nazwy dni tygodnia, miesięcy i formaty daty. (plotly_lokalizacja_pl)
- Ukryto logo Plotly na wszystkich wykresach w panelu administracyjnym (admin_dashboard) oraz w widokach metryk ewaluacyjnych (ewaluacja_metryki). (plotly_ukryj_logo)
- Dodano wykres poziomy z ilością zgłoszeń publikacji według dni tygodnia w pierwszej kolumnie panelu zarządzania (dane z ostatniego miesiąca). Kliknięcie w słupek wykresu przekierowuje do listy zgłoszeń z wybranego dnia tygodnia. (zglos_publikacje_weekday_chart)

## bpp 202510.1265 (2025-10-17)

### Naprawione

- Naprawiono fałszywe pytania o opuszczenie strony w admincie - teraz pytanie pojawia się tylko gdy użytkownik faktycznie zmieni dane w formularzu. (naprawiono_falszywe_alerty_opuszczenia_strony)
- Naprawiono brak animacji "throbbera" na przyciskach "Zapisz" w panelu administracyjnym w przeglądarce Safari. Safari zatrzymywała wykonywanie JavaScriptu podczas submitu formularza, więc animacja oparta na zmianie wartości przycisku nie była widoczna. Rozwiązanie: dla Safari używana jest animacja CSS (obracające się kółko ładowania) wyświetlana wewnątrz przycisku, która działa niezależnie od JavaScriptu. Inne przeglądarki zachowują oryginalną animację ze znakami Braille'a (safari-submit-spinner)

### Usprawnienie

- Dodano aplikację **django_countdown** umożliwiającą planowane wyłączanie serwisu. Administrator może ustawić czas odliczania do zamknięcia serwisu - na stronie pojawi się czerwony, pulsujący baner z komunikatem i odliczaniem czasu. Po osiągnięciu wyznaczonego czasu serwis zostaje automatycznie zablokowany dla wszystkich użytkowników (z wyjątkiem superużytkowników, którzy mogą zalogować się do panelu administracyjnego i usunąć odliczanie, aby odblokować serwis). Dodatkowo, administrator może określić planowany czas zakończenia prac konserwacyjnych (pole **maintenance_until**) - na zablokowanej stronie wyświetlane jest wówczas odliczanie do końca przerwy, a po jego zakończeniu strona automatycznie odświeża się po 5 sekundach. Superużytkownicy w trakcie konserwacji widzą zamiast zablokowanej strony normalną stronę z pomarańczowym bannerem informującym o trwającej konserwacji i pozostałym czasie do jej zakończenia. Funkcjonalność przydatna przy planowanych pracach konserwacyjnych (django_countdown)
- Skonsolidowano kod licznika odliczającego do przerwy technicznej w jednym miejscu - całość logiki (HTML i JavaScript) znajduje się teraz w szablonie django_countdown/countdown_banner.html, co ułatwia utrzymanie i rozwój tej funkcjonalności. (django_countdown_consolidation)
- Dodano kompletne testy dla aplikacji `django_countdown` obejmujące walidację modelu, middleware blokujący dostęp oraz context processor. (django_countdown_tests)

## bpp 202510.1264 (2025-10-16)

No significant changes.

## bpp 202510.1263 (2025-10-16)

No significant changes.

## bpp 202510.1262 (2025-10-16)

No significant changes.

## bpp 202510.1261 (2025-10-16)

No significant changes.

## bpp 202510.1260 (2025-10-16)

No significant changes.

## bpp 202510.1259 (2025-10-16)

No significant changes.

## bpp 202510.1258 (2025-10-16)

No significant changes.

## bpp 202510.1257 (2025-10-16)

No significant changes.

## bpp 202510.1256 (2025-10-16)

No significant changes.

## bpp 202510.1255 (2025-10-16)

No significant changes.

## bpp 202510.1254 (2025-10-16)

No significant changes.

## bpp 202510.1253 (2025-10-16)

No significant changes.

## bpp 202510.1252 (2025-10-15)

No significant changes.

## bpp 202510.1251 (2025-10-15)

No significant changes.

## bpp 202510.1250 (2025-10-15)

No significant changes.

## bpp 202510.1249 (2025-10-15)

No significant changes.

## bpp 202510.1248 (2025-10-15)

No significant changes.

## bpp 202510.1248 (2025-10-15)

No significant changes.

## bpp 202510.1248 (2025-10-15)

No significant changes.

## bpp 202510.1247 (2025-10-15)

No significant changes.

## bpp 202510.1246 (2025-10-14)

### Usprawnienie

- dodaj "zapasowy" konwerter do MS Word dla środowisk, w których najnowszy pandoc zawodzi (VMWare ESX na procesorach Xeon Silver) - za pomocą dockera i obrazu iplweb/html2docx

## Bpp 202510.1245 (2025-10-13)

No significant changes.

## Bpp 202510.1244 (2025-10-13)

No significant changes.

## Bpp 202510.1243 (2025-10-12)

No significant changes.

## Bpp 202510.1242 (2025-10-12)

### Usprawnienie

- Dodano pola punkty_kbn i charakter_formalny do widoku rozbieżności dyscyplin źródeł.
  Dodano filtr "punkty MNISW/MEIN" z opcjami filtrowania: większe niż 5, 10, 20, 30, 50, 100. (rozbieznosci_punkty_charakter)
- Przy tworzeniu rekordu "tamże" w wydawnictwach zwartych teraz kopiowane są również pola kwartylów (WoS i SCOPUS), obok już istniejących punktów i Impact Factor. Wcześniej kwartyle były kopiowane tylko w wydawnictwach ciągłych. (tamze_kwartyle_copy)

## Bpp 202510.1241 (2025-10-12)

### Usprawnienie

- Poprawiono system śledzenia wysyłania danych do PBN (SentData).

  - Dodano tworzenie rekordów SentData PRZED wywołaniem API PBN, co zapewnia pełny audyt prób wysyłki.
  - Wprowadzono nowe pola w modelu SentData:
    - `submitted_successfully` - flaga wskazująca czy wywołanie API zakończyło się sukcesem
    - `submitted_at` - timestamp momentu wysyłki danych
    - `api_response_status` - pełna odpowiedź z API PBN (jako TextField)
  - Zmieniono logikę tworzenia rekordów tak, aby aktualizować istniejące rekordy zamiast tworzyć nowe przy próbach ponowienia, co zapobiega niekontrolowanemu wzrostowi bazy danych.
  - Dodano nowe metody w SentDataManager:
    - `create_or_update_before_upload()` - tworzy lub aktualizuje rekord przed API
    - `check_if_upload_needed()` - sprawdza czy wysyłka jest potrzebna (tylko na podstawie udanych wysyłek)
    - `mark_as_successful()` - oznacza rekord jako udany po sukcesie API
    - `mark_as_failed()` - oznacza rekord jako nieudany z informacjami o błędzie
  - Zapewniono kompatybilność wsteczną - istniejące metody `check_if_needed()` i `updated()` zostały zachowane.
  - Poprawiono logikę ponawiania prób przy błędach walidacji API, przywracając `time.sleep(0.5)` między próbami.

  Dzięki tym zmianom system teraz tworzy kompletne ślady audytowe dla wszystkich prób wysyłki do PBN (zarówno do API publikacji jak i repozytorium), jednocześnie utrzymując czystość i wydajność bazy danych. (pbn-sentdata-pre-api-creation)

## Bpp next (2025-10-12)

### Usprawnienie

- Poprawiono system śledzenia wysyłania danych do PBN (SentData).

  - Dodano tworzenie rekordów SentData PRZED wywołaniem API PBN, co zapewnia pełny audyt prób wysyłki.
  - Wprowadzono nowe pola w modelu SentData:
    - `submitted_successfully` - flaga wskazująca czy wywołanie API zakończyło się sukcesem
    - `submitted_at` - timestamp momentu wysyłki danych
    - `api_response_status` - pełna odpowiedź z API PBN (jako TextField)
  - Zmieniono logikę tworzenia rekordów tak, aby aktualizować istniejące rekordy zamiast tworzyć nowe przy próbach ponowienia, co zapobiega niekontrolowanemu wzrostowi bazy danych.
  - Dodano nowe metody w SentDataManager:
    - `create_or_update_before_upload()` - tworzy lub aktualizuje rekord przed API
    - `check_if_upload_needed()` - sprawdza czy wysyłka jest potrzebna (tylko na podstawie udanych wysyłek)
    - `mark_as_successful()` - oznacza rekord jako udany po sukcesie API
    - `mark_as_failed()` - oznacza rekord jako nieudany z informacjami o błędzie
  - Zapewniono kompatybilność wsteczną - istniejące metody `check_if_needed()` i `updated()` zostały zachowane.
  - Poprawiono logikę ponawiania prób przy błędach walidacji API, przywracając `time.sleep(0.5)` między próbami.

  Dzięki tym zmianom system teraz tworzy kompletne ślady audytowe dla wszystkich prób wysyłki do PBN (zarówno do API publikacji jak i repozytorium), jednocześnie utrzymując czystość i wydajność bazy danych. (pbn-sentdata-pre-api-creation)

## Bpp 202510.1240 (2025-10-12)

### Usprawnienie

- Add your info here (pbn-sentdata-pre-api-creation)

## Bpp 202510.1240 (2025-10-12)

No significant changes.

## Bpp 202510.1236 (2025-10-07)

### Usprawnienie

- Dodano możliwość opcjonalnego włączenia statystyk Prometheus poprzez zmienną środowiskową DJANGO_BPP_ENABLE_PROMETHEUS (prometheus_stats)

## Bpp 202510.1235 (2025-10-07)

### Usprawnienie

- Zastąpienie systemu śledzenia błędów Sentry SDK na Rollbar. Wszystkie wywołania `capture_exception` z modułu `sentry_sdk` zostały zamienione na `rollbar.report_exc_info(sys.exc_info())`. (sentry-rollbar)

## Bpp 202510.1234 (2025-10-05)

### Naprawione

- errata (logo na pierwszej stronie)

## Bpp 202510.1232 (2025-10-05)

### Usprawnienie

- Dodano dedykowaną stronę błędu 500 (wewnętrzny błąd serwera) z przyjaznym dla użytkownika interfejsem oraz poleceniem zarządzającym umożliwiającym wygenerowanie statycznej wersji strony dla środowiska produkcyjnego. (custom-500-page)
- Raport slotów: obliczanie slotów dla wszystkich typów autorów (dyscyplina, zatrudniony, doktorant, inny zatrudniony, naukowiec). (raport-slotow-wszystkie-typy-autorow)

## Bpp 202510.1231 (2025-10-05)

### Naprawione

- Zaktualizowano bibliotekę django-sendfile2 z wersji 0.7.0 do 0.7.2 w celu naprawienia błędu kompatybilności z Python 3.12. Wcześniejsza wersja powodowała błąd AttributeError podczas próby wyświetlenia ikony favicon ('module posixpath has no attribute pathmod') ze względu na zmiany w wewnętrznych interfejsach modułu pathlib wprowadzone w Python 3.12. (django_sendfile2_python312)
- Poprawiono obliczanie metryk ewaluacyjnych dla autorów dwudyscyplinowych. (ewaluacja_metryki_dwudyscyplinowi)
- Wyłączono widget dostępności UserWay podczas uruchamiania testów (gdy settings.TESTING = True) w celu poprawy stabilności testów. (userway_tests)

### Usprawnienie

- Moduł ewaluacji liczba N: dodano czerwone ostrzeżenie w widoku weryfikacji bazy danych dla rekordów Autor_Dyscyplina (2022-2025) bez uzupełnionego rodzaju zatrudnienia (rodzaj_autora). Ostrzeżenie wyświetla się w pierwszej sekcji raportu weryfikacyjnego wraz z linkiem do przeglądania problematycznych rekordów w panelu administracyjnym. (ewaluacja_liczba_n_weryfikacja_ostrzezenie)
- Zmieniono angielskie słowo "Bottom" na polskie "Najniższe" w statystykach metryk ewaluacyjnych dla lepszej czytelności i bardziej neutralnego brzmienia. (ewaluacja_metryki_najnizsze)
- Moduł ewaluacji metryk: dodano rodzaje autora "Z" (inni zatrudnieni) oraz "brak danych". Domyślnie przy generowaniu metryk zaznaczone są wszystkie rodzaje autorów (N, D, Z, brak danych). Zrefaktoryzowano kod: wspólna funkcja generuj_metryki() w utils.py eliminuje duplikację kodu między zadaniem Celery a komendą zarządzającą. (ewaluacja_metryki_rodzaje_autora)
- Dodano widget wsparcia technicznego Freshworks dla zalogowanych użytkowników, umożliwiający bezpośredni kontakt z zespołem pomocowym. Widget automatycznie identyfikuje użytkownika na podstawie jego danych w systemie. Dodano niestandardowy przycisk wsparcia "!?!" w prawym dolnym rogu strony, który po najechaniu myszką wyświetla tekst "Support BPP" z animacją fade-in, a po kliknięciu uruchamia widget Freshworks. (freshworks_widget)
- Dodano wsparcie dla awaryjnego wyświetlania logo w skali szarości. Gdy plik logo uczelni nie istnieje w systemie plików (nawet jeśli pole jest ustawione w bazie danych), system wyświetla domyślną ikonę bpp-icon.png w skali szarości z 70% przezroczystością, co wizualnie odróżnia ją od prawdziwego logo. (greyscale_fallback_logo)
- Dodano nową opcję "nie porównuj po tytułach" do importu list ministerialnych, która umożliwia porównywanie źródeł wyłącznie po identyfikatorach ISSN, E-ISSN i MNISWID, bez uwzględniania tytułów czasopism. Opcja jest domyślnie włączona i zapobiega problemom z dopasowywaniem periodyków o identycznych lub podobnych nazwach (np. "Electronics" oraz "Electronics (Switzerland)"), gdy w bazie występuje tylko jedno źródło o danej nazwie. Użytkownicy mogą wyłączyć tę opcję w formularzu importu, aby przywrócić dopasowywanie również po tytułach. (import_list_ministerialnych_nie_porownuj_po_tytulach)
- Zwiększono elastyczność polecenia zarządzającego <span class="title-ref">remap_jednostka</span>. Teraz akceptuje zarówno slugi, jak i identyfikatory numeryczne jednostek jako parametry wejściowe. Dodano obsługę formatów mieszanych oraz zaktualizowano tekst pomocy z przykładami użycia. (remap_jednostka_slug_support)
- Strona główna wyświetla teraz bezpośrednio szablon uczelnia.html zamiast przekierowania HTTP 301. Zmiana poprawia SEO, eliminując niepotrzebne przekierowanie z głównego URL na URL uczelni. (root_page_no_redirect)
- Dodano testowe linki do podglądu stron błędów 403 i 500 pod adresami /test_403/ i /test_500/ (wymagane logowanie). (test_error_pages)
- Zmieniono wykrywanie serwera testowego z analizy nazwy domeny na użycie zmiennej konfiguracyjnej DJANGO_BPP_ENABLE_TEST_CONFIGURATION dla bardziej niezawodnej identyfikacji środowiska testowego. (test_server_settings)

### Usunięto

- Usunięto pakiet django-robots i zastąpiono go statycznym plikiem robots.txt blokującym roboty od dostępu do wrażliwych adresów URL (admin, raporty, logowanie, ewaluacja itp.) (robots-static)

## Bpp 202509.1230 (2025-09-30)

### Naprawione

- Poprawiono wyświetlanie liczby prac nazbieranych algorytmem plecakowym na stronie szczegółów metryk ewaluacyjnych autora. Wcześniej liczba mogła być niepoprawnie wyświetlana jako 0 gdy lista prac nie była pobrana z bazy danych. (metryki-liczba-prac)

### Usprawnienie

- Dodano widget dostępności UserWay (WCAG) do stron ogólnodostępnych systemu, umożliwiający użytkownikom dostosowanie interfejsu do własnych potrzeb w zakresie dostępności. Widget automatycznie dostosowuje swoją kolorystykę do aktualnie używanego motywu kolorystycznego strony. (widget_wcag)

## Bpp 202509.1228 (2025-09-28)

### Naprawione

- Poprawiono mechanizm przypinania i odpinania dyscyplin w optymalizacji publikacji - teraz używa właściwych identyfikatorów powiązań autor-publikacja zamiast identyfikatorów cache. (optymalizacja_publikacji_id_fix)

## Bpp 202509.1227 (2025-09-28)

### Naprawione

- Poprawiono wyświetlanie zakresów lat na stronie "Przeglądaj wg roku". Nagłówki dekad teraz poprawnie pokazują rzeczywiste zakresy lat dostępnych w bazie danych (np. "2020-2025" dla bieżącej dekady, "2010-2019" dla pełnych dekad) zamiast błędnych wartości. (przegladaj_wg_roku)

### Usprawnienie

- Ulepszono funkcjonalność deduplikatora autorów PBN w zakresie wyszukiwania i priorytetyzacji.

  Zmiany obejmują:

  - Resetowanie licznika pominiętych autorów podczas wyszukiwania - teraz wyszukiwanie po nazwisku zawsze pokazuje wszystkie pasujące wyniki, niezależnie od wcześniej pominiętych autorów
  - Priorytetyzacja autorów z najnowszymi publikacjami (2022-2025) - autorzy z publikacjami z ostatnich lat są teraz wyświetlani jako pierwsi, co ułatwia pracę z aktywnymi naukowcami
  - Zachowanie funkcjonalności pomijania autorów podczas zwykłego przeglądania (bez wyszukiwania)

  Aplikacja automatycznie sprawdza czy główny autor lub którykolwiek z jego duplikatów ma publikacje z lat 2022-2025 i wyświetla takich autorów w pierwszej kolejności. (deduplikator_autorow_priorytet)

- Dodano nową aplikację "Przemapuj prace autora" umożliwiającą masowe przenoszenie prac autorów między jednostkami organizacyjnymi.

  Funkcjonalność obejmuje:

  - Wyszukiwanie autorów po nazwisku i imieniu z poziomu interfejsu webowego
  - Automatyczne sugerowanie przemapowania z "Jednostki Domyślnej" do aktualnej jednostki autora
  - Zabezpieczenie przed przypadkowym przemapowaniem do "Jednostki Domyślnej" (jednostka ta może być tylko źródłem, nie celem)
  - Podgląd zmian przed wykonaniem przemapowania z listą przykładowych prac
  - Pełna historia operacji z zapisem szczegółów przemapowanych prac (ID, tytuły, rok, źródło/wydawnictwo) w formacie JSON
  - Integracja z interfejsem przeglądania autorów - przycisk "Przemapuj prace" widoczny obok "Otwórz do edycji" dla zalogowanych użytkowników
  - Panel administracyjny z możliwością przeglądania historii przemapowań, w tym szczegółowej listy przemapowanych publikacji

  Aplikacja jest dostępna pod adresem <span class="title-ref">/przemapuj_prace_autora/</span> i wymaga zalogowania. (przemapuj_prace_autora)

- Dodano polecenie zarządzające `ukryj_nieuzywane_dyscypliny` umożliwiające ukrycie nieużywanych dyscyplin naukowych w systemie. Polecenie ustawia `Dyscyplina_Naukowa.widoczna = False` dla wszystkich dyscyplin, które nie są przypisane do żadnych autorów ani publikacji. Opcja `--dry-run` pozwala na podgląd zmian bez ich zapisywania. (ukryj_nieuzywane_dyscypliny)

- Dodano nowe polecenie zarządzania `ukryj_nieuzywane_jezyki` do automatycznego ukrywania nieużywanych języków w systemie. Polecenie skanuje wszystkie publikacje (wydawnictwa ciągłe, zwarte, prace doktorskie i habilitacyjne oraz źródła) i oznacza jako widoczne tylko te języki, które są faktycznie używane. Obsługuje tryb testowy `--dry-run` do podglądu zmian bez ich zapisywania. (ukryj_nieuzywane_jezyki)

- Na stronie szczegółów źródła wyświetlane są teraz tylko dyscypliny oznaczone jako widoczne (widoczna=True). (ukryj_niewidoczne_dyscypliny_na_stronie_zrodla)

## Bpp 202509.1226 (2025-09-27)

### Usprawnienie

- lepsze wyświetlanie kolejki eksportu do PBN: odświeżanie on-demand, sortowanie, możliwośc filtrowania
- możliwość grupowej wysyłki rekordów z kolejki eksportu PBN

## Bpp 202509.1225 (2025-09-26)

### Usprawnienie

- filtruj efekt importu list ministerialnych
- matchuj import źródeł po mniswId (ID ministerialne) - import_list_ministerialnych
- nie pozwalaj na import innych formatów niz XSLX i CSV w import_polon i import_list_ministerialnych

## Bpp 202509.1224 (2025-09-26)

### Naprawione

- import POLON: nie importuj osób z plików XLS/CSV którzy są zatrudnieni w innych instytucjach

### Usprawnienie

- możliwość filtrowania rankingu autorów po rodzajach prac

## Bpp 202509.1223 (2025-09-08)

### Naprawione

- eksport raportu rozbieżności dyscyplin: zamiast numerków czytelny plik XLSX + przejście z głównej strony na stronę z filtrowaniem rok \>= 2022

## Bpp 202509.1221 (2025-09-07)

### Naprawione

- nie licz slotów/punktów za publikację autorom "inny zatrudniony"

## Bpp 202508.1214 (2025-08-31)

### Naprawione

- poprawnie wylogowuj z Microsoft Office

## Bpp 202508.1213 (2025-08-31)

### Usprawnienie

- możliwość umieszczenia prostego "widgetu" z pracami autora na jego stronie

## Bpp 202508.1208 (2025-08-25)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- export BibTeX z poziomu administratora
- komparator PBN -- BETA
- możliwość eksportu XLSX oraz BibTeX jako akcja admina
- możliwość ponownej wysyłki elementu z kolejki eksportu PBN
- umożliwiaj wpisywanie przecinków zamiast kropek w DecimalField
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych
- ładniejsza strona 503,503,504 serwera nginx

## Bpp 202508.1207 (2025-08-25)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat
- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- export BibTeX z poziomu administratora
- możliwość eksportu XLSX oraz BibTeX jako akcja admina
- możliwość ponownej wysyłki elementu z kolejki eksportu PBN
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych

## Bpp 202508.1206 (2025-08-25)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat
- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- export BibTeX z poziomu administratora
- możliwość eksportu XLSX oraz BibTeX jako akcja admina
- możliwość ponownej wysyłki elementu z kolejki eksportu PBN
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych

## Bpp 202508.1205 (2025-08-25)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat
- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- export BibTeX z poziomu administratora
- możliwość eksportu XLSX oraz BibTeX jako akcja admina
- możliwość ponownej wysyłki elementu z kolejki eksportu PBN
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych

## Bpp 202508.1204 (2025-08-24)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat
- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych

## Bpp 202508.1203 (2025-08-24)

### Usprawnienie

- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat
- eksport ISSNów i e-ISSNów źródeł z publikacjami z ostatnich 5 lat do formatu XLSX
- umożliwiaj łatwe przechodzenie na profil instytucji celem weryfikacji danych

## Bpp 202508.1202 (2025-08-23)

### Usprawnienie

- nie pozwalaj na dwukrotne kliknięcie przycisków "Zapisz..." w module redagowania

## Bpp 202508.1201 (2025-08-22)

### Naprawione

- napraw (raz jeszcze) formularz użytkownika przy zainstalowanej autoryzacji microsoft_auth

## Bpp 202508.1199 (2025-08-21)

### Naprawione

- Poprawnie pokazuj pole "Przedstawiaj w PBN jako" dla formularza użytkownika w module redagowania dla
  instalacji używających Microsoft Auth.
- spraw, aby formularz logowania poprawnie przesyłał na stronę docelową

## Bpp 202508.1188 (2025-08-11)

### Usprawnienie

- możliwość wysyłki prac PBN bez zadeklarowanych oświadczeń (#1414)

## Bpp 202508.1186 (2025-08-11)

### Naprawione

- dodaj charakter `edited-book` dla importu z CrossRef (#1455)

## Bpp 202508.1184 (2025-08-11)

### Usprawnienie

- eksport samych oświadczeń
- polecenie do ustawienia pustych dat oświadczeń rekordów po 2022.

## Bpp 202507.1183 (2025-07-02)

### Naprawione

- usuń problem z przeliczaniem publikacji HST (PKd autora większe niż PK pracy)

## Bpp 202506.1182 (2025-06-04)

### Naprawione

- nie stosuj mnożnika 1.5 dla HST poziom 1 redakcja monografi, autorstwo rozdziału

## Bpp 202506.1181 (2025-06-04)

### Naprawione

- errata do mappera punktów dla wydawnictw ciągłych

### Usprawnienie

- procedura weryfikująca zamapowania autorów przy pierwszym imporcie z PBN

## Bpp 202506.1180 (2025-06-04)

### Usprawnienie

- popraw przypisywanie punktów PK po imporcie z PBN (#1490)
- opcjonalne pole z pytaniem o publikację pełnego tekstu pracy (#1491)

## Bpp 202505.1179 (2025-05-11)

### Naprawione

- jeżeli ilość slotów za 4 lata jest mniejsza, jak 1 to podciągaj slot dla artykułów do 1; analogicznie slot dla
  monografii za 4 lata -- jeżeli mniejszy, jak 1 to podciągaj do 1.
- zaokrąglaj ilość udziałów oraz liczby N do 2 miejsc po przecinku

### Usprawnienie

- flaga dla obiektu Uczelnia umożliwiająca włączenie/wyłączenie zaokrąglania udziałów do pełnych slotów
- obniżaj ilość udziałów do 4 jeżeli wyjdzie więcej
- obsługa dyscyplin nie raportowanych (ilość slotów mniejsza niż 12 za ostatni rok ewaluacji)
- podgląd ilości udziałów autorów za każdy rok wraz z eksportem

## Bpp 202504.1178 (2025-04-13)

### Naprawione

- naliczaj udziały dla doktorantów/innych zatrudnionych, ale nie wliczaj ich do liczby N

### Usprawnienie

- dodaj system kadrowy ID do eksportu danych autor+dyscyplina z modułu redagowania
- w przypadku zdublowania adresu strony WWW, wymuszaj unikalny dodając hashtag i losowe znaki

## Bpp 202504.1176 (2025-04-07)

### Naprawione

- nie licz punktacji N dla autorów spoza N

## Bpp 202504.1174 (2025-04-01)

### Naprawione

- błąd importu POLON przy określonym autorze, ale nie określonych polach dyscyplin
- lepsze parsowanie daty w plikach importu POLON w formacie CSV

## Bpp 202503.1172 (2025-03-31)

### Naprawione

- poprawne liczenie liczby N

## Bpp 202503.1171 (2025-03-31)

### Naprawione

- workerserver nie wymaga obecności polecenia zip(1)

## Bpp 202503.1169 (2025-03-31)

### Usprawnienie

- można zapisywać/wczytywać snapshoty przypięć i odpięć w module optymalizacji

## Bpp 202503.1166 (2025-03-21)

### Usprawnienie

- Lepsza wysyłka wydawnictwa nadrzędnego w PBN
- automatyczne obliczanie liczby N dla uczelni
- licz dyscypliny dla autora rodzaju 'inny zatrudniony'
- raporty ewaluacyjne 2022-2025
- tłumacz dyscyplin PBN obsługuje teraz 3 zakresy lat

## Bpp 202503.1165 (2025-03-16)

### Usprawnienie

- Lepsza wysyłka wydawnictwa nadrzędnego w PBN

## Bpp 202503.1164 (2025-03-16)

### Naprawione

- lepsze matchowanie dyscyplin zawierających wielkie litery, spacje, nawiasy z opisem w imporcie POLON

### Usprawnienie

- PBN UID dla publikacji musi być unikalny na całą bazę
- import absencji z POLON
- importuj "zatrudnienie do" i "zatrudnienie od" z POLONu
- lepsze drukowanie oświadczeń
- możliwość importu POLON z CSV
- ostrzegaj, jeżeli serwer PBN nie odpowie PBN UID
- uwzględniaj pole 'rodzaj autora' obiektu Autor_Dyscyplina przy obliczeniach -- autorzy
  z innym rodzajem niż "pracownik zaliczany do liczby N" lub "doktorant" NIE będą mieli
  obliczanych punktów za dyscypliny

## Bpp 202503.1162 (2025-03-05)

### Naprawione

- errata importu PBN (redaktorzy)

### Usprawnienie

- możliwość ukrywania języków - dla danych nieużywanych

## Bpp 202503.1161 (2025-03-03)

### Naprawione

- prawidłowa obsługa ostrzeżeń w TextNotificatorze

### Usprawnienie

- zwiększ czas grace-time dla tokena PBN do 24 godzin

## Bpp 202503.1160 (2025-03-02)

### Usprawnienie

- umożliwiaj dla wydawnictw zwartych wprowadzanie "okładek" z PBNu czyli wydawnictw nadrzędnych tylko w PBN
- uszczelnianie PBN UID: odmawiaj ustawienia istniejącego PBN UID dla nowego rekordu (dublowanie PBN UID) oraz ostrzegaj, gdy PBN UID dla rekordu jest modyfikowany (czyli rekord ma PBN UID i po wysyłce wg odpowiedzi z PBNu powinien być ten UID inny...)
- wyłącz bezpośrednią modyfikację pola PBN UID

## Bpp 202502.1159 (2025-02-27)

### Usprawnienie

- ostrzegaj w przypadku wysyłki PBN, jeżeli autor z dyscypliną nie posiada odpowiednika w PBN
- pokazuj wartość licencji OpenAccess w raporcie uczelnia - ewaluacja

## Bpp 202502.1158 (2025-02-22)

### Usprawnienie

- w przypadku nowych instalacji, włączaj domyślnie opcję "Wysyłaj zawsze PBN UID uczelni jako afiliację"

## Bpp 202502.1157 (2025-02-18)

### Usprawnienie

- możliwość wysyłki prac do PBN za pomocą kolejki - w tle (work in progress...)

## Bpp 202502.1156 (2025-02-17)

### Naprawione

- popraw niepoprawne wyświetlanie jednostek na pierwszej stronie uczelni

## Bpp 202502.1155 (2025-02-17)

### Usprawnienie

- lepsze wyświetlanie danych z PBN w module redagowania
- możliwość zmiany nazewnictwa, uczelnia -\> instytut, wydział -\> zakład, jednostka -\> zespół, i inne
- pokazuj źródła bez prac w przeglądaniu danych -- opcja

## Bpp 202502.1154 (2025-02-16)

### Naprawione

- zabezpieczaj przed pojawianiem się błędu "Connection already closed" po restarcie serwera bazodanowego

## Bpp 202412.1152 (2024-12-29)

### Usprawnienie

- umożliwiaj podanie parametru roku za który wgrywane będą informacje o opłatach do PBN

## Bpp 202412.1150 (2024-12-05)

### Usprawnienie

- wyłączaj wysyłanie e-mail gdy SentrySDK skonfigurowane

## Bpp 202412.1149 (2024-12-05)

### Usprawnienie

- zaimplementowano "miękkie kasowanie" w zgłoszeniach publikacji (#1468)
- specjalny widok do testowania konfiguracji Sentry

## Bpp 202411.1148 (2024-11-25)

### Usprawnienie

- obsługa publikacji z punktacją HST + nie-HST (#1316)

## Bpp 202411.1145 (2024-11-25)

### Naprawione

- korekta raportu zerowego -- opcja "pokazuj występujących we wszystkich latach
  z zakresu" poprawnie obsługuje autorów nie mających deklaracji dyscyplin
  za cały raportowany czasokres (#1413)

## Bpp 202411.1144 (2024-11-18)

### Usprawnienie

- import list ministerialnych, kolory dla dyscyplin (#1411)
- przeszukiwanie po polu "Status korekty" w multiwyszukiwarce (#1437)
- możliwość wydruku oświadczeń dot. dyscyplin z poziomu widoku publikacji dla osób zalogowanych, z uprawnieniem do dodawania
  rekordów (#1438)
- dodaj punktację do źródła / uzupełnij punktację ze źródła obsługuje również kwartyle (#1460)
- usunięto odwołania do pól dla Komisji Centralnej z kodu (#1462)
- wyświetlaj kwartyl WoS/SCOPUS w raportach (#1464)

## Bpp 202410.1142 (2024-10-14)

### Naprawione

- nie pokazuj dyscyplin z nie-aktualnego roku (#1314)

### Usprawnienie

- obsługa dyscyplin źródeł dla kolejnych lat; możliwość odfiltrowania autorów nie będących pracownikami w rozbieżności
  dyscyplin źródeł, możliwość filtrowania po roku, ograniczenie wyświetlanych prac do prac
  z roku 2017 i wyższych;

  możliwość eksportowania rozbiezności dyscyplin źródeł/rekordów do formatu XLS, (#1411)

- dodaj ID systemu kadrowego do raportu slotów zerowego i raportu slotów ewaluacja upoważnienia (#1458)

- dodaj PBN UID do raportu slotów - ewaluacja (#1459)

- wyświetlaj kwartyl źródła (WoS i SCOPUS) w raporcie slotów - ewaluacja (#1464)

## Bpp 202410.1141 (2024-10-08)

### Naprawione

- parametryzacja czasu otwarcia połączeń + domyślne wyłączenie persistent connections na produkcji (do momentu Django 5,
  gdzie można będzie użyć psycopg-pool)

## Bpp 202410.1140 (2024-10-07)

### Naprawione

- usuń błąd który nie wyświetlał nie-obcych autorów w sytuacji gdy byli przypisani do obcej jednostki + błędnej jednostki (ale mieli dodatkowe przypisania, właściwe dla uczelni) w sytuacji wyłączonej opcji "pokazuj obcych autorów w przeglądaniu danych" (#1445)
- podpowiadaj dyscyplinę dla wpisywania autorów przez "zakładkę" (powyżej 25 autorów)
- szybsze generowanie XLSa w raport slotów - ewaluacja

### Usprawnienie

- maksymalny rok dla PBN ustawiony na 2025 (#1409)
- wyswietlaj ID systemu kadrowego w raport slotów - uczelnia (#1412)

## Bpp 202410.1138 (2024-10-02)

### Naprawione

- celery aktualizacja do 5.4.0 (lepsza współpraca z Python 3.11)
- obsługuj "puste" email backends (dummy, console, memory) na produkcji (w przypadku nie działającego e-maila mogą się przydać)

## Bpp 202410.1137 (2024-10-02)

### Naprawione

- celery aktualizacja do 5.4.0 (lepsza współpraca z Python 3.11)

## Bpp 202409.1136 (2024-09-26)

### Naprawione

- poprawka błędu uniemożliwiającego zaznaczenie wydziałów w rankingu autorów

## Bpp 202407.1135 (2024-07-27)

### Naprawione

- popraw błąd wyświetlania niektórych prac doktorskich (#1440)

### Usprawnienie

- nie pokazuj obcych autorów na stronach przeglądania danych (opcja obiektu 'Uczelnia')
- opcjonalnie nie wyświetlaj autorów bez publikacji na stronach przeglądania danych (opcja obiektu 'Uczelnia') (#1439)

## Bpp 202407.1134 (2024-07-26)

### Naprawione

- przeniesiono ustawienia "ranking autorów bez kół naukowych" do obiektu uczelnia,
- poprawki kodu: usunięcie kodu raportów jednostek i autorów, w tym tzw. "raport jednostek / autorów 2012",
- poprawki kodu: usunięcie celeryui oraz raportów zależnych (j/w); przesunięcie rankingu autorów do oddzielnego modułu (#1395)

## Bpp 202407.1133 (2024-07-25)

### Usprawnienie

- ranking autorów bez kół naukowych (#1395)

## Bpp 202407.1132 (2024-07-21)

### Naprawione

- importuj plik dyscyplin bazując na formacie POLON (fix \#1434)

## Bpp 202407.1131 (2024-07-20)

### Naprawione

- nie wyświetlaj nieaktualnych kół naukowych w polu "aktualne jednostki", przesuń do "jednostki historyczne"

## Bpp 202407.1130 (2024-07-20)

### Naprawione

- poprawiono dodawanie autorów przez "zakładkę Autorzy" - problem z komunikatem "wpisz rok" w polu dyscypliny
  dla wydawnictw ciągłych i zwartych

## Bpp 202406.1129 (2024-06-24)

### Naprawione

- eksport do PBN dopasowany do nowego API (błąd ValueError("Field 'id' expected a number but got '\*\*UID\*\*'.")) (#1410)
- poprawnie wyświetlaj w raportach aktualną jednostkę, gdy wybrano również autorów "zerowych"

## Bpp 202405.1128 (2024-05-23)

### Usprawnienie

- umożliwiaj dodawanie książek / rozdziałów przez CrossRef API (#1371)

## Bpp 202405.1126 (2024-05-22)

### Naprawione

- poprawne edytowanie autorów wydawnictwa zwartego przez "zakładkę"

### Usprawnienie

- dodano deklarację dostępności z opcją skonfigurowania jej w ramach serwisu
  lub na zewnątrz (#1398)
- dodaj flagi HttpOnly oraz Secure do ciasteczek sessionId oraz csrftoken,
  dodaj nagłówek X-Frame-Options (#1406)

## Bpp 202405.1125 (2024-05-13)

### Usprawnienie

- dodano kolumnę "impact factor" do raportu uczelnia - ewaluacja (new-1)
- dodano kolumnę "Aktualna jednostka" dla raportu slotów - uczelnia bez podziału na jednostki i wydziały (new-2)

## Bpp 202312.1123 (2023-12-11)

### Naprawione

- korekta literówek w nazwach pól w wyszukiwarce + migracja zapisanych formularzy wyszukiwania (new-1)

## Bpp 202312.1122 (2023-12-10)

### Naprawione

- napraw edycję dyscyplin dla prac przy większej ilości autorów -- przez
  zakładkę "Autorzy" dla wydawnictw ciągłych i zwartych (#1194)
- umożliwiaj edycję rekordów z dużą ilością autorów (wcześniej: błąd timeout) (#1207)
- porównuj prawidłowo autorów po ORCID w module dodawania z CrossRef (#1356)

### Usprawnienie

- opis w HTML również dla wydziału (new-1)
- wyświetlaj aktualną dyscyplinę/subdyscyplinę autora (#1314)
- więcej opcji edytora HTML - opis autora i jednostki (#1341)
- lepsza lista aktualnych pracowników na stronie jednostki (#1342)
- sortuj jednostki alfabetycznie (fix \#1344) (#1344)
- Zmiana nazw kolumn/etykiet:
  - PK na MNiSW/MEiN
  - Typ KBN/MNiSW na Typ MNiSW/MEiN (#1351)
- opcjonalnie wysyłaj do PBN prace bez oświadczeń (#1358)
- nie ustawiaj domyślnie ISSN bazując na e-issn dla prac pobieranych z
  CrossRef (#1361)
- wyłącz django-password-policies gdy aktywne logowanie przez Microsoft (#1364)

## Bpp 202311.1121 (2023-11-12)

### Usprawnienie

- kompatybilność z nowym API PBN w zakresie wysyłania dyscyplin ze słowników aktualnych i nieaktualnych (odpowiedniki-pbn)

## Bpp 202310.1118 (2023-10-19)

### Usprawnienie

- umożliwiaj importowanie punktów i dyscyplin źródeł z informacji z PBN,
  umożliwiaj weryfikację źródeł po stronie PBN (ten sam ISSN, różne MNISWID,
  brak informacji o dyscyplinach) (#1354)

## Bpp 202310.1116 (2023-10-01)

### Usprawnienie

- autoryzacja za pomocą Office 365 (office365)
- możliwość instalowania backendów autoryzacyjnych jako warianty podstawowego pakietu (warianty)

## Bpp 202309.1115 (2023-09-25)

### Usprawnienie

- licz sloty dla roku 2024, przy pomocy dotychczasowego algorytmu (rok-2024)

## Bpp 202309.1114 (2023-09-14)

### Naprawione

- napraw pobieranie journali przez ich PBN UID (pobieranie-journala-przez-pbn-id)
- ponownie włacz widoczność przycisków "Eksport" oraz "Dodaj z CrossRef API" (regresja-eksport-api)

### Usprawnienie

- import list ministerialnych 2023 (import-list-2023)

## Bpp 202309.1113 (2023-09-10)

### Usprawnienie

- obsługa API v2 dla dyscyplin PBN (nowe-dyscypliny-pbn)

## Bpp 202308.1112 (2023-08-31)

### Naprawione

- poprawka dotycząca parametru 'minimalne PK' dla raportu zerowego (ignoruj
  prace z wynikiem PK mniejszym, niż zadany parametr; poprzednio - mniejszym
  lub równym) (raport-zerowy-1)

## Bpp 202308.1111 (2023-08-29)

### Naprawione

- poprawiono wyświetlanie bannera dot. cookies; kod trackera Google pojawia się w tej sytuacji opcjonalnie (bug1-cookie)

### Usprawnienie

- konfigurowalny raport zerowy (raport-zerowy-1)

## Bpp 202307.1110 (2023-07-25)

### Naprawione

- poprawka błędu pojawiającego się przy wyświetlaniu wielu stron w multiwyszukiwarce (bug1)

## Bpp 202307.1107 (2023-07-21)

### Usprawnienie

- Django 4.2 (new)

## Bpp 202307.1106 (2023-07-09)

### Naprawione

- napraw błąd związany z przetwarzaniem zmiennych przez bibliotekę formularzy `django-crispy-forms` (template1)

### Usprawnienie

- Nie loguj "anonimowych" zdarzeń związanych ze zmianą rekordu przez easyaudit (new)

## Bpp 202307.1105 (2023-07-09)

### Usprawnienie

- Moduł import_dbf przesunięty do oddzielnego modułu -- plugina (new-2)

## Bpp 202307.1104 (2023-07-04)

### Naprawione

- poprawne wyszukiwanie po wydziale pierwszego zgłaszającego autora w module "Zgłoś publikację" (new-2)

### Usprawnienie

- modułowość oprogramowania -- możliwość instalowania pakietów w namespace `bpp_plugins`, które to
  kolejno zostaną automatycznie wykryte i dodane do INSTALLED_APPS (new-1)
- pole 'Opis' również dla autorów (new-2)

## Bpp 202305.1102 (2023-05-22)

### Usprawnienie

- nowy styl prezentacji jednostek na stronie wydziału (#1344)

## Bpp 202304.1101 (2023-04-17)

No significant changes.

## Bpp 202304.1100 (2023-04-17)

### Usprawnienie

- poprawna obsługa punktacji dyscyplin z dziedzin humanistycznych, społecznych i teologicznych (1331-dyscypliny)
- opis jednostki może zawierać tagi HTML (#1341)

## Bpp 202302.1099 (2023-02-21)

### Usprawnienie

- umożliwiaj pobieranie raportu slotów - uczelnia przez API w formacie JSON (#1332)

## Bpp 202302.1098 (2023-02-06)

### Naprawione

- poprawna obsługa parametrów początkowych dla formularzy inline z autorami w przypadku dodawania rekordu
  przy pomocy CrossRef API (#1310)

### Usprawnienie

- Możliwość dodawania i wyszukiwania oświadczeń Komisji Ewaluacji Nauki
  (Uniwersytet Medyczny w Lublinie) (#1318)
- dodanie kolumny z jednostką afiliowaną do raportu ewaluacja - upoważnienia (#1330)

## Bpp 202301.1097 (2023-01-01)

### Usprawnienie

- możliwość wysyłania wyłącznie informacji o płatnościach do PBNu (bez_numeru2)

## Bpp 202212.1096 (2022-12-27)

### Usprawnienie

- - mapowanie kół naukowych do powiązania autora i jednostki do rekordu --
    dla jednostek przypisz koło naukowe, do którego przypisany jest autor. (bez_numeru)

## Bpp 202211.1095 (2022-11-30)

### Naprawione

- naprawiono generowanie raportu slotów uczelnia w formacie XLSX (#1316)

### Usprawnienie

- umożliwiaj import opłat za publikację z plików XLSX generowanych przez system (bez_numeru)

## Bpp 202211.1094 (2022-11-22)

### Naprawione

- popraw literówkę (bez_numeru)

### Usprawnienie

- możliwość wyszukiwania po rodzaju jednostki (jednostka / koło naukowe) (bn1)
- możliwość wyszukiwania po kierunkach studiów (bn2)

## Bpp 202210.1092 (2022-11-20)

### Naprawione

- popraw literówkę (bez_numeru)

### Usprawnienie

- użyj standardowego polecenia env() zamiast django_getenv() do konfigurowania serwisu (bez_numeru)

## Bpp 202210.1091 (2022-10-16)

### Naprawione

- popraw literówkę w nazwie kolumny modułu redagowania (bez_numeru)

## Bpp 202210.1090 (2022-10-16)

### Naprawione

- załącz prawidłowo pliki tłumaczeń w pakiecie WHL (bez_numeru)

## Bpp 202209.1089 (2022-10-16)

### Naprawione

- prawidłowe łączenie do kanałów ASGI w sytuacji, gdy nazwa użytkownika zawiera znaki nie-alfanumeryczne lub akcenty (bez_numeru-01)
- prawidłowe wysyłanie listów e-mail w sytuacji gdy tytuł pracy zawiera nowe linie (moduł `zglos_publikacje`) (bez_numeru-02)
- prawidłowo obsługuj pliki dodawane w formularzu zgłoszenia pracy (bez_numeru-03)
- zmiana w powiadamianiu zgłaszających publikację: użyj nie jednostki pierwszego autora do określenia wydziału (a przez to
  osoby do powiadomienia), ale użyj pierwszej nie-obcej jednostki, jeżeli taka występuje, do określenia wydziału (a przez
  to osoby do powiadomienia) (bez_numeru-04)
- poprawne komunikaty przy braku ID autora w autocomplete dla dyscypliny (bez_numeru-05)

### Dokumentacja

- użycie `towncrier` do generowania list zmian (bez_numeru-01)

### Usprawnienie

- pokazuj aktualną funkcję autora po nazwisku w wyszukiwaniu globalnym (bez_numeru-01)
- umożliwiaj większy wybór kolumn przy wyświetlaniu tabelki autorów w module redagowania (bez_numeru-02)
- możliwość szybkiego dodawania zgłoszeń prac użytkowników jako
  wydawnictwo zwarte lub wydawnictwo ciągłe (b/n),
- możliwość porównywania danych prac z CrossRef API po DOI (b/n),
- możliwość importu rekordów z CrossRef API - do nowego rekordu wydawnictwa
  ciągłego (b/n),
- możliwość eksportowania danych z tabeli autora do formatu XLS (b/n),
- popraw błąd wyszukiwarki objawiający się problemami z sortowaniem po polu
  źródło/wydawnictwo nadrzędne (b/n),
- poprawiono błąd wysyłania rekordu do PBN w sytuacji, gdy lokalnie nie istnieje
  instytucja lub osoba (b/n),
- poprawki aplikacji do uruchamiania procesów w tle (b/n),
- nie wyświetlaj przycisku "pokaż w PBN" gdy autor nie ma określonego odpowiednika w PBN (b/n),
- szybsze wyświetlanie listy nazwisk dla odpowiedników PBN dla autora (b/n),
- możliwość wyboru widocznych kolumn w module redagowania (b/n),
- synchronizacja danych z istniejącymi rekordami z CrossRef API (b/n),
- możliwość oznaczenia jednostki jako "koło naukowe" (b/n),
- możliwość oznaczenia afiliacji autora do kierunku studiów (b/n),
- możliwość wymuszenia wysyłania publikacji afiliujących na uczelnię w sytuacji, gdy jednostka
  nie ma odpowiednika PBN UID a jest poprawną, zatrudniającą autorów jednostką uczelni (b/n),
- popraw wyszukiwanie autorów w sytuacji, gdy autor o nazwisku o tym samym początku
  posiada więcej prac naukowych, niż autor o krótszym nazwisku (b/n),
- użyj funkcji do pełnotekstowego wyszukiwania z Django (porzuć .extra) (b/n),
- pozbądź się wyszukiwania wg podobieństwa z modułu redagowania dla wydawców (b/n),

## Zmiany w poprzednich wersjach

Poniżej znajduje się lista zmian w formacie sprzed używania narzędzia `towncrier`.

### 202209.1088

- usunięto moduł generowania drukowanej "Kroniki Uczelni" (b/n),
- obsługa Python 3.10, Django 3.2 (#1115),
- użycie model_bakery zamiast model_mommy (b/n),
- aktualizuj listę charakterów w multiwyszukiwarce na bieżąco (#647),
- obsługa PostgreSQL 14 (#1243),
- aktualizacja biblioteki Celery do 5.2.2 (b/n),
- podgląd edycji schematu opisu bibliograficznego (#898),
- możliwość dopisywania własnych publikacji do bazy danych przez pracowników uczelni (#1237),
- możliwość edycji zgłoszeń publikacji + powiadomienia przez e-mail (#1255),
- nowa grupa użytkowników "zgłoszenia publikacji" - redaktorzy zajmujący się zgłoszeniami
  publikacji (b/n),
- w przypadku pustej grupy użytkowników "zgłoszenia publikacji", wysyłaj informację mailową
  do grupy użytkowników "wprowadzanie danych"
- możliwość wyłączenia wymagania informacji o opłatach w formularzu zgłaszania prac (b/n),
- wyświetlaj "flash messages" dla użytkownika niezalogowanego (b/n),
- włącz język zapytań dla modułu redagowania: autorzy, źródła, jednostki, itp.
  (b/n),
- możliwość eksportu danych wydawnictw ciągłych i zwartych do formatu XLSX (b/n),
- możliwość autoryzacji użytkowników za pomocą protokołu LDAP / ActiveDirectory (b/n),
- wstępna konfiguracja za pomocą django-environ (b/n),
- wszyscy zalogowani użytkownicy którzy chcą uzyskać dostęp do raportów muszą być dodani
  do grupy "generowanie raportów" (b/n),
- formularz zgłaszania publikacji opcjonalnie wymaga zalogowania (b/n),
- możliwość konfiguracji e-mail za pomoca pliku .env (b/n)
- możliwość konfiguracji kont administratora za pomocą pliku .env (b/n),
- usunięty błąd wyszukiwania wydawców w module redagowania po PBN ID (b/n),
- możliwość obliczania slotów za 2023 (b/n),
- zgłaszanie publikacji: mozna dopisywac redaktorow do grupy "zgłoszenia publikacji" aby
  tylko do nich docierały zgłoszenia publikacji, można też dodać ich jako osoby obsługujące
  zgłoszenia dla wydziału (Redagowanie -\> Administracja) aby dostawały e-maile wg wydziału
  pierwszej jednostki autora ze zgłoszenia publikacji (b/n),
- użycie backendu django-celery-email dla wysyłania e-maili out-of-band (b/n),
- logowanie dostępu do serwisu BPP za pomocą django-easy-audit (b/n),

### 202207.1087

- aktualizacja biblioteki do generowania PDF z systemu do wersji WeasyPrint 55.0, dodatkowe
  "uodpornienie" systemu drukującego na przestarzałe certyfikaty SSL na serwerze bpp (#1223),
- wyświetlaj aktualną jednostkę w raporcie slotów - ewaluacja (#1036)
- filtry wracają do raportu slotów - uczelnia (#985)
- możliwość edycji nagłówka strony dla wyświetlania i wydruków po stronie
  użytkownika (#1226)
- możliwość edycji stopki z poziou bazy danych (b/n),
- w sytuacji, gdy kolejność jednostek ustalana jest ręcznie, nie dziel strony
  Struktura -\> Jednostki w module redagowania na podstrony (#1211)
- umożliwiaj wygenerowanie kodu JSON wysyłanego do PBN API z linii
  poleceń -- polecenie `pbn_show_json` (b/n),
- poprawnie wysyłaj strony do PBN API (#1176),
- informacja o aktualnej jednostce w raportach "zerowych" (#1224),
- możliwość pobierania/uruchamiania systemu BPP za pomoca polecenia pipx (#1231),
- przed wyszukiwaniem pełnotekstowym usuń tagi HTML z zapytania (#1222),
- pokazuj w pierwszej kolejności odpowiedniki PBN dla wydawców, które posiadają
  ID ministerialne w module redagowania (#1174)
- pole bazodanowe "aktualny" znika z modelu Autor (b/n),
- pola "aktualna jednostka" oraz "aktualna funkcja" dla modelu Autor mogą mieć
  wartość pustą (null) (b/n),
- poprawiony skrypt odpinający miejsca pracy podczas importu danych
  kadrowych (#1229),
- polecenie przebudowania pola 'aktualna jednostka' dla powiązań autor+jednostka (b/n),
- możliwość wpisywania i eksportowania do PBN danych o kosztach publikacji (#1235),
- możliwość wyszukiwania publikacji w multiwyszukiwarce po aktualnej jednostce autora (#1236),
- ostrzegaj przed zdublowanym PBN UID przy zapisie prac w module redagowania (#1152),
- wyświetlaj opis jednostki na podstronie jednostki (#1217),
- lepsza prezentacja autorów na stronie jednostki przy wykorzystaniu pola "podstawowe miejsce pracy"
  oraz importu danych kadrowych (#1215)

### 202205.1086

- import pracowników: autorzy będą mieli aktualizowane tytuły naukowe przy imporcie,
  pod warunkiem, że tytuł o takiej samej nazwie lub skrócie jak w pliku XLS istnieje również
  po stronie BPP; w sytuacji, gdyby w pliku aktualizacji był
  podany pusty tytuł lub tytuł nie istniejący w systemie BPP, zmiana
  tytułu naukowego autora nie zostanie przeprowadzona (#1033)
- aktualna jednostka: w sytuacji, gdyby autor miał dwa lub więcej przypisań do jednostek
  w tym samym okresie czasu lub w sytuacji gdy daty rozpoczęcia lub zakończenia
  pracy są puste, system w pierwszej kolejności jako aktualną jednostkę
  ustali tą, gdzie autor rozpoczął pracę najwcześniej, zakończył najpóźniej,
  zaś w sytuacji braku jednej lub obydwu tych dat -- ustali jednostkę
  aktualną na tą, która została najpóźniej przypisana, wg numeru ID
  przypisania, zwiększającego się z każdym kolejnym przypisaniem (#1177),
- w REST-API przy eksporcie danych pojawiają się streszczenia z bazy danych,
  wraz z polem języka (#1208),
- poprawiono błąd związany z niepoprawnym wyliczaniem punktów dla prac
  w roku 2022 (#1209),
- raport slotów - ewaluacja pozwala na tworzenie raportów później niż dla
  2021 roku (#1210),
- definiowalna ilość wyświetlanych jednostek na stronę (#1211),
- możliwość ukrycia jednostek podrzędnych na stronie prezentacji danych (#1212),
- możliwość wyszukiwania w multiwyszukiwarce po pierwszej jednostce i po pierwszym
  wydziale (b/n),
- tylko jedno "podstawowe miejsce pracy" dla połączenia autor+jednostka (b/n),
- poprawna obsługa pola importowanego z Excela "podstawowe miejsce pracy" (#1213),
- pokazuj rekordy, którym należy skorygować pole "podstawowe miejsce pracy" oraz
  umożliwiaj jego wyłączenie (b/n),
- ustawiaj 'Aktualne miejsce pracy' autora na podstawie pola 'Podstawowe miejsce pracy' (b/n),
- szybsze i skuteczniejsze dopasowania źródeł przy integracji danych z PBN (b/n),
- polecenie `check_email` znika, korzystamy ze standardowego `sendtestemail` (b/n),
- pokazuj 'Aktualne miejsce pracy' na podstronie przeglądania autora oraz
  w module redagowania (b/n),
- nie pokazuj 'Aktualnego miejsca pracy' na podstronie autora jezeli jest to obca jednostka (b/n),
- import pracowników: umożliwiaj automatyczne przypisywanie obcej jednostki osobom,
  których nie ma w wykazie pracowników (b/n),
- przeglądanie/autor: umożliwiaj wyszukiwanie wyłącznie w jednostkach, w których
  autor ma publikacje (b/n),

### 202202.1085

- pola "kwartyl w SCOPUS" oraz "kwartyl w WoS" dla wydawnictwa ciągłego (częściowa
  implementacja \#1204),
- pola "kwartyl w SCOPUS" oraz "kwartyl w WoS" dla punktacji źródła na dany rok
  (częściowa implementacja \#1203),
- poprawne wykrywanie serwera testowego (#1191),
- ustawiaj nagłówek X-Forwarded-Proto i korzystaj z jego zawartości - celem poprawnego
  generowania linków m.in. w REST API (https zamiast http) (#1180),

### 202201.1083

- licz punktacje dla rozdziałów i monografii z roku 2022 wg reguł dla roku
  2021 (#1200),
- w przypadku uruchomienia na serwerze z nazwą "test" w domenie, ustaw tło na
  zawierające napis "serwer testowy" (#1191),
- wielowątkowy raport genetyczny (#1202),
- edycja tytułu raportu multiwyszukiwarki - teraz może zawierać on dodatkowe linie (#1201).

### 202201.1082

- nie używaj tagów HTML w generowanych raportach 3N (b/n),
- zawężaj raporty 3N do zakresu lat 2017-2021 (b/n),

### 202201.1081

- poprawka błędu związanego z uruchamianiem procedur na serwerze przez django_tee (#1171)
- potencjalna poprawka błędu związanego z jednoczesnym działaniem wielu wątków generujących raporty,
  przebudowujących dane itp. a powstawaniem deadlocks przy przebudowie bazy (#1185),
- wliczaj monografie do limitu 2.2N dla uczelni dla algorytmów liczących 3N (#1198),
- do algorytmu genetycznego wprowadzone zostały epoki - kolejne pokolenia osobników, korzystające z populacji
  rozwiązań obliczonych przez algorytm z poprzednimi ustawieniami (b/n),
- napraw stronę administracyjną django_tee (b/n).

### 202111.1081-rc7

- automatycznie odpinanie publikacji dla raportu genetycznego 3N (#965),

### 202110.1081-rc6

- raporty 3N plecakowy i genetyczny (#965),

### 202110.1081-rc1

- poprawka błędu związanego z importem maksymalnych slotów autora (b/n),
- możliwość złapania logów z poleceń uruchamianych w nocy do bazy danych (#1136),
- raport ewaluacja - upoważnienia (#1083),
- sprawdzanie i ostrzeganie użytkownika przy zapisie rekordów w sytuacji, gdy dane DOI lub WWW
  już istnieją w bazie danych (#1059),
- raport rozbieżności autor-źródło (#1023),
- z kodu usunięto funkcjonalność importu dyscyplin źródeł (#1122),
- możliwość importu streszczeń z rekordów PBN (#1146),
- dołączaj liczbę PK dla raportów wyjściowych 3N (#1159),
- nie bierz pod uwagę autorów bez okreslonych maksymalnych udziałów jednostkowych do raportów 3N (#1158),

### 202110.1081-rc0

- liczba N dla autora staje się ilością udziałów oraz ilością udziałów monografii (#1153),
- możliwość importu udziałów dla autorów z plików XLSX (#1144),
- raport 3N pobiera dane z bazy danych (#1157),
- możliwość dodawania streszczeń do rekordów (#1155),
- możliwość eksportu streszczeń do PBN (#1155),
- możliwość eksportu słów kluczowych do PBN (#1155),
- możliwość pobierania danych autora po PBN UID z modułu redagowania (#1154),
- usuń błąd polegający na nie wysyłaniu rekordu do PBN w sytuacji istniejących już identycznych danych
  w tabeli "Przesłane dane" po wycofaniu jego oświadczeń (#1149),
- usuń błąd polegający na nieprawidłowym importowaniu oświadczeń z PBN po eksporcie rekordu zawierającego
  oświadczenia z datą (pole statedTimestamp) (#1147),

### 202110.1081-beta2

- drobna korekta opisu bibliograficznego - wraca pole "uwagi" (b/n),
- drobna korekta funkcji `strip_html` - w przypadku pustego ciągu znaków, nie podnoś wyjątku (b/n)
- aktualizajca [django-denorm-iplweb](https://github.com/mpasternak/django-denorm-iplweb/) do wersji 0.5.3 -- korekta błędu z deadlockami (b/n),

### 202110.1081-beta1

- poprawiono błąd występujący przy wysyłaniu publikacji do PBN przez panel redagowania, w sytuacji, gdy
  wydawnictwo nadrzędne nie miało odpowiednika PBN UID, a użytkownik nie był autoryzowany (b/n),
- poprawiono bład występujący przy wysyłaniu publikacji do PBN i włączonym kasowaniu oświadczeń,
  w sytuacji, gdy serwer PBN odpowiada statusem 200 ale dokument nie zawiera tresci (b/n),
- usunięto kod odpowiadający za eliminowanie ciągu znaków \[kropka\]\[przecinek\] z opisów bibliograficznych (b/n),

### 202110.1081-beta0

- zmiana określenia z formularza raportu "tylko prace z jednostek uczelni" -\> "tylko prace z afiliacją uczelni"
  (#1094),
- okreslanie liczby N dla autora dla każdej z dyscyplin (#1143),
- poprawne przebudowywanie rekordów przy zmianie szablonu przy pomocy [django-denorm-iplweb](https://github.com/mpasternak/django-denorm-iplweb/) (#1107, \#1135),
- opcja "tylko prace afiliowane" dla raportów: uczelni, wydziału, jednostki i autora (#1092).

### 202110.1081-alpha

- pełnotekstowe wyszukiwanie dla indeksu wydawców, wydawców PBN, wydawnictw zwartych (#1102)
- caching-framework przy użyciu [django-denorm-iplweb](https://github.com/mpasternak/django-denorm-iplweb/) (#1099)
- raport optymalizujący 3N (#1131),
- liczba N dla uczelni dla każdej z dyscyplin (#1131),
- oznaczaj alias wydawcy w nazwie (#1097),
- pozwalaj odszukać aliasy wydawcy w adminie (#1097),

### 202109.1080-beta1

- kasowanie oświadczen dla rekordów z PK=0 z linii poleceń (#1121),
- błąd przy zapytaniu kasowania wszystkich dyscyplin przed wysłaniem do PBN nie zaburza
  dalszej wysyłki rekordu (#1130),
- poprawna obsługa parametru "nie wysyłaj prac z PK=0" dla integratora uruchamianego
  z linii poleceń (#1108),
- poprawne wyświetlanie komunikatu w przypadku próby eksportu pracy z PK=0 (#1108),

### 202109.1080-beta0

- możliwość nadpisywania dyscyplin podczas importu -- wystarczy podać imie i nazwisko istniejacego
  w systemie autora w pliku XLS (#884)
- możliwość zmiany opisu bibliograficznego przez użytkownika (#898),
- możliwośc zmiany tabelki z widokiem publikacji przez użytkownika (b/n),

### 202109.1080-alpha

- przypisywanie dyscyplin za pomocą opcji "rozbieżności dyscyplin" (#909),
- sortowanie opcji multiwyszukiwarki (opcja "Szukaj") (#895),
- polecenie `reset_multiseek_ordering` do resetowania kolejności sortowania do domyślnej (#895),

### 202109.1079

- akcja grupowego wysyłania do PBN w module Redagowania dostepna dla wydawnictwo zwartych (b/n),
- usunięto regresję związaną z polami WWW/DOI/publiczny WWW, polegającą na nie pojawianiu się ich
  wartości w formularzu w module redagowania i nie zapisywaniu się ich (b/n),
- pobieranie po DOI/ISBN zawsze pobiera rekordy z bazy danych PBNu (które to mogły się zmienić w
  tak zwanym międzyczasie w stosunku do lokalnego cache) (b/n),
- normalizuj ISBN zapisywany dla lokalnego cache publikacji PBNu (b/n),
- eksperymentalne wyszukiwanie za pomocą DjangoQL dla wydawnictw zwartych (b/n),
- wyświetlanie linku do wysłanych danych przy komunikacie błędu (b/n),
- łatwe przechodzenie z aliasu do wydawcy nadrzędnego (b/n),
- usunięto błąd który pojawiał się gdy tworzono wydawcę będącym aliasem z przypisaniem poziomów (b/n),
- możliwość wyszukania po konkretnym wydawcy indeksowanym z poziomu rekordu wydawcy w module Redagowania (b/n),
- poprawione tłumaczenie drobnych elementów w panelu Redagowania ("Add" -\> "Dodaj", "Filter" -\> "Filtruj) (b/n),
- poszerzone pole wyszukiwania tekstowego/języka DjangoQL w module redagowania (b/n),
- włącz DjangoQL dla wydawnictw ciągłych (b/n),
- usunięto błąd pojawiający sie w module Redagowania przy wysyłaniu do PBN, gdy wystąpił inny błąd,
  niż autoryzacji lub związany z wysłanymi już danymi (b/n),
- zmiana nomenklatury: publikacja w PBN API -\> publikacja z PBN API (b/n),
- możliwość pobierania prac z PBN API po identyfikatorze PBN UID z Redagowanie -\> PBN API -\> Publikacje -\> Dodaj (b/n),
- możliwość pobierania prac z PBN API po numerze MongoID z pola "Odpowiednik w PBN" (b/n),
- konfigurowalne w obiekcie uczelnia: kasowanie oświadczeń rekordu przed wysłaniem danych do PBN (b/n),
  konfigurowalne nie wysyłanie z automatu prac z PK=0 (b/n),
- liczenie slotów dla roku 2022 (wg algorytmu 2021) (b/n),
- wyłaczono opcje "Dodaj" dla widoczności pól w wyszukiwarce (b/n),
- polecenie 'pbn_importuj_wydawcow', pozwalające pobrać nowe dane z PBN do lokalnego indeksu wydawców (b/n),
- możliwość pobrania źródła przez PBN UID (b/n),

### 202108.1078

- pobieranie pracy z PBNu za pomocą ISBN uwzględnia E-ISBN w sytuacji, gdy ISBN nie jest wypełniony (b/n),
- w przypadku wielu prac z tym samym ISBN, wcisnienie przycisku "pobierz po ISBN" wyświetla je wszystkie (b/n),
- przy wysyłaniu do PBN, w przypadku braku wartości w polu ISBN, weź wartość z pola E-ISBN, jezeli istnieje (b/n),
- przy wysyłaniu do PBN, w przypadku trybu udostępnienia "po publikacji", gdy ilośc miesięcy jest pusta,
  wstawiaj tam cyfrę zero (b/n),
- przy wysyłaniu do PBN "z automatu", w przypadku gdyby po stronie PBN istniał już rekord o takim DOI lub
  ISBN, spróbuj automatycznie pobrać ten rekord i dopasować do wysyłanego (b/n),
- przy eksporcie do PBN, użyj strony WWW wydawnictwa nadrzędnego dla rozdziałów, w sytuacji, gdyby nie miały
  określonej strony WWW (b/n),
- nie pokazuj "publikacje instytucji" w module redagowania w menu (b/n),
- nie wysyłaj artykułów bez zadeklarowanych oświadczeń do PBN (b/n),
- kasowanie oswiadczen kasuje rowniez historie wysłanych danych (b/n),
- narzedzie command-line do PBN: możliwość wysłania wyłącznie błędnych rekordów ponownie, możliwość wymuszonego
  wysłania wszystkich rekordów (b/n),
- kasowanie obiektów SentData przy usuwaniu oświadczeń (b/n),
- poprawka błędu przy wysyaniu rekordów przy odpowiedzi serwera PBN 400 i istniejącym DOI/ISBN (b/n),
- opcja dla narzędzia command-line umożliwiająca wysyłąnie do PBN wyłącznie nowych rekordów (bez
  informacji w tabeli SentData) (b/n),
- nie wysyłaj do PBN, jeżeli rozdział nie ma oświadczeń (b/n),
- rozszerzono zakres wysyłanych prac do PBN przez automatyczne narzędzie zgodnie z w/wym poprawkami (b/n)
- umożliwiaj "odpinanie" dyscyplin (b/n),
- przycisk "pobierz po DOI" pobierający prace z PBNu po adresie DOI,
- lepsze komunikaty błędów w przypadku braku autoryzacji w PBN i kliknięciu przycisku "pobierz po DOI"
  lub "pobierz po ISBN" (b/n),
- nie pozwalaj na wpisanie adresu WWW w pole DOI (b/n),
- nie pozwalaj na wpisanie odnośnika do doi.org w pole WWW (b/n),
- lepsze komunikaty błędu w przypadku braku tokena autoryzacyjnego przy eksporcie do PBN (b/n),
- PBN wysłane dane otrzymują typ rekordu i możliwosć filtrowania/sortowania po nim (b/n),
- poprawki kodu przycisku "Wyślij ponownie" z wyslanych danych PBN (b/n)

### 202108.1077

- widoki PBN API umożliwiają łatwiejsze odnajdywanie rekordów na stronie PBN oraz w serwisie BPP (b/n),
- zwiększ ilosć widocznych prac w multiwyszukiwarce do 25000,
- aktualizuj lokalną kopię oświadczeń przy wysyłce rekordu (b/n),
- wycofywanie oświadczeń instytucji z poziomu modułu "Redagowanie" (b/n),
- przyciski umożliwiające szybkie przechodzenie między modułami PBN API a edycją prac w module "Redagowanie" (b/n)
- możliwość filtrowania rekordów wydanwnictwa zwartego wg posiadania lub nie wydawnicwa nadrzędnego oraz
  wg kryterium bycia lub nie wydawnictwem nadrzędnym dla innego rekordu (b/n),
- przycisk "Pobierz wg ISBN" w module redagowania, do pobierania odpowiedników z PBN po ISBN - interaktywnie
  (b/n),
- matchuj prace po ISBN - wyłącznie rekordy nadrzędne (b/n),
- użyj bardziej efektywnej metody pobierania danych do generowania PDF do raportu autorów (b/n),
- bardziej wydajne pobieranie PBN UID po ISBN (b/n),
- usuwanie wszystkich oświadczeń instytucji z linii poleceń (b/n),

### 202108.1075

- szybsze przeglądanie zawartości bazy w opcji PBN API w module redagowania (b/n),

### 202108.73

- poprawki importu i synchronizacji danych z PBN (b/n),
- możliwość konfiguracji wyświetlanych opcji w multiwyszukiwarce (#896),

### 202108.72

- poprawki matchowania rekordów przy wpisywaniu odpowiedników PBN w module redagowania: szybsze wyszukiwanie
  autorów, instytycji i publikacji, czytelniejsze rekordy instytucji i autorów, możliwość wyszukiwania publikacji
  po PBN ID, DOI, źródeł po PBN ID, ISSN, E-ISSN, książek po ISBN i inne
- pole "język oryginalny" dla tłumaczeń + eksport do PBN,
- jeżeli autor ma identyfikator PBN to nie wysyłaj ORCIDu (błąd o braku po stronie PBN),

### 202107.71

- usunięto pole "data ostatniej aktualizacji dla PBN" (#1061),
- szybsze pobieranie publikacji z profilu instytycji PBN, dokładniejsze matchowanie, pobieranie
  oświadczeń z profilu instytucji PBN, wydajniejsze importowanie do bazy danych danych z PBN (#1088),
- szukaj po tytule w danych wysłanych do PBN (#1086),
- nie wysyłaj ORCID gdy autor nie posiada dyscypliny (#1085),
- wysyłanie wydawnictwo zwartych do PBN (#1044),

### 202106.71

- w przypadku braku daty udostępnienia OpenAccess, wysyłaj rok + pierwszy miesiąc (b/n),

### 202106.70

- szybsze globalne wyszukiwanie (#1067),

- wyszukiwanie jednostek po PBN UID w module redagowania (#1071),

- wyświetlaj płaską listę jednostek przy wyszukiwaniu lub filtrowaniu w module redagowania (#1082),

- eksport PBN: wysyłaj nie-puste oświadczenia, nawet gdy jednostka nie ma ustawionego odpowiednika w PBN (#1070,

- wyświetlaj kolumne "Profil ORCID" dla raportu slotów - ewaluacja (#1075),

- usuń zbędny tekst "jest nadrzędną jednostką dla" (#1074)

- powiązania autorów z dyscyplinami z modułu redagowania:
  - wyświetlają PBN UID i umożliwiają filtrowanie po nim (#1072),
  - eksportują poprawnie wartość ORCID i PBN UID do formatu XLS/CSV (#1072),

- eksport PBN: nie wysyłaj pola 'months' w przypadku trybów opublikowania innych, niż 'po publikacji'
  (#1081)

- eksport PBN: próbuj wysyłać wszystkie ORCIDy, niezależnie czy są po stronie PBN czy nie (wyłącz
  "ciche" wysyłanie autorów z brakującym po stronie PBNu ORCIDem) (#1078),

- eksport PBN: matchuj publikacje również po źródle (#1080),

- eksport PBN: pobieraj wszystkich autorow (#1077) i wszystkie publikacje z PBNu (b/n)

### 202105.67

- usunięcie błędu polegającego na niemożliwości zapisania rekordu gdy w momencie
  tworzenia go dodany był autor z dyscypliną (b/n)
- hierarchia jednostek (#1018),
- raport uczelni (#1028)

### 202105.66

- w przypadku synchronizacji prac z PBN i podwójnego DOI, wyswietlaj komunikat,
- wyłącz raportowanie Sentry dla procesów interaktywncyh (#1064),

### 202105.65

- eksportuj naturalId w danych z PBN (#1063),
- lepsze matchowanie źródeł z PBN (#1064),
- weryfikuj obecnośc ORCID w PBN dla niezmatchowanych autorów (#1054),
- pobieraj wszystkie osoby z PBNu (b/n),
- pole dla wpisania wartości, czy praca występuje w profilu ORCID autora (#1054),
- nie eksportuj oświadczeń dla autorów bez afiliacji (#1055),

### 202105.64

- eksport danych dot. OpenAccess do PBN (#1045),
- możliwosć wyswietlania raportów tylko dla członków zespołu (#1047),
- nie dodawaj automatycznie linków w tytułach prac (#976),
- możliwość ponownej synchronizacji rekordów niepoprawnie wyslanych
  (#1052),
- możliwość wysłania wielu rekordów do PBN z poziomu listy rekordów w module
  redagowania (b/n),
- synchronizacja wysyłania do PBN opcjonalna przy edycji rekordu (#1051),
- edycja autorów może odbywać się niezależnie od edycji "głównego" rekordu
  (#1049),
- ograniczenie maksymalnej liczby autorów edytowanej razem z
  formularzem rekordu do 25,
- lepszy komponent dla określania uprawnień w module administratora (#1048),
- wyszukiwanie po DOI w multiwyszukiwarce, module redagowania, globalnym
  wyszukiwaniu (b/n),
- ostrzeganie o zdublowanych DOI w module administratora (b/n),
- możliwość wyszukiwania po PBN UID w globalnym wyszukiwaniu w module redagowania
  oraz w interfejsie użytkownika (b/n),

### 202104.62

- nie sprawdzaj obecnosci tabel rozbieżnosci dyscyplin przy starcie serwera (b/n),

### 202104.61

- tagi Google Scholar na podstronach publikacji (#993),
- wymiana danych z PBN przez API (#949),

### 202103.60

- pole "Afiliuje" w wyszukiwaniu traci operator "różne od" (#988),
- czasopismom (źródłom) można określać listę dyscyplin naukowych (#863),
- ulepszone linki tekstowe dla rekordów w bazie danych (#1001),
- raport slotów - autor może być eksportowany do PDF bezpośrednio z poziomu
  BPP (b/n),
- korygowanie "starych" linków tekstowych przy założeniu, że ID pracy na końcu
  linku nie uległo zmianie (#1015),
- umożliwiaj filtrowanie rekordów w module redagowania po osobie, która ostatnia
  zmieniała rekord oraz po osobie, która utworzyła rekord (#957),
- raport wyświetlający rozbieżności punktacji IF pomiędzy źródłem a rekordem
  (#1002),
- poprawne wyszukiwanie po słowach kluczowych (#1027),
- konfigurowalne numerki baz danych REDIS (#1026),
- walidacja pola 'Kod' przy edycji dyscyplin naukowych w module redagowania (#1030),

### 202103.59

- poprawnie generuj raporty slotów - uczelnia dla eksportu wszystkich prac (#1010),

### 202103.58

- poprawny link do przykladowego pliku do importu list IF (#1008),
- opis tekstowy artykułów na miniblogu w UI redagowania (#706),
- sortowanie powiązań Autor+Jednostka po dacie zatrudnienia, nie po nazwie (#1006),
- możliwośc wyświetlania wybranych stanowisk autorów dla aktualnych jednostek za nazwiskiem autora
  na stronie prezentacji danych autora (#1005),
- naprawiono błąd związany z przebudowaniem cache po wyłączeniu transakcji (b/n)
- nie licz punktów dla dyscypliny w sytuacji, gdy nie ma żadnych autorów w tej dyscypline
  (k=0) nawet dla progu 1 (#1006),
- prawidłowo formatuj tekstowe opisy obiektu "Poziom wydawcy" w module redagowania (#999),
- pola "od roku", "do roku" i "upoważnienie PBN" oraz kolumna "upoważnienie PBN" w
  raport slotów uczelnia - ewaluacja (#995)

### 202103.57

- limit slotów w raporcie slotów-uczelnia, możliwość wygenerowania wszystkich prac (#997),
- import list IF (#868),
- poprawka importu pól daty z plików XLSX (b/n),
- licz poprawnie punktację w przypadku k=0 (#986),
- rozbij źródło/wydawnictwo nadrzędne i szczegóły na dwie kolumny w raporcie slotów - ewaluacja (#939),

### 202103.56

- wyeliminowano błędy związane z niepoprawnie sformułowanymi zapytaniami w multiwyszukiwarce (b/n),
- wyeliminowano błędy związane z przeszukiwaniem po datach w przypadku operatorów mniejszy/większy/
  mniejszy lub równy/wiekszy lub równy (#982),
- wyeliminowano drobny bład podczas importu dyscyplin (#962),
- raport uczelnia-ewaluacja: jeżeli autor ma punktowane prace w danym roku w danej dyscyplinie, ale w innym
  roku będącym w zakresie raportu autor jest "zerowy", to nie pokazuj go jako zerowego (#984),
- wyeliminowano błąd przebudowy cache poprzez usuniecie 'globalnej' transakcji (#989),
- prawdziwe, indeksowane słowa kluczowe dla wszystkich rekordów, z możliwością edycji oraz przeszukiwania (#883),
- \[API\] słowa kluczowe eksportowane są teraz jako lista, nie jako ciąg znaków (b/n),
- \[raporty\] poprawka błędu uniemożliwiającego wygenerowanie raportu w formacie XLSX podczas gdy
  jeden z nagłówków elementów raporty zawierał w sobie znak "/" (slash) (b/n),
- poprawka błędu związanego z resetowaniem hasła,
- usunięto identyfikator pesel_md5 z systemu,
- import danych kadrowych z plików XLS (#983),
- \[ASGI\] raporty opracowywane w tle powinny przestać gubić komunikaty powiadomień,
- popraw błędy z wyświetlaniem stron z podwójnym znakiem "-" w polu "slug" (#980),
- popraw błędy przy imporcie dyscyplin w sytuacji gdy nie określono pola tytuł naukowy (#885),
- popraw błędy przy wyszukiwaniu jednostek bez wydziału (#964),
- możliwość indywidualnego określenia wliczania do rankingu dla każdego charakteru formalnego
  oraz typu KBN (#973)

### 202102.55

- ograniczenie ilości zapytań przy generowaniu rekordów do API (#981),
- poprawne sortowanie po źródle/wydawnictwie nadrzędnym (#938),
- ORCID i PBN ID w raporcie zerowym (#940),
- umozliwiaj grupową zmianę statusu korekty w module redagowania (#948),
- umożliwiaj tworzenie raportu z wymierną liczbą slotów dla autora (#966),
- opcjonalnie pokazuj autorów zerowych w raporcie slotów-uczelnia (#941),
- pokazuj ORCID w module redagowania przy powiązaniach autor-jednostka (#970),
- optymalizacja algorytmu liczącego dla zadania dużej ilości slotów w sytuacji,
  gdy pracownik jej nie osiąga (b/n),
- poprawne ukrywanie prac w wyszukiwaniu globalnym oraz po wpisanu URL (#950).

### 202101.54

- poprawne wyświetlanie charakteru formalnego dla doktoratów i habilitacji
  w widoku prac (b/n),
- możliwość wyszukania prac z ustawioną strona WWW \[errata\] (#865),
- aktualizacja pakietu django-password-policies-iplweb do wersji 0.8.0 (b/n),
- aktualizacja pakietu django-multiseek do wersji 0.9.43 (b/n),
- lepsze wyszukiwanie wg daty utworzenia rekordu dla zakresu dat (#932),
- wyświetlaj link do PubMedCentral dla prac z PMC ID (#959),
- poprawki pobierania PubMed ID (#958),
- poprawne zawężanie do zakresu punktów PK (#967),
- katalog cache ma nazwę z numerem wersji (#961),
- raport slotów uczelnia wg algorytmu plecakowego (#923),
- ustawienie ukrywania publikacji na podglądzie i w wyszukiwaniu globalnym (#950),
- w multiwyszukiwarce w polu "Wydawnictwo nadrzędne" pokazuj wyłącznie rekordy
  będące już wydawnictwami nadrzędnymi dla rekordów (#953).

### 202101.53

- poprawne opisy powiązań autora z dyscypliną w module redagowania (#686)
- zezwalaj na więcej, niż jedną pracę doktorską dla autora (#873)
- pełne BPP ID na stronie pracy (#951)
- możliwość wyszukania prac z ustawionym DOI (#864)
- możliwość wyszukania prac z ustawioną strona WWW (#865)
- opcjonalnie traktuj jako slot zerowy prace z PK=5 (#877)
- wygodny podgląd powiązań autora z dyscypliną w module redagowania (b/n)
- możliwość eksportu danych dyscyplin autorów w formacie XLS (#893)
- wyświetlanie rekordów powiązanych dla wydawnictw zwartych (#897)
- wyszukiwanie rekordów powiązanych dla wydawnictw zwartych (#897)

### 202101.52

- raport slotów - autor umożliwia zbieranie "do N slotów" dla autora (b/n),
- konfigurowane wartości domyślne dla daty w formularzach (#947)
- wyszukiwanie pełnotekstowe uwzględnia myślniki (#851)
- poprawne wyszukiwanie po polu "Licencja OpenAccess ustawiona" (#934)
- możliwość wyszukiwania po polu "charakter formalny ogólny" (#933)
- poprawne wyszukiwanie w polach numerycznych (#913)
- możliwość powiązania zewnętrznej bazy danych również dla wydawnictwo zwartych (#935)
- poprawne działanie funkcjo restartującej hasło na produkcji (#936)

### 202012.51

- zbieranie slotów dla autora za pomocą algorytmu plecakowego (b/n),
- ukrywanie statusów korekt w multiwyszukiwarce (#942),
- ukrywanie statusów korekt przy obliczaniu slotów -
  liczenie punktów za sloty w zależności od ustawienia statusu korekty (#945),
- ukrywanie wybranych statusów korekt w rankingach (#946),
- ukrywanie wybranych statusów korekt w raortach (#943),
- ukrywanie wybranych statusów korekt w API (#946),

### 202011.50

- prawidłowe obliczanie punktów dla tłumaczeń (#931)

### 202011.49

- podczas obliczania slotów dla liczby autorów z dyscypliny nie uwzględniaj autorów
  z odznaczonym polem "afiliuje" (#927)
- pole "pseudonim" dla autora (#921)
- wyświetlanie wewnętrznego ID autora na podstronie autora (b/n),
- możliwość otwarcia strony autora po ID za pomocą linku /bpp/autor/{ID}/ (b/n),
- prawidłowe obliczanie punktów dla referatów (#930)

### 202009.48

- umożliwiaj konfigurację domyślnych wartości parametrów dla
  wybranych formularzy oraz wyświetlanie dowolnego tekstu HTML przed i
  po formularzach (#922)
- zamiast zbierać prace na minimalny slot, zbieraj prace do osiągnięcia maksymalnego
  slotu: usunięta zostaje opcja "minimalny slot" oraz "wyświetlaj prace poniżej minimalnego
  slotu", dodana zostaje opcja "maksymalny slot" (#917)
- licz sloty dla roku 2021 jak dla roku 2020 (#925)
- poprawka błędu edycji wydawców (#925)

### 202008.47

- ograniczaj wyświetlanie do 20 tys rekordów przy braku zapytania w wyszukiwarce (b/n),

### 202008.46

- możliwość przypisywania grantów rekordom (b/n),
- możliwość przypisywania elementów repozytoryjnych (plików) rekordom (b/n),

### 202008.45

- backend cache zmieniony na django-redis-cache (wcześniej: pylibmc) (b/n),

### 202008.43

- lepszy silnik notyfikacji dynamicznych (channels+ASGI+uvicorn) (b/n),
- import danych o dyscyplinach autorów z plików DBF (b/n),
- dodatkowe pola "rodzaj autora" oraz "wymiar etatu" (b/n),
- import danych grantów, nr odbitek i liczne drobne poprawki importu DBF (b/n),

### 202007.41

- poprawione regenerowanie opisów bibliograficznych (#875)
- prawidłowe renumerowanie kolejności z poziomu polecenia nawet w sytuacji gdy afiliacja
  autora przypisana jest niepoprawnie (afiliuj="tak" przy obcej jednostce) (b/d)
- prawidłowe wyszukiwanie wydawnictw nadrzędnych w module redagowania (#882)

### 202006.40

- poprawne importowanie niektórych akcentowanych znaków z plików DBF (n/d),
- zamień pola "szczegóły" i "informacje" przy imporcie (#857)
- opcjonalna walidacja pola "Afiliowana" przy przypisaniu autora do rekordu
  za pomocą zmiennych środowiskowych (n/d),
- dodatkowe pole "nie eksportuj do API" dla rekordów wydawnictw zwartych, ciągłych,
  patentów, prac doktorskich i habilitacyjnych.

### 202006.39

- prace habilitacyjne i patenty w API (#859)
- nie importuj pola źródła 200C w przypadku importu DBF dla prac z redaktorami (#797)
- przy imporcie z plików DBF ustawiaj to samo ID jednostki co po stronie DBF (n/d)
- przy imporcie plików DBF poprawnie importuj wartości niepoprawnie zapisane w DBF (#876)
- upoważnienie PBN - pole (#840)

### 202006.38

- procedura serwerowa do wycinania wartości pola ISBN z pola "Uwagi" (#796)
- poprawione wycinanie numerów i suplementów (#845)
- lepszy opis dla rekordów z wydawnictwem nadrzędnym - oznaczenie wydania dla rozdziałów (#843)
- charakter formalny dostaje nowe pole - charakter ogólny (książka/rozdział/artykuł) (wynika z \#843)
- wyświetlaj informacje o czasie udostępnienia OpenAccess w API (#861)

### 202005.37

- eksport promotora w pracach doktorskich w API (b/n),
- pole "oznaczenie wydania" (#843),
- poprawnie importuj ilość stron dla monografii dla plików DBF (#847),
- lepsze przypisywanie grup punktowych w imporcie DBF (b/n),

### 202005.36

- poprawki importu rekordów z plików DBF oraz procedur wycinających
  dane na temat numeru i tomu (#845)
- import z plików DBF zachowuje oryginalne numery ID (b/n),
- eksport prac doktorskich w API (b/n),

### 202004.35

- filtrowanie po roku publikacji w API (#844)

### 202004.34

- zmiany nazw kolumn raportu ewaluacji (#830)
- dodatkowe pola metryczki rekordu oraz sumowanie w XLS w raportach slotów
  (#829),
- rozszerzanie listy źródeł przy imporcie plików DBF (b/n),
- nie wymagaj wydziału przy eksporcie do PBN - eksportuj całą uczelnię (#828)
- wygodniejsze sortowanie wydziałów w module redagowania oraz możliwość
  ręcznego sortowania jednostek (#802)

### 202004.33

- eksport pola public-uri do PBNu eksportuje w pierwszej kolejnosci adres publiczny,
  w drugiej - płatny, adresy generowane na podstawie PubMedID nie są już wysyłane (#834)
- eksportowane jest pole book-with-chapters do PBN (#824)
- nie usuwaj spacji przed kropką przy imporcie publikacji (b/n),

### 202004.32

- filtrowanie po charakterze formalnym w API (b/n)

### 202004.31

- filtrowanie po dacie w REST API dla obiektów Autor,
  Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Zrodlo (b/n),
- dodatkowe pola ISSN / EISSN w REST API (b/n),
- eksportuj identyfikator ORCID autora do PBN, datę modyfikacji rekordu
  dla wydawnictw, datę dostępu dla OpenAccess (#824)

### 202003.29

- Django 3.0 (b/n),
- REST API (b/n),
- narzędzie do dzielenia "podwójnych" wydawców po imporcie (b/n)

### 202003.27

- napraw błąd importu pliku dyscyplin uniemożliwiający zmianę zaimportowanych już
  dyscyplin (b/n),
- drobne poprawki zachowania admina (nie wyświetlaj listy tabel z importem danych z
  pliku DBF jeżeli nie są zaimportowane, nie pozwalaj na usuwanie własnego konta,
  nie pozwalaj na usunięcie ostatniego konta superużytkownika, nie wyświetlaj
  komunikatu błędu gdy próbujemy dopisać rekord z powiązaniem autora do rekordu
  w sytuacji gdy nie podano jednostki) (b/n),

### 202003.26

- wyświetlaj również wydawnictwa zwarte w raporcie slotów - ewaluacja (b/n),
- skracaj listę autorów gdy powyżej 100 znaków dla widoku HTML w raporcie slotów - ewaluacja (b/n),
- umożliwiaj filtrowanie raportu slotów - ewaluacja (b/n),

### 202003.25

- wyświetlaj kolumnę z ilością wszystkich autorów w raporcie slotów - autor (#807)
- wyświetlaj mniejsze czcionki w raporcie slotów - autor
- raport slotów - ewaluacja (#809)

### 202003.23

- wyświetlaj dodatkowe kolumny w raporcie slotów - autor (#807)

### 202003.22

- regresja: błędy raportu slotów (#811)

### 202003.21

- regresja: wyszukuj po polu "Dostęp dnia (wolny dostęp)" (#815)
- regresja: wyszukuj prawidłowo prace w obcych jednostkach (#816) + poprawki
  wydajności,
- ustalaj obcą jednostkę w uczelni przy imporcie (b/d),
- nie pozwalaj na ustalenie nie-obcej jednostki jako obcej dla uczelni (b/d),
- regresja: wyszukuj prawidłowo prace w obcych jednostkach (#816)
- poprawnie wyszukuj przypisania autora do dyscypliny w multiwyszukiwarce (b/d),
- mniejsza ilość zapytań o grupy użytkownika w redagowaniu (b/d),

### 202003.20

- ORCID i PBN ID w raport slotów - uczelnia (#808),
- wyświetlanie numeru PBN ID na stronie autora (b/n),
- licz sloty tylko dla autorów afiliowanych (#810)
- w przypadku zaznaczenia opcji 'afiliuje' przy obcej jednostce, zgłaszaj błąd (b/n),
- operatory do multiwyszukiwarki: afiliuje TAK/NIE, dyscyplina ustawiona TAK/NIE,
  obca jednostka TAK/NIE (umożliwia zapytania z \#816, \#817, \#814, \#815)

### 202003.19

- import pliku DBF nie dzieli tytułu po znaku równości na oryginalny i pozostały (b/n),
- autorom przypisanym do rekordów patentów można przypisywać dyscypliny naukowe (b/n),
- aktualizacja pakietów zależnych z przyczyn bezpieczeństwa (bleach3) (b/n),
- eksport PBN: eksportuj prace z PK większym, niż 5 (poprzedni warunek: większe lub równe) (b/n),
- aliasy wydawców (b/n),
- tworzenie źródła wprost z formularza dodawania wydawnictwa ciągłego w module redagowania (#800),
  tak utworzone źródło dostanie zawsze rodzaj źródła równy: periodyk,
- wyświetlanie PubMed ID, PMC ID oraz ISBN i ISSN w opisie bibliograficznym (#801, \#799),

### 202002.18

- wyświetlaj lata dla raportu zerowego w jednej kolumnie (#812)
- nie uwzględniaj wpisów dyscyplin bez punktacji w raporcie zerowym (#785)
- umożliwiaj oddzielne zarządzanie widocznością raportu slotów zerowych (#785)
- nie dodawaj pola 103 do konferencji przy imporcie DBF (#794)
- akceptuj podwójnych autorów przy imporcie DBF (#792)
- poprawnie rozpoznawaj formę główną autora (#806)
- poprawnie importuj z plików DBF numery stron i pola szczegółów (#795, \#796)

### 202002.17

- umożliwiaj poprawne wylogowanie użytkownika z systemu, bez wyświetlania strony błędu (#714)
- nie zgłaszaj awarii dla eksportu XLS pustych skoroszytów dla raportu slotów - autor (#782)
- umożliwiaj poprawne resetowanie hasła użytkownika (#675)
- napraw błąd w wyszukiwaniu pełnotekstowym (#683)

### v202002.16

- raport slotów "zerowy", pokazujący autorów z zadeklarowaną dyscypliną, ale bez prac w tej
  dyscyplinie (#785)

### v202002.15

- rezygnacja z Pipfile na rzecz pip-tools
- rezygnacja z Raven na rzecz sentry-sdk
- zmiany eksportu do PBN:
  - wyrzucono pole eksport-pbn-size,
  - wyrzucono pole employed-in-unit dla autorów/redaktorów,
  - wykasowano pola "other-contributors", generują się wszyscy autorzy (również obcy)
  - dla książek pod redakcją generują się wszyscy redaktorzy oraz nie generują się autorzy rozdziałów
  - dla książek i rozdziałów generują się tylko publikacje z punktacją PK\>5

### v202001.14

- poprawiony błąd związany z obliczaniem punktów dla dyscyplin z dziedziny nauk humanistycznych, etc.
  (sentry:BPP-UP-8Q)

### v202001.12

- poprawne obliczanie punktacji dla dyscyplin z dziedziny nauk humanistycznych, społecznych i teologicznych (#775)
- mniejszy rozmiar pliku wynikowego (whl)
- usunięto minimalną ilośc slotów dla raportu slotów - uczelnia (#781)
- rozbijanie raportu slotów - uczelnia na jednostki i wydziały (#784)

### v201911.9

- import baz danych z systemów zewnętrznych
- równolegle działające polecenie rebuild_cache, przyspieszające czas nocnej przebudowy cache bazy

### v201910.7

- niezwykle eleganckie tabele w XLS wraz z opisem (#766)
- bardziej widoczny indeks wydawców w module redagowania (#771)
- uwzględniaj prace posiadające 100 punktów PK dla "Monografia – wydawnictwo poziom I" (#770)
- klikalny tytuł pracy w raporcie slotów (#772)
- raport slotów z możliwością podania parametru poszukiwanej ilości slotów i opcjonalnym
  wyświetlaniem autorów poniżej zadanego slotu (#765)
- nie licz slotów dla prac wieloośrodkowych (typ MNiSW/MEiN=PW) (#761)
- zmiana nazwy kolumny "PKdAut" na "punkty dla autora" (#754)
- wyświetlaj punkty PK w raporcie autora (#769)
- nie kopiuj linku do płatnego dostępu w opcji "tamże" (#722)
- konfigurowalne "Rozbij punktację na jednostki" dla rankingu autorów (#750)

### v201910.6

- możliwość niezależnego ustalenia opcji widoku raportów "raport slotów - uczelnia" i "raport slotów - autor"
- poprawne kasowanie wcześniej zapisanej informacji o slotach i punktach
- poprawki pobierania arkuszy XLS dla raportu slotow - poprawnie eksportowane liczby, szerokośc kolumn

### v201910.5a0

- raport slotów - uczelnia: eksport do XLS bez tagów HTML, możliwość filtrowania
- usunięto zdublowaną tabelę dla raportu slotów autorów

### v201910.1a0

- tabelki z możliwością eksportu XLS - punkty i sloty dla autorów i uczelni

### v201909.0001-alpha

- przełączenie na system wersji numerowanych od kalendarza (calver, \#746)
- opcje wyświetlania raportu slotów i tabelki z punktacją slotów na podstronie pracy -- dla wszystkich,
  tylko dla zalogowanych lub dla nikogo.
- nie licz slotów dla punkty PK = 0 dla wydawnictw ciągłych
- możliwość umieszczenia dowolnego tekstu przed i po liście autorów w opisie bibliograficznym

### 1.0.31

- drobne poprawki zmiany nazwy raportu slotów

### 1.0.31-dev3

- w przypadku braku wpisanej wartości w pole "liczba znakow wydawniczych", do paczek dla PBN
  wrzucaj wartosc 0 (zero). Pole wg Bibliotekarzy nie jest już wymagane przez Ministerstwo,
  zas oprogramowanie PBN na ten moment jeszcze tego pola wymaga.
- kolumna z PK dla raportu slotów
- poprawiono matchowanie autorów dla importu dyscyplin w sytuacji szukania autora po tytule
  naukowym (#742)

### 1.0.31-dev2

- polecenie do automatycznego przypisywania dyscyplin - dla autorów, którzy mają przypisaną tylko
  jedną dyscyplinę dla danego roku, można za pomocą polecenia command-line przypisać z automatu
  tą dyscyplinę do wszystkich ich prac, które nie mają przypisanej dyscypliny
- raport slotów

### 1.0.31-dev1

- nie wymagaj ilości znaków wydawniczych od rozdziałów i monografii przy eksporcie dla PBN
- połącz 3 pola obiektu Charakter Formalny: "Artykuł w PBN", "Rozdział w PBN", "Ksiażka w PBN" w jedno
  pole "Rodzaj dla PBN", które to może przyjąć jedną z 3 powyższych wartości; wcześniejszy model umożliwiał
  eksportowanie jednego charkateru formalnego jako rozdział bądź książka, jednakże po usunięciu
  warunku dotyczącego liczby znaków wydawniczych, niektóre rekordy mogłyby w takiej sytuacji być
  eksportowane więcej, niż jeden raz.
- konfigurowalne podpowiadanie dyscypliny autora (w sytuacji gdy ma tylko jedną na dany rok) podczas
  przypisywania autora do rekordu publikacji; zmiana konfiguracji za pomoca obiektu 'Uczelnia' (#728),
- poprawka błędu gdzie dla autorow z dwoma dyscyplinami była podpowiedź dyscypliny a nie powinno jej byc
  (#729)
- rozbicie pliku test_admin.py na klika mniejszych celem usprawnienia efektywności testow uruchamianych
  za pomocą pytest-xdist (na wielu procesorach)

### 1.0.31-dev0

- liczenie punktów i slotów dla wydawnictw zwartych
- "charakter dla slotów" dla charakteru formalnego
- informacja o możliwości (lub niemożliwości) policzenia punktów dyscyplin dla rekordu w panelu administracyjnym

### 1.0.30-dev3

- "rozbieżności dyscyplin" - moduł umożliwiający podejrzenie różnic pomiędzy dyscyplinami
  przypisanymi na dany rok dla autora a dyscyplinami przypisanymi do rekordów
- lepsza obsługa kolejki cache

### 1.0.30-dev2

- poprawki drobnych błędów

### 1.0.30-dev1

- drobne poprawki

### 1.0.30-dev0

- poprawki

### 1.0.29-dev3

- wyświetlanie informacji o punktacji dla dyscyplin i slotach

### 1.0.29-dev2

- powiązanie rekordu publikacji z autorem pozwala również wprowadzić informację
  na temat dyscypliny

### 1.0.29-dev1

- umożliwiaj konfigurację opcji "pokazuj liczbę cytowań na stronie autora",
- poprawione kasowanie patentów
- poprawne wyszukiwanie po dyscyplinach
- procent odpowiedzialności za powstanie pracy wyświetla się na podstronie pracy

### 1.0.28

- poprawki importu dyscyplin: lepsze dopasowywanie autora z jednostką z pliku wejściowego
  do danych w systemie
- poprawiony błąd importu dyscyplin utrudniający poprawne wprowadzenie pliku do bazy
- możliwość wyszukiwania przez ORCID w multiwyszukiwarce oraz w globalnym wyszukiwaniu
- numer ORCID staje się unikalny dla autora

### 1.0.27

- dyscyplina główna i subdyscyplina wraz z procentowym udziałem
- możliwość identyfikowania autorów po ORCID przy imporcie dyscyplin
- nowy plik z przykładowymi informacjami dla importu dyscyplin,
- możliwość przypisywania rodzaju kolumny przy imporcie dyscyplin,
- możliwosć wprowadzania procentowego udziału odpowiedzialności autora w powstaniu
  publikacji
- Django 2.1

### 1.0.26

- wyszukiwanie zaawansowane: gdy podane jest imię i nazwisko ORAZ np jednostka lub
  typ autora, wyniki będą poprawne tzn związane ze sobą (autor + afiliacja), a nie
  tak jak do tej pory pochodzące z dowolnych powiązań autora do rekordu,
- nowy operator dla pól autor, jednostka, wydział, typ odpowiedzialności "równy+wspólny",
  który zachowuje się tak, jak do tej pory zachowywał się operator "równy". Gdy chcemy
  znaleźć rekordy wspólne opublikowane przez dwóch lub więcej autorów/jednostki/wydziały,
  gdy chcemy znaleźć rekordy, które np. mają typ autora "redaktor" i "tłumacz" - korzystamy
  z tego operatora; gdy chcemy znaleźć prace autora afiliowane na konkretną jednostkę,
  korzystamy z operatora "równy"
- kosmetyka wyświetlania szczegółów rekordu: pole "Zewnętrzna baza danych", justowanie
  nagłówków do prawej strony.
- wyszukiwanie: prawidłowo obsługuj zapytania o rekordy zarejestrowane
  w kilku zewnętrznych bazach danych

### 1.0.27-alpha

- obsługa punktacji SNIP

### 1.0.25

- mniejsza wielkość tytułu na wydruku z opcji "Wyszukiwanie" (#632)
- tytuł naukowy autora nie wchodzi do elementu opisu bibliograficznego rekordu
  (#633)
- możliwość określania drzewiastej struktury dla charakterów formalnych - określanie
  charakterów nadrzędnych, wraz z możliwością wyszukiwania z uwwzględnieniem
  tej struktury (#630)
- możliwość określenia dla rankingu autorów, aby wybierane były jedynie prace
  afiliowane na jednostkę uczelni (= czyli taką, która ma zaznaczone "skupia
  pracowników" w module Redagowanie - Struktura) (#584)

### 1.0.23

- możliwość skonfigurowania, czy na wydrukach z "Wyszukiwania" ma pojawiać się logo
  i nazwa uczelni oraz parametry zapytania (#603)
- poprawki wydruków - mniejsza czcionka i marginesy (#619)
- ukryj liczbę cytowań dla użytkowników niezalogowanych w wyszukiwaniu; dodaj raporty
  z opcjonalnie widoczną liczbą cytowań (#626)
- pozwalaj na określanie szerokości logo na wydrukach przez edycję obiektu "Uczelnia"
- automatycznie dodawaj ciąg znaków "W: " dla opisu bibliograficznego wydawnictwa
  zwartego (#618)
- wyszukiwanie po liczbie autorów, możliwość wyszukiwania rekordów bez uzupełnionych
  autorów (#598)
- możliwość sortowania przy użyciu pól liczba autorów, liczba cytowań, data ostatniej
  zmiany, data utworzenia rekordu i innych (#589)
- kropka na końcu opisu bibliograficznego, prócz rekordów z DOI (#604)
- definiowana ilość rekordów przy której pojawia się opcja "drukuj" i "pokaż wszystkie"
  dla użytkowników zalogowanych i anonimowych, poprzez edycję obiektu Uczelnia (#610)
- możliwość podglądania do 100 rekordów wydawnictw zwartych i ciągłych powiązanych
  do konferencji
- możliwość jednoczasowej edycji do 100 rekordów powiązań autora i jednostki w module
  redagowanie, przy edycji obiektu Jednostka

### 1.0.21

- możliwość ustalenia domyślnej wartości pola "Afiliuje" dla rekordów wiążących
  rekord pracy z rekordem autora
- możliwość wyszukiwania po liczbie cytowań; wyświetlanie liczby cytowań w tabelkach
  wyszukiwania
- możliwość pokazywania liczby cytowań w rankingu autorów z opcjonalnym ukrywaniem
  tego parametru za pomocą modułu redagowania (opcje obiektu Uczelnia)
- możliwość pokazywania liczby cytowań na podstronie autora z opcjonalnym ukrywaniem
  tego parametru za pomocą modułu redagowania (opcje obiektu Uczelnia)
- poprawiono błąd powodujący niewłaściwe generowanie eksportów PBN dla rekordów książek
  w których skład wchodziło powyżej 1 rozdziału (#623)
- poprawne wyświetlanie raportów jednostek i wydziałów, zgodne z ustawieniami
  obiektu "Uczelnia"
- poprawne eksportowanie do PBN konferencji indeksowanych w WOS/Scopus (#621)
- poprawione generowanie plików XLS w niektórych środowiskach (#601)
- możliwość określania rodzaju konferencji w module redagowanie: lokalna, krajowa,
  międzynarodowa oraz wyszukiwania po typach konferencji (#620)

### 1.0.20

- możliwość wyszukiwania nazwiska autora dla pozycji 1-3, 1-5 oraz dla ostatniej
  pozycji - dla użytkowników zalogowanych

### 1.0.19

- możliwość globalnej konfiguracji sposobu wprowadzania powiązań autorów z rekordami

### 1.0.18

- obsługa API WOS-AMR od Clarivate Analytics
- lepsze wyświetlanie rekordu patentu w widoku rekordu
- poprawka formularza edycji autorów powiązanych z rekordem w module redagowania -
  obecnie edycja odbywa się za pomocą formularzy poziomych, co zwiększyło czytelnosć
- możliwość oznaczania i wyszukiwania rekordów indeksowanych w zewnętrznych bazach danych
  (np. WoS, Scopus) dla wydawnictw ciągłych
- nazwa konferencji zawiera etykietę "WoS" lub "Scopus" w przypadku, gdy konferencja
  jest indeksowana,
- eksport PBN działa poprawnie w przypadku podania tej samej daty w polu "od" i "do"
- ukrywanie pól w "wyszukiwaniu" oraz brak dostępu do raportów zgodnie z ustawieniami
  systemu dokonanymi w module "Redagowanie"

### 1.0.17

- import i wyszukiwanie dyscyplin naukowych

### 1.0.16 (2018-03-20)

- błąd wyświetlania strony w przeglądarce Edge został naprawiony,
- data ostatniej modyfikacji dla PBN wyświetla się dla zalogowanych użytkowników

### 1.0.15 (2018-03-07)

- dodatkowe pole dla typu odpowiedzialności, umożliwiające mapowanie charakterów
  formalnych autorów na charaktery formalne dla PBN
- nowe pola dla patentów: wydział, rodzaj prawa patentowego, data zgłoszenia,
  numer zgłoszenia, data decyzji, numer prawa wyłącznego, wdrożenie.
- impact factor dla Komisji Centralnej ma 3 pola po przecinku (poprzednio 2)
- zmiana sposobu nawigacji na menu na górze ekranu,
- wyszukiwanie zyskuje nową szatę graficzną i animacje.

### 1.0.4 (2018-02-13)

- poprawienie błędu wyszukiwania autorów w przypadku, gdy w wyszukiwanym
  ciągu znajdzie się spacja,
- zezwalaj na dowolną wartość zapisanego imienia i nazwiska w module
  redagowania,
- umożliwiaj wyszukiwanie po pierwszym nazwisku i imieniu (pierwszy autor,
  redaktor, etc)

### 1.0.1 (2018-01-01)

- wyświetlanie danych OpenAccess na widoku pracy,
- wyświetlanie DOI w opisach bibliograficznych, raportach oraz widoku pracy,
- poprawiony błąd budowania zapytania SQL na potrzeby wyszukiwania pełnotekstowego

### 0.11.112 (2017-12-09)

- wyszukiwanie konferencji w globalnej nawigacji modułu redagowania

### 0.11.111 (2017-11-16)

- poprawiony błąd związany z wyborem pola "tylko prace z afiliowanych jednostek"
  występujący w formularzu raportu autorów
- optymalizacja wyświetlania podstrony jednostki w przypadku, gdy zawiera
  ona więcej, niż 100 autorów.

### 0.11.109 (2017-11-14)

- możliwość przejścia do panelu redagowania z każdej strony serwisu, gdzie
  tylko ma to sens (jednostki, autorzy, artykuły, wydziały),
- kosmetyczne poprawki wyświetla raportów,
- poprawiony błędny warunek dla funkcji raportu autorów "uwzględniaj tylko
  prace afiliowanych jednostek uczelni",

### 0.11.107 (2017-11-12)

- opcja "Stwórz autora" tworzy domyślnie autora niewidocznego na stronach
  jednostek, kapitalizując nazwiska,
- poprawiono błąd powodujący niepoprawne działanie funkcji usuwania
  pojedynczych rekordów z wyników wyszukiwania.

### 0.11.106 (2017-11-10)

- możliwość łatwego przechodzenia z formularza edycji w module redagowania do
  stron WWW dostepnych dla użytkownika końcowego
- \[kod\] generowanie opisu bibliograficznego autorów za pomocą systemu
  templatek Django; usunięcie kodu generowania opisu bibliograficznego
  autorów za pomocą własnych tagów,
- pole "Pokazuj na stronach jednostek" dla Autorów staje się polem "Pokazuj"
  i określa widoczność autora na stronie jednostki oraz w "Rankingu autorów"

### 0.11.104 (2017-11-08)

- usunięto błąd uniemożliwiający edycję już zapisanego autora w rekordach
  wydawnictwa ciągłego i zwartego

### 0.11.103 (2017-11-06)

- od tej wersji, dla wydawnictw zwartych, gdzie określone jest wydawnictwo nadrzędne,
  nie ma już potrzeby uzupełniania pola "Informacje", gdyż system w opisie
  bibliograficznym użyje tytułu wydawnictwa nadrzędnego,
- miniblog - możliwość umieszczenia aktualności na pierwszej stronie serwisu.
- obsługa przycisku "Uzupełnij rok" dla wydawnictwa zwartego (uzupełnia dane
  na podstawie pola "Szczegóły" bądź z "Wydawnictwo nadrzędne") oraz dla
  wydawnictwa ciągłego (uzupełnia dane na podstawie pola "Informacje").

### 0.11.101 (2017-11-03)

- opcjonalne uwzględnianie prac spoza jednostek uczelni w raportach autorów,
- naprawiono działanie konektora OAI-PMH,
- "prawdziwa" funkcja "pozostałe prace" dla raportów,
- poprawione wyświetlanie rekordów (poprawna obsługa tagów "sup" i "sub"
  w opisach bibliograficznych).

### 0.11.90 (2017-09-23)

- opcjonalne rozbicie na jednostki i wydziały w rankingu autorów
- możliwość ukrycia pola "Praca recenzowana"
- poprawki wyświetlania podstron autora i jednostki

### 0.11.77 (2017-09-19)

- poprawiono liczenie punktacji sumarycznej w rankingu autorów
- poprawiono wyszukiwanie dla podanych jednocześnie par autor + jednostka
- poprawki wydajności wyszukiwania

### 0.11.55 (2017-08-30)

- domyślne sortowanie rankingu autorów
- obsługa PostgreSQL 9.6

### 0.11.53 (2017-08-29)

- poprawiony błąd eksportowania plików XLS i DOCX utrudniający ich otwieranie
- poprawiony błąd wyszukiwania dla pola "Źródło"
- opcjonalne ukrywanie elementów menu serwisu dla użytkowników zalogowanych
  i niezalogowanych

### 0.11.50 (2017-08-23)

- poprawiony błąd uniemożliwiający sortowanie w rankingu autorów
- tabela rankingu autorów stylizowana podobnie jak inne tabele w systemie
- możliwość eksportowania rankingu autorów oraz raportów autorów, jednostek i
  wydziałów w różnych formatach wyjściowych (m.in. MS Excel, MS Word, CSV)

### 0.11.43 (2017-08-15)

- możliwość zmiany wyglądu kolorystycznego systemu
- nowy framework raportów oparty o zapytania w języku DSL, obsługiwany
  w pełni przez użytkownika końcowego
- konfigurowalny czas długości trwania sesji - możliwość wybrania, jak długo
  system czeka na reakcję użytkownika przed automatycznym jego wylogowaniem
- autorzy przy wyszukiwaniu przez globalną nawigację oraz w module "Redagowanie"
  wyświetlani są zgodnie z ilością publikacji w bazie
- możliwość automatycznego utworzenia autora i serii wydawniczej
  podczas wpisywania rekordu - bez konieczności przechodzenia do innej częsci
  modułu redagowania
- opcja resetu hasła w przypadku jego zapomnienia
- konfigurowalny czas do przymusowej zmiany hasła, konfigurowalny moduł
  zapamiętujący ostatnio wpisane hasła oraz konfigurowalna ilość
  ostatnio zapamiętanych haseł

### 0.11.19 (2017-07-15)

- do rekordu powiązania autora z wydawnictwem (zwartym, ciągłym lub patentem)
  dochodzi pole "afiliowany", domyślnie mające wartość 'PRAWDA'. Należy je
  odznaczyć w sytuacji, gdyby autor danej publikacji zgłosił powiązanie
  do jednostki będącej w strukturach uczelni w której jest zatrudniony jednakże
  jednoczasowo do tej publikacji zgłosił inną jednost
- do rekordu wydawnictwa zwartego, ciągłego, patentu, pracy doktorskiej i
  pracy habilitacyjnej dochodzą pola "strony", "tom" i "numer zeszytu":
  - w sytuacji, gdy są wypełnione, to ich wartości są używane do eksportu PBN,
  - w sytuacji, gdy są niewypełnione, system spróbuje wyekstrahować te dane z
    pól "szczegóły" i "informacje" analizując ciągi znaków, poszukując ciągów
    takich jak "vol.", "t.", "r.", "bd." dla tomu, "nr", "z.", "h." dla numeru
    zeszytu, "ss." lub "s." dla stron, "b. pag." dla braku paginacji,
  - podczas edycji rekordu w module "redagowanie" pola te zostaną uzupełnione
    przez system na podstawie pól "szczegóły" i "informacje" gdy użytkownik
    kliknie odpowiedni przycisk; w takiej sytuacji pola te, jeżeli zawierają
    jakieś informacje, zostaną nadpisane.
- konferencje - w module redagowania można dopisywać dane o konferencjach, które
  następnie mogą być przypisane do wydawnictwa ciągłego lub wydawnictwa
  zwartego
- struktura - w module redagowania za pomocą rekordu uczelni można ukryć
  wyświetlanie punktacji wewnętrznej oraz Index Copernicus
- autor - nowe pole "Open Researcher and Contributor ID"
- wygodna edycja kolejności wydziałów w module Redagowanie➡Struktura➡Uczelnia
- poprawiono błąd związany z obsługą pola dla rekordu Autor "Pokazuj na stronie
  jednostki". Autorzy którzy mają to pole odznaczone, nie będą prezentowani
  na stronach jednostek.
- dla typów KBN można określać odpowiadający im charakter PBN. Pole to zostanie
  użyte jako fallback w sytuacji, gdy rekord charakteru formalnego do którego
  przypisana jest dana praca nie ma określonego odpowiadającego mu charakteru
  PBN
- podgląd na znajdujące się w bazie charaktery PBN i przypisane im charaktery
  formalne i typy KBN w module "Redagowanie"
- w bloku "Adnotacje" w module "Redagowanie" wyświetla się ID oraz PBN ID
- pola "Seria wydawnicza" oraz "ISSN" dla wydawnictwa zwartego
- możliwość określania nagród oraz statusu wybitności pracy dla rekordów
  wydawnictw zwartych i wydawnictw ciągłych
- możliwość filtrowania po statusach openaccess w module "Wyszukiwanie" dla
  użytkowników niezalogowanych

### 0.11.0 (2017-07-05)

- obsługa Python 3 + Django 1.10

### 0.10.96 (2017-04-02)

- pierwsza publicznie dostępna wersja
