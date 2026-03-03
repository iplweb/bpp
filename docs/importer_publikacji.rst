Importer publikacji
-------------------

Wprowadzenie
============

Moduł **Importer publikacji** umożliwia import rekordów publikacji do systemu BPP
na podstawie danych pobranych z zewnętrznych źródeł. Import odbywa się w formie
wielokrokowego kreatora (wizarda), który prowadzi użytkownika przez kolejne etapy:
od pobrania danych, przez dopasowanie typu publikacji, źródła i autorów, aż po
utworzenie rekordu w bazie danych.

Moduł dostępny jest z menu Redagowanie, w pozycji "Import publikacji".

Wymagane uprawnienia
====================

Aby korzystać z importera, użytkownik musi spełniać jeden z warunków:

* posiadać status **pracownika** (``is_staff = True``), lub
* należeć do grupy **"wprowadzanie danych"**.

Dostawcy danych (providerzy)
============================

System obsługuje import z wielu źródeł danych. Każde źródło nazywane jest
**dostawcą** (providerem). Obecnie dostępni są:

CrossRef
~~~~~~~~

Dostawca **CrossRef** umożliwia import publikacji na podstawie identyfikatora DOI.

* **Dane wejściowe:** DOI publikacji (np. ``10.1234/example.2024``)
* **Sposób działania:** System pobiera metadane publikacji z bazy CrossRef API.
  Wymagane jest, aby DOI był wcześniej zbuforowany w tabeli ``CrossrefAPICache``
  (np. przez wcześniejsze wyszukiwanie w komparatorze).
* **Automatycznie rozpoznawane dane:**

  - tytuł, rok, DOI, tom, numer, strony
  - autorzy (imię, nazwisko, ORCID)
  - nazwa czasopisma lub wydawcy
  - ISSN, E-ISSN, ISBN, E-ISBN
  - typ publikacji (np. ``journal-article``, ``book``, ``book-chapter``)
  - język, abstrakt, słowa kluczowe, URL, licencja

BibTeX
~~~~~~

Dostawca **BibTeX** umożliwia import publikacji na podstawie wklejonego kodu BibTeX.

* **Dane wejściowe:** Kod BibTeX wklejony w pole tekstowe, np.:

  .. code-block:: bibtex

     @article{klucz2024,
       title = {Tytuł publikacji},
       author = {Kowalski, Jan and Nowak, Anna},
       year = {2024},
       journal = {Nazwa Czasopisma},
       doi = {10.1234/example}
     }

* **Sposób działania:** System parsuje kod BibTeX i wyodrębnia metadane.
  Obsługiwane są formaty autorów ``Nazwisko, Imię`` oraz ``Imię Nazwisko``.
  Wiele wpisów w jednym bloku BibTeX jest dozwolone, ale importowany jest
  **tylko pierwszy wpis**.
* **Mapowanie typów BibTeX na typy CrossRef:**

  - ``article`` → ``journal-article``
  - ``book`` → ``book``
  - ``inbook``, ``incollection`` → ``book-chapter``
  - ``inproceedings``, ``conference`` → ``proceedings-article``
  - ``phdthesis``, ``mastersthesis`` → ``dissertation``
  - ``proceedings`` → ``proceedings``

Kroki importu
=============

Krok 1: Pobranie danych
~~~~~~~~~~~~~~~~~~~~~~~~

Po wybraniu dostawcy i wpisaniu identyfikatora (DOI) lub wklejeniu kodu BibTeX
użytkownik klika przycisk "Pobierz". System:

1. Waliduje dane wejściowe zgodnie z regułami wybranego dostawcy.
2. Pobiera i normalizuje metadane publikacji.
3. Tworzy **sesję importu** z pobranymi danymi.
4. Automatycznie dopasowuje język publikacji.
5. Automatycznie dopasowuje typ publikacji (charakter formalny) na podstawie
   mapowania CrossRef (patrz: konfiguracja Crossref Mapper w instrukcji
   administratora).
6. Automatycznie dopasowuje autorów do istniejących rekordów w BPP.
7. Uzupełnia brakujące dyscypliny z danych zgłoszeń publikacji (jeśli istnieje
   pasujące zgłoszenie).

Na stronie głównej importera widoczna jest także lista ostatnich sesji importu
danego użytkownika, umożliwiając kontynuację przerwanych importów.

Krok 2: Weryfikacja typu publikacji
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

W tym kroku użytkownik weryfikuje i ewentualnie koryguje:

* **Charakter formalny** -- typ publikacji w systemie BPP (np. artykuł
  w czasopiśmie, książka, rozdział). Jeśli dostępne jest mapowanie CrossRef,
  pole jest wstępnie wypełnione.
* **Typ KBN** -- klasyfikacja MNiSW.
* **Język** -- język publikacji.
* **Typ wydawnictwa** -- czy jest to wydawnictwo zwarte (książka/rozdział)
  czy ciągłe (artykuł w czasopiśmie).

System automatycznie wykrywa **duplikaty** -- szuka istniejących rekordów
po DOI (z normalizacją) oraz po tytule (dokładne porównanie). Jeśli znaleziono
potencjalne duplikaty, wyświetlane jest ostrzeżenie. Użytkownik może kontynuować
import mimo wykrycia duplikatów.

Krok 3: Dopasowanie źródła
~~~~~~~~~~~~~~~~~~~~~~~~~~~

W zależności od typu wydawnictwa:

**Wydawnictwo ciągłe** (artykuł w czasopiśmie):

* Wymagane jest wskazanie **źródła** (czasopisma) z bazy BPP.
* System próbuje automatycznie dopasować źródło na podstawie nazwy
  czasopisma z danych dostawcy.

**Wydawnictwo zwarte** (książka, rozdział):

* Wymagane jest wskazanie **wydawcy** z bazy BPP lub wpisanie opisu wydawcy.
* System próbuje automatycznie dopasować wydawcę na podstawie nazwy
  z danych dostawcy.

Krok 4: Dopasowanie autorów
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Najważniejszy krok importu. System wyświetla listę autorów z danych dostawcy
wraz z informacją o statusie dopasowania:

* **Dokładne** (zielony) -- automatyczne dokładne dopasowanie do autora w BPP.
* **Luźne** (żółty) -- automatyczne częściowe dopasowanie (np. skrócone imię).
* **Ręczne** (niebieski) -- dopasowanie wykonane ręcznie przez użytkownika.
* **Niedopasowany** (czerwony) -- brak dopasowania; wymaga interwencji.

Dla każdego autora wyświetlane są:

* Imię i nazwisko z danych dostawcy
* ORCID (jeśli dostępny)
* Dopasowany autor, jednostka i dyscyplina w BPP
* Źródło dyscypliny (skąd pochodzi automatycznie wypełniona wartość)

**Edycja dopasowania autora**

Kliknięcie ikony ołówka przy autorze rozwija formularz edycji z polami:

* **Autor w BPP** -- wyszukiwanie autora (autouzupełnianie).
* **Jednostka** -- wyszukiwanie jednostki (autouzupełnianie).
* **Dyscyplina** -- lista rozwijana z dyscyplinami przypisanymi autorowi
  na dany rok.

Po wybraniu autora system automatycznie podpowiada jednostkę i dyscyplinę
na podstawie aktualnych danych w BPP.

**Źródło dyscypliny**

Przy automatycznie wypełnionej dyscyplinie system wyświetla informację
o jej pochodzeniu:

* *(Jedyna dyscyplina autora)* -- autor ma dokładnie jedną dyscyplinę
  na rok publikacji w tabeli ``Autor_Dyscyplina``.
* *(Z aplikacji zgłoszeń publikacji)* -- dyscyplina pochodzi z pasującego
  zgłoszenia publikacji (moduł "Zgłoś publikację").
* *(Wybór użytkownika)* -- dyscyplina została wybrana ręcznie.

**Tworzenie autorów dla niedopasowanych**

Jeśli istnieją niedopasowani autorzy, dostępny jest przycisk
"Utwórz autorów dla niedopasowanych". System:

1. Sprawdza, czy autor ma ORCID -- jeśli tak i istnieje autor z takim ORCID
   w BPP, dopasowuje go.
2. W przeciwnym razie tworzy nowy rekord autora w BPP.
3. Przypisuje wszystkich nowych/dopasowanych autorów do **obcej jednostki**
   skonfigurowanej w ustawieniach uczelni.

.. note::
   Operacja wymaga skonfigurowanej "obcej jednostki" w rekordzie uczelni.
   W przypadku jej braku wyświetlany jest komunikat o błędzie.

**Ustawianie ORCID**

Jeśli dostawca dostarczył identyfikator ORCID dla autora, a dopasowany autor
w BPP nie ma jeszcze ORCID, system umożliwia jego ustawienie -- pojedynczo
(przycisk przy autorze) lub grupowo (przycisk "Ustaw ORCIDy").

Warunki ustawienia ORCID:

* Autor importowany ma ORCID od dostawcy.
* Jest dopasowany do autora w BPP.
* Autor w BPP nie ma przypisanego ORCID.
* Ten sam autor BPP nie jest dopasowany wielokrotnie w danej sesji.

Krok 5: Przegląd końcowy
~~~~~~~~~~~~~~~~~~~~~~~~~

Podsumowanie wszystkich danych przed utworzeniem rekordu:

* Metadane publikacji (tytuł, rok, DOI, tom, numer, strony itp.)
* Dopasowane źródło lub wydawca
* Lista autorów z jednostkami i dyscyplinami

Użytkownik potwierdza dane i przechodzi do utworzenia rekordu.

Krok 6: Utworzenie rekordu
~~~~~~~~~~~~~~~~~~~~~~~~~~

System tworzy rekord publikacji w BPP:

* **Wydawnictwo ciągłe** -- z przypisanym źródłem (czasopismem).
* **Wydawnictwo zwarte** -- z przypisanym wydawcą i danymi ISBN.

Do rekordu dodawani są wszyscy dopasowani autorzy z odpowiednimi jednostkami,
dyscyplinami i typem odpowiedzialności "autor". Autorzy przypisani do obcej
jednostki oznaczani są jako nieafiliowani.

Automatycznie uzupełniana jest punktacja na podstawie danych źródła
dla danego roku (jeśli dostępne).

Rekord otrzymuje adnotację ``Dodano przez importer publikacji (nazwa dostawcy)``.

Po utworzeniu wyświetlana jest strona potwierdzenia z linkiem do edycji
rekordu w module redagowania.

Anulowanie importu
==================

Na każdym etapie importu dostępny jest przycisk "Anuluj", który po potwierdzeniu
oznacza sesję jako anulowaną. Anulowane sesje nie są wyświetlane na liście
ostatnich importów.

Kontynuacja przerwanego importu
================================

Jeśli użytkownik przerwie import (np. zamknie przeglądarkę), może go
kontynuować z listy ostatnich sesji na stronie głównej importera.
Sesja zostanie wznowiona od ostatniego zapisanego kroku.
