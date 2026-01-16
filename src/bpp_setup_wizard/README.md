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

### Kontrola dostępu

#### Etap 1: Konfiguracja administratora (publicznie dostępna)
- **Dostęp**: Publiczny (bez uwierzytelnienia)
- **Warunek**: `BppUser.objects.exists() == False`
- **Działanie**: Middleware przekierowuje wszystkie żądania do `/setup/` gdy brak użytkowników
- Po utworzeniu administratora: automatyczne logowanie i przekierowanie

#### Etap 2: Konfiguracja uczelni (tylko superużytkownik)
- **Dostęp**: Wymagane uwierzytelnienie + `is_superuser`
- **Warunek**: Użytkownik zalogowany jako superuser I `Uczelnia.objects.exists() == False`
- **Działanie**: Middleware przekierowuje tylko superużytkowników do `/setup/uczelnia/`
- Zwykli użytkownicy: brak przekierowania, komunikat błędu przy próbie bezpośredniego dostępu

#### Po zakończeniu konfiguracji
- Oba etapy stają się **permanentnie niedostępne**
- Zmiana konfiguracji tylko przez panel administracyjny (`/admin/`)

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

`SetupWizardMiddleware` automatycznie sprawdza stan systemu i przekierowuje użytkowników do odpowiednich etapów kreatora.

### Logika przekierowań

Middleware działa według następującego algorytmu (kolejność ma znaczenie):

#### 1. Pomijane ścieżki (bez przekierowań)
- `/static/*` - pliki statyczne
- `/media/*` - pliki multimedialne
- `/setup/*` - sam kreator (zapobiega pętli przekierowań)
- `/admin/*` - panel administracyjny (z wyjątkiem `/admin/` gdy brak użytkowników)
- Ścieżki zawierające: `migrate`, `__debug__`
- Ścieżki logowania/wylogowania: `login`, `logout`, `accounts`

#### 2. Sprawdzenie istnienia użytkowników
```python
needs_user_setup = not BppUser.objects.exists()
```
- Jeśli `True`: Przekierowanie wszystkich do `/setup/`
- Jeśli `False`: Kontynuacja do kroku 3

#### 3. Sprawdzenie istnienia uczelni (tylko dla zalogowanych superużytkowników)
```python
needs_uczelnia_setup = not Uczelnia.objects.exists()
```
- Jeśli `True` I użytkownik jest zalogowany I `is_superuser`: Przekierowanie do `/setup/uczelnia/`
- Zwykli użytkownicy: Brak przekierowania

### Konfiguracja Django

Middleware musi być umieszczony **PO** `AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    # ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'bpp_setup_wizard.middleware.SetupWizardMiddleware',
    # ...
]
```

## Automatyczne ustawienia PBN

Podczas konfiguracji uczelni, następujące pola są automatycznie ustawiane na `True`:
- `pbn_api_kasuj_przed_wysylka` - Kasuj oświadczenia przed wysłaniem do PBN
- `pbn_api_nie_wysylaj_prac_bez_pk` - Nie wysyłaj do PBN prac z PK=0
- `pbn_api_afiliacja_zawsze_na_uczelnie` - Wysyłaj zawsze UID uczelni jako afiliację
- `pbn_wysylaj_bez_oswiadczen` - Wysyłaj prace bez oświadczeń
- `pbn_integracja` - Używać integracji z PBN
- `pbn_aktualizuj_na_biezaco` - Włącz opcjonalną aktualizację przy edycji

## Wymagane pola

### Etap 1: Konfiguracja administratora

#### Pola wymagane (required=True)
| Pole | Typ | Opis | Walidacja |
|------|-----|------|-----------|
| `username` | CharField(150) | Nazwa użytkownika | Unikalna, alfanumeryczna + @/./+/-/_ |
| `email` | EmailField | Adres email | Format email, NOT NULL w bazie |
| `password1` | CharField | Hasło | Min. 8 znaków, walidacja siły hasła Django |
| `password2` | CharField | Powtórz hasło | Musi być identyczne z password1 |

#### Pola ustawiane automatycznie
Po zapisaniu formularza, użytkownik otrzymuje następujące uprawnienia:
- `is_staff = True` - Dostęp do panelu administracyjnego
- `is_superuser = True` - Pełne uprawnienia w systemie
- `is_active = True` - Konto aktywne

**Implementacja:** `SetupAdminForm` w `forms.py:11-72` (dziedziczy po `UserCreationForm`)

### Etap 2: Konfiguracja uczelni

#### Pola wymagane (required=True)
| Pole | Typ | Opis | Walidacja |
|------|-----|------|-----------|
| `nazwa` | CharField(512) | Pełna nazwa uczelni | Unikalna, NOT NULL |
| `nazwa_dopelniacz_field` | CharField(512) | Nazwa w dopełniaczu | Wymagane w formularzu* |
| `skrot` | CharField(128) | Skrót/akronim uczelni | Unikalny, NOT NULL |
| `pbn_api_root` | URLField | Środowisko PBN | Wybór: test / produkcja |

*Uwaga: W bazie danych `nazwa_dopelniacz_field` ma `blank=True, default=""`, ale formularz wymaga wypełnienia.

#### Pola opcjonalne (required=False)
| Pole | Typ | Opis | Domyślna wartość |
|------|-----|------|------------------|
| `pbn_app_name` | CharField(128) | Nazwa aplikacji w PBN | "" (pusty string) |
| `pbn_app_token` | CharField(128) | Token aplikacji w PBN | "" (pusty string) |
| `uzywaj_wydzialow` | BooleanField | Czy uczelnia używa wydziałów | True |

**Uwagi:**
- Pola `pbn_app_name` i `pbn_app_token` są opcjonalne - można je skonfigurować później
- Integracja z PBN będzie wymagała uzupełnienia tych pól przed pierwszą synchronizacją
- Formularz nie waliduje, czy oba pola PBN są wypełnione jednocześnie

#### Pola ustawiane automatycznie (hardcoded w formularzu)
Następujące pola są **zawsze** ustawiane na `True` podczas konfiguracji (linie 186-199 w `forms.py`):
- `pbn_api_kasuj_przed_wysylka = True`
- `pbn_api_nie_wysylaj_prac_bez_pk = True`
- `pbn_api_afiliacja_zawsze_na_uczelnie = True`
- `pbn_wysylaj_bez_oswiadczen = True`
- `pbn_integracja = True`
- `pbn_aktualizuj_na_biezaco = True`

**Implementacja:** `UczelniaSetupForm` w `forms.py:75-204`

### Minimalne wymagania do ukończenia kreatora

**Etap 1 - Administrator:**
- 4 pola: username, email, password1, password2

**Etap 2 - Uczelnia:**
- 4 pola: nazwa, nazwa_dopelniacz_field, skrot, pbn_api_root
- Opcjonalnie: pbn_app_name, pbn_app_token (można pominąć)

**Łącznie:** Minimum 8 pól wymaganych do pełnej konfiguracji systemu.

## Testy

```bash
pytest src/bpp_setup_wizard/tests.py
```

## Użycie

1. Zainstaluj aplikację dodając `'bpp_setup_wizard'` do `INSTALLED_APPS`
2. Dodaj middleware `'bpp_setup_wizard.middleware.SetupWizardMiddleware'` po `AuthenticationMiddleware`
3. Dodaj URL: `path("setup/", include("bpp_setup_wizard.urls"))`
