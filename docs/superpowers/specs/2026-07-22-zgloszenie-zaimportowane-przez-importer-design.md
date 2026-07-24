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
   `SoftDeleteModel` (`models.py:61`); kasowanie ustawia `deleted_at`,
   a dostęp przez FK idzie `_base_manager`, który **nie filtruje
   usuniętych** — sam FK nie ochroni przed oznaczeniem skasowanego
   zgłoszenia.

   Uściślenie po testach: `SoftDeleteModel.delete()` **emuluje `on_delete`**
   dla relacji odwrotnych (`django_softdelete/models.py:281-283`), więc na
   typowej ścieżce (operator kasuje zgłoszenie w module redagowania) FK na
   sesji **zostanie wyzerowany**. Guard `deleted_at is None` pozostaje
   konieczny dla ścieżek omijających `delete()`: bulk `UPDATE deleted_at`,
   surowy SQL, migracje danych, wyścig transakcji.

   Uboczna konsekwencja emulacji: skasowanie zgłoszenia **po cichu gubi
   wiązanie**, więc po `restore()` sesja już go nie wskaże. Zachowanie
   przypięte testem charakteryzującym, żeby zmiana biblioteki nie przeszła
   niezauważona.
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
| **D10** | **Zapis zwrotny osobno, po zapisie `COMPLETED`** | transakcja tworząca rekord (`publikacja.py:327`) commituje przed powrotem do taska; „ta sama transakcja" i „tuż po COMPLETED" wykluczają się |

### Decyzje dodane po adwersarialnej recenzji PR #657

Recenzja wykazała, że trzy założenia projektu były błędne. Poniższe decyzje je
zastępują.

| # | Decyzja | Uzasadnienie |
|---|---|---|
| **D11** | **DOI zgłoszenia czytamy z `doi` **oraz** ze `strona_www`** | pole `doi` jest produkcyjnie **zawsze puste**: publiczny formularz (`forms.py:277-283`) go nie ma, a help-text (`forms.py:121`) każe wkleić DOI do `strona_www`. Samo `doi__iexact` czyniło ścieżki B i C martwym kodem. Tę samą kolejność stosuje już `importer_url()` |
| **D12** | **Prefiltr SQL `icontains` + dokładne porównanie w Pythonie** | LIKE nie umie rozpoznać, gdzie w URL-u kończy się DOI. Bez dofiltrowania DOI będące **prefiksem** innego (`10.1/abc` vs `10.1/abc.2`) dawałoby ciche oznaczenie cudzego zgłoszenia |
| **D13** | **Ścieżka jawna egzekwuje te same reguły co kandydaci** (`zgloszenie_dozwolone`) | pierwotnie `_zgloszenie_z_pola` robiło gołe `objects.filter(pk=…)` — bez granicy uczelni i bez filtra statusów. Redaktor jednej uczelni mógł POST-em przestemplować zgłoszenie innej |
| **D14** | **Zapis zwrotny to warunkowy `UPDATE`, rewalidujący status** | między związaniem a zapisem mija cała praca operatora w kreatorze. Guard „przeczytaj, potem zapisz" pozwalał przestemplować zgłoszenie zwrócone w międzyczasie autorowi. Warunek w `WHERE` usuwa przy okazji wyścig |
| **D15** | **`kod_do_edycji` kasowany przy oznaczaniu** | widok edycji autoryzuje **samym kodem**, nie statusem. Żywy kod na zgłoszeniu `ZAIMPORTOWANY` pozwalał autorowi cofnąć status na `PO_ZMIANACH` → panel audytu znikał → przycisk „Użyj importera" wracał → duplikat rekordu |
| **D16** | **`WYMAGA_ZMIAN` należy do grupy „Do obsługi"** | zgłoszenie u autora jest „w toku" — operator musi je widzieć. Poza żadną grupą znikało wszędzie poza „Wszystkie", co było regresem widoczności wobec stanu sprzed zmiany |
| **D17** | **Filtr „Stan obsługi" przepuszcza queryset, gdy jawnie wybrano `status`** | oba filtry składały się koniunkcją, więc kliknięcie „status → spam" dawało pustą listę bez wyjaśnienia. `choices()` nie zaznacza wtedy „Do obsługi", żeby UI nie kłamał o zawężeniu |
| **D18** | **Informację zwrotną niesie callout, nie flash** | `base.html` renderuje ramkę komunikatów **dwukrotnie** (`:184`, `:210`), więc flash pokazywałby się 2×, a z calloutem 3×. Callout jest idempotentny i trwały (przeżywa F5); znika ~25 linii maszynerii „pokaż dokładnie raz" |

### Decyzje z drugiej rundy recenzji

Druga runda potwierdziła D11–D18 jako poprawnie wdrożone, ale wykazała, że
**naprawa D17 wyhodowała swoje rodzeństwo**.

| # | Decyzja | Uzasadnienie |
|---|---|---|
| **D19** | **Przezroczystość filtra obejmuje `status`, `zaimportowal` i `zaimportowano`** — nie samo `status` | `zaimportowal` jest niepuste **wyłącznie** na zgłoszeniach `ZAIMPORTOWANY`, czyli spoza grupy „Do obsługi". Koniunkcja z domyślnym zawężeniem była więc **sprzeczna z definicji**: kliknięcie dowolnej osoby w filtrze „zaimportował" zawsze dawało zero wyników. Lista pól zamiast pojedynczej stałej, żeby kolejny filtr skorelowany ze statusem nie powtórzył tego błędu |
| **D20** | **Tryb DjangoQL liczy się dopiero z niepustym `q`** | samo przełączenie trybu bez wpisanego zapytania nie jest wyborem operatora — domyślny widok „Do obsługi" ma zostać |
| **D21** | **`zwiaz_automatycznie` też przez warunkowy `UPDATE`** | sprawdzenie `zgloszenie_id` na obiekcie w pamięci + bezwarunkowy zapis zostawiało okno: gałąź idempotency `FetchView` zapisuje **równolegle**, więc auto-match po DOI mógł przestemplować jawny wybór operatora i oznaczyć inne zgłoszenie. Reguła „tylko gdy puste" należy do klauzuli `WHERE`, nie do kodu Pythona — symetrycznie do widoku |
| **D22** | **Zapis zwrotny ustawia `ostatnio_zmieniony` jawnie** | `.update()` omija `auto_now`, a `Meta.ordering` sortuje po tym polu — bez tego świeżo zaimportowane zgłoszenie zostawałoby ze starą datą na dole listy |

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

baza = Zgloszenie_Publikacji.objects      # SoftDeleteManager pomija usunięte
    .exclude(status__in=(ODRZUCONO, SPAM, ZAIMPORTOWANY, ZAAKCEPTOWANY,
                         WYMAGA_ZMIAN))                              # D9
    .filter(<zawężenie do uczelni>)                                  # D8

# prefiltr zgrubny — LIKE nie wie, gdzie w URL-u kończy się DOI      # D11, D12
kandydaci_pk = {
    pk for pk, doi_pola, strona_www in baza.order_by()
                                           .values_list("pk", "doi", "strona_www")
    if normalize_doi(doi_pola) == doi or extract_doi_from_url(strona_www) == doi
}
→ Zgloszenie_Publikacji.objects.filter(pk__in=kandydaci_pk)
```

Zwracany jest **QuerySet**, nie lista — reszta kodu (walidacja wyboru
operatora przez `.filter(pk=…)`, liczenie, iteracja w szablonie) na tym polega.

`order_by()` kasuje domyślne `Meta.ordering`: bez tego `SELECT DISTINCT`
z `ORDER BY` po kolumnie spoza listy pól wywala się na PostgreSQL-u.

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

Jeden **warunkowy `UPDATE`** — nie „przeczytaj, sprawdź, zapisz" (D14):

```
zgl = session.zgloszenie
pomiń (zwróć False) gdy: brak zgl | zgl.deleted_at is not None   # patrz §1.3

zaktualizowane = (
    Zgloszenie_Publikacji.objects.filter(pk=zgl.pk)
        .exclude(status__in=_wykluczone_statusy())   # rewalidacja W CHWILI ZAPISU
        .update(
            status            = ZAIMPORTOWANY,
            zaimportowano     = timezone.now(),
            zaimportowal      = session.created_by,
            content_type      = ...,                 # GenericFK to DWIE kolumny
            object_id         = record.pk,
            kod_do_edycji     = None,                # D15
        )
)
jeśli zaktualizowane == 0 → zaloguj (ze świeżo odczytanym statusem) i zwróć False
```

Warunek w `WHERE` załatwia trzy rzeczy naraz: idempotencję (`ZAIMPORTOWANY` jest
na liście wykluczonych), rewalidację statusu (D14) i wyścig — nie ma okna między
odczytem a zapisem. `content_type` i `object_id` muszą być wymienione jawnie:
`odpowiednik_w_bpp` to `GenericForeignKey`, czyli nie kolumna, tylko para kolumn.

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

**Walidacja przy odczycie (D13) — kluczowa.** Nie wystarczy sprawdzić, że
zgłoszenie istnieje: ścieżka jawna musi egzekwować **te same reguły co
kandydaci** — granicę uczelni (D8) i wykluczone statusy (D9). Służy do tego
`zgloszenie_dozwolone(pk, uczelnia)` z `zgloszenia.py`, dzieląca implementację
z `kandydaci_dla_sesji` (jedno źródło reguł, zero duplikacji).

Bez tego pole `zgloszenie` jest zwykłym ukrytym inputem, a enumeracja `pk` to
jedno `curl`: redaktor jednej uczelni POST-em wiąże i przestemplowuje
zgłoszenie innej — także takie w statusie `SPAM` czy `WYMAGA_ZMIAN`.

Wartość niepoprawna, spoza uczelni albo o wykluczonym statusie jest **ignorowana
po cichu** (import startuje bez wiązania), nigdy nie powoduje błędu widocznego
dla użytkownika.

**Gałąź idempotency** (`wizard.py`) zwraca istniejącą sesję in-flight
z pominięciem `_start_import_session` — wiązanie zostałoby po cichu zgubione.
Reguła „dopisz gdy puste, nie nadpisuj gdy zajęte" jest realizowana **atomowym
warunkowym UPDATE**, nie sekwencją odczyt-zapis:

```python
ImportSession.objects.filter(pk=…, zgloszenie__isnull=True).update(zgloszenie=…)
```

Sekwencja odczyt-zapis nie wystarcza, bo dla tej sesji **równolegle biegnie**
`fetch_session_task`, który trzyma własną, wcześniej załadowaną instancję.
Jego pełne `session.save()` wpisywałoby `zgloszenie_id = NULL` z nieaktualnego
stanu. Dlatego zadania zapisują wyłącznie przez `update_fields` (zawsze
z `modified`, bo `auto_now` odpala się tylko dla pól z listy, a `is_stalled()`
czyta to pole), a przed etapem `prefill_zgl` przeładowują `zgloszenie` z bazy.

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
    session.save(update_fields=[…, "modified"])

# POZA transakcją i w wąskim try/except — uzasadnienie niżej
_oznacz_zgloszenie_nie_wywracajac_importu(session, record)
```

Własności:

- **idempotentny** — ponowienie zadania nie przesuwa daty ani nie zmienia
  autora (`ZAIMPORTOWANY` jest wśród statusów wykluczonych w `WHERE`),
- **odporny na soft-delete** — guard `deleted_at is None`; przypadek jest
  logowany, nie podnoszony,
- **niepowodzenie importu nie zmienia statusu zgłoszenia** — zapis siedzi
  w gałęzi sukcesu, przed blokiem `except`,
- **przeładowuje `zgloszenie` z bazy** — żeby uszanować „Odepnij" / „Żadne
  z nich" kliknięte przez operatora w trakcie trwania zadania.

**Dlaczego poza transakcją i w `try/except`.** Zapis zwrotny wykonuje się
*po* commicie `_create_publication`, czyli gdy rekord już istnieje. Gdyby
rzucił wyjątek wewnątrz `atomic`, transakcja zostałaby zatruta, `COMPLETED`
wycofane, a blok `except` ustawiłby `IMPORT_FAILED` — operator kliknąłby
„Ponów" i powstałby **drugi rekord tej samej publikacji**. Dlatego wyjątek
jest tu przechwytywany wąsko: `logger.exception(...)` + `rollbar.report_exc_info()`,
**bez re-raise**. Najgorszy skutek to nieoznaczone zgłoszenie, nie duplikat.

To wyjątek od reguły repo „nigdy nie połykaj wyjątków" uzasadniony tym, że
zdarzenie jest w pełni raportowane (log + Rollbar), a alternatywa jest
gorsza od problemu.

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
| Strona wyników importera | callout „Domknięto zgłoszenie #402 ↗" | `partials/step_done.html` + `DoneView` |

**Bez flash message** (D18). Pierwotny projekt przewidywał `messages.success(…)`
przy wejściu na `DoneView`, ale `base.html` renderuje ramkę komunikatów
**dwukrotnie** (`:184` i `:210`), więc flash pokazywałby się 2×, a razem
z calloutem 3×. Callout daje dokładnie jedno wystąpienie, jest trwały (przeżywa
F5 i powrót na stronę) i nie wymaga maszynerii „pokaż dokładnie raz" — znika
flaga w sesji HTTP, jej limit i cała obsługa.

Gdyby ktoś jednak chciał prawdziwego flasha: trzeba najpierw naprawić podwójne
renderowanie w `base.html`, co dotyka **każdego** komunikatu w BPP.

Niezależnie od wariantu obowiązuje reguła: komunikat **musi** powstawać
w cyklu żądania, **nie w zadaniu Celery** — worker jawnie wyrzuca wiadomości do
kosza (`_NoopMessageStorage`, `tasks.py:254-265`).

Panel w adminie jest wyłącznie prezentacją: admin ma
`has_change_permission → False` (`admin/zgloszenie_publikacji.py:144`), więc
nowe pola i tak nie są edytowalne przez formularz.

## 9. Lista zgłoszeń w adminie

`ZAIMPORTOWANY` wchodzi automatycznie do istniejącego filtra `"status"`
(`admin/zgloszenie_publikacji.py:96-107`).

Dodatkowo filtr **„Do obsługi / Załatwione / Wszystkie"**, domyślnie
*Do obsługi*. Realizuje prośbę „żeby przestało się pokazywać jako otwarte" —
dotąd takiego filtra nie było w ogóle, a lista pokazywała wszystko łącznie
z odrzuconymi i spamem.

Podział grup (D16):

| Grupa | Statusy |
|---|---|
| **Do obsługi** (domyślnie) | `NOWY`, `WYMAGA_ZMIAN`, `PO_ZMIANACH` |
| Załatwione | `ZAIMPORTOWANY`, `ZAAKCEPTOWANY`, `ODRZUCONO`, `SPAM` |
| Wszystkie | bez zawężenia |

`WYMAGA_ZMIAN` **należy do „Do obsługi"** — zgłoszenie u autora jest w toku,
operator musi je widzieć (przypomnieć, po czasie odrzucić). Poza żadną grupą
znikałoby wszędzie poza „Wszystkie", co byłoby regresem widoczności.

**Przezroczystość wobec filtra `status` (D17).** Oba filtry składają się
koniunkcją, więc bez tego kliknięcie „status → spam" na widoku domyślnym
dawałoby pustą listę bez wyjaśnienia. Reguła: gdy `stan_obslugi` nie został
wybrany ręcznie, a w `request.GET` jest `status` (lub dowolne `status__*`),
filtr przepuszcza queryset bez zmian, a `choices()` nie zaznacza „Do obsługi" —
inaczej UI kłamałby o zastosowanym zawężeniu. Przy jawnym wyborze obu filtrów
koniunkcja zostaje (obie pozycje są widocznie zaznaczone, więc pustka jest
zrozumiała).

Kolumny listy zyskują `zaimportowano`; `list_filter` — `zaimportowal`
przez `RelatedOnlyFieldListFilter` (gołe pole renderowałoby pozycję dla
**każdego** użytkownika w bazie).

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
- **Import wielu prac** (`MultipleWorksImport`) — ~~poza zakresem~~.
  Sprostowanie po recenzji: wpisy paczki idą przez `_start_import_session` →
  `fetch_session_task` → `zwiaz_automatycznie`, więc **auto-wiązanie po DOI
  działa tam samo z siebie**. Zostawione świadomie — to sensowne zachowanie,
  a wyłączanie go wymagałoby dodatkowego guardu bez powodu. Poza zakresem
  zostaje jedynie *jawne* wiązanie per-wpis (paczka nie ma skąd wziąć numeru
  zgłoszenia).
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
| Oznaczenie cudzego zgłoszenia (inny autor) | wiązanie tylko jawne albo po DOI przy jednym kandydacie; tytuł wykluczony (D5); prefiks DOI odsiany porównaniem w Pythonie (D12) |
| Oznaczenie cudzego zgłoszenia (inna uczelnia) | zawężenie przez autorów do uczelni — **na obu ścieżkach**, jawnej i po DOI (D8 + D13) |
| IDOR przy wyborze kandydata | walidacja id względem wyliczonej listy kandydatów + `ImporterPermissionMixin` + scoping sesji (§6C) |
| Przestemplowanie zgłoszenia zwróconego autorowi | warunkowy `UPDATE` rewalidujący status w chwili zapisu (D14) |
| Cofnięcie statusu przez autora → duplikat rekordu | `kod_do_edycji` kasowany przy oznaczaniu (D15) |
| Utrata wiązania na gałęzi idempotency | atomowy `UPDATE … WHERE zgloszenie IS NULL` + `update_fields` w zadaniach, żeby task nie nadpisał wiązania swoją nieaktualną instancją |
| Oznaczenie soft-usuniętego zgłoszenia | guard `deleted_at is None` (§5.2) |
| Podwójny import tego samego zgłoszenia | ukrycie przycisku „Użyj importera" dla `ZAIMPORTOWANY` (§7) + D15 |
| Wyjątek w zapisie zwrotnym → duplikat po „Ponów" | zapis zwrotny poza `atomic`, w wąskim `try/except` z `logger.exception` + Rollbar, bez re-raise: sesja zostaje `COMPLETED` |
| Watchdog uzna żywe sesje za martwe | `update_fields` w zadaniach **zawsze** zawiera `modified` — `auto_now` odpala się tylko dla pól z listy, a `is_stalled()` czyta to pole |
| Dane nieosiągalne z UI po dodaniu filtra | przezroczystość przy jawnym wyborze statusu (D17), przy `zaimportowal`/`zaimportowano` (D19) i przy zapytaniu DjangoQL (D20) + `WYMAGA_ZMIAN` w „Do obsługi" (D16). Grupy **partycjonują** wszystkie statusy, więc żaden nie może wypaść niezauważony |
| Auto-match przestemplowuje jawny wybór operatora | `zwiaz_automatycznie` przez warunkowy `UPDATE … WHERE zgloszenie IS NULL` (D21) |
| Zaimportowane zgłoszenie ginie na dole listy | `ostatnio_zmieniony` ustawiany jawnie, bo `.update()` omija `auto_now` (D22) |
| Rozjazd paska postępu | reużycie etapu `prefill_zgl`, zero nowych nazw (§6B) |
| Kolizja numerów migracji importera | numer `0020` podany jawnie (§4.2) |
| Dwie migracje w jednej gałęzi | `make baseline-update` raz, przy scalaniu — nie w gałęzi |

### Ograniczenia świadomie zaakceptowane

- **Przeciek D8 przy współautorstwie międzyuczelnianym.** Join przez autorów
  daje semantykę OR: zgłoszenie, którego autorzy siedzą w jednostkach dwóch
  uczelni, jest kandydatem dla obu. Bez pola `uczelnia` na samym zgłoszeniu nie
  da się tego rozstrzygnąć czysto — praca współautorska naprawdę „należy" do
  obu. Wariant restrykcyjny (*wszyscy* autorzy z jednej uczelni) ukrywałby takie
  zgłoszenia przed obiema. Mitygacja częściowa: baner **nie pokazuje e-maila
  zgłaszającego**.
- **Zgłoszenia bez autorów wypadają** w instalacji wielouczelnianej (INNER JOIN
  nie ma czego dopasować). Decyzja **fail-closed**: takiego zgłoszenia nie da
  się przypisać do uczelni, więc lepiej nie pokazać go nikomu niż wszystkim.
- **`base.html` renderuje ramkę komunikatów dwukrotnie** (`:184`, `:210`) —
  defekt dotyczący **każdego** komunikatu w BPP, nie tylko tej funkcji.
  Poza zakresem; nadaje się na osobne zgłoszenie.
