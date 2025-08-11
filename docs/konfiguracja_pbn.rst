=========================================================
Konfiguracja integracji z serwisami PBN - dla użytkownika
=========================================================

System BPP oferuje integrację z Polską Bibliografią Naukową (PBN), umożliwiając automatyczne
wysyłanie publikacji do PBN oraz pobieranie danych ze źródeł PBN. Niniejsza dokumentacja
przedstawia sposób konfiguracji tej integracji przez panel administracyjny.

Wymagania wstępne
=================

Przed rozpoczęciem konfiguracji należy:

1. Posiadać konto w systemie PBN z uprawnieniami Importer Publikacji.
2. Założyć aplikację w systemie PBN - z konta z poziomem uprawnień Menedżer Aplikacji - i otrzymać dane dostępowe:

   - **Identyfikator aplikacji** (App ID)
   - **Token aplikacji** (App Token)

3. Mieć uprawnienia administratora w systemie BPP aby skonfigurować dostęp do PBN w systemie BPP

Dostęp do konfiguracji
======================

Konfigurację integracji z PBN wykonuje się w module Redagowania:

1. Zaloguj się do panelu administracyjnego BPP
2. Przejdź do sekcji **BPP**
3. Wybierz z górnej belki menu **Struktura** a następnie **Uczelnia (Instytut)**
4. Kliknij na nazwę swojej instytucji, aby edytować jej ustawienia
5. Przewiń do sekcji **Konfiguracja PBN**

Konfiguracja parametrów PBN
===========================

W formularzu edycji uczelni/instytucji znajdziesz następujące pola związane z integracją PBN:

Podstawowe ustawienia API
-------------------------

**Adres API w PBN**
    - **Pole:** ``pbn_api_root``
    - **Domyślna wartość:** ``https://pbn-micro-alpha.opi.org.pl``
    - **Opis:** Adres serwera testowego API PBN. W wersji produkcyjnej należy ustawić ``https://pbn.nauka.gov.pl/``
    - **Format:** Pełny adres URL (np. ``https://pbn-micro-alpha.opi.org.pl``)

**Nazwa aplikacji w PBN**
    - **Pole:** ``pbn_app_name``
    - **Wymagane:** Tak
    - **Opis:** Identyfikator aplikacji otrzymany przy rejestracji w PBN
    - **Maksymalna długość:** 128 znaków

**Token aplikacji w PBN**
    - **Pole:** ``pbn_app_token``
    - **Wymagane:** Tak
    - **Opis:** Token bezpieczeństwa aplikacji otrzymany z PBN
    - **Maksymalna długość:** 128 znaków
    - **Uwaga:** Pole to zawiera dane poufne

**Odpowiednik w PBN**
    - **Pole:** ``pbn_uid``
    - **Opis:** Instytucja w bazie PBN odpowiadająca Twojej uczelni
    - **Uwaga:** Pole to zostanie automatycznie wypełnione po zaimportowaniu danych instytucji z PBN

Opcje eksportu danych
--------------------

**Kasuj oświadczenia rekordu przed wysłaniem do PBN**
    - **Pole:** ``pbn_api_kasuj_przed_wysylka``
    - **Domyślnie:** Nie zaznaczone
    - **Opis:** Gdy zaznaczone, system usunie wszystkie istniejące oświadczenia publikacji w PBN przed przesłaniem nowych danych

**Nie wysyłaj do PBN prac z punktami MNISW = 0**
    - **Pole:** ``pbn_api_nie_wysylaj_prac_bez_pk``
    - **Domyślnie:** Nie zaznaczone
    - **Opis:** Blokuje wysyłanie do PBN publikacji bez punktów MNiSW

**Wysyłaj zawsze PBN UID uczelni jako afiliację**
    - **Pole:** ``pbn_api_afiliacja_zawsze_na_uczelnie``
    - **Domyślnie:** Zaznaczone
    - **Opis:** Gdy zaznaczone, wszystkie publikacje będą afiliowane do uczelni, a nie do konkretnych jednostek organizacyjnych;
      zachowanie to jest obecnie domyślne - pole używane było w czasach, gdy publikacja mogła być afiliowana na konkretną
      jednostkę uczelni/instytucji w PBN (na Klinikę, Dział, Katedrę itp...).

**Użytkownik BPP dla PBN API**
    - **Pole:** ``pbn_api_user``
    - **Opis:** Użytkownik systemu BPP odpowiedzialny za automatyczne operacje z PBN wykonywane przez procesy systemowe
    - **Uwaga:** Ten użytkownik musi wykonać autoryzację w PBN, aby umożliwić automatyczne operacje (w tle)

Zapisywanie konfiguracji
========================

Po wypełnieniu wszystkich wymaganych pól:

1. Sprawdź poprawność wprowadzonych danych
2. Kliknij **Zapisz** u dołu formularza
3. System wyświetli komunikat potwierdzający zapisanie zmian

Autoryzacja w systemie PBN
===========================

Po skonfigurowaniu podstawowych parametrów należy wykonać autoryzację:

1. Przejdź do głównej strony systemu BPP
2. W menu wybierz **Operacje** → **Autoryzuj w PBN**
3. System przekieruje Cię do strony logowania PBN
4. Zaloguj się używając swoich danych dostępowych PBN
5. Potwierdź udzielenie uprawnień aplikacji BPP
6. Zostaniesz automatycznie przekierowany z powrotem do BPP

Po pomyślnej autoryzacji system będzie mógł komunikować się z PBN w Twoim imieniu.

Weryfikacja konfiguracji
========================

Aby sprawdzić czy konfiguracja działa prawidłowo:

1. W panelu administracyjnym przejdź do **PBN API** → **Instytucje**
2. Jeśli lista nie jest pusta, oznacza to, że komunikacja z PBN działa
3. Sprawdź czy w polu **Odpowiednik w PBN** w ustawieniach uczelni została automatycznie wybrana odpowiednia instytucja

Import danych słownikowych
==========================

Po skonfigurowaniu integracji zaleca się import podstawowych danych słownikowych z PBN:

1. Przejdź do **Operacje** → **Import danych PBN**
2. Wybierz **Importuj dyscypliny i punkty źródeł**
3. System automatycznie pobierze aktualne słowniki z PBN

Typowe problemy i rozwiązania
=============================

**Problem:** Komunikat "Brak nazwy aplikacji dla API PBN"
    - **Rozwiązanie:** Wypełnij pole "Nazwa aplikacji w PBN" w ustawieniach uczelni

**Problem:** Komunikat "Brak tokena aplikacji dla API PBN"
    - **Rozwiązanie:** Wypełnij pole "Token aplikacji w PBN" w ustawieniach uczelni

**Problem:** Komunikat "Token aplikacji PBN nieprawidłowy"
    - **Rozwiązanie:** Sprawdź poprawność skopiowanego tokena w PBN, upewnij się że nie ma dodatkowych spacji

**Problem:** Komunikat "Najpierw wykonaj autoryzację w PBN API"
    - **Rozwiązanie:** Wykonaj proces autoryzacji opisany w sekcji "Autoryzacja w systemie PBN"

**Problem:** Brak możliwości wysyłania publikacji do PBN
    - **Rozwiązanie:** Upewnij się, że pole "Odpowiednik w PBN" jest wypełnione i że wykonano autoryzację użytkownika

Operacje na publikacjach
=========================

Po skonfigurowaniu integracji możesz:

**Wysyłać pojedyncze publikacje do PBN:**
    1. Otwórz publikację w panelu administracyjnym
    2. Użyj przycisku **Wyślij do PBN** (jeśli dostępny)
    3. System automatycznie wyśle publikację i pobierze z powrotem dane wraz z PBN UID

**Importować dane publikacji z PBN:**
    - System może automatycznie pobierać informacje o publikacjach już istniejących w PBN
    - Możliwe jest też pobieranie abstraktów i innych metadanych

**Zarządzać oświadczeniami dyscyplin:**
    - System automatycznie wysyła oświadczenia dotyczące dyscyplin naukowych autorów
    - Możliwa jest również wysyłka samych oświadczeń bez całej publikacji

Bezpieczeństwo danych
=====================

**Ważne informacje dotyczące bezpieczeństwa:**

- Token aplikacji PBN jest informacją poufną - nie udostępniaj go osobom trzecim
- System automatycznie szyfruje i zabezpiecza dane dostępowe
- Wszystkie operacje z PBN są logowane w systemie
- W przypadku podejrzenia naruszenia bezpieczeństwa natychmiast zmień token w systemie PBN

**Zalecenia:**

- Regularnie sprawdzaj logi operacji PBN w panelu administracyjnym
- Monitoruj powiadomienia systemowe dotyczące integracji z PBN
- W razie problemów skontaktuj się z administratorem systemu

Wsparcie techniczne
===================

W przypadku problemów z konfiguracją integracji PBN:

1. Skonsultuj się z administratorem swojego systemu BPP
2. W przypadku problemów po stronie PBN skontaktuj się z pomocą techniczną PBN (Helpdesk)
3. Dla błędów systemowych BPP zgłoś problem do zespołu rozwoju systemu

Dodatkowe zasoby
================

- Dokumentacja użytkownika PBN dostępna na stronie: https://pbn.nauka.gov.pl
- Pomoc techniczna PBN: kontakt dostępny przez stronę PBN
