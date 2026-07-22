# Domknięcie pętli: zgłoszenie publikacji ↔ importer prac

**Zgłoszenie:** FD#443 „Oznaczanie zgłoszeń jako zużyte"
(<https://iplweb.freshdesk.com/a/tickets/443>), zgłaszający Jan Bichałowicz
(`jbihalowicz@apoz.edu.pl`), klient `bpp.apoz.edu.pl`.
Powiązane: FD#430 (przycisk „Użyj importera" nad tabelą), FD#425 (oryginał).

**Data:** 2026-07-22 · **Wersja bazowa:** `202607.1398` · **Gałąź:**
`fix-fd443-zgloszenie-zaimportowane`

---

## 1. Problem

Operator otwiera zgłoszenie publikacji w adminie, klika „Użyj importera",
przechodzi przez importer i tworzy rekord. Zgłoszenie zostaje w stanie
`NOWY` — wygląda, jakby nikt się nim nie zajął. Nie widać, że praca została
już zaimportowana, kto to zrobił ani kiedy.

Przyczyną nie są trzy osobne braki, tylko **jedna przerwana krawędź**:
`ImportSession` nie wie, że uruchomiono ją ze zgłoszenia. Link „Użyj
importera" jest bezstanowy — przekazuje wyłącznie `?provider=&identifier=`
(`src/zglos_publikacje/admin/zgloszenie_publikacji.py:389-417`), po czym
kontekst ginie.

### Co już jest w kodzie (i jest martwe)

| Element | Stan |
|---|---|
| `Zgloszenie_Publikacji.odpowiednik_w_bpp` — GenericFK do rekordu (`models.py:82`) | pole istnieje, **nic w `src/` go nie zapisuje** |
| `Statusy.ZAAKCEPTOWANY = 1` („dodany do bazy BPP") | **nigdy nie ustawiany programowo** |
| `ImportSession.created_by` (`wizard.py:190-198`), `created_record` (`tasks.py:226-231`) | wypełniane poprawnie |
| `_find_matching_zgloszenie()` (`importer_publikacji/views/authors.py:148-188`) | heurystyka DOI → tytuł, używana **wyłącznie** do prefilla dyscyplin (`:200`) |

### Pułapki potwierdzone w kodzie

1. **`ImportSession.modified` to `auto_now=True`** (`models.py:188`) — znaczy
   „kiedy ostatnio cokolwiek ruszyło wiersz", nie „kiedy zaimportowano".
   `mark_stalled()` (`models.py:305-321`) przesuwa tę datę. Moment importu
   wymaga **jawnego pola**.
2. **`IndexView` nie tworzy sesji.** Renderuje tylko `FetchForm`
   (`wizard.py:87-126`). Sesję zakłada `FetchView.post` (`wizard.py:205-281`)
   przez `_start_import_session` (`:183-202`). Parametr GET nieprzeniesiony
   ukrytym polem formularza **ginie bezpowrotnie**.
3. **Soft-delete nie usuwa wiersza.** `Zgloszenie_Publikacji` dziedziczy
   `SoftDeleteModel` (`models.py:61`); kasowanie ustawia `deleted_at`.
   `on_delete=SET_NULL` nigdy się nie uruchomi, a dostęp przez FK idzie
   `_base_manager`, który **nie filtruje usuniętych**.
4. **`report_progress` rzuca `ValueError` na nieznanym etapie**
   (`progress.py:49-50`), a wagi `FETCH_STAGES` sumują się do 100. Nie wolno
   dokładać nowych nazw etapów — trzeba reużyć istniejący `prefill_zgl`.
5. **`Zgloszenie_Publikacji` nie ma pola `uczelnia`** — zapytanie po DOI jest
   z natury cross-uczelniane.

## 2. Cel

Po zakończeniu importu uruchomionego ze zgłoszenia:

1. zgłoszenie automatycznie dostaje status **`ZAIMPORTOWANY`** i przestaje
   wyglądać na wymagające obsługi,
2. przy zgłoszeniu widać **kto** i **o której** je zaimportował oraz **jaki
   rekord** powstał,
3. operator dostaje **informację zwrotną** w trzech miejscach: na stronie
   zgłoszenia, na stronie wyników importera i jako flash message.

## 3. Decyzje projektowe

| # | Decyzja | Uzasadnienie |
|---|---|---|
| D1 | Nowy status `ZAIMPORTOWANY = 6`, nie ożywianie `ZAAKCEPTOWANY = 1` | odróżnia „dodane importerem" od „dodane ręcznie"; słowo z prośby klienta. Wartość 6 jest wolna (`Statusy` kończy się na `SPAM = 5`) |
| D2 | Audyt denormalizowany na zgłoszeniu (`zaimportowano`, `zaimportowal`) | filtrowalny i sortowalny na liście; przeżywa skasowanie sesji importu |
| D3 | Jawne pole czasu, nie `auto_now` | `ImportSession.modified` nie jest wiarygodnym znacznikiem zakończenia |
| D4 | Wiązanie jawne (`?zgloszenie=`) + fallback po DOI | determinizm; DOI to identyfikator mocny |
| D5 | Dopasowanie po **tytule wykluczone** z wiązania | dwa zgłoszenia o tym samym tytule → oznaczono by przypadkowe (korupcja danych) |
| D6 | Przy ≥2 kandydatach — operator wybiera, system nie zgaduje | jawny wybór zamiast cichego pominięcia |
| D7 | Bez soft-delete zgłoszenia po imporcie | jawny status niesie tę samą informację, a zachowuje ślad na liście |
| **D8** | **Kandydaci po DOI ograniczeni do uczelni sesji importu** | `Zgloszenie_Publikacji` nie ma `uczelnia`; bez zawężenia baner pokazałby tytuł i e-mail zgłaszającego z cudzej uczelni, a auto-wiązanie oznaczyłoby cudze zgłoszenie |
| **D9** | **`WYMAGA_ZMIAN` wykluczony z auto-wiązania** | zgłoszenie jest w rękach autora (aktywny `kod_do_edycji`); przestemplowanie go w trakcie edycji zabrałoby mu pracę |
| **D10** | **Zapis zwrotny w osobnym `transaction.atomic` razem z `COMPLETED`** | transakcja tworząca rekord (`publikacja.py:327`) commituje przed powrotem do taska; „ta sama transakcja" i „tuż po COMPLETED" wykluczają się |

## 4. Zmiany w modelach

### 4.1 `zglos_publikacje` — migracja `0027` (ostatnia istniejąca: `0026`)

Na `Zgloszenie_Publikacji` (`src/zglos_publikacje/models.py:60`):

| Pole | Definicja |
|---|---|
| `Statusy.ZAIMPORTOWANY` | `= 6, "zaimportowany przez importer prac"` |
| `zaimportowano` | `DateTimeField("Zaimportowano", null=True, blank=True, db_index=True)` |
| `zaimportowal` | `FK(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="+", verbose_name="Zaimportował")` |
| `odpowiednik_w_bpp` | bez zmian — istniejący GenericFK, zaczyna być zapisywany |

`SET_NULL` na `zaimportowal`: skasowanie konta operatora nie może kasować ani
blokować zgłoszenia.

### 4.2 `importer_publikacji` — migracja `0020`

Numer podany jawnie: historia tej aplikacji ma już zdublowane numery
i merge'e (0005/0006/0007/0012), więc równoległa gałąź łatwo dorobi kolejny dub.

Na `ImportSession` (`src/importer_publikacji/models.py:15`):

| Pole | Definicja |
|---|---|
| `zgloszenie` | `FK("zglos_publikacje.Zgloszenie_Publikacji", on_delete=SET_NULL, null=True, blank=True, related_name="sesje_importu", verbose_name="Zgłoszenie publikacji")` |
| `zgloszenie_odrzucone_przez_operatora` | `BooleanField(default=False)` — operator kliknął „żadne z nich"; wycisza baner |

FK jest wymogiem technicznym, nie ozdobą: `create_publication_task` dostaje
wyłącznie id sesji, więc bez tego pola zadanie Celery nie ma jak ustalić,
które zgłoszenie oznaczyć.

**Kierunek zależności** jest już ustalony — `importer_publikacji` importuje
`Zgloszenie_Publikacji` (`views/authors.py`), więc FK nie tworzy cyklu.

### 4.3 Baseline

Dwie nowe migracje. Zgodnie z regułą repo `make baseline-update` wykonuje się
**raz, przy scalaniu**, nie w gałęzi feature.

## 5. Nowy moduł `src/importer_publikacji/zgloszenia.py`

Cała logika wiązania mieszka w jednym module, żeby `tasks.py`, `wizard.py`
i nowy widok nie powielały reguł. Kontrakt publiczny:

```python
def kandydaci_dla_sesji(session) -> QuerySet:
    """Zgłoszenia, które ta sesja importu mogłaby domknąć."""

def zwiaz_automatycznie(session) -> bool:
    """Ustawia session.zgloszenie, gdy kandydat jest dokładnie jeden."""

def oznacz_jako_zaimportowane(session, record) -> bool:
    """Zapis zwrotny na zgłoszeniu. Idempotentny."""
```

### 5.1 `kandydaci_dla_sesji`

```
doi = normalize_doi(session.normalized_data.get("doi"))   # jak authors.py:160-162
jeśli brak doi → pusty queryset

Zgloszenie_Publikacji.objects            # SoftDeleteManager pomija usunięte
    .filter(doi__iexact=doi)
    .exclude(status__in=(ODRZUCONO, SPAM, ZAIMPORTOWANY, ZAAKCEPTOWANY,
                         WYMAGA_ZMIAN))                              # D9
    .filter(<zawężenie do session.uczelnia>)                         # D8
    .distinct()
```

**Zawężenie do uczelni (D8).** `Zgloszenie_Publikacji` nie ma `uczelnia`;
jedyna droga w ORM prowadzi przez autorów zgłoszenia:
`zgloszenie_publikacji_autor_set__jednostka__uczelnia`. Reguła:

- gdy `session.uczelnia` jest ustawione → filtruj po tej ścieżce,
- gdy `session.uczelnia` jest `NULL` **lub** instalacja ma jedną uczelnię →
  bez zawężenia (zachowanie jak dziś).

Dopasowanie po tytule **nie bierze udziału** w wiązaniu (D5). Pozostaje bez
zmian tam, gdzie jest dziś — w prefillu dyscyplin, gdzie pomyłka jest
nieszkodliwa.

### 5.2 `oznacz_jako_zaimportowane`

```
zgl = session.zgloszenie
pomiń (zwróć False) gdy: brak zgl
                       | zgl.deleted_at is not None     # soft-delete, patrz §1.3
                       | zgl.status == ZAIMPORTOWANY    # idempotencja

w transaction.atomic:
    zgl.status            = ZAIMPORTOWANY
    zgl.zaimportowano     = timezone.now()
    zgl.zaimportowal      = session.created_by
    zgl.odpowiednik_w_bpp = record
    zgl.save(update_fields=[...])
```

`zaimportowal` z `created_by`, nie `modified_by` — „kto to zrobił" znaczy kto
uruchomił import, nie kto ostatnio dotknął wiersza.

## 6. Wiązanie sesji ze zgłoszeniem

### Ścieżka A — jawna (z przycisku), przez rundę formularza

To **cztery** zmiany, nie jedna — parametr musi przeżyć GET → render → POST:

1. `importer_url()` (`admin/zgloszenie_publikacji.py:389-417`) dokłada
   `&zgloszenie={pk}`.
2. `FetchForm` (`forms.py:38-55`) zyskuje ukryte pole
   `zgloszenie = IntegerField(required=False, widget=HiddenInput)`.
3. `IndexView._get_fetch_form` (`wizard.py:87-126`) wypełnia je z
   `request.GET`.
4. `FetchView.post` (`wizard.py:205-281`) odczytuje z `cleaned_data`
   i przekazuje do `_start_import_session` (`:183-202`).

**Walidacja przy odczycie:** wartość musi być liczbą i wskazywać istniejące,
nie-usunięte zgłoszenie. Wartość niepoprawna jest ignorowana (import startuje
bez wiązania), nie powoduje błędu.

**Gałąź idempotency** (`wizard.py:259-273`) zwraca istniejącą sesję in-flight
z pominięciem `_start_import_session` — wiązanie zostałoby po cichu zgubione.
Reguła: jeśli zwrócona sesja ma `zgloszenie` puste, dopisz je; jeśli ma już
inne, **nie nadpisuj**.

### Ścieżka B — auto po DOI (dokładnie jeden kandydat)

W istniejącym etapie `prefill_zgl` (`tasks.py:87-90`), gdy `session.zgloszenie`
jest puste. Wywołanie `zwiaz_automatycznie(session)`. Dokładnie jeden kandydat
→ FK ustawione. Zero → nic. Dwa lub więcej → ścieżka C.

**Nie wolno dokładać nowego etapu** — `report_progress` rzuca `ValueError` na
nieznanej nazwie (`progress.py:49-50`), a wagi `FETCH_STAGES` sumują się do 100.
DOI jest dostępne przed tym etapem: `normalized_data["doi"]` powstaje
w `create_session` (`tasks.py:60-62`, `:114`).

### Ścieżka C — dwuznaczna (≥2 kandydatów)

Baner na pierwszym ekranie po pobraniu danych, z listą kandydatów:

```
┌──────────────────────────────────────────────────────────┐
│ ℹ  Mamy 2 zgłoszenia publikacji na to DOI (10.1234/abc). │
│    Które z nich domknąć tym importem?                    │
│                                                          │
│    [ #402 — Kowalski J., „Wpływ…", 2025 ]                │
│    [ #417 — Nowak A., „Wpływ…", 2025 ]                   │
│    [ Pokaż wszystkie w adminie ↗ ]  [ Żadne z nich ]     │
└──────────────────────────────────────────────────────────┘
```

Przy **jednym** kandydacie baner pokazuje się w wersji potwierdzającej:
*„Ten import domknie zgłoszenie #402 [zobacz] [odepnij]"* — operator może
zaprotestować, zanim import się wykona.

**Nowy widok wyboru:**

- URL `<int:session_id>/zgloszenie/wybierz/` — `pk` sesji jest **int**, wzorem
  reszty `urls.py`,
- `ImporterPermissionMixin` (superuser lub grupa `GR_WPROWADZANIE_DANYCH`)
  + `get_scoped_or_404(ImportSession, pk=session_id)` — jak wszystkie widoki
  importera (`permissions.py:7-54`),
- **waliduje, że wskazane id znajduje się wśród `kandydaci_dla_sesji(session)`**
  — bez tego byłby to IDOR: operator mógłby oznaczyć jako zaimportowane
  dowolne zgłoszenie w systemie,
- „żadne z nich" ustawia `zgloszenie_odrzucone_przez_operatora = True`.

Kandydaci są **wyliczani przy renderowaniu**, nie cache'owani w polu — DOI
jest stabilne, a dzięki temu lista nie starzeje się względem stanu bazy.

### Wpływ na prefill dyscyplin

`_prefill_dyscypliny_z_zgloszen` (`authors.py:191-224`) woła dziś
`_find_matching_zgloszenie` (`:200`), które po Ścieżce A mogłoby zwrócić
**inne** zgłoszenie niż związane — dyscypliny z X, status na Y. Reguła:

> gdy `session.zgloszenie` jest ustawione, prefill używa go wprost;
> heurystyka (z tytułem włącznie) zostaje wyłącznie jako fallback.

## 7. Zapis zwrotny

W `create_publication_task` (`src/importer_publikacji/tasks.py:217-239`),
w **tym samym bloku, co zapis `status = COMPLETED`** (`:226-231`) — czyli po
powrocie z `_create_publication`, którego własna transakcja
(`publikacja.py:327`) już się zamknęła (D10):

```
with transaction.atomic():
    session.status = COMPLETED; session.created_record = record; …
    session.save(...)
    oznacz_jako_zaimportowane(session, record)
```

Własności:

- **idempotentny** — ponowienie zadania nie przesuwa daty ani nie zmienia
  autora (guard `status == ZAIMPORTOWANY`),
- **odporny na soft-delete** — guard `deleted_at is None`; przypadek jest
  logowany, nie podnoszony,
- **niepowodzenie importu nie zmienia statusu zgłoszenia** — zapis siedzi
  w gałęzi sukcesu, przed blokiem `except` (`tasks.py:232-239`).

### Efekt uboczny w szablonie

Gate statusowy dla „Dodaj wyd. ciągłe/zwarte" siedzi **w szablonie**
(`change_form.html:10`: `{% if original.status == 0 or original.status == 3 %}`),
a nie w metodach modelu — `pokazuj_przycisk_wydawnictwo_*`
(`models.py:281-290`) sprawdzają rodzaj publikacji, nie status. Status
sprawdza tylko `moze_zostac_zwrocony` (`models.py:275-279`).

Skutek: po zmianie statusu przyciski „Zwróć do autora" i „Dodaj wyd. …"
**znikają same**. Ale przycisk **„Użyj importera" nie ma żadnego gate'u
statusu** (`change_form.html:4-6`) — trzeba go jawnie ukryć dla
`ZAIMPORTOWANY`, inaczej operator zaimportuje to samo drugi raz.

## 8. Informacja zwrotna

| Miejsce | Co pokazuje | Gdzie w kodzie |
|---|---|---|
| Strona zgłoszenia w adminie | panel readonly: „📥 Zaimportowane 22.07.2026 16:40 przez jkowalski · rekord ↗ · sesja importu ↗" | `admin/zgloszenie_publikacji.py` + `change_form.html` |
| Strona wyników importera | baner „Domknięto zgłoszenie #402 ↗" | `DoneView` (`views/wizard.py:1069-1083`) |
| Flash message | `messages.success(...)` przy pierwszym wejściu na `DoneView` | tamże |

Flash **musi** powstawać w cyklu żądania, **nie w zadaniu Celery** — worker
jawnie wyrzuca wiadomości do kosza (`_NoopMessageStorage`,
`tasks.py:254-265`), więc flash postawiony w tasku przepadłby bez śladu.

`DoneView.get` jest odświeżalny (F5), więc flash musi być stawiany **raz** —
flaga w sesji HTTP kluczowana id-em sesji importu.

Panel w adminie jest wyłącznie prezentacją: admin ma
`has_change_permission → False` (`admin/zgloszenie_publikacji.py:144`), więc
nowe pola i tak nie są edytowalne przez formularz.

## 9. Lista zgłoszeń w adminie

`ZAIMPORTOWANY` wchodzi automatycznie do istniejącego filtra `"status"`
(`admin/zgloszenie_publikacji.py:96-107`).

Dodatkowo filtr **„Do obsługi / Załatwione / Wszystkie"**, domyślnie
*Do obsługi* (`NOWY`, `PO_ZMIANACH`). Realizuje prośbę „żeby przestało się
pokazywać jako otwarte" — dziś takiego filtra nie ma w ogóle, a lista pokazuje
wszystko łącznie z odrzuconymi i spamem.

Kolumny listy zyskują `zaimportowano`; `list_filter` — `zaimportowal`.

## 10. Testy

`src/zglos_publikacje/tests/` i `src/importer_publikacji/tests/`; pytest bez
klas, `@pytest.mark.django_db`, `model_bakery.baker.make`.

**Wiązanie — ścieżka A**

- przycisk „Użyj importera" zawiera `zgloszenie=<pk>` w URL
- `?zgloszenie=N` przeżywa rundę GET → render → POST i ląduje na sesji
- `?zgloszenie=` niepoprawne / nieistniejące / soft-usunięte → import startuje
  bez wiązania, bez błędu
- gałąź idempotency: sesja in-flight bez wiązania dostaje FK; z wiązaniem — nie
  jest nadpisywana

**Wiązanie — ścieżki B i C**

- auto-wiązanie przy dokładnie jednym kandydacie
- brak auto-wiązania przy dwóch kandydatach + oba na liście
- brak wiązania po samym tytule (dwa zgłoszenia o identycznym tytule, różne DOI)
- kandydaci pomijają `ODRZUCONO`, `SPAM`, `ZAIMPORTOWANY`, `ZAAKCEPTOWANY`,
  `WYMAGA_ZMIAN` i soft-usunięte
- **kandydaci nie przekraczają granicy uczelni** (D8) — zgłoszenie autora z
  innej uczelni nie trafia na listę
- prefill dyscyplin używa `session.zgloszenie`, gdy jest ustawione

**Wybór operatora**

- `POST` z id kandydata ustawia FK
- `POST` z id **spoza** listy kandydatów jest odrzucany (regresja IDOR)
- `POST` bez uprawnień importera → 403
- `POST` na sesję innej uczelni → 404
- „żadne z nich" wycisza baner

**Zapis zwrotny**

- po `COMPLETED` zgłoszenie ma status, datę, autora i `odpowiednik_w_bpp`
- ponowienie zadania nie przesuwa `zaimportowano` (idempotencja)
- import zakończony błędem nie zmienia statusu zgłoszenia
- zgłoszenie soft-usunięte w trakcie importu **nie** zostaje oznaczone
- po imporcie znikają przyciski „Zwróć do autora", „Dodaj wyd. …" **oraz
  „Użyj importera"**

**Prezentacja**

- panel w adminie pokazuje datę, użytkownika i link do rekordu
- `DoneView` renderuje baner; flash pojawia się raz, nie dubluje po F5

## 11. Poza zakresem

- **Ścieżka ręczna „Dodaj wyd. ciągłe/zwarte"** (`?numer_zgloszenia=`,
  `bpp/const.py:131`) nadal nie oznacza zgłoszenia — numer trafia wyłącznie do
  pola tekstowego `adnotacje` (`bpp/admin/zglos_publikacje_helpers.py:72-77`).
  Ta sama luka, innym korytarzem; osobne zgłoszenie.
- **Import wielu prac** (`MultipleWorksImport`) — wiązanie ze zgłoszeniami
  per-wpis; poza zakresem.
- **Powiadomienie po zamknięciu karty** (liveops / e-mail) — importer nie
  używa dziś żadnego z trzech mechanizmów powiadomień obecnych w projekcie.
  Osobna decyzja produktowa.
- **Soft-delete zgłoszenia po imporcie** — świadomie odrzucone (D7).
- **Pole `uczelnia` na `Zgloszenie_Publikacji`** — właściwe rozwiązanie
  problemu z D8, ale to migracja danych na modelu z ruchem produkcyjnym.
  Tu obchodzimy je zawężeniem przez autorów; docelowo osobne zgłoszenie.

## 12. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Oznaczenie cudzego zgłoszenia (inny autor) | wiązanie tylko jawne albo po DOI przy jednym kandydacie; tytuł wykluczony (D5) |
| Oznaczenie cudzego zgłoszenia (inna uczelnia) | zawężenie kandydatów przez autorów do `session.uczelnia` (D8) |
| IDOR przy wyborze kandydata | walidacja id względem wyliczonej listy kandydatów + `ImporterPermissionMixin` + scoping sesji (§6C) |
| Utrata wiązania na gałęzi idempotency | jawna reguła „dopisz, gdy puste; nie nadpisuj" (§6A) |
| Oznaczenie soft-usuniętego zgłoszenia | guard `deleted_at is None` (§5.2) |
| Podwójny import tego samego zgłoszenia | ukrycie przycisku „Użyj importera" dla `ZAIMPORTOWANY` (§7) |
| Rozjazd paska postępu | reużycie etapu `prefill_zgl`, zero nowych nazw (§6B) |
| Kolizja numerów migracji importera | numer `0020` podany jawnie (§4.2) |
| Dwie migracje w jednej gałęzi | `make baseline-update` raz, przy scalaniu — nie w gałęzi |
