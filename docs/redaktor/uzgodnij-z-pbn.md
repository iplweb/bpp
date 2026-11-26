# Uzgodnij z PBN — brakujące prace i raport różnic jednym działaniem

Przewodnik dla redaktorów, którzy chcą, żeby **stan prac w BPP za wybrany
rok zgadzał się z profilem instytucji w PBN**. Typowa sytuacja: w PBN
poprawiłaś lub dodałaś do profilu instytucji kilkanaście prac i chcesz mieć
je w BPP — bez przepisywania każdej osobno.

Dotąd BPP nie miał do tego narzędzia: „Import z PBN” jest dla
administratora i służy do pierwszego zasilenia pustej bazy, a „pobieranie
danych z PBN” przygotowuje dane dla deduplikatorów i komparatorów — żadne
z nich nie synchronizuje prac ([szczegóły niżej](#stare-funkcje)).
**„Uzgodnij z PBN” jest drogą dla redaktora**: pobierasz dane z PBN,
a system uzupełnia BPP i mówi wprost, co zmienił, a co zostawił do Twojej
decyzji.

Wysyłanie prac **z BPP do PBN** opisuje osobna strona:
[PBN: wysyłanie prac, kolejka i porównanie](pbn-wysylka-i-synchronizacja.md).

## Zanim zaczniesz {#zanim-zaczniesz}

- Potrzebujesz grupy **„wprowadzanie danych”** — wtedy w górnym menu jest
  pozycja **PBN**, a w niej **uzgodnij z PBN**.
- Musisz być **zalogowana/zalogowany do PBN** (menu **PBN** → **autoryzuj
  PBN API**). Bez ważnej autoryzacji strona pokaże czerwony komunikat
  i nie pozwoli uruchomić operacji.
- Operacja dotyczy **prac z profilu Twojej instytucji w PBN**. Jeśli pracy
  na profilu nie ma (np. istnieje tylko w repozytorium PBN), najpierw dodaj
  ją w PBN do instytucji.

## Jak uruchomić {#jak-uruchomic}

Praca ma dwa kroki: **pobranie danych z PBN** i **uzgodnienie** na tych
danych. Uzgadnianie samo niczego nie pobiera — dzięki temu zawsze widzisz,
z kiedy są dane, na których pracuje.

1. Menu **PBN** → **uzgodnij z PBN**.
2. Wpisz zakres lat: **Rok od** i **Rok do** (dla jednego roku wpisz ten
   sam rok w obu polach, np. `2026` i `2026`).
3. Kliknij **Pobierz dane z PBN**. System czyta z PBN profil instytucji,
   aktualne dane prac z wybranych lat i oświadczenia (dyscypliny), a dla
   rekordów BPP z tych lat, które nie są powiązane z PBN, pyta PBN, czy ma
   pracę o tym DOI (dla książek także o tym ISBN). Trwa to w tle, z licznikiem
   postępu; w rekordach BPP nic się nie zmienia.
4. Wróć na stronę **uzgodnij z PBN** i kliknij:
   - **Pokaż, co się zmieni** — podgląd: pełny raport, ale **żaden rekord
     w BPP się nie zmienia**;
   - **Uzgodnij teraz** — to samo, ale zmiany są od razu wykonywane.
5. Operacja działa w tle. Strona pokazuje pasek postępu i odświeża się
   sama; możesz ją zamknąć i wrócić później — przebieg jest na liście
   **Ostatnie przebiegi**.

Jeśli zaczęłaś od podglądu i wynik Ci odpowiada, kliknij **Wykonaj ten
podgląd**. System zrobi dokładnie to, co pokazał.

### Z kiedy są dane {#z-kiedy-dane}

Ramka **„Dane z PBN, na których pracuje uzgadnianie”** podaje datę pobrania
osobno dla każdego źródła — np. „profil instytucji — pobrane wczoraj,
22.11.2026 14:10”:

- **profil instytucji** — lista prac uczelni w PBN i wersje przypięte,
- **publikacje** — dane prac z wybranych lat,
- **oświadczenia** — dyscypliny autorów,
- **wyszukiwanie w PBN po DOI/ISBN** — dla rekordów BPP bez powiązania.

**Lista prac z profilu nie musi być pobierana za każdym razem.** Jej
pobranie trwa najdłużej (system przechodzi cały profil, nie tylko wybrane
lata). Jeśli lista była pobrana w ciągu ostatnich 24 godzin, „Pobierz dane
z PBN” odświeża tylko dane prac, oświadczenia i wyszukiwanie dla wybranych
lat — a pod polami lat pojawia się pole wyboru „pobierz ponownie także listę
prac z profilu instytucji”. **Zaznacz je, jeśli od ostatniego pobrania
dodawano albo usuwano prace na profilu instytucji w PBN** — inaczej system
nie zobaczy nowo dodanych prac. Data listy profilu jest w ramce pokazana
osobno.

Te same daty są w raporcie każdego przebiegu (na stronie i w pliku XLSX).

- **Dane starsze niż 24 godziny** — ramka robi się żółta i ostrzega: zmian
  wprowadzonych w PBN po tej dacie uzgadnianie nie zobaczy. Odśwież dane
  przyciskiem **Pobierz dane z PBN**. Uruchomić uzgadnianie nadal możesz —
  np. gdy wiesz, że w PBN nic się od tego czasu nie zmieniło.
- **Brak danych** — strona pisze „Nie ma jeszcze pobranych danych z PBN”,
  a próba uruchomienia kończy się komunikatem, dla jakich lat trzeba je
  pobrać. Dane pobrane dla lat 2024–2025 nie wystarczą do uzgadniania roku
  2026; pobrane dla 2025–2026 — wystarczą.

Przycisk **Anuluj** zatrzymuje przebieg po bieżącej pracy. Anulowany podgląd
niczego nie zmienia. Anulowane wykonanie zostawia to, co zdążyło zrobić —
wystarczy uruchomić je jeszcze raz, żeby dokończyć resztę.

## Co system robi sam {#co-robi-sam}

| Sytuacja | Co się dzieje |
|---|---|
| Praca jest na profilu instytucji w PBN, a w BPP jej nie ma | System **tworzy rekord** w BPP (artykuł, książka albo rozdział) z autorami i redaktorami z PBN. |
| Praca jest w BPP, ale bez identyfikatora PBN, i **zgadza się DOI** (albo ISBN książki) i rok | System **wiąże** istniejący rekord z pracą w PBN. Nie powstaje duplikat. |
| Rozdział, którego książki nadrzędnej nie ma w BPP | System tworzy rozdział **i książkę nadrzędną**; raport to zaznacza. |

Dane nowego rekordu pochodzą z **wersji przypiętej na profilu instytucji**
w PBN — czyli tej, którą zatwierdziła uczelnia — a nie z najnowszej wersji
w repozytorium PBN, którą mógł zmienić ktoś spoza uczelni. Jeśli profil nie
wskazuje wersji, system bierze wersję bieżącą i pisze o tym w raporcie
(kolumna „Użyta wersja z PBN”).

### Dyscypliny w nowych rekordach {#dyscypliny}

Nowo utworzony rekord od razu dostaje **dyscypliny autorów z oświadczeń
złożonych na profilu instytucji w PBN** (pobranych przyciskiem „Pobierz dane
z PBN”). System przypisuje dyscyplinę tylko wtedy, gdy nie musi niczego
zgadywać:

- autor rekordu to ta sama osoba co w oświadczeniu (ten sam identyfikator
  PBN, ta sama rola — autor albo redaktor),
- dyscyplina z oświadczenia jest w słowniku dyscyplin BPP,
- autor ma tę dyscyplinę **przypisaną w BPP na rok pracy**.

W każdym innym wypadku autor zostaje **bez dyscypliny**, a raport (kolumna
„Dyscypliny w nowym rekordzie”) podaje powód:

| Powód w raporcie | Co zrobić |
|---|---|
| Brak oświadczenia tej osoby na profilu instytucji w PBN | Złóż oświadczenie w PBN albo przypisz dyscyplinę w rekordzie ręcznie. |
| Autor nie ma w BPP przypisanej dyscypliny … na rok … | Uzupełnij dyscypliny autora na ten rok, potem przypisz dyscyplinę w rekordzie. |
| Dyscypliny … nie ma w słowniku dyscyplin BPP | Zgłoś administratorowi — słownik dyscyplin wymaga aktualizacji. |
| W PBN jest oświadczenie osoby, której nie ma wśród autorów/redaktorów rekordu | Sprawdź listę osób w rekordzie i w PBN. |

System **nie dopisuje sam autorowi dyscypliny na dany rok** — wolimy
pokazać brak niż zgadywać.

Każde utworzenie i powiązanie widać w **historii zmian** rekordu, razem
z osobą, która uruchomiła uzgadnianie.

## Czego system nie robi {#czego-nie-robi}

- **Nie zmienia istniejących rekordów BPP.** Jeśli tytuł, rok czy DOI różnią
  się między BPP a PBN, zobaczysz to w raporcie — decyzja, która wersja jest
  poprawna, należy do Ciebie.
- **Nie zmienia autorów, dyscyplin ani oświadczeń** w istniejących rekordach.
  Jeśli dyscyplina autora w rekordzie różni się od oświadczenia w PBN,
  raport pokazuje to jako różnicę „Dyscyplina (autor)”.
- **Niczego nie kasuje** — także wtedy, gdy praca została skasowana w PBN.
- **Niczego nie wysyła do PBN.**
- **Nie przywraca rekordów z kosza** — rekord usunięty w BPP został usunięty
  świadomie.
- **Nie importuje prac spoza profilu instytucji**, nawet jeśli są w lokalnej
  kopii danych PBN.
- **Nie tworzy rekordu „na wszelki wypadek”.** Gdy w BPP jest tylko *podobny*
  rekord (zbliżony tytuł, ale bez zgodnego DOI/ISBN), system ani nie tworzy
  nowego, ani nie wiąże istniejącego — pokazuje oba w sekcji „Do decyzji”.

## Jak czytać raport {#raport}

Raport jest na stronie przebiegu i do pobrania przyciskiem **Pobierz raport
(XLSX)**. Każda praca trafia do jednej sekcji.

### Prace z profilu instytucji w PBN {#raport-pbn}

| Sekcja | Co oznacza | Co zrobić |
|---|---|---|
| **Utworzono rekord w BPP** | Nowy rekord z danych PBN, z dyscyplinami z oświadczeń. W podglądzie: „Do wykonania”. | Przejrzyj rekord: charakter formalny, punktację; uzupełnij dyscypliny tam, gdzie raport pisze „BEZ DYSCYPLINY”. |
| **Powiązano istniejący rekord BPP z pracą w PBN** | Rekord dostał identyfikator PBN (zgodny DOI/ISBN). | Nic; ewentualne różnice pól są podane obok. |
| **Praca jest po obu stronach, dane się różnią** | Ten sam identyfikator PBN po obu stronach, ale dane się rozjechały — patrz niżej. | Zdecyduj, co jest poprawne, i popraw w BPP albo w PBN. |
| **Do decyzji: w BPP jest podobny rekord** | Dopasowanie niepewne (np. tylko podobny tytuł). Nic nie zmieniono. | Jeśli to ta sama praca — wpisz w rekordzie BPP identyfikator PBN. Jeśli inna — zaimportuj ją pojedynczo [importerem publikacji](importer-publikacji.md). |
| **Konflikt powiązań** | Pasujący rekord BPP jest już powiązany z inną pracą w PBN albo kilka rekordów BPP ma ten sam identyfikator PBN. | Zwykle to duplikat — w PBN albo w BPP. Patrz [Duplikaty publikacji](duplikaty-publikacji.md). |
| **Pominięto** | Z podanym powodem: rekord w koszu, praca bez autorów w PBN, niezgodna liczba autorów/redaktorów po imporcie, niekompletne dane w PBN. | Według powodu; najczęściej import pojedynczy z ręcznym sprawdzeniem osób. |
| **Błąd przy przetwarzaniu pracy** | Tej jednej pracy nie udało się przetworzyć; pozostałe poszły dalej. | Uruchom ponownie; jeśli błąd się powtarza — zgłoś go z numerem pracy w PBN. |
| **Praca skasowana w PBN** | Praca ma w PBN status „skasowana”. Rekord BPP (jeśli jest) pozostał bez zmian. | Sprawdź, czy rekord w BPP jest nadal potrzebny. |
| **Praca jest po obu stronach, bez różnic** | Wszystko się zgadza. | Nic. Pełna lista jest w pliku XLSX. |

**Różnice są pokazane linijka po linijce.** Przy każdej pracy z sekcji „dane
się różnią” jest tabelka: **pole | w BPP | w PBN**, po jednym wierszu na
różnicę (tytuł, rok, DOI, ISBN, adres WWW, liczba autorów, liczba
redaktorów, dyscyplina każdego autora względem oświadczenia). W długich
tekstach — np. w tytule — **podświetlone są tylko słowa, które się różnią**.
Pusta wartość jest nazwana słowami, np. „brak oświadczenia w PBN” albo
„brak dyscypliny w rekordzie BPP”. Nad tabelką jest identyfikator PBN
(ten sam po obu stronach), a w kolumnach obok — odnośniki do rekordu w BPP
i do pracy w PBN. W pliku XLSX te same wiersze są w arkuszu **„Różnice”**.

### Rekordy BPP bez powiązania z PBN {#raport-bez-powiazania}

Rekord z wybranych lat, który nie ma identyfikatora PBN, to nie zawsze
„praca, której w PBN nie ma”. Raport dzieli je na cztery grupy:

| Sekcja | Co oznacza | Co zrobić |
|---|---|---|
| **…prawdopodobny duplikat rekordu powiązanego z PBN** | W BPP jest drugi rekord tej samej pracy, już powiązany z PBN (np. pracę wpisano ręcznie, a potem pobrano ją z PBN). Raport pokazuje oba rekordy i to, po czym je dopasowano. | Sprawdź oba i scal je [deduplikatorem publikacji](duplikaty-publikacji.md). System niczego nie scala sam. |
| **…praca jest w PBN, ale nie jest powiązana z rekordem** | PBN ma pracę o tym DOI/ISBN (albo jest ona w pobranych danych). Raport podaje identyfikator PBN i mówi, czy praca **jest**, czy **nie jest** na profilu instytucji. | To propozycja powiązania: wpisz identyfikator PBN w rekordzie; jeśli pracy nie ma na profilu — dodaj ją w PBN do instytucji. Dopisek „dopasowanie niepewne” (zgodny tylko tytuł i rok) oznacza, że najpierw trzeba sprawdzić, czy to ta sama praca. |
| **…nie ma go w PBN (kandydat do wysłania)** | PBN nie ma pracy o tym DOI/ISBN. Raport dopisuje historię wysyłki z BPP: „nigdy nie wysyłany” albo „wysyłka nieudana” z datą i powodem. | Wyślij rekord do PBN; przy nieudanej wysyłce najpierw usuń podaną przyczynę. |
| **…nie da się sprawdzić automatycznie (brak DOI/ISBN)** | Rekord nie ma DOI ani ISBN, więc nie ma o co zapytać PBN. | Sprawdź ręcznie; uzupełnij DOI, jeśli praca go ma. |

Dopasowanie po tytule nie zwraca uwagi na wielkość liter, interpunkcję ani
znaczniki formatowania w tytule (kursywa, indeksy).

### Rekordy BPP powiązane z pracą spoza profilu {#raport-poza-profilem}

| Sekcja | Co oznacza | Co zrobić |
|---|---|---|
| **…która jest na profilu innej uczelni tej instalacji** | Tylko w instalacjach z kilkoma uczelniami: praca jest na profilu wskazanej uczelni, a nie Twojej — choć rekord ma afiliowanego autora Twojej uczelni. | Dodaj pracę w PBN także do profilu swojej instytucji. |
| **…której nie ma na żadnym znanym profilu instytucji w PBN** | Praca jest w PBN, ale poza profilem. | Dodaj ją w PBN do instytucji albo wyślij ponownie z BPP. |

Listy „po stronie BPP” obejmują tylko rekordy, które na profilu instytucji
powinny się znaleźć: z afiliowanym autorem z jednostki Twojej uczelni
i o charakterze formalnym wysyłanym do PBN. W instalacji z kilkoma
uczelniami praca współautorska pojawia się w raporcie każdej z nich —
każda powinna mieć ją na własnym profilu.

## Co może pójść nie tak {#co-moze-pojsc-nie-tak}

- **„Uzgadnianie z PBN dla tej uczelni już trwa”** — jednocześnie może
  działać jeden przebieg. Poczekaj albo anuluj poprzedni.
- **Przebieg ma stan „błąd” z dopiskiem o braku postępu** — zadanie zostało
  przerwane (np. restart serwera). Uruchom ponownie; to, co zostało zrobione,
  nie zostanie zdublowane.
- **Dużo wpisów „Pominięto” z powodem o liczbie autorów lub redaktorów** —
  to celowy bezpiecznik: przy części prac zbiorowych dane o rolach osób
  w PBN są niejednoznaczne i automat nie zgaduje. Takie prace importuj
  pojedynczo.
- **Pierwsze pobranie danych trwa długo** — system czyta cały profil
  instytucji z PBN (strona pokazuje licznik, np. „lista prac i osób:
  1250 z 4100”). Kolejne są szybsze, zwłaszcza gdy lista profilu jest
  świeża i nie jest pobierana ponownie.
- **Praca dodana w PBN przed chwilą nie pojawia się w raporcie** — sprawdź
  datę w ramce „Dane z PBN…” i pobierz dane ponownie.

## A „Import z PBN” i „pobieranie danych z PBN”? {#stare-funkcje}

To **nie są** inne sposoby na to samo i nie są przeznaczone do
synchronizacji prac przez redaktora:

- **Import z PBN** — narzędzie **administratora** do pierwszego zasilenia
  **pustej bazy** przy wdrożeniu systemu (słowniki, autorzy, wszystkie
  publikacje z lokalnej kopii danych PBN). Nie uruchamiaj go, żeby „dociągnąć”
  kilka prac — do tego służy uzgadnianie.
- **pobieranie danych z PBN** — pobiera dane na potrzeby **deduplikatorów
  i komparatorów** (osoby, źródła, oświadczenia, publikacje instytucji).
  Nie zmienia rekordów BPP i nie jest źródłem danych dla uzgadniania:
  publikacji już pobranych nie pobiera ponownie, więc poprawek
  wprowadzonych w PBN by nie zauważyło. Uzgadnianie ma własny przycisk
  **Pobierz dane z PBN**.

## Zobacz też {#zobacz-tez}

- [PBN: wysyłanie prac, kolejka i porównanie](pbn-wysylka-i-synchronizacja.md)
- [Jak dodać publikację importerem](importer-publikacji.md)
- [Duplikaty publikacji](duplikaty-publikacji.md)
