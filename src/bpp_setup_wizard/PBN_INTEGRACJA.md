# Integracja z PBN (Polska Bibliografia Naukowa)

## Wprowadzenie

System BPP umożliwia pełną integrację z Polską Bibliografią Naukową (PBN). Aby korzystać z tej funkcjonalności, należy zarejestrować aplikację w systemie PBN i uzyskać dane dostępowe.

## Kroki rejestracji aplikacji w PBN

### 1. Przygotowanie

Przed rozpoczęciem procesu rejestracji należy:
- Posiadać konto w systemie PBN z odpowiednimi uprawnieniami administratora instytucji
- Przygotować nazwę dla aplikacji (np. "BPP - [Nazwa Uczelni]")
- Zdecydować czy korzystać ze środowiska testowego czy produkcyjnego

### 2. Środowiska PBN

#### Środowisko testowe
- **URL:** https://pbn-micro-alpha.opi.org.pl
- **Przeznaczenie:** Testy integracji, nauka obsługi API, weryfikacja poprawności danych
- **Zalety:** Bezpieczne testowanie bez wpływu na dane produkcyjne
- **Uwaga:** Dane w środowisku testowym są okresowo czyszczone

#### Środowisko produkcyjne
- **URL:** https://pbn.nauka.gov.pl
- **Przeznaczenie:** Rzeczywista praca z danymi publikacji
- **Wymaga:** Szczególnej ostrożności przy konfiguracji i testowaniu

### 3. Proces rejestracji aplikacji

Szczegółowa instrukcja rejestracji dostępna jest w oficjalnej dokumentacji PBN:
https://pbn.nauka.gov.pl/centrum-pomocy/baza-wiedzy/uzyskanie-integracji-z-api-pbn/

Podstawowe kroki:
1. Zaloguj się do systemu PBN jako administrator instytucji
2. Przejdź do sekcji zarządzania integracjami API
3. Zarejestruj nową aplikację podając:
   - Nazwę aplikacji
   - Opis zastosowania
   - Adresy URL callback (jeśli wymagane)
4. Po zatwierdzeniu otrzymasz:
   - **Nazwa aplikacji** - identyfikator aplikacji w systemie PBN
   - **Token aplikacji** - klucz autoryzacyjny do API

### 4. Konfiguracja w BPP

Po uzyskaniu danych z PBN, wprowadź je podczas konfiguracji uczelni:

- **Środowisko PBN:** Wybierz testowe lub produkcyjne
- **Nazwa aplikacji w PBN:** Wprowadź otrzymany identyfikator
- **Token aplikacji w PBN:** Wprowadź otrzymany token

## Ważne informacje

### Bezpieczeństwo
- Token aplikacji jest poufny - nie udostępniaj go osobom nieupoważnionym
- Przechowuj kopię zapasową tokena w bezpiecznym miejscu
- W razie kompromitacji tokena, natychmiast wygeneruj nowy w systemie PBN

### Uprawnienia
- Aplikacja będzie miała dostęp do danych w zakresie uprawnień użytkownika, który ją autoryzuje
- Upewnij się, że użytkownicy autoryzujący aplikację mają odpowiednie uprawnienia w PBN

### Wsparcie
- Oficjalna dokumentacja PBN: https://pbn.nauka.gov.pl/centrum-pomocy/
- Dokumentacja integracji BPP z PBN: https://bpp.readthedocs.io/pl/latest/konfiguracja_pbn.html
- Przykłady i najlepsze praktyki: https://bpp.iplweb.pl/zrodla

## Często zadawane pytania

**P: Czy mogę najpierw skonfigurować BPP bez danych PBN?**
O: Tak, możesz skonfigurować podstawowe dane uczelni i uzupełnić dane PBN później w panelu administracyjnym.

**P: Czy mogę zmienić środowisko z testowego na produkcyjne?**
O: Tak, ale wymaga to zmiany w panelu administracyjnym i ponownej autoryzacji użytkowników.

**P: Co zrobić gdy token przestanie działać?**
O: Wygeneruj nowy token w systemie PBN i zaktualizuj go w konfiguracji BPP.

**P: Czy jeden token może być używany dla wielu instancji BPP?**
O: Nie zalecamy tego ze względów bezpieczeństwa. Każda instancja powinna mieć własny token.

## Automatyczne ustawienia BPP

System BPP automatycznie konfiguruje następujące opcje dla optymalnej współpracy z PBN:

- **Kasowanie oświadczeń przed wysłaniem** - zapewnia aktualność danych
- **Niewysyłanie prac z PK=0** - chroni przed wysłaniem niepełnych danych
- **Wysyłanie UID uczelni jako afiliacji** - zapewnia spójność danych
- **Wysyłanie prac bez oświadczeń** - umożliwia pełny eksport
- **Włączona integracja z PBN** - aktywuje funkcjonalności wymiany danych
- **Opcjonalna aktualizacja przy edycji** - umożliwia bieżącą synchronizację

Te ustawienia można później modyfikować w panelu administracyjnym według potrzeb instytucji.
