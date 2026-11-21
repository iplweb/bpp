# Dla deweloperów i agentów

!!! note "Dla kogo jest ta sekcja"
    To dokumentacja techniczna dla **deweloperów** rozwijających BPP oraz dla
    **agentów AI** (np. Claude Code) pracujących nad kodem. **Nie** jest to
    instrukcja dla bibliotekarzy ani administratorów wdrożenia — tych szukaj
    w sekcjach „Instrukcja użytkownika" i „Instrukcja administratora".

Źródłem prawdy o zasadach pracy z kodem jest plik
[`CLAUDE.md`](https://github.com/iplweb/bpp/blob/dev/CLAUDE.md) w korzeniu
repozytorium. Poniższe strony rozwijają wybrane tematy:

- [Mapa kodu](mapa-kodu.md) — architektura i rozmieszczenie modułów
  (generowane maszynowo).
- [Polecenia](polecenia.md) — referencja komend (testy, build, Celery,
  zarządzanie).
- [Pakiety klienckie PBN](pakiety-pbn.md) — pakiety `pbn-client` /
  `django-pbn-client` (PyPI), podział odpowiedzialności i aktualizacja wersji.
- [Soft-delete (kosz)](soft-delete.md) — co jest kasowane miękko
  (`deleted_at`), a co nie, i co dzieje się z danymi powiązanymi, PBN
  i historią wersji przy usunięciu i przywróceniu.
- [Budowanie CSS/SCSS](budowanie-css.md) — pipeline frontendu (Grunt,
  Foundation).
- [euroCRIS — co jeszcze zostało](eurocris-co-jeszcze.md) — stan eksportu
  CERIF/OpenAIRE i lista braków (encje, mapowania słownikowe, rejestracja
  w DRIS).
- [Rozwijanie projektu](rozwijanie-projektu.md) — jak współtworzyć.
- [WeasyPrint na macOS](weasyprint-macos.md) — konfiguracja PDF lokalnie.
- [Testy: Channels broadcast (flake)](testy-channels-broadcast.md) —
  diagnostyka niestabilnego testu.
