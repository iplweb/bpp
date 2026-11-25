# Wzbogacanie rekordu danymi z CrossRef i PBN

Rekord jest już w BPP, a chcesz sprawdzić, czy w CrossRef albo w PBN są
dane, których w nim brakuje albo które się różnią — bez importowania pracy
od nowa. Do tego służą przyciski **„🧩 Wzbogać z CrossRef”** i **„🧩 Wzbogać
z PBN”** w formularzu wydawnictwa ciągłego i zwartego (moduł redagowania,
prawy górny róg, obok „Historia”).

- „Wzbogać z CrossRef” jest widoczny, gdy rekord ma wypełnione pole
  **„DOI”** — CrossRef wyszukuje publikacje po numerze DOI.
- „Wzbogać z PBN” jest widoczny, gdy rekord ma wskazany **„Odpowiednik
  w PBN”**.

Przyciski wymagają uprawnienia do zmiany rekordu. Są osobną funkcją —
przyciski „Pobierz po DOI” / „Pobierz po ISBN” przy polu „Odpowiednik
w PBN” działają jak dotąd.

## Porównanie: źródło ↔ BPP {#porownanie}

Po kliknięciu otwiera się lista różnic dla tego jednego rekordu. Na górze
jest podsumowanie:

- **„✅ Wszystko się zgadza”** — źródło nie ma nic, czego brakuje
  w rekordzie albo co się od niego różni, albo
- **„Różni się N pól: …”** z nazwami pól.

Niżej tabela, pole po polu: po lewej wartość **w źródle**, po prawej
**w rekordzie BPP**, w środku **„Zmiana po przeniesieniu”** — w tekstach
(tytuł, streszczenie) różnice są zaznaczone na poziomie słów (usuwane
przekreślone na czerwono, dodawane na zielono). Przy każdym polu jest
status:

| Status | Znaczenie |
|---|---|
| zgodne | wartość w źródle i w BPP jest ta sama |
| różne | obie strony mają wartość, ale inną |
| brak w BPP | źródło ma wartość, pole w BPP jest puste |
| brak w źródle | pole jest wypełnione tylko w BPP — nie ma czego przenosić |
| nie rozpoznano | źródło podaje język albo licencję, której nie ma w słowniku BPP |

Różnice w samym zapisie nie są pokazywane jako różnice: kreski w ISSN
i ISBN, wielkość liter w DOI, półpauza zamiast łącznika w zakresie stron,
znaczniki HTML i podwójne odstępy w tytule. ISSN zapisany w BPP w polu
„e-ISSN” (i odwrotnie) oraz adres WWW wpisany w polu wolnego dostępu są
uznawane za zgodne, z dopiskiem, w którym polu jest wartość.

Porównywane pola: tytuł oryginalny, tytuł (z CrossRef — tytuł w języku
oryginału), rok, DOI, tom, nr zeszytu, strony, ISSN, e-ISSN, ISBN, e-ISBN,
adres WWW, język, licencja otwartego dostępu, słowa kluczowe
i streszczenie. Dane ze źródeł są odczytywane tak samo jak w
[importerze publikacji](importer-publikacji.md).

## Przenoszenie wybranych pól {#przenoszenie}

1. Zaznacz pola, które chcesz przenieść (pole wyboru przy nazwie pola;
   przycisk **„☑️ Zaznacz wszystkie różnice”** zaznacza wszystkie naraz).
2. Kliknij **„⬇️ Przenieś zaznaczone pola do BPP”** na dolnej belce.

Zmieniają się **tylko zaznaczone pola** — reszta rekordu zostaje bez zmian.
Samo otwarcie porównania niczego w rekordzie nie zmienia. Po zatwierdzeniu
wracasz do porównania i widzisz stan po zmianie.

- **Słowa kluczowe**: przeniesienie **dopisuje brakujące** słowa; słowa
  wpisane w rekordzie ręcznie zostają. Dane z PBN są porównywane osobno dla
  pola „Słowa kluczowe” i „Słowa kluczowe -- język angielski” — angielskie
  słowa z PBN trafiają do pola angielskiego. CrossRef nie dzieli słów na
  języki, więc są porównywane ze wszystkimi słowami rekordu, a brakujące
  trafiają do pola „Słowa kluczowe”. Słowa dłuższego niż 100 znaków (w polu
  angielskim: 255) nie da się przenieść — zwykle to kilka słów sklejonych
  w źródle w jedno; wpisz je ręcznie.
- **Streszczenie**: przeniesienie **dodaje** streszczenie ze źródła jako
  kolejne; streszczenia już wpisane w rekordzie zostają.
- **Adres WWW** trafia do pola „Adres WWW (płatny dostęp)”. Adresu
  w serwisie doi.org nie da się przenieść — numer DOI ma swoje pole.
- Wartości, której BPP nie przyjmie (np. za długiej), nie da się zaznaczyć;
  przy polu jest wyjaśnienie.
- Jeżeli między otwarciem porównania a zatwierdzeniem zmieniły się dane
  w źródle **albo sam rekord** (np. pole poprawił w tym czasie inny
  redaktor), takie pole nie jest przenoszone — pojawia się komunikat
  i trzeba sprawdzić porównanie jeszcze raz. Cudza poprawka nie zostanie
  po cichu nadpisana.

## Z kiedy są dane i jak je odświeżyć {#odswiezanie}

Otwarcie porównania **nie łączy się** za każdym razem ze źródłem — nad
tabelą widać, z kiedy są pokazywane dane, i przycisk odświeżenia:

- **CrossRef**: „Dane pobrane z CrossRef (data)”. BPP pamięta odpowiedź
  CrossRef do 14 dni; pierwsze otwarcie dla danego DOI pobiera dane od
  razu. **„🔄 Odśwież z CrossRef”** pobiera je ponownie.
- **PBN**: „Dane z lokalnej kopii PBN z (data)” — kopii pobieranej przy
  synchronizacji z PBN. **„🔄 Odśwież z PBN”** pobiera aktualny stan tej
  jednej publikacji (wszystkie wersje) i zapisuje go w lokalnej kopii.

Odświeżenie to jedno krótkie zapytanie. Gdy źródło nie odpowiada, zostają
dane pobrane wcześniej, a na górze strony jest o tym komunikat.

Każde przeniesienie zostawia wpis w [historii rekordu](wydawnictwa.md#historia-zmian)
(przycisk „Historia”): kto, kiedy i które pola, np. „Wzbogacono z CrossRef:
pola Strony, Nr zeszytu”. Zmianę można tam porównać z poprzednią wersją
i cofnąć.

## Autorzy {#autorzy}

Pod tabelą pól jest porównanie list autorów: kogo **brakuje w BPP**, kto
jest **tylko w BPP** i kto jest **w innej kolejności**. Osoby są
dopasowywane kolejno po identyfikatorze w PBN, po ORCID, a na końcu po
nazwisku i pierwszej literze imienia; przy każdej osobie widać, jak ją
dopasowano. Przy pracach z bardzo długą listą autorów pokazywane są same
różnice.

### Dodawanie brakujących autorów {#brakujacy-autorzy}

Dodanie autora wymaga wskazania jednostki i dyscypliny, dlatego brakujące
osoby dodaje się w kroku „Autorzy” [importera publikacji](importer-publikacji.md)
— tym samym, co przy imporcie nowej pracy:

1. Kliknij **„👥 Dodaj brakujących autorów (N) w importerze”** pod
   podsumowaniem autorów.
2. Otwiera się krok „Autorzy” z samymi brakującymi osobami i informacją,
   że trafią do **istniejącego rekordu** — nowy rekord nie powstanie. Dla
   każdej osoby dopasuj autora, jednostkę i dyscyplinę (albo utwórz nowego
   autora), tak jak przy imporcie. Osobę, której nie chcesz dodawać, usuń
   z listy przyciskiem „Usuń”.
3. Kliknij **„Dodaj autorów do rekordu”**. Wracasz do porównania.

„Wróć do porównania bez dodawania” na górze kroku „Autorzy” porzuca
dodawanie (niczego nie zapisuje). Dodani autorzy trafiają **na koniec listy autorów** rekordu — kolejność
popraw w formularzu rekordu. W historii rekordu zostaje wpis „Dodano
autorów z CrossRef (kreator importera publikacji): …”. Osoby, która już
jest na liście autorów rekordu, nie da się dodać drugi raz.

Przycisk widzą osoby z dostępem do importera publikacji (grupa
„wprowadzanie danych”). Gdy brakuje więcej niż 100 osób, dodaj autorów
w formularzu rekordu albo zaimportuj pracę importerem. Autorów nadmiarowych
i kolejność poprawia się w formularzu rekordu (przycisk „✏️ Wróć do
rekordu”).

## PBN: wersje publikacji i odtwarzanie ze starszej wersji {#wersje-pbn}

PBN przechowuje historię wersji każdej publikacji. W porównaniu z PBN nad
tabelą jest lista **„Wersje tej publikacji w PBN”**: data każdej wersji
i oznaczenia **„najnowsza w PBN”** oraz **„przypięta na profilu
instytucji”**.

- Domyślnie porównanie pokazuje wersję **przypiętą na profilu instytucji**,
  a gdy profil żadnej nie wskazuje — **najnowszą**.
- Gdy wersja przypięta i najnowsza to dwie różne wersje, na górze strony
  jest ostrzeżenie z datami obu.
- **„Porównaj z tą wersją”** przy dowolnej wcześniejszej wersji pokazuje
  różnice między nią a obecnym rekordem BPP.

Tak odtwarza się dane rekordu, który został zepsuty (nadpisany ręcznie,
złym importem albo scaleniem), a w PBN jest jego wcześniejsza, poprawna
wersja: wybierz tę wersję, zaznacz pola i zatwierdź. Wpis w historii
rekordu ma wtedy postać „Odtworzono z PBN, wersja z dnia 10.01.2023, 11:00:
pola Tytuł oryginalny”.

Porównanie korzysta z lokalnej kopii danych PBN; przycisk „🔄 Odśwież
z PBN” pobiera aktualne dane tej publikacji (sam odczyt — zob.
[wyżej](#odswiezanie)). Jeśli spodziewasz się nowej wersji w PBN, a nie ma
jej na liście — odśwież. **Do PBN nic nie jest wysyłane** — ani przy
porównaniu, ani przy odświeżaniu, ani przy przenoszeniu pól. Zmieniony
rekord wysyłasz do PBN tak jak zwykle (zob.
[PBN: wysyłanie prac](pbn-wysylka-i-synchronizacja.md)).

PBN nie podaje, kto utworzył daną wersję — na liście jest tylko data.

## Co może pójść nie tak {#co-moze-pojsc-nie-tak}

| Komunikat | Co zrobić |
|---|---|
| „Rekord nie ma numeru DOI…” | Uzupełnij pole „DOI” w rekordzie i zapisz go. |
| „CrossRef nie ma danych dla DOI …” | Sprawdź numer DOI; nie każdy DOI jest zarejestrowany w CrossRef (np. DataCite). |
| „Rekord nie ma odpowiednika w PBN…” | Wskaż „Odpowiednik w PBN” w rekordzie i zapisz go. |
| „Nie udało się pobrać aktualnych danych z PBN…” / „…z CrossRef…” | Porównanie pokazuje dane pobrane wcześniej; spróbuj odświeżyć później. |
| „Uczelnia nie ma skonfigurowanego dostępu do PBN.” | Odświeżanie z PBN wymaga danych dostępowych PBN w ustawieniach uczelni; porównanie z lokalną kopią działa bez nich. |
| „Nie przeniesiono, bo rekord albo dane w źródle zmieniły się od podglądu…” | Otwórz porównanie jeszcze raz i zaznacz pola ponownie. |
| „Nie ma już takiej wersji tej publikacji w PBN…” | Wybierz inną wersję z listy. |
| „Tego języka / tej licencji nie ma w słowniku…” | Dopisz pozycję w słowniku BPP albo ustaw pole ręcznie w rekordzie. |
