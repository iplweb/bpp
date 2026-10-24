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
- odrzucane są hasła z listy popularnych haseł, hasła podobne do loginu lub
  adresu e-mail, ciągi typu `qwerty`/`12345` oraz więcej niż 3 jednakowe
  znaki z rzędu,
- nie można wrócić do żadnego z 12 ostatnich haseł.

Istniejące krótsze hasła pozostają ważne — nowa długość obowiązuje przy
najbliższej zmianie lub resecie hasła.

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DJANGO_BPP_PASSWORD_MIN_LENGTH` | `15` | minimalna długość hasła |
| `DJANGO_BPP_PASSWORD_DURATION_SECONDS` | `0` | co ile sekund wymuszać zmianę hasła; `0` = nigdy (np. `2592000` = 30 dni) |
| `DJANGO_BPP_USE_PASSWORD_HISTORY` | `true` | czy pamiętać poprzednie hasła |
| `DJANGO_BPP_PASSWORD_HISTORY_COUNT` | `12` | ile poprzednich haseł pamiętać |

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
