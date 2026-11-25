# Raporty: tabele, kolumny i źródła danych

Raporty z menu **raporty** (Raport autorów, jednostek, wydziałów, uczelni
i raporty dodane przez uczelnię) składają się z trzech rodzajów definicji,
które edytuje się w module redagowania, w menu **Raporty**:

- **Tabele** — lista kolumn raportu, ich etykiety i domyślne sortowanie,
- **Źródła danych** — zapytania wybierające prace do poszczególnych sekcji,
- **Raporty** — szablon raportu i jego sekcje („Składowe raportu”); każda
  sekcja łączy jedno źródło danych z jedną tabelą.

To, komu i w którym miejscu menu raport się pokazuje, ustawia się osobno
w **Raporty w menu strony**.

Definicje raportów może zmieniać superużytkownik oraz osoby z grupy
„raporty” (zob. [Grupy uprawnień](../administrator/grupy-uprawnien.md)).

## Zmiana etykiety kolumny {#zmiana-etykiety-kolumny}

1. Moduł redagowania → **Raporty** → **Tabele** → wybierz tabelę.
2. W sekcji **Kolumny** zmień pole **Etykieta** wybranej kolumny (np.
   z „Typ MNiSW/MEiN” na „Typ pracy”) i zapisz tabelę.

Nowa etykieta jest widoczna od razu — przy najbliższym wygenerowaniu raportu,
bez restartu serwera — w nagłówku tabeli na ekranie oraz w plikach pobranych
przyciskami **„pobierz jako MS Word”** i **„pobierz jako XLSX”**.

Warto wiedzieć:

- Jedna tabela bywa użyta w wielu raportach i sekcjach (domyślna tabela
  „Publikacje autorów” obsługuje wszystkie raporty zakładane przez system).
  Zmiana etykiety trafia do **wszystkich** raportów korzystających z tej
  tabeli. Jeśli etykieta ma się różnić tylko w jednym raporcie, najpierw
  [sklonuj tabelę](#klonowanie-tabeli).
- Zmiana etykiety nie zmienia danych w kolumnie ani sortowania: sortowanie
  („Informacje o sortowaniu kolumn”) wskazuje kolumnę, a nie jej nazwę.
- Kolumna z zaznaczonym **„Wyłączaj z eksportu”** (domyślnie „Lp”) nadal nie
  trafia do plików Word i Excel, niezależnie od etykiety.
- Etykiety kolumn w jednej tabeli powinny być różne — dwie kolumny o tej samej
  etykiecie pokażą się w raporcie jako jedna.

## Nazwy pól punktów i typu MNiSW/MEiN w zapytaniach {#nazwy-pol-mnisw}

W zapytaniach źródeł danych (**Raporty** → **Źródła danych**) punkty i typ
MNiSW/MEiN można zapisać nową nazwą — `punkty_mnisw`, `typ_mnisw` — albo
dawną: `punkty_kbn`, `typ_kbn`. Obie działają tak samo w obu językach zapytań
(django-dsl i DjangoQL), np. `punkty_mnisw > 0 AND NOT typ_mnisw = "PW"`.
Istniejących źródeł danych nie trzeba poprawiać.

Te same nowe nazwy działają w tabelach raportów (**Raporty** → **Tabele**
→ sekcja **Kolumny**):

- w polu **Atrybut** kolumny — `punkty_mnisw`, `typ_mnisw`, także ze
  ścieżką, np. `typ_mnisw.nazwa`. Kolumna wyświetla się, sortuje po
  kliknięciu w nagłówek i eksportuje do MS Word i XLSX tak samo jak
  z dawną nazwą,
- w polu **Szablon** kolumny — `{{ record.punkty_mnisw }}`,
  `{{ record.typ_mnisw }}`, `{{ record.typ_mnisw.nazwa }}`.

Kolumn z dawnymi nazwami (`punkty_kbn`, `typ_kbn`) nie trzeba zmieniać.

## Klonowanie tabeli {#klonowanie-tabeli}

Żeby przygotować nową tabelę na podstawie istniejącej, nie trzeba przepisywać
kolumn:

1. Moduł redagowania → **Raporty** → **Tabele** → otwórz tabelę, którą chcesz
   skopiować.
2. Kliknij **„Klonuj”** u góry formularza.

System tworzy kopię o nazwie z dopiskiem „(kopia)” — kolejne kopie tej samej
tabeli dostają „(kopia 2)”, „(kopia 3)”… — i od razu otwiera jej formularz.
Kopia ma te same kolumny, w tej samej kolejności i z tymi samymi ustawieniami
(szablon, sortowanie, eksport, podsumowania), oraz to samo domyślne sortowanie.
Wystarczy zmienić w niej to, czym ma się różnić.

- Oryginalna tabela zostaje bez zmian, a raporty dalej z niej korzystają.
- Kopia nie jest podpięta do żadnego raportu. Żeby jej użyć, wybierz ją w polu
  **Tabela** odpowiedniej sekcji raportu (**Raporty** → raport → „Składowe
  raportu”).
- Klonować może osoba, która ma prawo dodawania tabel.

Tak samo działa **„Klonuj”** w formularzu raportu (**Raporty** → **Raporty**):
kopia raportu ma te same sekcje, wskazujące te same tabele i źródła danych,
i dostaje nieaktywną pozycję w **Raporty w menu strony**.

## Edycja źródła danych z otwartego raportu {#edycja-zrodla-danych-z-raportu}

Poprawiając zapytanie, nie trzeba szukać źródła danych na liście ani
generować raportu od nowa:

1. Wygeneruj raport „w przeglądarce”.
2. Pod przyciskami pobierania rozwiń **„Źródła danych tego raportu”**. Lista
   pokazuje sekcje raportu w kolejności, a przy każdej odnośnik
   **„edytuj źródło danych”** z nazwą źródła.
3. Kliknij odnośnik, popraw zapytanie i kliknij **„Zapisz”**.

Po zapisaniu system wraca do tego samego raportu — dla tego samego autora
(jednostki, wydziału), tych samych lat i opcji — i generuje go ponownie,
więc efekt zmiany widać od razu. W formularzu źródła danych jest też odnośnik
**„Wróć do raportu”**, jeśli chcesz wrócić bez zapisywania.

- Listę widzą tylko osoby, które mogą zmieniać źródła danych w module
  redagowania; pozostali użytkownicy raportu jej nie zobaczą. Nie pojawia się
  też na wydruku.
- **„Zapisz i kontynuuj edycję”** zostawia w formularzu źródła danych (powrót
  do raportu nadal będzie możliwy); niepoprawne zapytanie także zostawia
  w formularzu, z komunikatem błędu.
- Jeżeli raport w ogóle się nie generuje („Nie udało się wygenerować
  raportu” — niepoprawne zapytanie w jednym ze źródeł danych), ta sama lista
  jest na stronie z komunikatem, od razu rozwinięta.
- Jedno źródło danych może być użyte w kilku raportach — zmiana zapytania
  dotyczy ich wszystkich.
- Sekcje bez własnego źródła danych — zbierające prace, które nie trafiły do
  żadnej innej sekcji (w domyślnych raportach „4.3. Inne”) — nie mają
  odnośnika.
- Formularz **Źródła danych** otwarty zwyczajnie, z menu, działa jak dotąd
  i po zapisaniu wraca na listę źródeł danych.

Przycisk **„otwórz do edycji”** nad raportem, jak dotąd, otwiera w nowej
karcie definicję raportu (szablon i sekcje).
