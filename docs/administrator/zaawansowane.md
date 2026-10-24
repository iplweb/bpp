# Ustawienia zaawansowane

W tej sekcji dokumentacji znajdują się zaawansowane ustawienia serwera. Instrukcje te przeznaczone
są dla administratorów systemu operacyjnego Linux na którym działa system BPP.

## Konfiguracja systemu BPP

Konfiguracja od wersji 202209 wzwyż powinna odbywać się przez plik `.env` umieszczony
w katalogu domowym użytkownika, z którego konta uruchamiany jest serwer BPP. Zmienne
konfiguracyjne będą stopniowo migrować do tego formatu.

[Przykładowy plik .env.example w repozytorium kodu na GitHub](https://github.com/iplweb/bpp/blob/dev/.env.example)

[Plik django_bpp/settings/base.py repozytorium kodu na GitHub](https://github.com/iplweb/bpp/blob/dev/src/django_bpp/settings/base.py)

Zmienne można nadpisać.

Jeżeli zainstalujemy BPP korzystając z pakietu [bpp-on-ansible](https://github.com/iplweb/bpp-on-ansible) ,
to utworzy on domyślny plik `.env`. Za zmienne odpowiada plik [config.yml](https://github.com/iplweb/bpp-on-ansible/blob/develop/ansible/roles/bpp-site/tasks/config.yml#L13).

## Konfiguracja LDAP (ActiveDirectory)

Konfiguracja LDAP (ActiveDirectory) odbywa się za pomocą zmiennych środowiskowych lub
konfiguracyjnych `AUTH_LDAP_SERVER_URI`, `AUTH_LDAP_BIND_DN`, `AUTH_LDAP_BIND_PASSWORD` oraz
`AUTH_LDAP_USER_SEARCH`. Zmienne te należy ustawić w pliku `.env` w katalogu domowym użytkownika.

## Logowanie przez Microsoft (Office 365 / Entra ID)

Logowanie kontem Microsoft wymaga opcjonalnego pakietu `django_microsoft_auth`
(`uv sync --extra office365`) i włącza się po ustawieniu w pliku `.env`
zmiennych `MICROSOFT_AUTH_CLIENT_ID` oraz `MICROSOFT_AUTH_CLIENT_SECRET`.

| Zmienna | Opis |
|---------|------|
| `MICROSOFT_AUTH_CLIENT_ID` | Identyfikator aplikacji zarejestrowanej w Entra ID. |
| `MICROSOFT_AUTH_CLIENT_SECRET` | Sekret tej aplikacji. |
| `MICROSOFT_AUTH_TENANT_ID` | **Wymagany.** Identyfikator katalogu (GUID) albo jego domena, np. `uczelnia.onmicrosoft.com`. |
| `MICROSOFT_AUTH_LINK_BY_EMAIL` | Domyślnie `False`. Patrz niżej. |
| `MICROSOFT_AUTH_EXTRA_SCOPES` | Dodatkowe zakresy OAuth (opcjonalnie). |

### Wymagany konkretny katalog (tenant)

Jeżeli ustawiono `MICROSOFT_AUTH_CLIENT_ID`, a `MICROSOFT_AUTH_TENANT_ID` jest
pusty albo ma wartość `common`, `organizations` lub `consumers`, serwer BPP
**nie wystartuje** (błąd `ImproperlyConfigured`). BPP przyjmuje wyłącznie
tokeny wystawione przez skonfigurowany katalog — sprawdzane są claimy `iss`
i `tid` tokenu. Identyfikator katalogu znajdziesz w portalu Azure:
*Microsoft Entra ID → Przegląd → Identyfikator dzierżawy*.

### Wiązanie kont Microsoft z istniejącymi kontami BPP

Przy pierwszym logowaniu kontem Microsoft BPP szuka użytkownika o tym samym
adresie e-mail. Domyślnie (`MICROSOFT_AUTH_LINK_BY_EMAIL=False`) **nie**
powiąże automatycznie konta Microsoft z istniejącym użytkownikiem, który:

- ma uprawnienia administracyjne (`is_staff` lub `is_superuser`), albo
- ma ustawione lokalne hasło do BPP.

Takie logowanie zostanie odrzucone. Administrator może powiązać konto ręcznie
w module administracyjnym (*Microsoft accounts*), albo — jeżeli adresy e-mail
w katalogu są w pełni zaufane — ustawić `MICROSOFT_AUTH_LINK_BY_EMAIL=True`.
Zwykłe konta bez hasła lokalnego oraz nowi użytkownicy są wiązani/zakładani
automatycznie, jak dotychczas.

Konta Microsoft **już powiązane** z użytkownikiem BPP logują się bez zmian.
Po aktualizacji użytkownicy zalogowani przez Microsoft muszą jednorazowo
zalogować się ponownie (zmieniła się nazwa backendu uwierzytelniania).
