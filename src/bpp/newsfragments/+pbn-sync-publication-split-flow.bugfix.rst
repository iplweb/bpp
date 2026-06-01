Refaktoryzacja wysyłki publikacji do PBN (``sync_publication``): publikacja
jest zawsze wysyłana przez endpoint repozytoryjny
``POST /api/v1/repositorium/publications`` (bez oświadczeń w body), a
dyscypliny/oświadczenia synchronizowane są w osobnym kroku przez
``/api/v2/institution-profile/statements`` dopiero po potwierdzeniu
wysyłki publikacji. Dzięki temu nieudana wysyłka publikacji (np. HTTP
423 Locked albo inna przejściowa awaria PBN) nie kasuje już istniejących
oświadczeń w profilu instytucji — wcześniej kasowanie działo się przed
POST i tracono dane przy każdym niepowodzeniu.

Algorytm synchronizacji oświadczeń: GET aktualnego stanu PBN, porównanie
z intencją BPP (``WydawnictwoPBNAdapter.pbn_get_json_statements()``)
przez klucz ``(personId, disciplineId)``, selektywne DELETE (per-osoba
przez ``delete_publication_statement(personId, role)``) brakujących w
BPP + POST dodatkowych. Tryb kasowania sterowany nową flagą
``Uczelnia.pbn_kasuj_dyscypliny_selektywnie`` (domyślnie ``True``;
``False`` używa ``delete_all`` + POST batch).

Nowy wyjątek ``StatementsResendFailedException`` (w
``pbn_api.exceptions``) jest podnoszony gdy retry x3 z exponential
backoff (2s/4s/8s) na GET/DELETE/POST /v2/statements się wyczerpie.
Klasyfikowany w ``pbn_export_queue`` jako ``RETRY_LATER`` — kolejka
ponowi wysyłkę za kilka minut.

Usunięto pole ``Uczelnia.pbn_api_kasuj_przed_wysylka`` (obsolete —
stary pre-upload DELETE zastąpiony nowym algorytmem diff po wysyłce).
Flaga ``Uczelnia.pbn_wysylaj_bez_oswiadczen`` pozostaje z dotychczasową
semantyką (odmawia wysyłki publikacji bez oświadczeń).
