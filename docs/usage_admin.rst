
=============================
Instrukcja dla administratora
=============================

Konfiguracja sposobu prezentacji danych dla użytkowników niezalogowanych
------------------------------------------------------------------------

Ustawienia globalne - rekord uczelni
====================================

* po zainstalowaniu systemu, gdy baza danych jest pusta, potrzebujesz
  utworzyć obiekt "Uczelnia" za pomocą funkcji Redagowanie➡Struktura➡Uczelnia,

* za pomocą tejże opcji możesz ustawić logo uczelni oraz ikonę favicon (czyli
  zmniejszoną ikonę strony wyświetlającą się w pasku adresu przeglądarki oraz
  na urządzeniach przenośnych),

* za pomocą tej opcji ustawić możesz domyślą wartość pola "afiliuje" dla rekordów
  wiążących rekordy prac (wydawnictwo ciągłe, zwarte i patent) z autorami

Kolejnośc i zakres wyświetlanych wydziałów
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* aby ustalić kolejność i zakres wyświetlanych wydziałów uczelni, potrzebujesz
  przejrzeć obiekty "Wydział" znajdujące się poniżej formularza dla rekordu
  Uczelni. Skorzystaj z funkcji Redagowanie➡Struktura➡Uczelnie. Wydziały mogą
  być wyświetlane lub nie, możesz za pomocą tej funkcji ustawić je w określonej
  kolejności.

  .. note::

    wydziały w module interfejsu uzytkownika niezalogowanego nie są wyświelane
    alfabetycznie a zgodnie z ustaloną kolejnością.

* aby obejrzeć szczegóły wydziału skorzystaj z opcji
  Redagowanie➡Struktura➡Wydział

* pozostałe części serwisu dla użytkowników niezalogowanych wyświetlają
  dane w formacie kolumnowym, posortowane alfabetycznie.

Ukrywanie autorów na stronach jednostek
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aby ukryć informacje na temat autora na stronie jednostki, należy skorzystać
z opcji "Pokazuj na stronach jednostek". W przypadku doktorantów lub autorów
którzy nie są pracownikami danej jednostki należy je odznaczyć.

Po wybraniu dowolnego autora w module Redagowanie➡Wprowadzanie danych➡Autorzy
odznacz to pole i zapisz rekord, aby nie wyświetlać autora na stronie jednostki.

.. image:: images/admin/pokazuj_na_stronach_jednostek.png

Ukrywanie lub wyświetlanie raportów na stronie głównej
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Celem konfiguracji sposobu wyświetlania strony głównej jak i innych elementów
serwisu, skorzystaj z opcji Redagowanie➡Struktura➡Uczelnie, a następnie w sekcji
"Strona wizualna" wyedytuj ustawienia dotyczące pokazywania różnych opcji
(rankingi, raporty, opcje rekordu). Niektóre ustawienia umożliwiają wyświetlanie
lub chowanie danego elementu, niektóre umożliwiają wyświetlenie danego elementu
tylko dla użytkowników zalogowanych.

.. image:: images/admin/uczelnia_strona_wizualna.png


Ukrywanie lub wyświetlanie formularzy wyszukiwania
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gdy stworzysz formularz wyszukiwania w opcji Wyszukaj, możesz go zapisać. W ten
sposób formularz będzie dostępny w późniejszym czasie. Podczas zapisywania formularza
(opcja ta dostępna jest jedynie dla zalogowanych użytkowników) masz możliwość
określenia, czy chcesz, aby ten formularz widoczny był również dla innych
osób.

Jeżeli chcesz później schować lub pokazać takie formularze, skorzystaj z opcji
Redagowanie➡Administracja➡Formularze wyszukiwania. Kliknij nazwę takiego
formularza, następnie zaznacz lub odznacz opcję "Publiczny" i zapisz rekord




