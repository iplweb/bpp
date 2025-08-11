API systemu BPP
===============

System BPP oferuje API tylko-do-odczytu dla obiektów bazodanowych zawierających istotne informacje takie jak: wydawnictwa ciągłe,
wydawnictwa zwarte, patenty, autorzy, jednostki i inne.

API dostępne jest dla użytkowników niezalogowanych.

API dostępne jest w formie "przyjaznej developerom", to znaczy, ze po wejściu w nie możemy
korzystając ze zwykłej przeglądarki WWW zapoznać się z udostępnianymi przez API możliwościami
a następnie płynnie przełączyć się w tryb JSON, aby pobierać dane czytelne nieco mniej dla
człowieka, a bardziej dla komputera.

.. image:: images/api/api_1.png

API dla raportów slotu - uczelnia
---------------------------------

BPP umożliwia tworzenie i pobieranie raportu slotów - uczelnia za pomocą API. Taka funkcja
wymaga jednak zalogowania jako użytkownik będący członkiem grupy "generowanie raportów".

#. Aby utworzyć raport slotów - uczelnia przez API, należy wejść w przeglądarce na stronę:

    ``/api/v1/raport_slotow_uczelnia/``

   Przeglądarka poprosi nas o zalogowanie się za pomoca loginu i hasła. Na samym dole
   strony zobaczymy formularz, który umożliwia utworzenie raportu przez API:

   .. image:: images/api/api_2.png

#. Aby utworzyć raport slotów - uczelnia przez API za pomocą polecenia ``curl(1)``,
   możemy w systemowej powłoce napisać:

    .. code-block:: shell

      curl -X POST -u login:haslo https://adres.serwera/api/v1/raport_slotow_uczelnia/

#. Zwrotnie otrzymamy kod JSON z danymi raportu:

    .. code-block:: json

        {
            "id": "https://adres.serwera/api/v1/raport_slotow_uczelnia/c9d4b477-4cc5-4922-a499-fce43fd37be1/",
            "created_on": "2023-02-21T23:25:36.864007+01:00",
            "last_updated_on": "2023-02-21T23:25:36.864018+01:00",
            "started_on": null,
            "finished_on": null,
            "finished_successfully": false,
            "od_roku": 2023,
            "do_roku": 2023,
            "akcja": "slot",
            "slot": "1.0000",
            "minimalny_pk": "0.00",
            "dziel_na_jednostki_i_wydzialy": true,
            "pokazuj_zerowych": false
        }

   W powyższym przykładzie dana nas interesująca to numer ID raportu, czyli w tym przykładzie
   będzie to ``c9d4b477-4cc5-4922-a499-fce43fd37be1``.

#. Dane raportu zwracane są asynchronicznie. Oznacza to, że dopóki raport nie otrzyma wartości
   w polach ``finished_successfully`` oraz ``finished_on``, oznacza to, że nie jest jeszcze
   utworzony. Należy cyklicznie odświeżać dane raportu np co 5-10 sekund, aż pojawi się
   wartość w tych polach:

   ``curl -u login:haslo https://adres.serwera/api/v1/raport_slotow_uczelnia/c9d4b477-4cc5-4922-a499-fce43fd37be1/``

    .. warning::

     Utworzenie zbyt dużej ilości raportów na raz skutecznie zapcha kolejkę przetwarzania
     asynchronicznego i utrudni kolejnym użytkownikom korzystanie z serwera.


#. Następnie możliwe będzie pobranie pojedynczych wierszy tego raportu. Przez stronę WWW
   potrzebne będzie doklikanie się do strony:

   ``/api/v1/raport_slotow_uczelnia_wiersz/?parent=c9d4b477-4cc5-4922-a499-fce43fd37be1``

   Jak łatwo zauważyć, będzie tam lista wierszy raportu, zawierająca informacje o autorze, jednostce,
   dyscyplinie, zebranym slocie i sumie PkD dla autora.

   .. image:: images/api/api_3.png

   Zapytanie o te wszystkie dane z pomocą polecenia ``curl(1)`` zwróci nam tekst w
   formacie JSON:

   ``curl -u login:haslo "https://adres.serwera/api/v1/raport_slotow_uczelnia_wiersz/?parent=c9d4b477-4cc5-4922-a499-fce43fd37be1" | python -m json.tool``

   **UWAGA**: tutaj na końcu nie dajemy slash.

#. dane w formacie JSON są stronnicowane, po kilka wpisów na stronę, aby nie przeciążać serwera. Warto zwrócić
   uwagę na parametry ``count``, ``next`` i ``previous``, znajdujące się w słowniku.

Pobieranie danych z systemu BPP przez JSON HTTP REST API
--------------------------------------------------------

System BPP udostępnia szereg endpoint'ów REST API dla pobierania danych o publikacjach i powiązanych obiektach.
API jest tylko-do-odczytu i nie wymaga autoryzacji dla dostępu do danych publikacji.

Główne endpoint'y API
~~~~~~~~~~~~~~~~~~~~

System udostępnia następujące główne endpoint'y dla pobierania danych publikacji:

* ``/api/v1/wydawnictwo_ciagle/`` - wydawnictwa ciągłe (artykuły w czasopismach)
* ``/api/v1/wydawnictwo_zwarte/`` - wydawnictwa zwarte (książki, rozdziały)
* ``/api/v1/patent/`` - patenty
* ``/api/v1/praca_doktorska/`` - prace doktorskie
* ``/api/v1/praca_habilitacyjna/`` - prace habilitacyjne

Dane pomocnicze dostępne są przez następujące endpoint'y:

* ``/api/v1/autor/`` - autorzy
* ``/api/v1/jednostka/`` - jednostki organizacyjne
* ``/api/v1/uczelnia/`` - uczelnie
* ``/api/v1/wydawca/`` - wydawcy
* ``/api/v1/zrodlo/`` - źródła publikacji
* ``/api/v1/charakter_formalny/`` - charaktery formalne

Przykłady użycia CURL
~~~~~~~~~~~~~~~~~~~~

#. **Pobranie listy wydawnictw ciągłych:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/wydawnictwo_ciagle/" | python -m json.tool

   To polecenie zwróci listę wydawnictw ciągłych w formacie JSON z paginacją.

#. **Pobranie konkretnego wydawnictwa ciągłego:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/wydawnictwo_ciagle/123/" | python -m json.tool

   Gdzie ``123`` to ID konkretnego wydawnictwa.

#. **Filtrowanie wydawnictw po roku:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/wydawnictwo_ciagle/?rok__gte=2020&rok__lte=2023" | python -m json.tool

   To polecenie zwróci wydawnictwa z lat 2020-2023.

#. **Pobranie wydawnictw zmienionych w określonym okresie:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/wydawnictwo_ciagle/?ostatnio_zmieniony__gte=2023-01-01T00:00:00Z" | python -m json.tool

   To polecenie zwróci wydawnictwa zmienione od 1 stycznia 2023 roku.

#. **Pobranie listy autorów:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/autor/" | python -m json.tool

#. **Pobranie konkretnego autora:**

   .. code-block:: shell

      curl "https://adres.serwera/api/v1/autor/456/" | python -m json.tool

   Gdzie ``456`` to ID konkretnego autora.

Przykłady użycia w Postman
~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
   Postman to darmowe narzędzie do testowania API. Można je pobrać ze strony https://www.postman.com/downloads/

#. **Konfiguracja podstawowa:**

   * Method: GET
   * URL: ``https://adres.serwera/api/v1/wydawnictwo_ciagle/``
   * Headers: ``Accept: application/json``

#. **Pobieranie z filtrowaniem po roku:**

   * Method: GET
   * URL: ``https://adres.serwera/api/v1/wydawnictwo_ciagle/``
   * Params:
     * ``rok__gte``: ``2020``
     * ``rok__lte``: ``2023``

#. **Pobieranie z paginacją:**

   * Method: GET
   * URL: ``https://adres.serwera/api/v1/wydawnictwo_ciagle/``
   * Params:
     * ``page``: ``2``
     * ``page_size``: ``50``

#. **Pobieranie konkretnego rekordu:**

   * Method: GET
   * URL: ``https://adres.serwera/api/v1/wydawnictwo_ciagle/123/``

Format odpowiedzi
~~~~~~~~~~~~~~~~

API zwraca dane w formacie JSON. Przykład odpowiedzi dla listy wydawnictw:

.. code-block:: json

    {
        "count": 1500,
        "next": "https://adres.serwera/api/v1/wydawnictwo_ciagle/?page=2",
        "previous": null,
        "results": [
            {
                "id": 123,
                "tytul": "Przykładowy tytuł artykułu",
                "rok": 2023,
                "charakter_formalny": {
                    "nazwa": "Artykuł w czasopiśmie"
                },
                "autorzy_set": [
                    {
                        "autor": {
                            "imiona": "Jan",
                            "nazwisko": "Kowalski"
                        }
                    }
                ],
                "ostatnio_zmieniony": "2023-12-01T10:30:00Z"
            }
        ]
    }

Parametry filtrowania
~~~~~~~~~~~~~~~~~~~

Większość endpoint'ów obsługuje następujące parametry filtrowania:

* ``rok`` - filtrowanie po roku publikacji
* ``rok__gte`` - publikacje od podanego roku (włącznie)
* ``rok__lte`` - publikacje do podanego roku (włącznie)
* ``ostatnio_zmieniony`` - filtrowanie po dacie ostatniej modyfikacji
* ``ostatnio_zmieniony__gte`` - rekordy zmienione od podanej daty
* ``charakter_formalny`` - filtrowanie po charakterze formalnym publikacji

Paginacja
~~~~~~~~

Wszystkie listy są paginowane. Odpowiedzi zawierają:

* ``count`` - łączna liczba rekordów
* ``next`` - URL do następnej strony (jeśli istnieje)
* ``previous`` - URL do poprzedniej strony (jeśli istnieje)
* ``results`` - aktualne wyniki

Domyślnie zwracane jest 20 rekordów na stronę. Można to zmienić parametrem ``page_size``.
