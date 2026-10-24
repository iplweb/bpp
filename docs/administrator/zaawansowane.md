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

## Polityka haseł

Polityka haseł użytkowników logujących się loginem i hasłem (nie dotyczy
logowania przez Microsoft i ORCID) idzie za zaleceniami NIST SP 800-63B:
liczy się długość hasła, a nie wymogi „cyfra + znak specjalny", i nie ma
cyklicznego wymuszania zmiany hasła.

- hasło ma co najmniej 15 znaków; nie musi zawierać cyfr, wielkich liter ani
  znaków specjalnych — dobrze sprawdza się kilka słów albo całe zdanie,
- odrzucane są hasła z listy słabych haseł (bez reguł złożoności):
  - popularne hasła, hasła podobne do loginu lub adresu e-mail,
  - powtórzenia jednego znaku, hasła z mniej niż 5 różnymi znakami, proste
    sekwencje (`12345…`, `abcde…`, `qwerty…`, także malejąco) oraz więcej
    niż 3 jednakowe znaki z rzędu,
  - hasła zawierające słowa związane z serwisem: „bpp”, „bibliografia”,
    nazwę lub skrót uczelni, nazwę domeny serwisu i słowa z
    `DJANGO_BPP_PASSWORD_CONTEXT_WORDS` (bez rozróżniania wielkości liter
    i polskich znaków; słowa krótsze niż 3 znaki są pomijane),
  - hasła łatwe do odgadnięcia według oceny
    [zxcvbn](https://github.com/dwolfhub/zxcvbn-python) liczonej na
    serwerze (bez wysyłania hasła): złożone z popularnych haseł i słów,
    powtórzeń, sekwencji, sąsiednich klawiszy, dat lub danych konta —
    także w przeróbkach typu `P@ssw0rd`; słowniki zxcvbn są angielskie,
    polskie słowa sprawdza się przez słowa kontekstowe i dane konta,
  - hasła znane z wycieków danych — sprawdzane w serwisie
    [Have I Been Pwned](https://haveibeenpwned.com/Passwords) metodą
    k-anonimowości: do serwisu trafia tylko 5 pierwszych znaków skrótu
    SHA-1 hasła, nigdy samo hasło,
- nie można wrócić do żadnego z 12 ostatnich haseł.

Istniejące krótsze hasła pozostają ważne — nowa długość obowiązuje przy
najbliższej zmianie lub resecie hasła.

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DJANGO_BPP_PASSWORD_MIN_LENGTH` | `15` | minimalna długość hasła |
| `DJANGO_BPP_PASSWORD_DURATION_SECONDS` | `0` | co ile sekund wymuszać zmianę hasła; `0` = nigdy (np. `2592000` = 30 dni) |
| `DJANGO_BPP_USE_PASSWORD_HISTORY` | `true` | czy pamiętać poprzednie hasła |
| `DJANGO_BPP_PASSWORD_HISTORY_COUNT` | `12` | ile poprzednich haseł pamiętać |
| `DJANGO_BPP_PASSWORD_CONTEXT_WORDS` | (puste) | dodatkowe słowa zakazane w hasłach, rozdzielone przecinkami (np. `umlub,lublin`) |
| `DJANGO_BPP_PASSWORD_CHECK_PWNED` | `true` | sprawdzanie haseł w Have I Been Pwned; `false` wyłącza |
| `DJANGO_BPP_PASSWORD_MIN_ZXCVBN_SCORE` | `3` | minimalna ocena siły hasła wg zxcvbn (0–4); `0` wyłącza |

Sprawdzanie wycieków wymaga, żeby serwer aplikacji mógł łączyć się
z `api.pwnedpasswords.com` na porcie 443 (HTTPS). Gdy serwis jest
niedostępny (brak wyjścia do internetu, przekroczony czas 3 s, błąd po
stronie serwisu), hasło **zostaje przyjęte**, a w logu pojawia się
ostrzeżenie — awaria zewnętrznego serwisu nie blokuje zmiany haseł.
W sieciach bez dostępu do internetu warto ustawić
`DJANGO_BPP_PASSWORD_CHECK_PWNED=false`, żeby uniknąć opóźnienia przy
każdej zmianie hasła.

### Wymuszenie zmiany hasła

Żeby wymusić zmianę hasła przy najbliższym wejściu na stronę (np. po
podejrzeniu wycieku haseł albo żeby wszyscy przeszli na 15-znakowe hasła):

```bash
python src/manage.py wymus_zmiane_hasel --dry-run   # podgląd: kogo obejmie
python src/manage.py wymus_zmiane_hasel             # wszyscy z hasłem BPP
python src/manage.py wymus_zmiane_hasel --username jan --username ewa
python src/manage.py wymus_zmiane_hasel --grupa "wprowadzanie danych"
```

Komenda obejmuje aktywne konta z hasłem BPP — konta logujące się wyłącznie
przez Microsoft lub ORCID nie są ruszane. Uruchomienie drugi raz jest
bezpieczne. Wymuszenie dla pojedynczego użytkownika można też dodać i usunąć
w panelu administracyjnym („Enforced password changes").

## Konfiguracja LDAP (ActiveDirectory)

Konfiguracja LDAP (ActiveDirectory) odbywa się za pomocą zmiennych środowiskowych lub
konfiguracyjnych `AUTH_LDAP_SERVER_URI`, `AUTH_LDAP_BIND_DN`, `AUTH_LDAP_BIND_PASSWORD` oraz
`AUTH_LDAP_USER_SEARCH`. Zmienne te należy ustawić w pliku `.env` w katalogu domowym użytkownika.
