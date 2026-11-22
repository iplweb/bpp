# Edycja danych rekordów - wydawnictwa zwarte, ciągłe, patenty, itp

## Dodawanie autorów do rekordów

Aby dodać autora do rekordu, podczas dodawania lub edycji rekordu kliknij
„Dodaj kolejne(go)(-ną)(-ny) powiązanie autora z wyd. ciągłym” (w wydawnictwie
zwartym — „…z wyd. zwartym”, w patencie — „…z patentem”) pod listą autorów.

W formularzu rekordu można w ten sposób wpisać do 25 autorów. Przy dłuższej
liście autorów skorzystaj z przycisku **Autorzy** u góry formularza rekordu.

## Zmiana kolejności autorów

Kolejność autorów zmienia się techniką „przeciągnij i upuść”:

1. Zwiń powiązania autorów — ikoną ⇑ („zwiń wszystkie”) na pasku
   „Powiązania autorów z rekordem” albo klikając nagłówek pojedynczego
   powiązania. Zwinięta lista mieści się na ekranie, co ma znaczenie
   zwłaszcza na mniejszych monitorach.
2. Chwyć lewym przyciskiem myszy przycisk przeciągania (ikona ⇕ po prawej
   stronie nagłówka powiązania) i przeciągnij powiązanie w górę lub w dół.
3. Zapisz rekord.

![Zwinięta lista autorów rekordu z zaznaczonym przyciskiem przeciągania i odnośnikiem dodawania autora](../images/redaktor/wydawnictwa/01-kolejnosc-autorow.png)

Działania te również prezentuje film [Zmiana kolejności autorów](https://www.youtube.com/embed/oruEX3CykH8) .

<iframe width="560" height="315" src="https://www.youtube.com/embed/oruEX3CykH8" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>

## Data udostępnienia w otwartym dostępie {#data-udostepnienia-oa}

W formularzu artykułu (wydawnictwa ciągłego) oraz książki i rozdziału
(wydawnictwa zwartego), w zwijanej sekcji **OpenAccess**, jest pole
**OpenAccess: data udostępnienia (dzień lub miesiąc i rok)**. Wpisz w nim:

- **pełną datę**, gdy znasz dzień udostępnienia — np. `30.12.2025`,
  `2025-12-30` albo `2025.12.30`,
- **sam miesiąc i rok**, gdy dnia nie znasz — np. `12.2025`, `2025-12`
  albo `2025.12`.

**Sam rok (np. `2025`) nie wystarczy** — formularz go nie przyjmie, bo PBN
wymaga co najmniej miesiąca i roku udostępnienia. Po zapisie pole pokazuje
wartość w jednym formacie: `30.12.2025` albo `12.2025`. Rok musi mieścić się
w zakresie od 1900 do bieżącego roku powiększonego o 10 lat.

Przy wysyłce do PBN:

- pełna data trafia do PBN jako data udostępnienia,
- miesiąc i rok trafiają do PBN jako miesiąc i rok udostępnienia — BPP
  **nie dopisuje** żadnego dnia,
- gdy pole jest puste, BPP użyje daty dostępu do strony WWW
  („Dostęp dnia (wolny dostęp)”, a potem „Dostęp dnia (płatny dostęp)”),
  o ile ją podano; inaczej data udostępnienia nie jest wysyłana.
  Data wpisana w sekcji OpenAccess ma zawsze pierwszeństwo przed tymi
  datami.

Prace pobierane z PBN, dla których PBN podaje miesiąc i rok udostępnienia,
mają w tym polu wpisany miesiąc i rok (bez zmyślonego dnia). Jeśli PBN
podaje sam rok, BPP nie wpisuje daty — uzupełnij ją ręcznie przed wysyłką
do PBN (raport kompletności danych POL-on pokaże taki brak).

## Historia zmian i przywracanie poprzedniej wersji {#historia-zmian}

Każda zmiana rekordu publikacji (wydawnictwa ciągłego, zwartego, patentu,
pracy doktorskiej i habilitacyjnej) jest zapisywana jako **wersja**. Tak
samo każdy inny rekord edytowany w module redagowania: zgłoszenia
publikacji, źródła, wydawcy, konferencje, serie wydawnicze, jednostki,
wszystkie słowniki (charaktery formalne, języki, typy, dyscypliny…),
użytkownicy, grupy i ustawienia. Wersja publikacji obejmuje także **listę
autorów** (z jednostką, dyscypliną, afiliacją i kolejnością), streszczenia,
dodatkowe tytuły, zewnętrzne bazy danych, granty, nagrody, pliki
w repozytorium i słowa kluczowe.

Historię otwiera przycisk **„Historia”** w prawym górnym rogu formularza.
Przy każdej wersji widać **kto i kiedy** wprowadził zmianę, **skąd**
przyszła (moduł redagowania, strona — np. edycja profilu, import lub
narzędzie, API / MCP z nazwą aplikacji, system) i co zmieniono (np.
„Zmodyfikowano Tytuł oryginalny”, „Przeniesiono do kosza (powód: …)”,
„Ustawiono status korekty: po korekcie (akcja masowa)”).

- **Porównanie wersji** — zaznacz wersję starszą w kolumnie **A** i nowszą
  w kolumnie **B**, a potem kliknij **„Porównaj zaznaczone wersje”**.
  Tabela pokazuje tylko pola, które się zmieniły: usunięte słowa są
  przekreślone na czerwono, dodane — podświetlone na zielono. Dla list
  (autorzy, granty, pliki…) widać pozycje dodane, usunięte i zmienione,
  np. „Afiliuje: tak → nie”. Przyciski „Wcześniejsza zmiana” / „Następna
  zmiana” przechodzą po kolejnych parach wersji.
- **Przywrócenie wersji** — kliknięcie daty otwiera formularz w stanie
  z tej wersji; **zapisanie go przywraca tę wersję** (samo przywrócenie też
  trafia do historii, więc da się je cofnąć). Przywrócenie wersji
  publikacji przywraca też listy powiązane — nad formularzem wypisane są
  pozycje, które **zostaną usunięte** (np. autorzy dopisani po tej wersji)
  i które **zostaną przywrócone**.

Uwagi:

- Wersje są zapisywane od chwili aktualizacji systemu. Rekord, który nie
  był od tego czasu edytowany, dostaje pierwszą wersję automatycznie tuż
  przed pierwszą zmianą (komentarz „Stan sprzed pierwszej zarejestrowanej
  zmiany”) — dzięki temu i tę zmianę można cofnąć. Starsze zmiany widać
  w tabeli **„Wcześniejsza historia”** (kto i kiedy, bez przywracania).
- Przywrócenie wersji z plikiem w repozytorium przywraca wpis o pliku,
  ale nie treść pliku usuniętego z serwera.
- Historia jest przechowywana bez limitu czasu.
- Historię i porównanie wersji rekordu z kosza można oglądać, ale
  przywrócić wersję da się dopiero po wyjęciu rekordu z kosza — strona
  „Historia” pokazuje wtedy ramkę z przyciskiem **„♻️ Przywróć z kosza”**.
- Najnowsza wersja (obecny stan rekordu) ma w historii zieloną plakietkę
  **„wersja aktualna”**. Podgląd wersji o tej samej treści co aktualna
  (np. tej, do której rekord właśnie przywrócono) mówi wprost, że zapis
  niczego nie zmieni.
- Po przywróceniu wersji opis bibliograficzny i punktacja są przeliczane
  tak jak po zwykłym zapisie formularza.
- Przywrócenie wersji jednego rekordu nigdy nie zmienia innych rekordów —
  także po akcji masowej (np. zmianie statusu korekty wielu prac) każdy
  rekord ma własną wersję.

## Dlaczego nie można usunąć pracy z wpisanym „Odpowiednikiem w PBN"

Przy próbie skasowania wydawnictwa ciągłego lub zwartego może się okazać, że
system nie udostępnia przycisku **Usuń**, a przy próbie usunięcia pojawia się
komunikat **„Brak uprawnień do usuwania"** — nawet jeśli masz uprawnienia
redaktora.

Jest to **działanie celowe, a nie błąd**. Rekordu **nie da się usunąć tak długo,
jak długo ma wypełnione pole „Odpowiednik w PBN"** — czyli dopóki jest powiązany
z konkretną publikacją po stronie PBN. Dotyczy to zarówno wydawnictw ciągłych,
jak i zwartych.

### Dlaczego tak jest

Jeżeli praca została wysłana do PBN, BPP zapamiętuje powiązanie z nią w polu
„Odpowiednik w PBN". Gdyby można było skasować taki rekord wyłącznie w BPP,
praca **nadal pozostałaby w PBN**, a BPP straciłoby jedyną informację o tym, gdzie
w PBN się ona znajduje. Powstałby „osierocony" wpis w PBN, którego z poziomu BPP
nie dałoby się już ani usunąć, ani poprawić. Blokada chroni więc przed
rozjechaniem się danych między BPP a PBN.

### Jak prawidłowo usunąć taką pracę

1. **Najpierw usuń pracę po stronie PBN** — z **profilu Twojej instytucji**
   w PBN (a nie z samego repozytorium). Otwórz ją w PBN korzystając z odnośnika
   przy polu „Odpowiednik w PBN", **zanim** je wyczyścisz. Ten krok wykonujesz
   bezpośrednio w PBN — leży on po stronie redaktora / instytucji.
2. **Wyczyść pole „Odpowiednik w PBN"** w rekordzie w BPP i zapisz rekord. W ten
   sposób zdejmujesz powiązanie z PBN.
3. Po zapisaniu przycisk **Usuń** stanie się ponownie dostępny i będziesz mógł
   skasować rekord w BPP.

!!! warning "Zachowaj kolejność kroków"
    Pole „Odpowiednik w PBN" to jedyny ślad łączący rekord BPP z konkretną
    publikacją w PBN. Jeśli wyczyścisz je, zanim usuniesz pracę z PBN, stracisz
    informację, którą publikację w PBN należy skasować. Dlatego najpierw zajmij
    się PBN, a dopiero potem czyść pole i kasuj rekord w BPP.
