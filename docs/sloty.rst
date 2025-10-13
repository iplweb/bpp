Obliczanie slotów
=================

Uwagi ogólne
------------

#. System przelicza sloty w momencie zapisu rekordu pracy (dla wydawnictwa ciągłego
   lub wydawnictwa zwartego) w momencie naciśniecia przycisku "Zapisz" w module redagowania.

#. Jeżeli daną pracę uda się dopasować do odpowiedniego algorytmu kalkulacji punktów,
   użytkownik otrzyma komunikat na górze ekranu. Podobnie otrzyma komunikat, jeżeli nie da
   się takiej publikacji dopasować.

#. Reguły dla poszczególnych typów prac - warunki, które musi spełnić dany rekord, aby
   został włączony algorytm - opisane są poniżej.

#. W chwili tworzenia niniejszej dokumentacji system powinien liczyć punkty dla prac
   z lat 2017-2021 (dla roku 2021 używany jest identyczny algorytm jak dla 2020)

Rodzaje autorów
---------------

System rozróżnia cztery rodzaje autorów w powiązaniach autor-dyscyplina:

**N - naukowiec w N**
   - Wliczany do liczby N (parametr ewaluacyjny)
   - Liczone są dla niego sloty
   - Standardowy pracownik naukowy zaliczany do ewaluacji

**D - doktorant**
   - Nie jest wliczany do liczby N
   - Liczone są dla niego sloty
   - Osoba na studiach doktoranckich

**B - badawczy**
   - Nie jest wliczany do liczby N
   - Liczone są dla niego sloty
   - Pracownik o charakterze badawczym (np. post-doc, badacz bez etatu naukowego)

**Z - inny lub techniczny**
   - Nie jest wliczany do liczby N
   - Nie liczą się dla niego sloty
   - Pracownik techniczny, administracyjny lub inny niebędący pracownikiem badawczym

Jak system decyduje o rodzaju autora podczas importu z POLON?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

System automatycznie przypisuje każdyemu pracownikowi odpowiedni rodzaj autora podczas importu danych z pliku POLON.
Decyzja opiera się na dwóch kluczowych informacjach: oświadczeniu pracownika o dyscyplinach oraz charakterze jego zatrudnienia.

**Krok 1: Sprawdzenie oświadczenia o dyscyplinach**

System najpierw patrzy na kolumnę **"OSWIADCZENIE_N"** w pliku POLON:

* **Jeżeli pracownik złożył oświadczenie N** (w kolumnie "OSWIADCZENIE_N" wpisano "tak"):
  - System odnotowuje, że pracownik jest zaliczany do liczby N
  - Pobiera dyscypliny z kolumn "DYSCYPLINA_N" i "DYSCYPLINA_N_KOLEJNA"
  - **Pracownik otrzymuje rodzaj: N (naukowiec w N)**

* **Jeżeli pracownik nie złożył oświadczenia N** (kolumna pusta lub inna wartość):
  - System odnotowuje, że pracownik nie jest zaliczany do liczby N
  - Przechodzi do analizy charakteru zatrudnienia

**Krok 2: Analiza charakteru zatrudnienia**

Następnie system sprawdza kolumnę **"GRUPA_STANOWISK"**:

* **Jeżeli pracownik jest zatrudniony na stanowisku badawczym**:
  - "pracownik badawczo-dydaktyczny"
  - "pracownik badawczo-techniczny"

  System odnotowuje charakter badawczy zatrudnienia.

* **W pozostałych przypadkach** (np. pracownik techniczny, administracyjny):
  - System odnotowuje charakter niebadawczy zatrudnienia.

**Krok 3: Przypisanie rodzaju autora - nowe wpisy**

Gdy system tworzy nowy wpis dla pracownika, stosuje następującą kolejność:

1. **Jeżeli pracownik złożył oświadczenie N** → rodzaj autora = **N**
2. **Jeżeli nie złożył oświadczenia N, ale pracuje na stanowisku badawczym** → rodzaj autora = **B**
3. **W pozostałych przypadkach** → rodzaj autora = **Z**

**Krok 4: Aktualizacja istniejących wpisów**

Gdy system aktualizuje już istniejącego pracownika:

* **Jeżeli pracownik złożył oświadczenie N**:
  - Zawsze ustawia rodzaj autora na **N** (nawet jeżeli wcześniej był D, B lub Z)
  - Nawet doktorant staje się naukowcem w N

* **Jeżeli pracownik nie złożył oświadczenia N**:
  - **Gdy wcześniej był N** → zmienia na **Z**
  - **Gdy wcześniej był Z i pracuje badawczo** → zmienia na **B**
  - **Gdy wcześniej był B i nie pracuje badawczo** → zmienia na **Z**
  - **Doktorantów (D) pozostawia bez zmian**

**Przykłady w praktyce**

* **Pracownik badawczo-dydaktyczny z oświadczeniem N**:
  - Oświadczenie N: "tak"
  - Stanowisko: "pracownik badawczo-dydaktyczny"
  - **Wynik**: Rodzaj autora = **N** (oświadczenie N ma pierwszeństwo)

* **Pracownik techniczny bez oświadczenia N**:
  - Oświadczenie N: puste
  - Stanowisko: "pracownik techniczny"
  - **Wynik**: Rodzaj autora = **Z**

* **Post-doc bez oświadczenia N**:
  - Oświadczenie N: puste
  - Stanowisko: "pracownik badawczo-techniczny"
  - **Wynik**: Rodzaj autora = **B**

**Co warto wiedzieć?**

* Oświadczenie N ma **najwyższy priorytet** - ważniejsze niż rodzaj zatrudnienia
* System **ignoruje wielkość liter** przy sprawdzaniu pól
* Wszystkie zmiany rodzaju autora są **zapisywane w logu**
* Po zmianie rodzaju autora system **aktualizuje powiązania** z publikacjami
* **Doktoranci są chronieni** - ich rodzaj autora nigdy nie jest zmieniany

Progi algorytmu
---------------

* w kodzie oprogramowania opracowane są niniejsze procedury obliczające punkty,

* obliczenia dokonywane są wewnętrznie z precyzją zmiennoprzecinkową, następnie
  prezentowane są zaokrąglone z dokładnością do 4 miejsc po przecinku,

* w poniższych wzorach matematycznych litery oznaczają:

  - PK: punkty MNiSW/MEiN, wcześniej zwane *punkty KBN*
  - k: liczba autorów/redaktorów dla rekordu z danej dyscypliny, którzy mają w powiązaniu rekordu
    z autorem wybraną daną dyscyplinę oraz zaznaczone pole *Afiliuje* na *tak*,
  - m: liczba wszystkich autorów rekordu.

Próg nr 1
~~~~~~~~~

Punkty PKd dla rekordu, dla danej dyscypliny:

.. math::

   PK_{d} = PK

Punkty PKdAut dla rekordu, dla autora z danej dyscypliny:

.. math::

   PKd_{Aut} = \frac{ PKd}{k}

Slot dla autora:

.. math::

   slot_{Aut} = \frac {1}{k}

Slot dla dyscypliny:

.. math::

   slot_{d} = 1

Slot dla dyscypliny nie będzie liczony jeżeli nie ma żadnych autorów w danej dyscyplinie, tzn
gdy żaden z autorów nie jest afiliowany na jednostki uczelni.

Próg nr 2
~~~~~~~~~

Punkty PKd dla rekordu, dla danej dyscypliny:

.. math::

   PK_{d} = PK * \sqrt  { \frac{k}{m} }

Zakładamy, że mnożnik z powyższego przykładu (pierwiastek kwadratowy z k/m) nie będzie mniejszy, jak 0.1. Jeżeli będzie mniejszy,
to zostanie użyta wartość 0.1, chyba, że wszyscy autorzy z danej dyscypliny nie będą mieli afiliacji, wówczas zostanie użyta
wartość 0.

Punkty PKdAut dla rekordu, dla autora z danej dyscypliny:

.. math::

   PKd_{Aut} = \frac{ PKd}{k}

Slot dla autora:

.. math::

   slot_{Aut} = \sqrt  { \frac{k}{m} } * \frac {1}{k}

Slot dla dyscypliny:

.. math::

   slot_{d} = \sqrt  { \frac{k}{m} }

Próg nr 3
~~~~~~~~~

Punkty PKd dla rekordu, dla danej dyscypliny:

.. math::

   PK_{d} = PK * \frac{k}{m}

Zakładamy, że mnożnik z powyższego przykładu (wynik dzielenia k/m) nie będzie mniejszy, jak 0.1. Jeżeli będzie mniejszy,
to zostanie użyta wartość 0.1, chyba, że wszyscy autorzy z danej dyscypliny nie będą mieli afiliacji, wówczas zostanie użyta
wartość 0.

Punkty PKdAut dla rekordu, dla autora z danej dyscypliny:

.. math::

   PKd_{Aut} = \frac{ PKd}{k}

Slot dla autora:

.. math::

   slot_{Aut} = { \frac{1}{m} }

Slot dla dyscypliny:

.. math::

   slot_{d} = { \frac{1}{m * k} }

Wydawnictwa ciągłe
------------------

#. Charakter formalny rekordu nie ma znaczenia

#. Dla zakresu lat 2017-2018, punkty MNiSW/MEiN muszą wynosić odpowoednio:

   * powyżej 30 dla progu 1. algorytmu
   * 20 lub 25 dla progu 2. algorytmu
   * poniżej 20 i powyżej zera dla progu 3. algorytmu

#. Dla zakresu lat 2019-2021, punkty MNiSW/MEiN muszą wynosić odpowiednio:

   * 200, 140, 100 dla progu 1. algorytmu
   * 70 lub 40 dla progu 2. algorytmu
   * mniejsze lub równe jak 20 ale powyżej zera dla progu 3. algorytmu

Wydawnictwa zwarte
------------------

#. Charakter formalny rekordu ma znaczenie, a konkretnie pole charakteru formalnego określające
   "Charakter dla slotów". To pole może przyjmować wartości: książka, rozdział, referat. W
   zależności od wartości pola "charakter dla slotów" rekord dopasowywany będzie do
   odpowiednich grup.

#. Pole "typ odpowiedzialności" dla osób powiązanych z danym rekordem ma znaczenie. Jeżeli
   wszystkie powiązane osoby będą miały typ "redaktor", taki rekord będzie traktowany jako redakcja,
   jeżeli "autor" - to autorstwo i tak dalej.

#. Charakter dla slotów = refereat:

   * punkty MNiSW/MEiN = 15 oraz powiązanie z zewnętrzną bazą danych - nazwa bazy danych
     dowolna, skrót nazwy bazy danych równy "WOS". Powiązanie z zewnętrzną baza danych
     można dodać dla każdego rekordu, korzystając z formularza na końcu strony edycji
     rekordu - próg 3. algorytmu,

   * punkty MNiSW/MEiN 200, 140, 100 - próg 1. algorytmu,

   * punkty MNiSW/MEiN 70, 40 - próg 2. algorytmu,

   *  punkty MNiSW/MEiN równe 20:

      - gdy wydawca na dany rok ma poziom równy 1: próg 2. algorytmu
      - gdy wydawca nieokreślony lub inny poziom: próg 3. algorytmu

   * punkty MNiSW/MEiN równe 50 i poziom wydawcy równe 2: próg 1. algorytmu

   * punkty MNiSW/MEiN równe 5: próg 3. algorytmu

#. Charakter dla slotów = książka lub rozdział:

   * poziom wydawcy równy 2 oraz:

     - autorstwo + książka + punkty MNiSW/MEiN = (200 lub 100), lub
     - redakcja + książka + punkty MNiSW/MEiN = (100 lub 50), lub
     - rozdział + punkty MNiSW/MEiN = (50 lub 25)

     ... da w rezultacie próg 1. algorytmu

   * poziom wydawcy równy 1 oraz:

     - autorstwo + książka + punkty MNiSW/MEiN = (80 lub 40 lub 100), lub
     - redakcja + książka + punkty MNiSW/MEiN = (20 lub 10), lub
     - rozdział + punkty MNiSW/MEiN = (20 lub 10)

     ... da w rezultacie próg 2. algorytmu

   * poziom wydawcy inny lub bez określenia wydawcy oraz:

     - książka + autorstwo + punkty MNiSW/MEiN = (20 lub 10), lub
     - książka + redakcja + punkty MNiSW/MEiN = (5 lub 2.5), lub
     - rozdział + punkty MNiSW/MEiN = (5 lub 2.5)

     ... da w rezultacie próg 3. algorytmu.

   * warunek "książka" lub "rozdział" dopasowywany jest z uwzględnieniem
     pola "charakter dla slotów" dla danego charakteru formalnego rekordu,

   * warunek "autorstwo" lub "redakcja" dopasowywany jest uwzględniając
     pole "typ odpowiedzialności" przy powiązaniu osoby z rekordem, a konkretnie
     jego pod-pole "typ ogólny". Jeżeli będzie tam wartość "autor" lub
     "redaktor", system postąpi odpowiednio do wartości pola. Jeżeli rekord
     będzie posiadał jednocześnie autorów oraz redaktorów lub też rekord
     nie będzie posiadał ani autorów, ani redaktorów, system wyświeli komunikat
     o braku możliwości obliczenia slotów.

Wydawnictwa HST
---------------

Dla dyscyplin będących w grupie HST (nauki humanistyczne, nauki społeczne, teologia):

* jeżeli publikacja zawiera wyłącznie takie dyscypliny, należy zwiększyć punktację PK
  w sposób przewidziany w ustawie (czyli zamiast 80 punktów PK wpisujemy od razu 120),

* jeżeli publikacja zawiera dyscypliny HST oraz dyscypliny "zwykłe", wpisujemy punktację bazową;
  system w takim przypadku zwiększy o 1.5x punktację bazową dla dyscyplin HST przy obliczeniach
  punktacji za slot.

W ten sposób może dochodzić do rozbieżności w raportach, gdy zbierana (sumowana) jest punktacja PK całego rekordu
nie zaś punktacja slotu.
