# Domknięcie pętli: zgłoszenie publikacji ↔ importer prac

**Zgłoszenie:** FD#443 „Oznaczanie zgłoszeń jako zużyte"
(<https://iplweb.freshdesk.com/a/tickets/443>), zgłaszający Jan Bichałowicz
(`jbihalowicz@apoz.edu.pl`), klient `bpp.apoz.edu.pl`.
Powiązane: FD#430 (przycisk „Użyj importera" nad tabelą), FD#425 (oryginał).

**Data:** 2026-07-22 · **Wersja bazowa:** `202607.1397` · **Gałąź:**
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
(`src/zglos_publikacje/admin/zgloszenie_publikacji.py:404-410`), po czym
kontekst ginie.

### Co już jest w kodzie (i jest martwe)

| Element | Stan |
|---|---|
| `Zgloszenie_Publikacji.odpowiednik_w_bpp` — GenericFK do rekordu (`models.py:82`) | pole istnieje, **nic w `src/` go nie zapisuje** |
| `Statusy.ZAAKCEPTOWANY = 1` („dodany do bazy BPP") | **nigdy nie ustawiany programowo** |
| `ImportSession.created_by`, `created_record` | wypełniane poprawnie (`tasks.py:226-231`) |
| `_find_matching_zgloszenie()` (`importer_publikacji/views/authors.py:148-188`) | heurystyka DOI → tytuł, używana **wyłącznie** do prefilla dyscyplin |

### Pułapka do obejścia

`ImportSession.modified` to `auto_now=True` — znaczy „kiedy ostatnio cokolwiek
ruszyło wiersz", nie „kiedy zaimportowano". Watchdog `mark_stalled()`
(`importer_publikacji/models.py:305-321`) czy ponowne wejście na sesję
przesuwają tę datę. Dlatego moment importu wymaga **jawnego pola**.

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
| D1 | Nowy status `ZAIMPORTOWANY = 6`, nie ożywianie `ZAAKCEPTOWANY = 1` | odróżnia „dodane importerem" od „dodane ręcznie"; słowo z prośby klienta |
| D2 | Audyt denormalizowany na zgłoszeniu (`zaimportowano`, `zaimportowal`) | filtrowalny i sortowalny na liście; przeżywa skasowanie sesji importu |
| D3 | Jawne pole czasu, nie `auto_now` | `ImportSession.modified` nie jest wiarygodnym znacznikiem zakończenia |
| D4 | Wiązanie jawne (`?zgloszenie=`) + fallback po DOI | determinizm; DOI to identyfikator mocny |
| D5 | Dopasowanie po **tytule wykluczone** z wiązania | dwa zgłoszenia o tym samym tytule → oznaczono by przypadkowe (korupcja danych) |
| D6 | Przy ≥2 kandydatach — operator wybiera, system nie zgaduje | jawny wybór zamiast cichego pominięcia |
| D7 | Bez soft-delete zgłoszenia po imporcie | jawny status niesie tę samą informację, a zachowuje ślad na liście |

## 4. Zmiany w modelach

### 4.1 `zglos_publikacje` — migracja `0027`

Na `Zgloszenie_Publikacji` (`src/zglos_publikacje/models.py:60`):

| Pole | Definicja |
|---|---|
| `Statusy.ZAIMPORTOWANY` | `= 6, "zaimportowany przez importer prac"` |
| `zaimportowano` | `DateTimeField("Zaimportowano", null=True, blank=True, db_index=True)` |
| `zaimportowal` | `FK(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="+", verbose_name="Zaimportował")` |
| `odpowiednik_w_bpp` | bez zmian — istniejący GenericFK, zaczyna być zapisywany |

`SET_NULL` na `zaimportowal`: skasowanie konta operatora nie może kasować ani
blokować zgłoszenia.

### 4.2 `importer_publikacji` — migracja

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

## 5. Wiązanie sesji ze zgłoszeniem

### Ścieżka A — jawna (z przycisku)

`importer_url()` (`admin/zgloszenie_publikacji.py:389-417`) dokłada
`&zgloszenie={pk}`. `IndexView` (`views/wizard.py:87-119`) odczytuje parametr
i przekazuje do `_start_import_session` (`:183-202`), które zapisuje FK.

Parametr jest **walidowany** przy odczycie: musi być liczbą i wskazywać
istniejące, nie-usunięte zgłoszenie. Wartość niepoprawna jest ignorowana
(import startuje bez wiązania), nie powoduje błędu.

### Ścieżka B — auto po DOI (dokładnie jedno trafienie)

W istniejącym etapie `prefill_zgl` (`tasks.py:87-90`), gdy `session.zgloszenie`
jest puste. Kandydaci:

```
Zgloszenie_Publikacji.objects            # SoftDeleteManager — pomija usunięte
    .filter(doi__iexact=<doi sesji>)
    .exclude(status__in=(ODRZUCONO, SPAM, ZAIMPORTOWANY, ZAAKCEPTOWANY))
```

Dokładnie jeden wynik → `session.zgloszenie` ustawione. Zero → nic.
Dwa lub więcej → ścieżka C.

Dopasowanie po tytule **nie bierze udziału** w wiązaniu. Pozostaje bez zmian
tam, gdzie jest dziś — w prefillu dyscyplin, gdzie pomyłka jest nieszkodliwa.

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

Wybór to `POST` na nowy widok. Widok **waliduje, że wskazane id znajduje się
wśród aktualnie wyliczonych kandydatów** — bez tego byłby to IDOR: operator
mógłby oznaczyć jako zaimportowane dowolne zgłoszenie w systemie.
„Żadne z nich" ustawia `zgloszenie_odrzucone_przez_operatora = True`.

Kandydaci są **wyliczani przy renderowaniu**, nie cache'owani w polu — DOI
jest stabilne, a dzięki temu lista nie starzeje się względem stanu bazy.

## 6. Zapis zwrotny

W `create_publication_task` (`src/importer_publikacji/tasks.py:217-239`),
w tej samej transakcji, która tworzy rekord, tuż po `status = COMPLETED`:

```
jeżeli session.zgloszenie istnieje i jego status != ZAIMPORTOWANY:
    status            ← Statusy.ZAIMPORTOWANY
    zaimportowano     ← timezone.now()
    zaimportowal      ← session.created_by
    odpowiednik_w_bpp ← utworzony rekord
```

Własności:

- **idempotentny** — ponowienie zadania nie przesuwa daty ani nie zmienia
  autora,
- **odporny na wyścig** — zgłoszenie skasowane w międzyczasie nie wywala
  importu; brak wiersza jest logowany, nie podnoszony,
- `zaimportowal` z `created_by`, nie `modified_by` — „kto to zrobił" znaczy
  kto uruchomił import, nie kto ostatnio dotknął wiersza,
- **niepowodzenie importu nie zmienia statusu zgłoszenia** — zapis siedzi
  w gałęzi sukcesu, przed blokiem `except` (`tasks.py:232-239`).

### Efekt uboczny, którego nie trzeba kodować

Przyciski „Zwróć do autora", „Dodaj wyd. ciągłe", „Dodaj wyd. zwarte" mają
warunki `status in (NOWY, PO_ZMIANACH)` (`models.py:275, 281, 288` oraz
`templates/.../change_form.html`). Po zmianie statusu **znikają same** —
zgłoszenie przestaje wyglądać na wymagające obsługi.

## 7. Informacja zwrotna

| Miejsce | Co pokazuje | Gdzie w kodzie |
|---|---|---|
| Strona zgłoszenia w adminie | panel readonly: „📥 Zaimportowane 22.07.2026 16:40 przez jkowalski · rekord ↗ · sesja importu ↗" | `admin/zgloszenie_publikacji.py` + `change_form.html` |
| Strona wyników importera | baner „Domknięto zgłoszenie #402 ↗" | `DoneView` (`views/wizard.py:1069-1084`) |
| Flash message | `messages.success(...)` przy wejściu na `DoneView` | tamże |

Flash **musi** powstawać w cyklu żądania, **nie w zadaniu Celery** — worker
jawnie wyrzuca wiadomości do kosza (`_NoopMessageStorage`,
`tasks.py:254-265`), więc flash postawiony w tasku przepadłby bez śladu.

Panel w adminie jest wyłącznie prezentacją: admin ma
`has_change_permission → False` (`admin/zgloszenie_publikacji.py:144`), więc
nowe pola i tak nie są edytowalne przez formularz.

## 8. Lista zgłoszeń w adminie

`ZAIMPORTOWANY` wchodzi automatycznie do istniejącego filtra `"status"`
(`admin/zgloszenie_publikacji.py:96-107`).

Dodatkowo filtr **„Do obsługi / Załatwione / Wszystkie"**, domyślnie
*Do obsługi* (`NOWY`, `PO_ZMIANACH`). Realizuje prośbę „żeby przestało się
pokazywać jako otwarte" — dziś takiego filtra nie ma w ogóle, a lista pokazuje
wszystko łącznie z odrzuconymi i spamem.

Kolumny listy zyskują `zaimportowano`; `list_filter` — `zaimportowal`.

## 9. Testy

`src/zglos_publikacje/tests/` i `src/importer_publikacji/tests/`; pytest bez
klas, `@pytest.mark.django_db`, `model_bakery.baker.make`.

**Wiązanie**

- przycisk „Użyj importera" zawiera `zgloszenie=<pk>` w URL
- `IndexView` z `?zgloszenie=N` zapisuje FK na sesji
- `?zgloszenie=` niepoprawne / nieistniejące / usunięte → import startuje bez wiązania, bez błędu
- auto-wiązanie przy dokładnie jednym zgłoszeniu z tym DOI
- brak auto-wiązania przy dwóch zgłoszeniach z tym samym DOI + oba na liście kandydatów
- brak wiązania po samym tytule (dwa zgłoszenia o identycznym tytule, różne DOI)
- kandydaci pomijają zgłoszenia `ODRZUCONO`, `SPAM`, `ZAIMPORTOWANY`, soft-deleted

**Wybór operatora**

- `POST` z id kandydata ustawia FK
- `POST` z id **spoza** listy kandydatów jest odrzucany (regresja IDOR)
- „żadne z nich" wycisza baner

**Zapis zwrotny**

- po `COMPLETED` zgłoszenie ma status, datę, autora i `odpowiednik_w_bpp`
- ponowienie zadania nie przesuwa `zaimportowano` (idempotencja)
- import zakończony błędem nie zmienia statusu zgłoszenia
- zgłoszenie skasowane w trakcie importu nie wywala zadania
- po imporcie znikają przyciski „Zwróć do autora" i „Dodaj wyd. …"

**Prezentacja**

- panel w adminie pokazuje datę, użytkownika i link do rekordu
- `DoneView` renderuje baner i flash message

## 10. Poza zakresem

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

## 11. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Oznaczenie cudzego zgłoszenia | wiązanie tylko jawne albo po DOI przy jednym trafieniu; tytuł wykluczony (D5) |
| IDOR przy wyborze kandydata | walidacja id względem wyliczonej listy kandydatów (§5C) |
| Dwie migracje w jednej gałęzi | `make baseline-update` raz, przy scalaniu — nie w gałęzi |
| Rozjazd `zaimportowano` z sesją importu | pole zapisywane wyłącznie w jednym miejscu, w transakcji tworzącej rekord |
