# Profil autora — REWIZJA (2 kolumny, układ per-Uczelnia) + HANDOFF

Data: 2026-06-19
Dotyczy: kontynuacji prac nad PR #385 (branch `feature/profil-autora`).
Spec bazowy: `docs/superpowers/specs/2026-06-18-profil-autora-i-podstrona-design.md`.

> Ten dokument jest samowystarczalny — świeża sesja Claude'a ma z niego wznowić
> bez dostępu do poprzedniej rozmowy.

## 0. Stan obecny (co JUŻ jest na branchu)

- Worktree: `~/Programowanie/bpp-profil-autora`, branch `feature/profil-autora`,
  PR **#385** → `dev`. **CI w pełni zielone** (lint, build test-runner,
  12 shardów Tests, vitest, baseline freshness, CodeQL).
- Remote push: SSH nie działa (brak klucza); pushuj przez HTTPS z gh:
  `git push https://github.com/iplweb/bpp.git feature/profil-autora:feature/profil-autora`
  (po `gh auth setup-git`). gh zalogowany jako `mpasternak` (token HTTPS).
- Testy: `PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest src/bpp/tests/test_profil/`.
  UWAGA: reused testcontainer bywa STALE (błąd `bpp_uczelnia.site_id NOT NULL`
  przy fixture `uczelnia`). Gdy to wyskoczy → `make clean-testcontainers` i
  odpal bez reuse (świeży kontener jest OK).
- Faza 1 dostarczyła (działa, otestowane 35+ testów w `src/bpp/tests/test_profil/`):
  - Model `Autor`: `zdjecie` (ImageField), `biogram` + `biogram_format` (md/html),
    `uklad_profilu` (JSONField — UWAGA: do PRZENIESIENIA na Uczelnię, patrz §2.1),
    `cached_property biogram_html`. Model `WybranaPublikacjaAutora` (GenericFK).
    Migracja `0444`.
  - `bpp/util/biogram.py` `renderuj_biogram` + `bpp/util/text.py`
    `safe_biogram_html` (nh3, bogatszy zestaw tagów, usuwa script/style,
    rel=nofollow noopener).
  - `bpp/util/obrazy.py` `przetworz_zdjecie_autora` (EXIF→crop→WebP 400×400).
  - `bpp/profil_autora.py` — rejestr sekcji (`KATALOG_SEKCJI`, `TypSekcji`,
    `KLUCZ_*`, `waliduj_uklad`, `rozwiaz_uklad`, `domyslny_uklad`).
  - `bpp/profil_autora_dane.py` — buildery danych sekcji (`przygotuj_sekcje`).
  - `bpp/views/browse.py` `AutorView` — render sekcji + `_raport_links`.
  - `bpp/templates/browse/autor.html` + `browse/autor_sekcje/*.html`.
  - `bpp/admin/autor.py` — fieldset profilu, `clean_zdjecie`, inline
    `WybranaPublikacjaAutoraInline`.
  - `bpp/static/scss/_autor-bem.scss` — style sekcji.

## 1. Czego chce użytkownik (rewizja — wiadomość 2026-06-19)

1. **Klik w całą pozycję pracy** (najlepsze/najnowsze/ostatnio edytowane) ma
   prowadzić do szczegółów — NIE link `[szczegóły]` na końcu.
2. **Opisy bibliograficzne bywają dramatycznie długie** (dużo autorów) — trzeba
   je rozsądnie skracać.
3. **Wykres „Publikacje w latach"**: dla >10 lat robi się za szeroki → powyżej
   10 lat wersja **liniowa**, do 10 lat **słupkowa**.
4. **Statystyki wg charakteru**: klik w charakter formalny ma **budować
   wyszukiwanie** w formularzu (dany autor + ten charakter formalny).
5. **Układ 2-kolumnowy** strony autora:
   - LEWA: klasyka — (zdjęcie+biogram na górze), aktualna jednostka,
     historia zatrudnienia, wyszukiwarka prac, linki do raportów (+ pozostałe
     bloki tożsamości: identyfikatory, metryki, stopnie, cytowania).
   - PRAWA (od góry, domyślnie): Statystyki wg charakteru → wykres prac w latach
     → (wykres PK) → (wykres IF, **tylko jeśli IF ≠ 0**) → współautorzy →
     długi ogon „najlepsze prace" → najnowsze artykuły → najnowsze książki →
     ostatnio edytowane.
6. **Edytor kafelkowy = admin-only, układ GLOBALNY per-Uczelnia** (system bywa
   multi-uczelniany). Autor self-service edytuje TYLKO biogram + zdjęcie.
7. **Historia zatrudnienia** w jednostkach — sekcja w lewej kolumnie pod
   aktualną jednostką (dane z `Autor_Jednostka`).

## 2. Decyzje (zatwierdzone 2026-06-19)

| # | Decyzja |
|---|---|
| Układ — zakres | **Globalny per-Uczelnia**. Render bierze `Uczelnia.objects.get_for_request(request)` i czyta jego układ. `Autor.uklad_profilu` — usunąć (override per-autor NIEpotrzebny). |
| „Najnowsze" listy | Zostają w prawej kolumnie, w długim ogonie pod „najlepszymi". |
| Zdjęcie/biogram | Na górze LEWEJ kolumny (wizytówka). |
| Historia zatrudnienia | TAK, sekcja w lewej kolumnie pod „aktualna jednostka". |
| Skracanie opisów | CSS line-clamp (~3 linie) + cała pozycja klikalna do szczegółów. |
| Próg wykresu | >10 lat → liniowy (SVG), ≤10 lat → słupkowy. |
| Klik w charakter | POST do `bpp:browse_build_search` z `autor` + charakter formalny. |

## 3. Plan implementacji (konkretnie)

### 3.1. Przeniesienie układu na Uczelnię (multi-uczelnia)

- **Model**: dodać `Uczelnia.uklad_profilu_autora = JSONField(null=True, blank=True,
  default=None)` (schemat jak dotychczasowy `uklad_profilu`: lista
  `{"klucz","widoczna","limit"}` — ale tylko sekcje PRAWEJ kolumny, patrz §3.2).
- **Migracja 0445** (NIE edytować 0444 — reguła CLAUDE.md): `AddField` na
  Uczelni + `RemoveField(Autor, "uklad_profilu")` (pole nieshipowane, więc
  usunięcie czyste; zero danych produkcyjnych).
- **`rozwiaz_uklad`**: zmienić sygnaturę z `(autor)` na `(uczelnia)` — czyta
  `uczelnia.uklad_profilu_autora` (lub `None`→default). Zaktualizować testy
  `test_uklad.py` (stub `SimpleNamespace(uklad_profilu_autora=...)`).
- **`przygotuj_sekcje(autor, uczelnia, request)`** — układ z uczelni, dane z autora.
- **`AutorView`**: ma już `uczelnia = Uczelnia.objects.get_for_request(...)`;
  przekazać do `przygotuj_sekcje`.
- **Admin**: usunąć `uklad_profilu` z `AutorForm`/fieldsetu Autora; dodać edytor
  układu w adminie **Uczelni** (`UczelniaAdmin`). MVP: JSON w textarea + help.
  (Kafelkowy drag-drop można dołożyć później — patrz §4.)

### 3.2. Rejestr sekcji — tylko PRAWA kolumna

Lewa kolumna jest STAŁA w szablonie (klasyka). Rejestr (`KATALOG_SEKCJI`)
obsługuje wyłącznie kafelki PRAWEJ kolumny. Usuń z rejestru: `wyszukiwarka`,
`biogram`, `eksport` (wyszukiwarka+biogram → lewa stała; eksport → Faza 2).
Zostają (domyślny porządek prawej kolumny):

1. `statystyki_charakter` (ON)
2. `wykres_lata` (ON) — liczba prac/rok
3. `wykres_pk_lata` (ON) — suma `punkty_kbn`/rok  ← NOWA
4. `wykres_if_lata` (ON, auto-hide gdy suma IF = 0) — suma `impact_factor`/rok ← NOWA
5. `wspolautorzy` (ON)
6. `najlepsze_pk` (ON)
7. `najlepsze_if` (ON)
8. `najnowsze_artykuly` (ON)
9. `najnowsze_zwarte` (ON)
10. `ostatnio_edytowane` (ON)
11. `dyscypliny` (OFF), `zrodla` (OFF), `punkty_lata` (OFF), `wybrane_publikacje` (OFF)

Usuń `obowiazkowa` z `TypSekcji` (była tylko dla wyszukiwarki). Buildery
`_biogram`, `_wyszukiwarka`, `_eksport` z `profil_autora_dane.py` — usunąć.

### 3.3. Szablon 2-kolumnowy (`browse/autor.html`)

- Foundation grid (NIE nadpisywać klas grid w SCSS — zmiana w HTML):
  `grid-x grid-margin-x` → `cell large-4` (lewa) + `cell large-8` (prawa);
  na małych ekranach stackuje się automatycznie.
- Nagłówek (breadcrumb + H1 + funkcja + przyciski staff) — full-width nad gridem.
- LEWA `cell large-4` (kolejność): zdjęcie (awatar) → biogram → aktualna
  jednostka → **historia zatrudnienia** → identyfikatory → metryki → stopnie →
  cytowania → wyszukiwarka prac (`autor_sekcje/wyszukiwarka.html`) → linki
  raportu → (embed-kod). Wszystko STAŁE w szablonie.
- PRAWA `cell large-8`: pętla `{% for s in sekcje_profilu %}{% include s.template ... %}{% endfor %}`.

### 3.4. Listy prac — klik w całość + skracanie

`browse/autor_sekcje/_lista_prac.html`:
- Usuń link `[szczegóły]`. Każda pozycja `<li>` klikalna w całość → `data-href`
  = `praca.get_absolute_url`; mały, delegowany JS: klik w `.autor-page__praca`
  nawiguje do `data-href`, CHYBA że kliknięto wewnętrzny `<a>` (np. DOI). Nie
  zagnieżdżaj `<a>` w `<a>` (opis_bibliograficzny_cache zawiera własne linki).
- Skracanie: kontener opisu z CSS line-clamp (~3 linie, overflow hidden,
  `text-overflow: ellipsis` / `-webkit-line-clamp`). Cała pozycja i tak klikalna
  do pełnych szczegółów.

### 3.5. Wykresy (liniowy/słupkowy)

- Wspólny partial `browse/autor_sekcje/_wykres_lata.html`: dane = lista
  `(rok, wartosc)` + `maks`. Jeśli `len(dane) > 10` → SVG `<polyline>` (liniowy),
  inaczej słupki (jak obecnie). Bezzależnościowo (czysty SVG/HTML).
- Buildery w `profil_autora_dane.py`:
  - `_wykres_lata` (jest) — liczba prac/rok.
  - `_wykres_pk_lata` (NOWY) — `prace_autora` grupuj po `rok`, suma `punkty_kbn`.
  - `_wykres_if_lata` (NOWY) — suma `impact_factor`/rok; **return None gdy suma=0**.
  Histogramy: pobierz pary `(id, rok, wartosc)` z `values_list` (DISTINCT z `id`
  neutralizuje duplikaty join `autorzy`), sumuj w Pythonie.
- Sekcje `wykres_pk_lata`, `wykres_if_lata` w rejestrze + szablony korzystają
  z `_wykres_lata.html` (przekaż `dane`, `maks`, `etykieta`).

### 3.6. Statystyki wg charakteru — klikalne → wyszukiwarka

- `statystyki_charakter.html`: każdy wiersz = mały `<form method="post"
  action="{% url 'bpp:browse_build_search' %}">` z `autor=<pk>` +
  `charakter_formalny=<pk>` (lub przycisk-link). Builder musi zwrócić też
  `charakter_formalny_id` (nie tylko nazwę) — zmień `_statystyki_charakter` na
  `values_list("id","charakter_formalny__id","charakter_formalny__nazwa")`.
- **DO WERYFIKACJI**: `BuildSearch` (`browse.py` ~632-691) obecnie obsługuje
  `autor`, `typy`, `jednostka`, `rok`, `suggested-title`. Trzeba dodać obsługę
  `charakter_formalny` → zmapować na multiseek query object dla charakteru
  formalnego (sprawdź `bpp/multiseek_registry.py` — czy jest CharakterFormalny
  QueryObject; jeśli nie, użyć `TypRekorduObject`/`charakter`). To jedyny
  fragment wymagający rozpoznania przed kodowaniem.

### 3.7. Historia zatrudnienia (lewa kolumna)

- Metoda `Autor.historia_zatrudnienia()` → `Autor_Jednostka.objects.filter(
  autor=self).select_related("jednostka","funkcja").order_by("-rozpoczal_prace")`.
  (Model `Autor_Jednostka` w `bpp/models/autor.py` ~545: pola `jednostka`,
  `rozpoczal_prace`, `zakonczyl_prace`, `funkcja`, `podstawowe_miejsce_pracy`.)
- Partial w lewej kolumnie: lista „Jednostka — od–do (funkcja)". Pominąć wiersze
  bez dat lub pokazać „obecnie" gdy brak `zakonczyl_prace`.

### 3.8. Self-service autora (Faza 2, zawężona)

Autor edytuje TYLKO biogram (MD/HTML + live preview) i zdjęcie (upload+podgląd).
Brak edytora układu po stronie autora. Gate: zalogowany + `request.user.autor`.
Widok w „Mój profil" (`bpp:profil-uzytkownika`).

## 4. Otwarte / do decyzji później

- Edytor kafelkowy (drag-drop) układu prawej kolumny w `UczelniaAdmin` — MVP to
  JSON w textarea; ładny kafelkowy UI to osobne zadanie.
- Eksport zbiorczy BibTeX/RIS — Faza 2.
- Próg „10 lat" i liczba linii line-clamp — wartości wstępne, do kalibracji
  wizualnej.

## 5. Po implementacji

- `make baseline-update` **przy scalaniu** (migracje 0444 + 0445) — commit
  `baseline-sql/baseline.sql` + `baseline.meta.json`. NIE w branchu równolegle.
- `grunt build` po zmianach SCSS (skompilowane CSS jest poza gitem — kontrakt
  build-time; commituj tylko źródła SCSS).
- ruff/ruff-format + djLint przez pre-commit; CI „Lint changed files" odpala
  ruff-format na zmienionym zakresie z `--exit-non-zero-on-fix` → KAŻDY nowy
  plik .py musi być pre-formatowany (`uv run ruff format <plik>`), łącznie z
  migracjami Django (mają długie linie).
