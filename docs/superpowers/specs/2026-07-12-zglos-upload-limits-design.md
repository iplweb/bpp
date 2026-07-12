# Naprawa: anonimowe wyczerpanie dysku przez uploady formularza zgłoszeń

Data: 2026-07-12
Gałąź: `fix/zglos-upload-limits`
Dotyczy findingu #2 z review bezpieczeństwa (anonimowy DoS przez uploady
w `zglos_publikacje`).

## Problem

Publiczny kreator zgłaszania publikacji (`Zgloszenie_PublikacjiWizard`)
zapisuje pliki uploadowane na kroku 2 natychmiast na dysk, zanim zgłoszenie
zostanie ukończone. Brak jest:

- limitu rozmiaru pojedynczego pliku,
- limitu liczby plików w jednym żądaniu,
- czyszczenia porzuconych (nieukończonych) sesji — `_wyczysc_tmp_pliki`
  woła się tylko przy ponownym uploadzie w tej samej sesji albo po udanym
  `done()`; sesja porzucona zostawia pliki na zawsze,
- jakiegokolwiek cyklicznego cleanupu.

Walidowane jest wyłącznie rozszerzenie `.pdf` (`validators.py`), a pole
`pliki` przyjmuje wiele plików (`<input multiple>`). Formularz jest domyślnie
publiczny (`Uczelnia.wymagaj_logowania_zglos_publikacje` default=False).

Skutek: automat może wielokrotnie dojść do kroku 2, wysłać dużą porcję plików
i porzucić wizard, zapełniając dysk. CSRF nie chroni (bot pobiera token).

### Ustalenie kluczowe (weryfikacja w kodzie)

Pliki **tymczasowe** (kreator) i **trwałe** (ukończone zgłoszenia) lądują dziś
w **tym samym** katalogu:

- tmp: `FileSystemStorage(location=MEDIA_ROOT/protected/zglos_publikacje)`
  (`views.py:215`), zapis pod oryginalną nazwą pliku,
- trwałe: `upload_to = "protected/zglos_publikacje/{uuid}.pdf"`
  (`models.py:50-57`), z **dwóch** modeli: `Zgloszenie_Publikacji.plik`
  oraz `Zgloszenie_Publikacji_Zalacznik.plik`.

Dlatego naiwny cleanup „skasuj pliki starsze niż N godzin w tym katalogu"
skasowałby realne zgłoszenia. Wymóg biznesowy (instalacje klienckie):
**plików ukończonych zgłoszeń NIE WOLNO nigdy kasować.**

## Decyzje (parametry uzgodnione z właścicielem)

- Zakres: limity uploadu + cleanup sierot (bez zmiany domyślnej publiczności
  formularza, bez wymogu logowania).
- Limity: **20 MB / plik**, **max 5 plików** na żądanie.
- Cleanup: komenda kasująca porzucone tmp-pliki starsze niż **24 h**
  (domyślnie; parametryzowalne), wpinana w cron po stronie wdrożenia.

## Rozwiązanie

### A. Zamknięcie WSZYSTKICH ścieżek utrwalania plików + limity

Kluczowe ustalenie z review: walidacja pola `pliki` na kroku 2 **nie
wystarcza**, bo `formtools` utrwala każdy plik zwrócony przez
`process_step_files` do `file_storage` (`storage/base.py:117`), a obecny
override oddaje formtoolsowi surowe `request.FILES` dla kroków 0/1/3/4
(`super().process_step_files`) oraz `MultiValueDict` pozostałych kluczy
na kroku 2. Bot wysyłający **ważny** krok 0 z doczepionymi plikami
(dowolne klucze pól) → wszystkie lądują na dysku, omijając limity.
`process_step_files` wykonuje się tylko dla `form.is_valid()`, ale ważność
minimalnego kroku 0 jest trywialna.

**A1. `process_step_files` przepisany tak, by NIC nie oddawać formtoolsowi
i utrwalać wyłącznie zwalidowane pliki kroku 2** (`views.py`):

```
def process_step_files(self, form):
    # Żaden krok poza "2" nie ma pól plikowych — nie utrwalamy nic,
    # co doczepiono do request.FILES (zamyka wektor przez kroki 0/1/3/4).
    if self.steps.current != "2":
        return {}
    # OTWARTY: pole `pliki` usunięte z formularza → plików nie oczekujemy.
    # WAŻNE: wyczyść ew. tmp z wcześniejszego przejścia jako OGRANICZONY
    # (scenariusz OGRANICZONY→krok 1→OTWARTY→koniec), inaczej _process_files
    # doczepiłby stare pliki do zgłoszenia otwartego.
    if "pliki" not in form.fields:
        self._wyczysc_tmp_pliki()
        return {}
    files = form.files or {}
    if hasattr(files, "getlist"):
        pliki = self._pliki_w_limicie(files.getlist("2-pliki"))
        if pliki:
            self._wyczysc_tmp_pliki()
            ... zapis każdego do self.file_storage, metadane w extra_data ...
    # Zwracamy {} — WSZYSTKIE pliki obsłużyliśmy ręcznie; formtools nie
    # utrwala już żadnego surowego klucza z request.FILES.
    return {}
```

Zmiana względem dziś: (a) kroki ≠ „2" zwracają `{}` zamiast `form.files`;
(b) krok 2 zwraca `{}` zamiast `MultiValueDict` obcych kluczy; (c) zapis
tylko gdy pole `pliki` istnieje (nie-OTWARTY), a gałąź OTWARTY czyści tmp;
(d) filtr `_pliki_w_limicie` przed zapisem.

**Krytyczne: w `process_step_files` NIE wolno rzucać `ValidationError`.**
`formtools` woła je w `post()` PO `form.is_valid()==True` i nic nie łapie
(`formtools/wizard/views.py:311-314`) → wyjątek = HTTP 500, nie „nieważny
krok". Dlatego limity egzekwuje **walidacja formularza (A2)** — to ona daje
ładny błąd. `process_step_files` jest tylko obroną w głębi.

**A2. Limity jako pierwsza linia (walidacja formularza, dobre UX błędu)**
(`validators.py`, `forms.py`):
- stałe `MAX_ROZMIAR_PLIKU = 20 * 1024 * 1024`, `MAX_LICZBA_PLIKOW = 5`,
- walidator `validate_file_size(value)` → `ValidationError` (polski
  komunikat) gdy `value.size > MAX_ROZMIAR_PLIKU`; `value.size` jest
  bezpieczne (`forms.FileField.to_python` już wymaga `.size`),
- pole `pliki` (`MultipleFileField`) dostaje `validate_file_size` w
  `validators` (odpala per-plik, bo `clean` iteruje listę — jak istniejący
  `validate_file_extension_pdf`),
- `MultipleFileField.clean`: limit liczby sprawdzany **przed** rozgałęzieniem
  `isinstance(list)` (znormalizuj do listy, potem `len(...) > MAX...` →
  `ValidationError`),
- legacy pole `plik` w `Zgloszenie_Publikacji_Plik` też dostaje
  `validate_file_size` (formularz to martwy kod — brak importów poza
  definicją; dodajemy defensywnie, nie jako zamknięcie realnej ścieżki).

**A3. `_pliki_w_limicie(pliki)`** — defensywny filtr w `process_step_files`:
zwraca podlistę mieszczącą się w limitach (odrzuca pliki `> MAX_ROZMIAR_PLIKU`,
przycina do `MAX_LICZBA_PLIKOW`). **Nie rzuca** — jeśli cokolwiek odrzuci,
loguje przez `rollbar.report_message` (to „nie powinno się zdarzyć", bo
walidacja formularza A2 już przepuściła dokładnie tę listę; rozjazd = alarm).
To osobna funkcja od walidatora formularza: A2 (raise, UX) vs A3 (filtr+log,
obrona w głębi). Dzięki temu żadna ścieżka `process_step_files` nie robi 500.

Uwaga terminologiczna: Django spooluje pliki > `FILE_UPLOAD_MAX_MEMORY_SIZE`
(2.5 MB) do `TemporaryUploadedFile` w `/tmp` **przed** walidacją. „Nic nie
trafia na dysk" znaczy tu „nic nie zostaje **trwale** w naszym storage" —
temp Django sprząta sam.

### B. Rozdzielenie katalogu tmp od trwałego

- Nowy, wspólny punkt prawdy o lokalizacji tmp (funkcja/moduł-level), by
  wizard i komenda cleanup patrzyły w **ten sam** katalog:
  `MEDIA_ROOT/protected/zglos_publikacje_tmp/`.
- `Zgloszenie_PublikacjiWizard.file_storage` liczony w runtime (nie zamrożony
  na import), żeby `@override_settings(MEDIA_ROOT=...)` w testach działał;
  dziś `location` jest policzony na imporcie modułu i override go nie zmienia.
  **Musi to być class-level `cached_property`, NIE ustawienie w `__init__`:**
  `as_view()` → `get_initkwargs` sprawdza `hasattr(cls, "file_storage")` na
  **klasie** (`formtools/wizard/views.py:188-194`); krok 2 ma `FileField`,
  więc brak atrybutu na klasie → `NoFileStorageConfigured` przy imporcie
  `urls`. `cached_property` jest widoczne jako deskryptor klasy (hasattr=True),
  a `getattr(self, ...)` w `dispatch` odpala je poprawnie per-instancja.
- Trwałe pliki (`upload_to`) zostają w `protected/zglos_publikacje/`
  **bez zmian** → istniejące zgłoszenia nietknięte, brak migracji.
- `done()`/`_process_files`/`_wyczysc_tmp_pliki` idą przez `self.file_storage`
  → automatycznie na nowej lokalizacji; logika `done()` bez zmian.
- Efekt: katalog tmp zawiera **wyłącznie** pliki in-flight; trwałych tam
  nigdy nie ma. Bezpieczeństwo cleanupu wynika z konstrukcji.
- Oba katalogi pod `protected/` → `protected_media_serve` (`urls.py:49`)
  nadal blokuje bezpośredni dostęp HTTP do obu.

**B2. Odporność na late-completion (review #2).** `SESSION_COOKIE_AGE`
default = 14 dni, a cleanup kasuje tmp po 24 h. Użytkownik kończący wizard
po > 24 h trafiłby na `FileNotFoundError` w `_process_files`
(`self.file_storage.open(tmp_name)`, `views.py:651`) → HTTP 500.
**Nie da się tego naprawić przez `ValidationError`** — `render_done` woła
`self.done(...)` wprost (`formtools/wizard/views.py:381`) i po powrocie robi
`storage.reset()`; wyjątek z `done()` = 500, a render zwrócony z wnętrza
`done()` i tak zostanie wyresetowany. Mechanizm: **override `render_done`**
i sprawdzenie istnienia PRZED wejściem w `done()`:

```
def render_done(self, form, **kwargs):
    brakujace = [i for i in self.storage.extra_data.get(PLIKI_EXTRA_KEY, [])
                 if not self.file_storage.exists(i["tmp_name"])]
    if brakujace:
        self._wyczysc_tmp_pliki()                # skasuj metadane sierot
        self.storage.current_step = "2"
        messages.warning(self.request, "Wgrane pliki wygasły — wgraj ponownie.")
        return self.render(self.get_form("2",
                           data=self.storage.get_step_data("2")))
    return super().render_done(form, **kwargs)
```

**B3. Sprzątanie przy restarcie kreatora (review #8, tanie).** GET na URL
wizardu robi `storage.reset()` (→ `init_data()`, zeruje `extra_data`), ale
nie kasuje plików zapisanych naszą ścieżką → sieroty w żywej sesji.
**Kolejność jest krytyczna** — czyścimy PRZED `super().get()`, bo to on
resetuje storage; po resecie nie ma już listy `pliki_list` do skasowania:

```
def get(self, request, *args, **kwargs):
    self._wyczysc_tmp_pliki()            # PRZED super() — self.storage już
    return super().get(request, *args, **kwargs)   # jest (ustawiony w dispatch)
```

### C. Komenda czyszcząca sieroty

- `zglos_publikacje/management/commands/wyczysc_zglos_tmp.py`.
- Kasuje pliki **wyłącznie** w katalogu tmp (`protected/zglos_publikacje_tmp/`,
  ten sam punkt prawdy co wizard) starsze niż `--older-than-hours`
  (default 24), po `mtime`.
- Flagi: `--older-than-hours N` (default 24), `--dry-run`. Raportuje
  liczbę i sumaryczny rozmiar skasowanych/pominiętych.
- **Bezpieczeństwo wobec nakazu „nigdy nie kasuj plików zgłoszeń" opiera się
  na konstrukcji (B), nie na cross-checku DB.** Rezygnujemy z DB cross-checku
  (kruchy: `all_objects` nie istnieje w `django_softdelete` — są `objects`
  [bez usuniętych] i `global_objects`; do tego ścieżki DB są względem
  MEDIA_ROOT, a listing tmp daje nazwy względem storage → porównanie
  wymagałoby normalizacji i łatwo staje się martwym kodem). Zamiast tego:
  strażnik ścieżki — komenda **odmawia** działania, jeśli rozwiązany katalog
  celu nie jest dokładnie skonfigurowanym katalogiem tmp (dokładna reguła
  niżej), nie rekursuje poza niego, i ma `--dry-run`.
  W tym katalogu trwałych plików nie ma z definicji.
- **Konkretna reguła strażnika** (review #7, `endswith` był za słaby):
  komenda **nie** przyjmuje ścieżki z CLI — katalog bierze wyłącznie z tego
  samego punktu prawdy co wizard (funkcja modułowa). Dalej:
  `tmp = Path(zglos_tmp_dir()).resolve()` (realpath neutralizuje symlink
  i trailing slash); assert `tmp.name == "zglos_publikacje_tmp"` (**równość**
  basename, nie `endswith`); iteracja `tmp.iterdir()` **bez rekursji**;
  kasuj tylko `e.is_file() and not e.is_symlink()`; wiek po
  `e.lstat().st_mtime` (lstat — nie podążaj za linkiem).
- Wpięcie w cron należy do wdrożenia (`bpp-deploy`); poza zakresem PR,
  wspomniane w newsfragmencie.

## Testy (TDD — piszemy przed implementacją)

Walidatory (poziom jednostkowy, bez alokacji 20 MB — `SimpleUploadedFile`
z nadpisanym `.size`, bo `File.size` to zwykły atrybut/`cached_property`):
1. `validate_file_size`: plik `.size = 21 MB` → `ValidationError`; 19 MB → OK.
2. `MultipleFileField.clean`: 6 plików → `ValidationError` (liczba);
   5 plików → OK; 1 plik (nie-lista) → nie wywala limitu liczby; `[]` → OK.

Przepływ wizardu (test client / bezpośrednie wołanie widoku,
`@override_settings(MEDIA_ROOT=tmp_path)` + w razie potrzeby monkeypatch
`file_storage`):
3. Krok 2 (OGRANICZONY): 6 plików → krok nieważny, **żaden** plik nie
   utrwalony w tmp.
4. Krok 2: 5 plików ~1 MB → utrwalone; lądują w `zglos_publikacje_tmp/`,
   **nie** w `zglos_publikacje/`.
5. **Regresja wektora review #1:** ważny krok 0 z doczepionymi plikami pod
   dowolnymi kluczami → **żaden** plik nie utrwalony w storage.
6. Krok 2 OTWARTY (pole `pliki` usunięte) z doczepionym `2-pliki` → nic nie
   utrwalone.
6b. OGRANICZONY z plikami → powrót na krok 1 → zmiana na OTWARTY → koniec:
   `done()` **nie** tworzy `Zgloszenie_Publikacji_Zalacznik` (tmp wyczyszczone
   w gałęzi OTWARTY), zgłoszenie bez plików.
7. Late-completion: tmp-plik usunięty przed `done()` → **brak 500**;
   `render_done` wykrywa brak, resetuje na krok 2 z komunikatem (żadna
   `ValidationError` nie propaguje).

Komenda `wyczysc_zglos_tmp` (mtime ustawiany `os.utime`):
8. stary tmp (mtime > 24 h) → skasowany; świeży tmp → zostaje;
   `--dry-run` → nic nie kasuje.
9. plik trwały (`Zgloszenie_Publikacji_Zalacznik.plik` w
   `zglos_publikacje/`) → **nigdy** nie tknięty (komenda nie wchodzi do
   katalogu trwałego); strażnik ścieżki odmawia działania na złym katalogu.

## Świadome ograniczenia

- Pre-istniejące sieroty w starym wspólnym katalogu (`zglos_publikacje/`,
  sprzed rozdzielenia) nie będą tknięte przez komendę — bezpieczny kierunek
  błędu (wolimy zostawić śmieć niż skasować zgłoszenie). Sprzątanie
  jednorazowe/ręczne, poza tym PR.
- Happy-path DoS: 5×20 MB = 100 MB na w pełni „legalny" request pozostaje
  możliwe; cleanup ogranicza **wiek** śmieci, nie **tempo** zapełniania.
  Ograniczanie tempa (rate-limit/CAPTCHA/kwota) to warstwa brzegowa —
  osobny temat (nginx/`bpp-deploy`), poza zakresem PR.

## Poza zakresem

- Finding #1 (publiczne utworzenie superusera przez `/setup/`, setup-token).
- Throttling / nginx quota.
- Zmiana domyślnej publiczności formularza.
