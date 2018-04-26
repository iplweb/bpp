
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

Kolejnośc i zakres wyświetlanych wydziałów
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* aby ustalić kolejność i zakres wyświetlanych wydziałów uczelni, potrzebujesz
  przejrzeć obiekty "Wydział" znajdujące się poniżej formularza dla rekordu
  Uczelni. Skorzystaj z funkcji Redagowanie➡Struktura➡Uczelnia. Wydziały mogą
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
