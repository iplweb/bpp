# Profil autora (edytowalny) + przebudowa podstrony autora — projekt

Data: 2026-06-18
Status: zatwierdzony do napisania planu implementacji

## 1. Cel

Dwie powiązane zmiany:

1. **Przebudowa publicznej podstrony autora** (`/autor/<pk>/`, `/autor/<slug>/`) —
   z dotychczasowej strony „metadane + formularz wyszukiwania" na stronę
   złożoną z **konfigurowalnych sekcji treści** (kolejność + widoczność +
   limity), renderowanych nad spójnym, stałym nagłówkiem tożsamości.
2. **Edytowalny profil autora** — autor (zalogowany użytkownik powiązany z
   rekordem `Autor`) może wgrać zdjęcie i biogram oraz ułożyć własną stronę:
   wybrać które sekcje, w jakiej kolejności i w jakiej liczbie pozycji mają się
   wyświetlać.

Dostarczane **fazowo**:

- **Faza 1 (PR1):** model danych + render publicznej strony + edycja w Django
  adminie. Wszyscy autorzy bez konfiguracji dostają układ domyślny.
- **Faza 2 (PR2):** self-service edytor w „Mój profil" (drag-drop, uploady,
  live preview, picker wyróżnionych prac) + eksport RIS.

## 2. Stan obecny (ustalenia ze zwiadu po kodzie)

- **Publiczna strona:** `AutorView(DetailView)` — `src/bpp/views/browse.py:145`,
  szablon `src/bpp/templates/browse/autor.html`, URL-e `src/bpp/urls.py:262,288`
  (oba `bpp:browse_autor`). Dziś renderuje metadane + formularz „Wyszukaj
  publikacje autora" (POST → `bpp:browse_build_search` → multiseek) + kod do
  embedowania. Nie listuje publikacji inline.
- **„Mój profil":** `ProfilUzytkownikaView(LoginRequiredMixin, TemplateView)` —
  `src/bpp/views/profile.py:5`, URL `profil/` (`bpp:profil-uzytkownika`),
  szablon `src/bpp/templates/bpp/profil_uzytkownika.html`. **Wyłącznie
  read-only** — brak jakiegokolwiek formularza edycji.
- **Powiązanie User↔Autor:** `BppUser.autor` OneToOneField (`related_name="user"`)
  — `src/bpp/models/profile.py:56-64`. Auto-dopasowanie po e-mailu/nazwisku:
  `BppUser.sprobuj_dopasowac_autora()` (`profile.py:80-115`).
- **Model `Autor`:** `src/bpp/models/autor.py:81`. Ma `opis`
  (`HTMLField`/TinyMCE, `autor.py:129`) + `pokazuj_opis` — pokazywany w
  nagłówku jako „Opis". **Brak** jakiegokolwiek pola na zdjęcie. Pillow
  zainstalowany; wzorzec ImageField: `Uczelnia.logo_www`
  (`src/bpp/models/uczelnia.py:96`, `upload_to="logo"`).
- **Dane publikacji:** zdenormalizowany cache `Rekord`
  (`src/bpp/models/cache/rekord.py`), `RekordManager.prace_autora(autor)`
  (`rekord.py:45`) → `filter(autorzy__autor=autor).distinct()`. Pola: `rok`,
  `charakter_formalny`, `zrodlo` (`rekord.py:217`, FK `bpp.Zrodlo`),
  `ostatnio_zmieniony` (`rekord.py:231`), punktacja z `ModelPunktowanyBaza`
  (`punkty_kbn`, `impact_factor`, ... — `src/bpp/models/abstract/scoring.py`,
  wszystkie indeksowane).
- **Punkty autora:** `Cache_Punktacja_Autora` (`src/bpp/models/cache/punktacja.py:51`,
  `managed=True`), pola `autor`, `rekord_id` (TupleField), `pkdaut`, `slot`.
- **Charakter pracy:** `Charakter_Formalny` (MPTT) — `charakter_ogolny`
  (`art`/`roz`/`ksi`/`xxx`, `src/bpp/const.py:32-35`) rozróżnia
  artykuł/rozdział/książkę/inne; modele źródłowe `Wydawnictwo_Ciagle`
  (artykuły) i `Wydawnictwo_Zwarte` (zwarte).
- **Dyscypliny:** `Autorzy.dyscyplina_naukowa` (`src/bpp/models/cache/autorzy.py:22,52`,
  FK `bpp.Dyscyplina_Naukowa`).
- **Współautorzy:** `AuthorConnection` (`src/powiazania_autorow/models.py:6`) —
  `primary_author`, `secondary_author`, `shared_publications_count`,
  `ordering=["-shared_publications_count"]`. Stored undirected (para
  uporządkowana po id), więc filtrować po obu stronach. Prekomputowany
  okresowo (Celery). **To dokładnie ten sam obiekt, który zasila wizualny
  browser „powiązania autorów 2D/3D"** (URL-e `/autor/<pk>/powiazania/`,
  `/powiazania/3d/`, JSON-y — `powiazania_autorow.views`, gejtowane przez
  `czy_pokazywac_siec_powiazan` w `browse.py:150-163`).
- **Raport autora:** `nowe_raporty`, slug `raport-autorow`, pk-linkowalny
  (`/nowe_raporty/raport-autorow/<autor_pk>/<od_roku>/<do_roku>/`),
  `nowe_raporty:raport_form` / `:raport_generuj` (`src/nowe_raporty/urls.py`).
  Widoczność: `DefinicjaRaportu.widoczny_dla(request)`
  (`src/nowe_raporty/models.py:115-128`); domyślnie publiczny, admin-konfigurowalny.
- **Sanityzacja / Markdown:** `nh3` użyty w `bpp.util.text.safe_html()`
  (`src/bpp/util/text.py:168`) — idiomatyczny sanitizer repo. Pakiet `markdown`
  3.10.2 zainstalowany (importowalny), bez istniejącego pipeline'u renderu.
- **Eksport cytowań:** BibTeX istnieje i jest reużywalny dla listy prac
  (`src/bpp/export/bibtex.py`, `export_to_bibtex()` `bibtex.py:507`, metody
  `.to_bibtex()` na modelach) — operuje na konkretnych obiektach
  `Wydawnictwo_*`/`Patent`/`Praca_*` (z `Rekord` przez `.original`).
  **RIS nie istnieje — net-new.**
- **Wyróżnione/wybrane publikacje:** koncept **nie istnieje**
  (`Autorzy.przypieta` dotyczy przypinania dyscypliny do PBN, nie wyróżniania
  prac). **Net-new model.**

## 3. Decyzje projektowe (zatwierdzone)

| Zagadnienie | Decyzja |
|---|---|
| Biogram | Nowe pola `biogram` + `biogram_format` (md/html). `opis` nietknięty. |
| Kto edytuje (Faza 2) | Każdy zalogowany z ustawionym `user.autor`. |
| Dostawa | Fazowo: Faza 1 render + admin, Faza 2 self-service. |
| Bloki metadanych | Zostają stałym nagłówkiem; edytor steruje tylko sekcjami treści. |
| Ranking „best" | Osobno `najlepsze_pk` (`-punkty_kbn`) i `najlepsze_if` (`-impact_factor`). |
| Limit list | 10/20/30/50, domyślnie 10, per sekcja listowa. |
| Zdjęcie | Awatar w nagłówku, kwadrat 400×400 (center-crop), zapis **WebP** q≈85, ≤5 MB. |
| Statystyki | Liczba prac wg charakteru formalnego (szczegółowo). |
| Link do raportu | 3 linki: bieżący rok, ostatnie 4 lata, szczegółowy formularz; widoczność wg `widoczny_dla`. |
| Układ domyślny | „biogram-najpierw". |
| Domyślne sugestie | ON: `wykres_lata` + `wspolautorzy`; reszta sugestii OFF. |
| `opis` vs `biogram` | `opis` zostaje w nagłówku; biogram to osobna sekcja. |
| Współautorzy | `AuthorConnection` (prekomputowany) + CTA do browsera 2D/3D. |

## 4. Model danych (Faza 1)

Nowa migracja w `src/bpp/migrations/` (NIE edytować istniejących).

### 4.1. Nowe pola na `Autor` (`src/bpp/models/autor.py`)

- `zdjecie = models.ImageField(upload_to="autor_zdjecia", null=True, blank=True)`
  — przetwarzane przy zapisie do kwadratu 400×400 WebP (patrz 7.3).
- `biogram = models.TextField(blank=True, default="")` — surowe źródło.
- `biogram_format = models.CharField(max_length=4, choices=[("md","Markdown"),
  ("html","HTML")], default="md")`.
- `uklad_profilu = models.JSONField(null=True, blank=True, default=None)` —
  `null` = układ domyślny; inaczej lista pozycji (patrz 6).

### 4.2. Nowy model `WybranaPublikacjaAutora`

Wyróżnione prace (ręcznie wybierane). Plik: `src/bpp/models/wybrana_publikacja.py`
(zarejestrowany w `src/bpp/models/__init__.py`).

```
autor        = FK(Autor, related_name="wybrane_publikacje", on_delete=CASCADE)
content_type = FK(ContentType, on_delete=CASCADE)
object_id    = PositiveIntegerField
publikacja   = GenericForeignKey("content_type", "object_id")
kolejnosc    = PositiveIntegerField(default=0)
class Meta: ordering = ["kolejnosc"]; unique_together = [(autor, content_type, object_id)]
```

Rozwiązywane do `Rekord` przez `(content_type_id, object_id)` lub do `.original`.
W Fazie 1 wypełniane przez admina (inline); w Fazie 2 przez picker self-service.

## 5. Rejestr sekcji (w kodzie)

Plik: `src/bpp/profil/sekcje.py`. Katalog typów sekcji żyje w kodzie; per-autor
JSON trzyma tylko kolejność/widoczność/limit. Dodanie sekcji = zmiana kodu, bez
migracji danych.

Każdy wpis rejestru: `klucz`, `nazwa`, `obowiazkowa: bool`, `ma_limit: bool`,
`domyslnie_widoczna: bool`, `template` (partial), funkcja
`pobierz_kontekst(autor, limit, request) -> dict|None` (zwraca `None`/pusty →
sekcja auto-ukryta).

| klucz | nazwa | obow. | limit | dom. ON | źródło |
|---|---|---|---|---|---|
| `biogram` | Biogram | nie | – | tak | `autor.biogram_html` |
| `wyszukiwarka` | Wyszukiwarka prac | **tak** | – | tak (wymuszone) | obecny POST→multiseek |
| `najlepsze_pk` | Najlepsze prace (punkty MNiSW) | nie | tak | tak | `prace_autora` `-punkty_kbn` |
| `najlepsze_if` | Najlepsze prace (Impact Factor) | nie | tak | tak | `prace_autora` `-impact_factor` |
| `najnowsze_artykuly` | Najnowsze artykuły | nie | tak | tak | wyd. ciągłe `-rok` |
| `najnowsze_zwarte` | Najnowsze książki / rozdziały | nie | tak | tak | wyd. zwarte `-rok` |
| `ostatnio_edytowane` | Ostatnio edytowane | nie | tak | tak | `-ostatnio_zmieniony` |
| `wybrane_publikacje` | Wybrane publikacje | nie | – | nie | `WybranaPublikacjaAutora` |
| `statystyki_charakter` | Statystyki wg charakteru | nie | – | tak | `Count` po `charakter_formalny` |
| `wykres_lata` | Publikacje w latach | nie | – | **tak** | `autor.prace_w_latach` |
| `punkty_lata` | Punkty / sloty w latach | nie | – | nie | `Cache_Punktacja_Autora` |
| `dyscypliny` | Udział dyscyplin | nie | – | nie | `Autorzy.dyscyplina_naukowa` |
| `zrodla` | Najczęstsze źródła / czasopisma | nie | tak | nie | `Rekord.zrodlo` |
| `wspolautorzy` | Najczęstsi współautorzy | nie | tak | **tak** | `AuthorConnection` + CTA 2D/3D |
| `eksport` | Eksport listy publikacji | nie | – | nie | `export_to_bibtex` (BibTeX; RIS w Fazie 2) |

Wszystkie zapytania listowe: `select_related("charakter_formalny","zrodlo",
"wydawca")`, twardy limit, świadome unikanie N+1.

## 6. Konfiguracja układu (`uklad_profilu`) i jej rozwiązywanie

### 6.1. Schemat JSON

Lista pozycji w kolejności wyświetlania:

```json
[
  {"klucz": "biogram", "widoczna": true, "limit": null},
  {"klucz": "wyszukiwarka", "widoczna": true, "limit": null},
  {"klucz": "najlepsze_pk", "widoczna": true, "limit": 10},
  ...
]
```

`limit ∈ {10,20,30,50}` tylko dla sekcji `ma_limit=True`; w przeciwnym razie
`null`.

### 6.2. Walidacja (`waliduj_uklad`)

- Klucze spoza rejestru → odrzucone.
- `limit` poza `{10,20,30,50}` dla sekcji listowej → korekta do 10.
- Sekcja `obowiazkowa` → `widoczna` wymuszone na `True`.

### 6.3. Rozwiązywanie (`rozwiaz_uklad(autor) -> list[SekcjaUkladu]`)

1. Start od kanonicznego porządku domyślnego (kolejność z tabeli w §5,
   z `domyslnie_widoczna`).
2. Jeśli `autor.uklad_profilu` niepuste: nadpisz kolejność/widoczność/limit dla
   znanych kluczy.
3. Sekcje z rejestru nieobecne w zapisanym configu → dołączone w pozycji
   kanonicznej z domyślami (forward-compat: nowo dodana sekcja pojawia się
   automatycznie).
4. Wymuś `widoczna=True` dla obowiązkowych.
5. Zwróć tylko `widoczna=True`; przy renderze dodatkowo odpadają sekcje, których
   `pobierz_kontekst` zwróci pusto (auto-ukrywanie).

**Układ domyślny** (biogram-najpierw, z domyślnymi sugestiami ON):
`biogram → wyszukiwarka → najlepsze_pk → najlepsze_if → najnowsze_artykuly →
najnowsze_zwarte → ostatnio_edytowane → statystyki_charakter → wykres_lata →
wspolautorzy`. Pozostałe (`wybrane_publikacje`, `punkty_lata`, `dyscypliny`,
`zrodla`, `eksport`) istnieją w rejestrze, domyślnie OFF.

## 7. Render publicznej strony (Faza 1)

### 7.1. `AutorView` (`src/bpp/views/browse.py`)

`get_context_data`:
- `sekcje = rozwiaz_uklad(self.object)` z policzonym kontekstem każdej widocznej
  sekcji (leniwie), z auto-ukrywaniem pustych.
- `raport_links` — jeśli `DefinicjaRaportu.objects.filter(slug="raport-autorow")`
  istnieje i `.widoczny_dla(request)`:
  - bieżący rok: `…/raport-autorow/<pk>/<rok>/<rok>/`
  - ostatnie 4 lata: `…/raport-autorow/<pk>/<rok-3>/<rok>/`
  - szczegółowy: `nowe_raporty:raport_form` (slug `raport-autorow`).
  `rok = timezone.now().year`. Brak `DefinicjaRaportu` → brak linków (guard).

### 7.2. Szablony

- `src/bpp/templates/browse/autor.html` — refaktor: stały nagłówek
  (zdjęcie-awatar + nazwisko + jednostka + ORCID/PBN/metryki/stopnie/cytowania —
  jak dziś, **`opis` zostaje**) + blok linków raportu + pętla po `sekcje`
  renderująca `{% include sekcja.template %}`.
- `src/bpp/templates/browse/autor_sekcje/<klucz>.html` — partial na sekcję.
- Ikony: frontend publiczny → Foundation-Icons (`<span class="fi-icon"/>`).
- `wspolautorzy`: lista top-N (linki do podstron + `shared_publications_count`)
  + CTA „Zobacz pełną sieć powiązań" → `bpp:browse_autor_powiazania` /
  `…_3d` (gdy `ma_powiazania`).

### 7.3. Przetwarzanie zdjęcia

`src/bpp/util/obrazy.py`: `przetworz_zdjecie_autora(plik) -> ContentFile`:
- walidacja ≤5 MB i typu obrazu (na poziomie formularza),
- Pillow: `ImageOps.exif_transpose`, center-crop do kwadratu, resize 400×400,
  zapis WebP q≈85.
Wołane z save'a admina (Faza 1) i formularza self-service (Faza 2). Reużywalna
funkcja, jeden punkt prawdy.

### 7.4. Render biogramu

`Autor.biogram_html` (`cached_property`): `md` →
`markdown.markdown(biogram)` → `safe_html(...)`; `html` → `safe_html(biogram)`.
Jeden punkt sanityzacji (nh3, `bpp.util.text.safe_html`).

## 8. Admin (Faza 1)

`src/bpp/admin/` (admin `Autor`):
- Pola `zdjecie` (z podglądem miniatury), `biogram` + `biogram_format`.
- Edytor układu: formularz listujący sekcje z checkboxem widoczności, polem
  kolejności i selectem limitu; zapis do `uklad_profilu` (ta sama logika
  walidacji/serializacji reużyta w Fazie 2).
- Inline `WybranaPublikacjaAutora` z autocomplete prac.
- Admin używa emoji (bez Foundation Icons) zgodnie z konwencją repo.

## 9. Faza 2 (osobny PR)

- `src/bpp/views/profil_edycja.py` — widok edycji w „Mój profil", gate:
  `LoginRequiredMixin` + wymóg `request.user.autor`.
- Edytor: drag-drop kolejności (sprawdzić istniejący JS sortowania w repo przed
  dodaniem zależności), przełączniki widoczności, selecty limitów, upload
  zdjęcia z podglądem, edytor biogramu z przełącznikiem MD/HTML + **live
  preview** (render serwerowy AJAX-em przez ten sam pipeline), picker
  wyróżnionych prac (autocomplete add/remove/reorder).
- Eksport zbiorczy: `/autor/<pk>/eksport.bib` (BibTeX, reużycie
  `export_to_bibtex`) i `/autor/<pk>/eksport.ris` (**RIS net-new**). Świadomy
  limit/stream dla autorów z dużą liczbą prac.
- „Mój profil" (`profil_uzytkownika.html`) zyskuje link „Edytuj swoją stronę".

## 10. Testy (pytest + `model_bakery.baker`, bez unittest)

- Model: przetwarzanie zdjęcia (rozmiar/crop/format WebP, korekta EXIF),
  walidacja ≤5 MB; sanityzacja biogramu (XSS usunięty, MD wyrenderowany,
  niedozwolone tagi wycięte); walidacja i rozwiązywanie układu (domyślny vs
  override; forward-compat nowej sekcji; wymuszenie obowiązkowej).
- Widok: kolejność sekcji zgodna z configiem; wyszukiwarka zawsze obecna;
  auto-ukrywanie pustych sekcji; gating linków raportu (anon bez / uprawniony z);
  CTA współautorów tylko gdy `ma_powiazania`.
- Faza 2: gate edycji (obcy autor / brak `user.autor` → odmowa), zapis układu,
  eksport BibTeX/RIS.

## 11. Migracje i baseline

- Nowa migracja: pola na `Autor` + model `WybranaPublikacjaAutora`.
- Po migracjach (raz, przy scalaniu): `make baseline-update` — odświeżenie
  `baseline-sql/baseline.sql` + `baseline.meta.json` (commit obu). Nie odświeżać
  w równoległych branchach.

## 12. Dostawa (worktree + PR)

Praca w worktree jako siostrzany katalog (zgodnie z CLAUDE.md), **nie** w `bpp/`:

```
git worktree add ~/Programowanie/bpp-profil-autora -b feature/profil-autora
```

Zmiany trafiają do PR-a (osobny PR na Fazę 1 i Fazę 2).

## 13. Świadomie poza zakresem (YAGNI)

- RIS i eksport zbiorczy — dopiero Faza 2.
- Self-service picker / drag-drop / live preview — Faza 2.
- Pole „zainteresowania badawcze" — odrzucone w brainstormingu.
- Własna nowa wizualizacja współautorów — reużywamy istniejący browser 2D/3D.
- Migracja `opis` → `biogram` — `opis` zostaje niezależny.
