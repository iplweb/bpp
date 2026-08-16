# Soft-delete faza 05b: nagrobki dla konsumentów przyrostowych

> Spec zatwierdzony 2026-08-15. Wydzielony z fazy 05 decyzją właściciela
> 2026-08-10 (plan fazy 05 miał nagrobki w banerze zakresu i **zero tasków**).
> Termin: **przed fazą 07** — dopóki kasowanie jest rzadkie, luka jest
> teoretyczna; faza 07 czyni kasowanie rutynowym.

## Problem

BPP wystawia korpus przyrostowo: OAI-PMH (`/cerif/`, profil OpenAIRE CRIS)
i REST (`/api/v1/`). Konsument, który raz pobrał rekord, **nie ma jak się
dowiedzieć, że rekord przestał być wystawiany** — po prostu przestaje
przychodzić. Kopia po jego stronie zostaje niespójna na zawsze.

`src/cerif_export/const.py:115` deklaruje dziś `DELETED_RECORD = "no"`. To
nie jest „brak funkcji", tylko **obietnica w `Identify`**: harvester ma
prawo założyć, że usunięć nie ogłaszamy, i nie pytać o nie przyrostowo.

## Zakres

**Dwa kanały, nie trzy.** Baner rozszerzenia zakresu z 2026-08-08 wymieniał
„OAI-PMH + odpowiednik w CERIF + REST". W rzeczywistości `cerif_export/urls.py`
ma **jedną** ścieżkę (`OAICerifView`), a w OAI-PMH rekord usunięty to **sam
nagłówek** ze `status="deleted"` i **zero metadanych** — payload CERIF-owy
z definicji nie powstaje. „Nagrobek CERIF" nie jest osobnym bytem.

W zakresie: **OAI-PMH** (7 niepustych setów) + **REST** (nowy endpoint).
Poza zakresem: zmiana formatu metadanych, kosz w adminie (faza 07),
`SoftDeleteLog` (faza 06).

## Decyzje (zatwierdzone)

| # | Decyzja | Uzasadnienie |
|---|---|---|
| D1 | Nagrobek = **dopełnienie ekspozycji**, nie tylko soft-delete | Rekord znika z feedu na cztery sposoby, dla harvestera nierozróżnialne. Nagrobki tylko dla kosza czyniłyby deklarację `deletedRecord` częściowo nieprawdziwą |
| D2 | `deletedRecord = "transient"` | Nie gwarantujemy trwałości nagrobka: husk może zniknąć (twarde kasowanie, czyszczenie kosza w fazie 07), a sety bez soft-delete nie mają trwałego śladu |
| D3 | REST dostaje **osobny endpoint** `/api/v1/usuniete/` z samym identyfikatorem | Symetria z OAI (nagrobek nie niesie treści) i brak ryzyka wycieku huska, który usunięto właśnie dlatego, że był błędny lub zawierał dane osobowe |
| D4 | Nagrobki we **wszystkich 7 niepustych setach** | `deletedRecord` deklaruje się dla CAŁEGO repozytorium; w setach pominiętych deklaracja byłaby nieprawdziwa |
| D5 | REST znaczy **węziej** niż OAI: `/api/v1/usuniete/` to rekordy **z kosza** | REST nie składa obietnicy `deletedRecord`. Rozciąganie dopełnienia na modele API wymaga zdefiniowania reguł ekspozycji per model API — osobna praca |

### Cztery drogi zniknięcia (uzasadnienie D1)

`widoczne_wydawnictwa()` (`providers/publikacje.py:85`) odfiltrowuje rekord, gdy:

1. trafił do kosza (`.objects` pomija husk — faza 02),
2. `nie_eksportuj_przez_api=True`,
3. `status_korekty` zmieniony na ukryty w kanale `cerif`,
4. ostatni autor z tej uczelni odpięty (scope tenanta przez `autor_rekordu_klass`).

## Architektura

### Rozszczepienie przynależności i ekspozycji

Predykat widoczności skleja dziś dwie różne rzeczy. **Dopełniać wolno tylko
ekspozycję.** Naiwne „wszystko minus widoczne" wystawiłoby w multi-hosted
nagrobki dla rekordów **innych uczelni** — `widoczne_jednostki()` filtruje
`uczelnia=uczelnia` bezpośrednio, więc dopełnienie objęłoby cudze jednostki.
To wyciek identyfikatorów i lawina szumu.

Dochodzi jedna metoda kontraktu providera:

```python
def przynaleznosc(self, uczelnia, model):
    """Rekordy TEGO tenanta — także niewidoczne i te w koszu.

    Wyłącznie atrybucja tenanta; ŻADNYCH reguł ekspozycji
    (`nie_eksportuj_przez_api`, `status_korekty`, `widoczna`, `pokazuj`,
    przełączniki `Uczelnia.eksport_cerif_*`). Te należą do `queryset()`
    i to ich dopełnienie daje nagrobki.
    """
```

Nagrobki liczy **klasa bazowa** (providerzy implementują tylko `przynaleznosc`):

```
nagrobki(uczelnia, model) = przynaleznosc(uczelnia, model) − widoczne(uczelnia, model)
```

**Dwa rodzaje providerów.** Część setów ma atrybucję **własną** (publikacje,
patenty, osoby, jednostki, projekty, finansowanie — bezpośredni FK albo model
autorstwa). Część ma ją **pochodną**: `widoczne_konferencje()` to konferencje
wskazywane przez *widoczne* publikacje, a `widoczni_grantodawcy()` —
instytucje finansujące *widoczne* projekty.

Dla providerów pochodnych `przynaleznosc` powstaje przez podmianę wewnętrznego
zbioru: „konferencje wskazywane przez publikacje **należące** do tej uczelni"
zamiast „przez publikacje **widoczne**". Dopełnienie daje wtedy nagrobek dla
konferencji, do której prowadziły wyłącznie publikacje, które przestały być
widoczne — i to jest dokładnie pożądane zachowanie, bo taka konferencja realnie
znika z feedu.

**Przynależność historyczna.** Dla publikacji i patentów `przynaleznosc`
idzie przez `autor_rekordu_klass.global_objects` — czyli **z koszem
autorstw** (modele `*_Autor` mają `BppAutorstwoSoftDeleteMixin` od fazy 02).
Dzięki temu rekord, któremu odpięto ostatniego autora z naszej uczelni,
pozostaje „kiedyś nasz" i dostaje nagrobek, zamiast zniknąć po cichu.
To pokrywa drogę zniknięcia nr 4 w przypadku, gdy autorstwo skasowano;
gdy autorstwo **przepięto** (zmiana jednostki na inną uczelnię), śladu nie
ma i nagrobek nie powstanie — patrz „Ograniczenia".

### Stronicowanie: jeden strumień, nie dwa

`ProviderEncji.strona()` stronicuje keysetem po
`(COALESCE(ostatnio_zmieniony, EPOKA), pk)`. **Zmieniamy wyłącznie źródło**:
paginujemy `przynaleznosc` (nadzbiór) zamiast `queryset`. Dla każdej strony
jedno dodatkowe, tanie zapytanie ustala zbiór widocznych PK; obiekt spoza
niego dostaje nagłówek `status="deleted"` bez `<metadata>`.

**Dlaczego NIE drugi przebieg po żywych rekordach:** `resumptionToken` niesie
kursor `(datestamp, pk)` i zakłada **jeden** porządek po datestampie. Dwa
strumienie znaczą dwa kursory albo nagrobki poza porządkiem — a wtedy
`from`/`until` przestaje działać przyrostowo, czyli psujemy dokładnie to,
co ta faza naprawia.

Paginowanie nadzbioru zachowuje niezmiennik: jeden porządek, jeden kursor,
nagrobek to po prostu rekord, dla którego nie budujemy metadanych. Blizny
z `z_datestampem()` (`Trunc` do sekundy, `tzinfo=UTC` — obie zapisane po
realnych duplikatach na granicy strony) działają dalej bez zmian.

`przynaleznosc()` niesie te same `select_related`/`prefetch_related` co
`queryset()`. Prefetch na husku jest nieszkodliwy, a alternatywa (ponowne
pobranie żywych z prefetchami) dokładałaby zapytanie na stronę.

### Punkty dotknięcia

| plik | zmiana |
|---|---|
| `providers/base.py` | `przynaleznosc()` w kontrakcie; `nagrobki()`; `strona()`, `pojedynczy()`, `najstarszy_datestamp()` na nadzbiorze |
| `providers/{publikacje,osoby,patenty,jednostki,projekty,konferencje,finansowanie}.py` | implementacja `przynaleznosc()` |
| `providers/puste.py` | `przynaleznosc()` zwraca pusto (set bez zawartości) |
| `oai/czasowniki.py` | `_naglowek(..., usuniety=False)`; `_dopisz_rekordy` pomija `<metadata>` dla nagrobka; `_znajdz_rekord` szuka w nadzbiorze |
| `const.py` | `DELETED_RECORD = "transient"` |
| `api_v1/` | nowy viewset + routing `/api/v1/usuniete/` |

### Zachowanie czasowników OAI

- **`Identify`** → `<deletedRecord>transient</deletedRecord>`.
- **`ListIdentifiers`** → nagrobek to ten sam nagłówek + `status="deleted"`.
- **`ListRecords`** → `<record><header status="deleted">…</header></record>`,
  **bez** `<metadata>`.
- **`GetRecord`** na rekordzie niewidocznym, ale należącym do tenanta →
  rekord z nagłówkiem `status="deleted"` i bez metadanych, **zamiast**
  dotychczasowego błędu `idDoesNotExist`. Identyfikator spoza tenanta →
  `idDoesNotExist` bez zmian.
- **`earliestDatestamp`** liczony z nadzbioru (nagrobek też jest rekordem
  o dacie).

### REST: `/api/v1/usuniete/`

Read-only endpoint zwracający **wyłącznie** typ, klucz i znacznik czasu —
nigdy treści rekordu:

```json
{"model": "wydawnictwo_ciagle", "pk": 123, "usuniety_od": "2026-08-13T10:00:00Z"}
```

Źródło: `deleted_objects` modeli soft-delete (publikacje z fazy 02, `Autor`
z fazy 04). Filtr zakresowy po znaczniku czasu, spójny konwencją
z istniejącymi `DateTimeFromToRangeFilter` w `api_v1/viewsets/`. Scope
tenanta jak w pozostałych viewsetach (`Uczelnia.objects.get_for_request`).

## Ograniczenia i skutki uboczne (świadome)

- **Rekordy nigdy-niewidoczne też dostaną nagrobek.** Rekord od zawsze
  oznaczony `nie_eksportuj_przez_api` trafi do nagrobków, mimo że harvester
  nigdy go nie miał. Wg specyfikacji OAI to nieszkodliwe („niedostępny"),
  ale przy pierwszym pełnym harveście po wdrożeniu daje jednorazowy wolumen
  szumu. Alternatywa (trwały ślad „był wyeksportowany") wymagałaby nowej
  tabeli i zapisu na ścieżce read-only harvestu — odrzucona jako
  nieproporcjonalna.
- **⚠️ Wyłączenie `Uczelnia.eksport_cerif_osoby` wystawi nagrobki dla
  WSZYSTKICH autorów uczelni naraz.** `widoczni_autorzy()` zwraca wtedy
  `Autor.objects.none()`, więc dopełnienie obejmuje cały zbiór. To jest
  zachowanie **poprawne** — harvester ma te osoby usunąć, a przełącznik
  właśnie o to prosi — ale operator musi wiedzieć, że przestawienie go
  produkuje jednorazowy, bardzo duży wsad nagrobków. Do odnotowania
  w dokumentacji przełącznika.
- **Zmiana atrybucji tenanta bez śladu w koszu nie da nagrobka.** Gdy
  projekt zmieni `jednostka` na inną uczelnię albo autorstwo zostanie
  *przepięte* (a nie skasowane), rekord wypada z `przynaleznosc` i znika
  cicho — tak jak dziś. Pokrycie tego wymagałoby historii atrybucji.
- **Sety `projects` i `funding` w praktyce nie wygenerują nagrobków.**
  `widoczne_projekty()` i `widoczne_finansowania()` to czysta atrybucja bez
  reguł ekspozycji, a modele nie mają soft-delete → dopełnienie jest puste.
  Kontrakt i tak implementujemy (spójność, gotowość na przyszłe reguły).
  Uwaga: **`orgunits` nagrobki wygeneruje**, ale wyłącznie przez `Jednostka`
  (reguły `widoczna` i `nie_eksportuj_przez_api`). Trzeci model tego setu,
  `Instytucja_Finansujaca`, ma widoczność
  (`finansowanie__projekt__jednostka__uczelnia`) **równą** atrybucji, więc
  jego dopełnienie też jest puste — korekta ustalona przy pisaniu planu
  2026-08-16.
- **REST węższy niż OAI** (D5): rekord ukryty przez `nie_eksportuj_przez_api`
  dostanie nagrobek w OAI, ale nie pojawi się w `/api/v1/usuniete/`.

## Testy

Krytyczne (bez nich faza nie jest gotowa):

1. **Izolacja tenantów** — nagrobki uczelni A nigdy nie zawierają rekordów
   uczelni B. To ryzyko, które dopełnienie wnosi wprost.
2. **Cztery drogi zniknięcia → cztery nagrobki** — kosz, `nie_eksportuj_przez_api`,
   ukryty `status_korekty`, skasowane autorstwo ostatniego autora z uczelni.
3. **`resumptionToken` przez granicę żywy/nagrobek** — bez duplikatu i bez
   luki; osobno przypadek, gdy strona kończy się dokładnie na nagrobku.
   To tu żyły wcześniejsze bugi `Trunc`/`tzinfo`.
4. **`from`/`until` obejmuje nagrobki** — nagrobek wpada w okno po
   `ostatnio_zmieniony`, tak samo jak rekord żywy.

Pozostałe: `Identify` mówi `transient`; `ListRecords` nie emituje
`<metadata>` dla nagrobka i wynik waliduje się schematem OAI-PMH;
`GetRecord` na usuniętym zwraca nagrobek zamiast `idDoesNotExist`, a na
cudzym — nadal `idDoesNotExist`; `/api/v1/usuniete/` nie wypuszcza treści
huska i respektuje filtr zakresowy oraz scope tenanta.

## Zależności

- Faza 02 (publikacje `SoftDeleteModel`, kosz autorstw), faza 04 (`Autor`).
- Kontrakt PINNED z fazy 01: soft-delete bumpuje `ostatnio_zmieniony` —
  bez tego nagrobek nie wpadłby w okno `from`/`until`.
- **Nie** zależy od fazy 05a (wycofanie z PBN) ani od `SoftDeleteLog`
  z fazy 06.
