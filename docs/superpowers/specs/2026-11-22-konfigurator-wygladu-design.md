# Konfigurator wyglądu i migracja wyglądu — projekt

Data: 2026-11-22

## Dlaczego

Motywy BPP to ręcznie pisane pliki SCSS (`app-*.scss` + `_settings_*.scss`),
po jednym na klienta, rejestrowane w czterech miejscach (Gruntfile, settings,
admin, test). Każda zmiana wyglądu u klienta wymaga programisty, buildu
obrazu i wdrożenia (np. motyw `app-apoz`, FD#609).

Cel: klient (albo my na spotkaniu z klientem) sam ustawia wygląd w BPP:
zmienia opcje, od razu widzi podgląd prawdziwych stron i klika „Zastosuj”.
Bez programisty, bez buildu, bez wdrożenia.

## Cele

- Formularz dla laika: kolory, czcionki, menu, przyciski, komunikaty,
  kafle, grafika w tle, przycisk UserWay, tryb jasny/ciemny/automatyczny.
- Podgląd na żywo prawdziwych stron tej bazy (komputer i telefon) i strona
  demo ze wszystkimi komunikatami, przyciskami i polami.
- Czytelność pilnowana automatycznie (WCAG AA): kolory tekstu na kolorowym
  tle wylicza system, za jasne kolory są odrzucane z gotową poprawką.
- Appserver nie uruchamia kompilatora: robi to osobny, odizolowany kontener
  (dziura w silniku JS nie daje dostępu do bazy ani sekretów).
- **Migracja wyglądu:** po aktualizacji BPP zapisany motyw przebudowuje się
  sam z zapisanych ustawień. Administrator wyraził zgodę, klikając
  „Zastosuj”; nie pytamy go ponownie.

## Poza zakresem

- Panel admina (`/admin/`) — ma własne motywy (`admin-themes.css`).
- Style inline w szablonach i obce arkusze poza Select2 / jQuery UI
  (tryb ciemny ich nie obejmuje).
- Automatyczne pobieranie czcionek z internetu na serwer (self-hosting
  czcionek web) — dziś ładuje je przeglądarka odwiedzającego.

## Architektura

Jeden kod JS w trzech środowiskach. Dzięki temu podgląd, zapis i build dają
CSS identyczny bajt w bajt (sprawdzone: przeglądarka, Node `vm`, Grunt).

| Plik | Rola |
|------|------|
| `src/bpp/static/bpp/js/motyw-konfig.js` | schemat opcji (polskie etykiety), `waliduj`, `doScss` (konfig → punkt wejścia SCSS), `przetworzCss` (tryb ciemny, tło treści) |
| `src/bpp/static/bpp/js/motyw-kompilator.js` | importer plików SCSS z pamięci + `kompiluj(pliki, konfig, opcje)` |
| `src/bpp/static/scss/_app-konfig.scss` | jeden ogólny motyw sterowany zmiennymi `$cfg-*` |
| `bpp/js/dist/sass-przegladarka.js` | dart-sass (czysty JS) zbudowany esbuildem (Grunt `shell:esbuildSass`) |
| `bpp/js/dist/motyw-zrodla-scss.json` | wszystkie pliki SCSS BPP + Foundation (`scss/`, `_vendor/`) w jednym JSON-ie (Grunt `motywyZrodla`) |

Gdzie działa kompilacja:

1. **Podgląd** — web worker w przeglądarce (`motyw-kompilator-worker.js`).
   Strony w ramkach otwierane z `?podglad_motywu=1` (tylko obsługa) mają
   zamiast motywu pusty `<style>`, wypełniany synchronicznie z
   `window.top.BppKonfiguratorCss` przed startem JS Foundation (ten odczytuje
   breakpointy z CSS-a).
2. **„Zastosuj”** — osobny serwis `motyw-kompilator`
   (`docker/motyw-kompilator/`, obraz `iplweb/bpp_motyw_kompilator` w tej
   samej wersji co appserver). Node bez zależności npm uruchamia te same
   pliki co przeglądarka w kontekście `vm` bez API Node'a, waliduje ustawienia
   i kompiluje (~1,8 s). Appserver (`bpp/motyw_kompilator.py`) wysyła mu
   tylko dane (`POST /kompiluj {konfig, czcionkiUrl}`), nigdy kod; gotowego
   CSS-a z przeglądarki nie przyjmuje. Dev i testy bez serwisu: jednorazowe
   `node serwer.js --jednorazowo` na plikach z `src/`.
3. **Build** (opcjonalnie) — `src/bpp/static/scss/motywy/<nazwa>.json`
   kompiluje task Grunta `motywy` do `app-<nazwa>.css` (motyw wbudowany
   w obraz, sam trafia do `BPP_THEMES`).

Zapis i serwowanie:

- Model `MotywWlasny` (jeden na uczelnię, osobna tabela — CSS ma ~300–400
  KB, a `Uczelnia` jest ładowana przy każdym żądaniu): `konfig` (JSON),
  `css`, `skrot` (sha256 CSS-a), `wersja_bpp`, `zmienil`, `zmieniono`.
- `Uczelnia.theme_name = "app-wlasny"`; context processor podaje
  `MOTYW_WLASNY_URL` = `/bpp/motyw-wlasny/<skrot>.css` (skrót w cache),
  `bare.html` dołącza go **poza** `{% compress %}`.
- Plik serwowany z `Cache-Control: immutable` — nowa treść = nowy adres.
- `MotywWlasny` unieważnia cache stron publicznych
  (`MODELE_INWALIDUJACE_CACHE_PUBLICZNY`).

## Motyw roboczy (zapis bez stosowania)

`MotywWlasny.konfig_roboczy` — ustawienia zapisane, ale niezastosowane
(`POST /bpp/konfigurator-wygladu/zapisz/`, cała obsługa). Konfigurator
proponuje to zamiast „Zastosuj”, gdy kompilator jest niedostępny
(`kompilator_dostepny()`, test `/zdrowie` do 2 s) albo użytkownik nie jest
superużytkownikiem. Wczytywany na start konfiguratora (po szkicu z
przeglądarki), czyszczony przez „Zastosuj”. Migracja wyglądu go nie rusza.

## Historia, przymiarka, strona błędu

- `MotywWersja` — każde „Zastosuj” (konfig, motyw przed, kto, kiedy;
  10 ostatnich na uczelnię). Konfigurator: „Wczytaj” do edytora oraz
  „Wróć do motywu sprzed konfiguratora” (`POST …/przywroc/`, tylko wartości
  z `BPP_THEMES`, bez kompilacji).
- Przymiarka (`bpp/przymiarka_motywu.py`): serwer kompiluje motyw do
  `MotywPrzymiarka` (doba ważności), w sesji tylko skrót; context processor
  podmienia `MOTYW_WLASNY_URL` wyłącznie tej sesji obsługi, `base.html`
  pokazuje pasek z „Zakończ przymiarkę”. Nie w cache — w dev cache to
  `DummyCache`, a w produkcji wpis mógłby zniknąć.
- Strona 500 (`generate_500_page`) jest statyczna i serwuje ją nginx, gdy
  Django nie działa — CSS motywu z konfiguratora kopiowany jest do
  `$STATIC_ROOT/500/motyw-<sha>.css` (link przepisany na `/static/`),
  przebudowa po każdym „Zastosuj” i przy starcie kontenera.
- Panel administracyjny (grappelli) poza zakresem — osobny projekt.

## Kolejkowanie

- podgląd: naraz jedna kompilacja w przeglądarce; zmiany w trakcie
  koalescują się w jedną kolejną kompilację,
- ramki podglądu ładują się po kolei (nie kilkanaście stron naraz),
- „Zastosuj”: blokada w cache (jedna kompilacja na instalację); zajęty
  kompilator → 429 + `Retry-After` (nie 503 — nginx w bpp-deploy zamienia
  503 na stronę przerwy technicznej); migracja wyglądu czeka w kolejce.

## Migracja wyglądu

CSS zależy od SCSS-a wersji BPP, z której powstał. Po aktualizacji nowe
strony/elementy nie miałyby stylów motywu.

- `manage.py odswiez_motywy` przebudowuje motywy z `wersja_bpp != VERSION`
  (`--wszystkie` — wszystkie) z zapisanego `konfig`.
- Uruchamia go `entrypoint-appserver.sh` w fazie tła. Czeka do 90 s, aż
  serwis kompilatora odpowie (kontenery startują równolegle).
- Błąd jednego motywu: log z tracebackiem, stary CSS zostaje, pozostałe
  motywy się przebudowują, komenda kończy się kodem ≠ 0; kontener startuje.
- Konfigurator pokazuje ostrzeżenie, gdy zapisany motyw jest z innej wersji
  (np. gdy migracja się nie udała).

Zmiana schematu konfiga (nowe opcje) nie wymaga migracji danych:
`normalizuj` uzupełnia brakujące pola wartościami domyślnymi, więc stare
konfigi dalej są poprawne. Usunięcie lub zmiana znaczenia opcji wymaga
podbicia `WERSJA` w `motyw-konfig.js` i funkcji przenoszącej stare konfigi
(do dopisania, gdy pierwszy raz będzie potrzebna).

## Izolacja kompilatora (bpp-deploy)

Serwis `motyw-kompilator` w bpp-deploy (profil, opt-in — obraz istnieje
dopiero od wersji BPP z konfiguratorem, a host z przypiętą starszą
`DOCKER_VERSION` nie mógłby go pobrać):

- sieć `internal: true` wspólna tylko z appserverem — bez internetu,
- bez bazy, sekretów, wolumenów i publikowanego portu,
- `read_only`, `cap_drop: ALL`, `no-new-privileges`, użytkownik `node`,
- limity: pamięć 512 MB, 1 CPU, 64 procesy; zapytanie do 2 MB; 60 s na
  kompilację (`vm` timeout).

Bez serwisu BPP degraduje się łagodnie: „Zastosuj” zwraca komunikat,
migracja wyglądu zostawia poprzedni CSS.

## Tryb ciemny i tło treści (`przetworzCss`)

BPP ma setki kolorów wpisanych na sztywno, więc zamiast ręcznych nadpisań
przeliczamy kolory w gotowym CSS-ie (parser reguł + `@media`):

- jasne tła (luminancja > 0,179 — próg `color-pick-contrast` Foundation) →
  ciemne, z zachowaniem odcienia; ciemny tekst → jasny; ramki → ciemniejsze;
- reguła z kolorowym tłem i własnym kolorem tekstu (przycisk, kafel) zostaje
  bez zmian;
- `@media print` zostaje jasny;
- zakładka „Pomoc” (`.bpp-support-button`) ma zawsze proste dolne rogi;
- tryb automatyczny (domyślny) = CSS jasny + `@media (prefers-color-scheme:
  dark)` ze zmienionymi deklaracjami — przeglądarka wybiera wersję według
  ustawień systemu; wysoki kontrast zapewnia UserWay (bez własnego trybu);
- tło treści półprzezroczyste/przezroczyste dotyczy jasnych teł poza
  elementami nakładanymi i formularzami (menu, okienka, pola, przyciski —
  lista `RE_ZAWSZE_PELNE`).

Select2 i jQuery UI ładują własne arkusze po motywie — `_app-konfig.scss`
powtarza ich kolory z selektorem `html …`, żeby przeliczenie je objęło.

## Bezpieczeństwo

- Konfigurator i podgląd: `staff_member_required`; `?podglad_motywu` działa
  tylko dla obsługi.
- „Zastosuj”: tylko superużytkownik; serwer waliduje konfig i sam kompiluje
  CSS (nie przyjmuje CSS-a z przeglądarki).
- Obrazek tła: w przeglądarce przed wczytaniem typ (PNG, JPG, WebP, GIF,
  SVG), do 10 MB, do 10 000 px na bok; potem zmniejszenie do 1200 px.
  Zapisany jako `data:image/(png|jpeg|webp|gif|svg+xml);base64,…` do ~700 KB —
  sprawdzane w przeglądarce, w appserverze (przed wysłaniem do kompilatora)
  i w kompilatorze. W CSS `background-image` skrypty SVG się nie wykonują.
- Czcionki z internetu: domyślnie Bunny Fonts (bez śledzenia, RODO), opcja
  Google Fonts; CSP (`django_bpp/csp.py`) dopuszcza oba źródła.

## Koszty i ryzyka

- Obraz `iplweb/bpp_motyw_kompilator`: ~245 MB (głównie `node:22-alpine`),
  osobny — appserver nie rośnie. Rozważane i odrzucone: V8 w appserverze
  (`mini-racer`, +82 MB i silnik JS w procesie z dostępem do bazy), QuickJS
  (5 MB, ale kompilacja > 10 min).
- Trzeba pilnować aktualizacji `node:22-alpine` (Trivy skanuje obraz jak
  pozostałe).
- `dart-sass` w przeglądarce: 3,2 MB (700 KB gzip), ładowany tylko przez
  worker konfiguratora.
- Tryb ciemny jest algorytmiczny — elementy ze stylami inline albo
  z obcych arkuszy mogą zostać jasne. Strona demo „Komunikaty i przyciski”
  i podglądy służą do sprawdzenia.
- Podgląd w trybie dev: strony w ramkach trzymają połączenia SSE
  (autoprzeładowanie), a przeglądarka ma 6 połączeń na host (HTTP/1.1) —
  konfigurator odpina ramki na czas powiększenia i zapisu.

## Testy

- `tests/js/motyw-konfig.test.js` (vitest, z prawdziwą kompilacją SCSS),
- `src/bpp/tests/test_konfigurator_wygladu.py` (widoki, zapis, serwowanie,
  podgląd, admin, migracja wyglądu, klient kompilatora — HTTP i lokalny Node),
- `src/django_bpp/tests/test_motywy_z_konfiguracji.py` (motywy w repo).
