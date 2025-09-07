# BPP Setup Wizard

Aplikacja Django umożliwiająca łatwą konfigurację początkową systemu BPP na pustej bazie danych.

## Funkcjonalność

### Dwuetapowy proces konfiguracji

#### Etap 1: Utworzenie konta administratora
- Automatyczne przekierowanie gdy `BppUser.objects.count() == 0`
- Formularz tworzenia pierwszego użytkownika z uprawnieniami superużytkownika
- Automatyczne logowanie po utworzeniu konta
- Przekierowanie do strony głównej

#### Etap 2: Konfiguracja uczelni
- Automatyczne przekierowanie dla zalogowanych administratorów gdy brak obiektu `Uczelnia`
- Formularz konfiguracji podstawowych danych uczelni:
  - Dane podstawowe (nazwa, nazwa w dopełniaczu, skrót)
  - Integracja z PBN (środowisko, nazwa aplikacji, token)
  - Struktura organizacyjna (używanie wydziałów)
- Automatyczna konfiguracja optymalnych ustawień PBN

## Struktura aplikacji

```
bpp_setup_wizard/
├── __init__.py
├── apps.py              # Konfiguracja aplikacji Django
├── forms.py             # Formularze SetupAdminForm i UczelniaSetupForm
├── middleware.py        # SetupWizardMiddleware - automatyczne przekierowania
├── models.py            # Brak własnych modeli, używa istniejących
├── views.py             # Widoki setup wizarda
├── urls.py              # Konfiguracja URL
├── tests.py             # Kompletne testy jednostkowe
├── templates/
│   └── bpp_setup_wizard/
│       ├── setup.html           # Formularz tworzenia administratora
│       ├── uczelnia_setup.html  # Formularz konfiguracji uczelni
│       └── status.html          # Strona statusu konfiguracji
├── PBN_INTEGRACJA.md    # Dokumentacja integracji z PBN
└── README.md            # Ten plik
```

## Middleware

`SetupWizardMiddleware` automatycznie sprawdza stan systemu i przekierowuje:
1. Gdy brak użytkowników → `/setup/`
2. Gdy brak uczelni i użytkownik jest adminem → `/setup/uczelnia/`

**Ważne:** Middleware musi być umieszczony PO `AuthenticationMiddleware` w settings, aby mieć dostęp do `request.user`.

## Automatyczne ustawienia PBN

Podczas konfiguracji uczelni, następujące pola są automatycznie ustawiane na `True`:
- `pbn_api_kasuj_przed_wysylka` - Kasuj oświadczenia przed wysłaniem do PBN
- `pbn_api_nie_wysylaj_prac_bez_pk` - Nie wysyłaj do PBN prac z PK=0
- `pbn_api_afiliacja_zawsze_na_uczelnie` - Wysyłaj zawsze UID uczelni jako afiliację
- `pbn_wysylaj_bez_oswiadczen` - Wysyłaj prace bez oświadczeń
- `pbn_integracja` - Używać integracji z PBN
- `pbn_aktualizuj_na_biezaco` - Włącz opcjonalną aktualizację przy edycji

## Testy

Aplikacja zawiera kompleksowy zestaw 12 testów pokrywających:
- Przekierowania middleware
- Wyświetlanie formularzy
- Tworzenie administratora
- Konfigurację uczelni
- Zabezpieczenia dostępu
- Pełny przepływ konfiguracji

Uruchomienie testów:
```bash
pytest src/bpp_setup_wizard/tests.py
```

## Dokumentacja PBN

W formularzu konfiguracji uczelni znajdują się linki do:
- [Oficjalnej instrukcji PBN](https://pbn.nauka.gov.pl/centrum-pomocy/baza-wiedzy/uzyskanie-integracji-z-api-pbn/)
- [Dokumentacji BPP - Konfiguracja PBN](https://bpp.readthedocs.io/pl/latest/konfiguracja_pbn.html)
- [Przykładów i zasobów BPP](https://bpp.iplweb.pl/zrodla)

## Użycie

1. Zainstaluj aplikację dodając `'bpp_setup_wizard'` do `INSTALLED_APPS`
2. Dodaj middleware `'bpp_setup_wizard.middleware.SetupWizardMiddleware'` po `AuthenticationMiddleware`
3. Dodaj URL: `path("setup/", include("bpp_setup_wizard.urls"))`
4. Przy pierwszym uruchomieniu na pustej bazie, system automatycznie przekieruje do kreatora

## Uwagi

- Kreator może być uruchomiony tylko raz - po utworzeniu użytkowników i uczelni staje się niedostępny
- Dane PBN mogą być uzupełnione później w panelu administracyjnym
- Zalecane jest rozpoczęcie od środowiska testowego PBN
