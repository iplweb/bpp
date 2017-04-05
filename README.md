# django_bpp

## O projekcie

django_bpp to system informatyczny do zarządzania bibliografią publikacji pracowników naukowych.

System przeznaczony jest dla bibliotek naukowych i uniwersyteckich w Polsce.

Dostępny na licencji MIT.

## Startujemy!

Zainstaluj: Python, Vagrant i pluginy (vide: Vagrantfile), VirtualBox, Git.

```bash
$ git clone https://github.com/mpasternak/django-bpp.git
$ cd django-bpp
$ vagrant up
$ make release
```

Lokalne testy: 

```bash
$ virtualenv foo -ppython2.7
$ . foo/bin/activate
$ ./buildscripts/run-tests.sh # Uruchom testy lokalnie
```

## Wsparcie komercyjne

Wsparcie komercyjne dla projektu świadczy firma IPL, szczegóły na stronie domowej projektu http://bpp.iplweb.pl/

Live-demo serwisu dostępne jest pod adresem http://bppdemo.iplweb.pl
