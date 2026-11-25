# Raporty: tabele, kolumny i źródła danych

Raporty z menu **raporty** (Raport autorów, jednostek, wydziałów, uczelni
i raporty dodane przez uczelnię) składają się z trzech rodzajów definicji,
które edytuje się w module redagowania, w menu **Raporty**:

- **Tabele** — lista kolumn raportu, ich etykiety i domyślne sortowanie,
- **Źródła danych** — zapytania wybierające prace do poszczególnych sekcji,
- **Raporty** — szablon raportu i jego sekcje („Składowe raportu”); każda
  sekcja łączy jedno źródło danych z jedną tabelą.

Model, z którego raport bierze dane, wybiera się **tylko raz — w źródle
danych** (pole „Podstawowy model”). Tabela i sekcja raportu nie mają własnego
pola modelu: tabela stosuje się do modelu źródła danych, z którym została
połączona w sekcji raportu.

To, komu i w którym miejscu menu raport się pokazuje, ustawia się osobno
w **Raporty w menu strony**.

Definicje raportów może zmieniać superużytkownik oraz osoby z grupy
„raporty” (zob. [Grupy uprawnień](../administrator/grupy-uprawnien.md)).

## Źródło danych: model i zapytanie {#zrodlo-danych-model-i-zapytanie}

Moduł redagowania → **Raporty** → **Źródła danych** → **Dodaj** albo wybierz
istniejące źródło.

### Podstawowy model {#podstawowy-model}

Lista zawiera model, z którego buduje się raporty: **rekord** — wszystkie
publikacje (wydawnictwa ciągłe i zwarte, patenty, prace doktorskie
i habilitacyjne). Przy dodawaniu nowego źródła danych jest on od razu wybrany.
Po autorze, jednostce, charakterze formalnym itd. filtruje się w zapytaniu,
w ramach rekordu (np. `autorzy.autor`, skrót `autor`).

Źródło danych zapisane wcześniej z innym modelem działa bez zmian — jego model
pozostaje na liście w formularzu tego źródła i można je normalnie edytować.

### Edytor zapytania {#edytor-zapytania}

Pole **Query** jest edytorem:

- **Kolorowanie składni** — nazwy pól, operatory, `and`/`or`, wartości
  i parametry szablonu (`{{ obiekt.pk }}`, `{% if … %}`) mają różne kolory.
  Znak, którego język zapytań nie zna, jest podkreślony falką.
- **„Formatuj”** — przycisk pod polem. Rozbija zapytanie na wiersze: każdy
  warunek łączony przez `and`/`or` w osobnym wierszu, dłuższe grupy w nawiasach
  z wcięciem. Formatowanie zmienia wyłącznie odstępy i podział na wiersze;
  wartości w cudzysłowach i parametry szablonu zostają nietknięte, więc
  zapytanie wybiera te same prace co przed formatowaniem. Zapytania
  z niedomkniętym cudzysłowem albo nawiasem nie da się sformatować — pod polem
  pojawia się komunikat, a tekst zostaje bez zmian.
- **Podpowiadanie (język DjangoQL)** — w trakcie pisania edytor pokazuje pod
  kursorem listę pól wybranego modelu, potem operatory i wartości. Po wpisaniu
  nazwy powiązania i kropki, np. `charakter_formalny.`, lista pokazuje pola
  powiązanego obiektu (`nazwa`, `skrot`…). Podpowiedź wybiera się strzałkami
  i klawiszem Enter albo kliknięciem; Esc zamyka listę. Poza listą Enter
  wstawia nowy wiersz.
- **Lista pól (język django-dsl)** — pod polem jest rozwijana lista
  **„Dostępne pola”** oraz **„Skróty”** (np. `autor`, `jednostka`,
  `charakter`); kliknięcie nazwy wstawia ją w miejscu kursora.

Zmiana **„Podstawowego modelu”** albo **„Query language”** od razu przełącza
podpowiedzi i kolorowanie — nie trzeba zapisywać formularza. Poprawność
zapytania jest, jak dotąd, sprawdzana przy zapisie.

## Tabela nie ma własnego modelu {#tabela-bez-modelu}

Formularz tabeli (**Raporty** → **Tabele**) nie zawiera pola „Podstawowy
model”. Pole **„Nazwa atrybutu”** kolumny jest sprawdzane względem modelu
źródła danych, z którym tabela jest użyta w raporcie; dla tabeli, która nie
jest jeszcze podpięta do żadnego raportu — względem modelu **rekord**.

Kolejność ma znaczenie tylko w jednym, rzadkim przypadku: gdy tabela ma
służyć źródłu danych o **innym** modelu niż rekord (takie źródła mogły zostać
z wcześniejszych wersji). Nowa tabela, niepodpięta jeszcze do raportu, jest
sprawdzana względem rekordu, więc nazwy atrybutów istniejące tylko w tamtym
modelu zostaną odrzucone. Wtedy: załóż tabelę bez kolumn, wybierz ją w polu
**Tabela** sekcji raportu korzystającej z tego źródła danych, zapisz raport
i dopiero potem dodaj kolumny.

Także „Składowe raportu” nie mają pola modelu. Sekcja z **„Dane z”**
ustawionym na „wszystkie rekordy oprócz pasujących do źródeł danych raportu”
(w domyślnych raportach „4.3. Inne”) pokazuje po prostu wszystko, czego nie
wybrało żadne źródło danych tego raportu.

Tabele i raporty założone wcześniej działają bez zmian.

## Zmiana etykiety kolumny {#zmiana-etykiety-kolumny}

1. Moduł redagowania → **Raporty** → **Tabele** → wybierz tabelę.
2. W sekcji **Kolumny** zmień pole **Etykieta** wybranej kolumny (np.
   z „Typ KBN” na „Typ MNiSW”) i zapisz tabelę.

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
