# Uzgodnij z PBN — brakujące prace i raport różnic jednym działaniem

Przewodnik dla redaktorów, którzy chcą, żeby **stan prac w BPP za wybrany
rok zgadzał się z profilem instytucji w PBN**. Typowa sytuacja: w PBN
poprawiłaś lub dodałaś do profilu instytucji kilkanaście prac i chcesz mieć
je w BPP — bez przepisywania każdej osobno.

Dotąd wymagało to trzech kroków w dwóch podobnie nazwanych miejscach
(„pobieranie danych z PBN”, potem „Import z PBN”, potem komparatory).
**„Uzgodnij z PBN” robi to jednym działaniem** i mówi wprost, co zmieniło,
a co zostawiło do Twojej decyzji.

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

1. Menu **PBN** → **uzgodnij z PBN**.
2. Wpisz zakres lat: **Rok od** i **Rok do** (dla jednego roku wpisz ten
   sam rok w obu polach, np. `2026` i `2026`).
3. Kliknij jeden z przycisków:
   - **Pokaż, co się zmieni** — podgląd. System pobiera dane z PBN
     i pokazuje pełny raport, ale **nie zmienia żadnego rekordu w BPP**.
   - **Uzgodnij teraz** — to samo, ale zmiany są od razu wykonywane.
4. Operacja działa w tle. Strona pokazuje pasek postępu i odświeża się
   sama; możesz ją zamknąć i wrócić później — przebieg jest na liście
   **Ostatnie przebiegi**.

Jeśli zaczęłaś od podglądu i wynik Ci odpowiada, kliknij **Wykonaj ten
podgląd**. System zrobi dokładnie to, co pokazał, i nie pobiera już danych
z PBN ponownie.

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
złożonych na profilu instytucji w PBN**. System pobiera oświadczenia prosto
z PBN przy każdym uruchomieniu i przypisuje dyscyplinę tylko wtedy, gdy nie
musi niczego zgadywać:

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

System **nie dopisuje sam autorowi dyscypliny na dany rok** (robi to
dotychczasowy import oświadczeń w „Import z PBN”) — tu wolimy pokazać brak
niż zgadywać.

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
(XLSX)**. Każda praca trafia do jednej sekcji:

| Sekcja | Co oznacza | Co zrobić |
|---|---|---|
| **Utworzono rekord w BPP** | Nowy rekord z danych PBN, z dyscyplinami z oświadczeń. W podglądzie: „Do wykonania”. | Przejrzyj rekord: charakter formalny, punktację; uzupełnij dyscypliny tam, gdzie raport pisze „BEZ DYSCYPLINY”. |
| **Powiązano istniejący rekord BPP z pracą w PBN** | Rekord dostał identyfikator PBN (zgodny DOI/ISBN). | Nic; ewentualne różnice pól są podane obok. |
| **Praca jest po obu stronach, dane się różnią** | Lista różnic w układzie „BPP → PBN”: tytuł, rok, DOI, ISBN, adres WWW, liczba autorów i redaktorów, dyscypliny autorów względem oświadczeń. | Zdecyduj, co jest poprawne, i popraw w BPP albo w PBN. |
| **Do decyzji: w BPP jest podobny rekord** | Dopasowanie niepewne (np. tylko podobny tytuł). Nic nie zmieniono. | Jeśli to ta sama praca — wpisz w rekordzie BPP identyfikator PBN. Jeśli inna — zaimportuj ją pojedynczo [importerem publikacji](importer-publikacji.md). |
| **Konflikt powiązań** | Pasujący rekord BPP jest już powiązany z inną pracą w PBN albo kilka rekordów BPP ma ten sam identyfikator PBN. | Zwykle to duplikat — w PBN albo w BPP. Patrz [Duplikaty publikacji](duplikaty-publikacji.md). |
| **Pominięto** | Z podanym powodem: rekord w koszu, praca bez autorów w PBN, niezgodna liczba autorów/redaktorów po imporcie, niekompletne dane w PBN. | Według powodu; najczęściej import pojedynczy z ręcznym sprawdzeniem osób. |
| **Błąd przy przetwarzaniu pracy** | Tej jednej pracy nie udało się przetworzyć; pozostałe poszły dalej. | Uruchom ponownie; jeśli błąd się powtarza — zgłoś go z numerem pracy w PBN. |
| **Praca skasowana w PBN** | Praca ma w PBN status „skasowana”. Rekord BPP (jeśli jest) pozostał bez zmian. | Sprawdź, czy rekord w BPP jest nadal potrzebny. |
| **Rekord BPP bez powiązania z PBN** | Praca z wybranych lat, z afiliowanym autorem uczelni, której nie ma w PBN albo nie jest powiązana. | Wyślij ją do PBN albo uzupełnij identyfikator PBN. |
| **Rekord BPP powiązany z pracą spoza profilu instytucji w PBN** | Praca jest w PBN, ale nie na profilu Twojej instytucji. | Dodaj ją w PBN do instytucji albo wyślij ponownie z BPP. |
| **Praca jest po obu stronach, bez różnic** | Wszystko się zgadza. | Nic. Pełna lista jest w pliku XLSX. |

Dwie ostatnie listy „po stronie BPP” obejmują tylko rekordy, które na
profilu instytucji powinny się znaleźć: z afiliowanym autorem z jednostki
uczelni i o charakterze formalnym wysyłanym do PBN.

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
- **Pierwsze uruchomienie trwa długo** — system czyta cały profil
  instytucji z PBN. Kolejne są szybsze.

## Stare funkcje: co z „Import z PBN” i „pobieranie danych z PBN”? {#stare-funkcje}

Obie zostają i działają jak dotąd:

- **Import z PBN** — do pierwszego wdrożenia systemu i do słowników
  (źródła, wydawcy, konferencje, punktacja źródeł).
- **pobieranie danych z PBN** — odświeża lokalną kopię danych dla
  komparatorów (oświadczenia, osoby, źródła).

Do codziennej pracy — „poprawiłam coś w PBN i chcę to mieć w BPP” —
używaj **uzgodnij z PBN**.

## Zobacz też {#zobacz-tez}

- [PBN: wysyłanie prac, kolejka i porównanie](pbn-wysylka-i-synchronizacja.md)
- [Jak dodać publikację importerem](importer-publikacji.md)
- [Duplikaty publikacji](duplikaty-publikacji.md)
