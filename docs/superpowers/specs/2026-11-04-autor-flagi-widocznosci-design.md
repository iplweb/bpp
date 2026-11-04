# Rozdzielenie `Autor.pokazuj` na flagi widoczności — projekt

Data: 2026-11-04

## Dlaczego

Rollbar (#5235 i pokrewne, bpp.umlub.pl / apoz / piwet) zgłasza tysiące
`Http404` na `/bpp/autor/<slug>/`. Przyczyna:

- commit #899 (`73fc5216e`, 2026-10-24) sprawił, że `AutorView` zwraca 404
  dla autora z `pokazuj=False` każdemu poza redakcją (`moze_wprowadzac_dane`);
- tymczasem `pokazuj` z założenia znaczyło tylko „pokazuj na stronach
  jednostek oraz w rankingu” (help_text pola), a takich autorów jest dużo
  (UML: 28 320 z 67 891, w tym 25 892 obcych, jednostka 118);
- ci autorzy są dalej linkowani: opis pracy (`browse/praca_tabela.html:33`),
  globalne wyszukiwanie (nie filtruje po `pokazuj`), sitemap
  (`django_bpp/sitemaps.py` `AutorSitemap` — bez filtra) i inne → użytkownicy
  i boty trafiają na 404.

Jedna flaga obsługuje dziś kilka różnych decyzji. Rozdzielamy ją na flagi,
z których każda robi dokładnie to, co mówi jej nazwa.

## Cele

- Strona autora przestaje zwracać 404 dla autorów, których nikt świadomie nie
  schował (czyli dla wszystkich istniejących po migracji).
- Redakcja może osobno sterować: stroną jednostki, rankingiem, globalnym
  wyszukiwaniem, indeksem, API i samą stroną autora.
- Nigdzie na stronach publicznych nie generujemy linku do strony autora,
  która zwróci 404.

## Nie-cele

- Zmiana reguł widoczności rekordów (statusy korekty — `ukryte_statusy`).
- Zmiana `pokazuj_siec_powiazan` / `pokazuj_poprzednie_nazwiska` /
  `pokazuj_opis` — zostają jak są.

## Anty-cele

- Link na stronie publicznej prowadzący do 404 (to jest dokładnie dzisiejszy
  błąd).
- Cicha utrata decyzji redakcji: kto dziś ma `pokazuj=False`, nadal nie jest
  pokazywany na stronie jednostki ani w rankingu.

## Model — nowe pola `Autor` (decyzje usera)

| Pole | Default | Po migracji | Znaczenie |
|---|---|---|---|
| `pokazuj_na_stronie_jednostki` | True | = stare `pokazuj` | autor na listach autorów jednostki |
| `pokazuj_w_rankingu` | True | = stare `pokazuj` | autor w rankingu autorów |
| `pokazuj_w_wyszukiwaniu` | True | True | autor w publicznym globalnym wyszukiwaniu |
| `pokazuj_w_indeksie` | True | = stare `pokazuj` | autor na alfabetycznej liście `/bpp/autorzy/` |
| `pokazuj_w_api` | True | = stare `pokazuj` | pełne dane autora w `/api/v1/` i CERIF/OAI |
| `pokazuj_strone_autora` | True | True | strona `/bpp/autor/<slug>/` istnieje publicznie |

Stare pole `pokazuj` jest **usuwane** (migracja: AddField ×6 → RunPython
kopiujący `pokazuj` do `pokazuj_na_stronie_jednostki`, `pokazuj_w_rankingu`, `pokazuj_w_indeksie` i `pokazuj_w_api` → RemoveField). Migracje w `bpp`
po `0499`. Po scaleniu: `make baseline-update`.

### Walidacja (decyzja usera)

`pokazuj_strone_autora=False` jest dozwolone **tylko** gdy
`pokazuj_w_wyszukiwaniu=False` i `pokazuj_w_indeksie=False`. W przeciwnym
razie `Autor.clean()` rzuca `ValidationError` na polu
`pokazuj_strone_autora` z komunikatem w stylu „Aby schować stronę autora,
najpierw wyłącz pokazywanie w wyszukiwaniu i w indeksie”. Bez automatycznego
wyłączania pozostałych flag. Dodatkowo `CheckConstraint` w bazie (to samo
warunkiem), żeby `update()`/akcje masowe nie obeszły reguły.

## Zachowanie — gdzie która flaga działa

Reguła ogólna (jak dziś): redakcja (`moze_wprowadzac_dane`) widzi wszystko;
flagi dotyczą odbiorcy publicznego (anonim, zwykły zalogowany, `request=None`).

- **Strona autora** (`AutorView`): 404 tylko gdy
  `pokazuj_strone_autora=False` (i nie-redakcja). Eksport BibTeX/RIS autora
  (`eksport_autora._autor_dla_eksportu`) i sieć powiązań
  (`powiazania_autorow.views._autor_centralny`) — ta sama reguła co strona.
- **Linki do strony autora** na stronach publicznych: gdy
  `pokazuj_strone_autora=False`, renderujemy samo nazwisko (`zapisany_jako` /
  `str(autor)`) bez `<a>`. Dotyczy co najmniej: `browse/praca_tabela.html`,
  ranking (`ranking_autorow/views.py:151`), sieć powiązań (sąsiedzi),
  `global_nav.py`, `api_v1/viewsets/recent_author_publications.py`. Widoki
  wyłącznie dla redakcji (ewaluacja_*, deduplikator, raport_slotow,
  import_*) bez zmian.
- **Strona jednostki** (`Jednostka` metody w `models/jednostka.py:393/451/463`):
  `pokazuj_na_stronie_jednostki=True`.
- **Ranking** (`ranking_autorow/views.py:293`): `pokazuj_w_rankingu`.
- **Globalne wyszukiwanie** (`search_services.globalne_wyszukiwanie_autora`):
  w publicznym wyszukiwaniu odfiltrować `pokazuj_w_wyszukiwaniu=False`; admin
  search (`uczelnia=None`, ścieżka redakcji) bez filtra.
- **Indeks** `pokazuj_w_indeksie`: alfabetyczna lista `/bpp/autorzy/`
  (`AutorzyView.get_queryset` + `available_letters`, `browse.py:730/747`)
  — wyłącznie ta lista (decyzja usera); sitemap NIE zależy od tej flagi.
- **Sitemap** (`AutorSitemap`): zawsze pomija `pokazuj_strone_autora=False`
  (inaczej sitemap wskazuje 404).
- **API** (`api_v1/viewsets/autor.py`): autor z `pokazuj_w_api=False` nie
  znika (żeby hiperłącza z publikacji nie prowadziły do 404) — zwraca
  okrojony obiekt: `id`, `url`/self-link i `"dane_ukryte": true`, pozostałe
  pola pominięte. Dotyczy listy i detalu. Redakcja (`widzi_dane_osobowe`)
  dostaje pełny obiekt. `Autor_JednostkaViewSet` (filtr
  `autor__pokazuj=True`) → `autor__pokazuj_w_api=True`.
  `NagrodaViewSet` i `recent_author_publications` → `pokazuj_w_api`.
- **Eksport CERIF/OAI** (`cerif_export/providers/osoby.py` itd.):
  `pokazuj_w_api` (to kanał maszynowy, jak API).
- **Autocomplete przypisań dyscyplin w zgłoszeniach**
  (`autocomplete/authors.py:514`) i podrzędnej publikacji habilitacyjnej
  (`:412`): `pokazuj_w_wyszukiwaniu`.
- **`Uczelnia.nowy_autor_z_formularza_pokazuj`** (`Autor` tworzony z
  autocomplete, `models/autor.py:150`): ustawia obie flagi
  `pokazuj_na_stronie_jednostki` i `pokazuj_w_rankingu` (to było jego
  znaczenie). Nazwa pola uczelni zostaje; aktualizacja help_text.
- **Admin**: sześć pól w fieldsetach `AutorAdmin` (zamiast `pokazuj`),
  `list_filter` dla najważniejszych. Akcje „Pokaż/Ukryj wybranych autorów”
  (`admin/actions.py`) ustawiają `pokazuj_na_stronie_jednostki` +
  `pokazuj_w_rankingu` (zachowanie jak dziś).
- **DjangoQL** (`djangoql_schema.py` `_VISIBLE_WHEN_TRUE`): `pokazuj` jest
  generycznym słowem-kluczem — sprawdzić, czy nowe pola `pokazuj_*` nie
  wymagają wpisów; schemat zapytań dostaje nowe pola zamiast `pokazuj`.
- **`widoczni_autorzy()`** (`bpp/util/ukryte_statusy.py`) dostaje parametr
  flagi zamiast `lookup="pokazuj"` (np. `flaga="pokazuj_strone_autora"`,
  z obsługą prefiksu `autor__`).
- **`powiazania_autorow/queries.py`** (`_widoczni_autorzy`, `inny.pokazuj`):
  sąsiedzi w sieci — `pokazuj_strone_autora` (sąsiad bez strony nie jest
  klikalny/węzłem).

Cache publiczny: zmiana flag autora musi unieważniać `cache_publiczny`
(sprawdzić, czy zapis `Autor` już podbija generację; jeśli nie — dodać).

## Testy

- Migracja danych: `pokazuj=False` → cztery flagi (jednostka, ranking, indeks, api) False; `pokazuj_w_wyszukiwaniu` i `pokazuj_strone_autora` True.
- Walidacja + CheckConstraint.
- Każde miejsce z listy wyżej: test anonim vs redakcja.
- Regresja błędu: autor z `pokazuj_na_stronie_jednostki=False` ma działającą
  stronę (200), a link w opisie pracy prowadzi do niej.
- Autor ze schowaną stroną: brak `<a>` w opisie pracy, brak w sitemap.
- Ok. 23 pliki testów odwołują się dziś do `pokazuj` — do przepięcia.

## Wydanie

Newsfragment `feature` w `src/bpp/newsfragments/`. Komentarz w Rollbar
#5235 po wdrożeniu (boty będą jeszcze chwilę pytać o stare URL-e, ale po
zmianie strony odpowiadają 200).

## Rozstrzygnięte przez usera po przeglądzie

1. `pokazuj_w_api` i `pokazuj_w_indeksie` po migracji = stare `pokazuj`
   (default dla nowych autorów: True). Nikt dziś ukryty nie staje się
   widoczny w API/CERIF/indeksie.
2. „Indeks” = tylko alfabetyczna lista `/bpp/autorzy/`.

## Uzupełnienia po przeglądzie (moje decyzje)

- **Współautorzy na profilu autora** (`bpp/profil_autora_dane.py:359`,
  `_wspolautorzy`, filtr `*_author__pokazuj`): współautor zostaje na liście;
  link tylko gdy `pokazuj_strone_autora=True`, inaczej samo nazwisko.
- **CERIF lista autorów** (`cerif_export/cerif/wspolne.py:344`,
  `cerif/project.py:93`): ta sama reguła co `osoby.py` → `pokazuj_w_api`
  (nazwisko na liście zostaje, jak dziś).
- **Filtrowanie w API**: dla nie-redakcji filtry i wyszukiwanie
  (`?nazwisko=`, ORCID itd.) działają tylko na autorach z
  `pokazuj_w_api=True` — gdy w żądaniu jest jakikolwiek parametr filtra,
  autorzy z `pokazuj_w_api=False` są wykluczani z wyniku. Okrojony obiekt
  `dane_ukryte` pojawia się tylko w niefiltrowanej liście i w detalu (inaczej
  dopasowanie po nazwisku ujawniałoby tożsamość ukrytego autora).

## Decyzje podjęte przeze mnie (do sprawdzenia)

- API: okrojony obiekt `dane_ukryte` także na liście (nie tylko detal).
- CERIF/OAI, nagrody, ostatnie publikacje → `pokazuj_w_api`.
- Eksport BibTeX/RIS i sieć powiązań → `pokazuj_strone_autora`.
- Autocomplete'y zgłoszeń → `pokazuj_w_wyszukiwaniu`.
- Akcje admina pokaż/ukryj i `nowy_autor_z_formularza_pokazuj` → dwie
  flagi następczyni starego `pokazuj`.
- `CheckConstraint` w bazie oprócz walidacji formularza.
