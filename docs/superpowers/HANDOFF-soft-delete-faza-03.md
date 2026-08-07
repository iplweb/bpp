# Handoff: soft-delete, start fazy 03

> Dokument przekazania po zamknięciu **fazy 02** (publikacje), 2026-08-07.
>
> **Czytaj to zamiast odtwarzania historii z gita.** Zawiera rzeczy, których
> nie widać w diffie, a które w fazie 02 kosztowały rundy poprawek.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Gałąź | `feat/soft-delete-02`, worktree `~/Programowanie/bpp-soft-delete-02` |
| Baza | `feat/soft-delete` (faza 01, PR #312) — PR fazy 02 jest **stackowany**, nie na `dev` |
| Migracje | `bpp/0496`…`0499`, `rozbieznosci_dyscyplin/0023` |
| Testy | 306 passed / 1 xfailed (soft-delete+cache+rozbieżności), 416 passed (regresja publikacji) |

**Faza 02 objęła 5 modeli publikacji** — `Wydawnictwo_Ciagle`,
`Wydawnictwo_Zwarte`, `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna`.

Dokumenty warte otwarcia zanim cokolwiek zaczniesz:

- **inwentaryzacja ORM (wejście fazy 03)**:
  `docs/superpowers/reviews/2026-08-07-faza-02-inwentaryzacja-orm.md`
  — z self-review, który obala część własnych wniosków. Czytaj RAZEM z nim.
- inwentaryzacja widoków: `…/2026-08-07-faza-02-inwentaryzacja-widokow.md`
- zgłoszenie upstream do `django-easy-audit`:
  `…/2026-08-07-easyaudit-upstream-zgloszenie.md`

---

## 2. Najważniejsza lekcja fazy 02

Faza 01 zostawiła listę **siedmiu** mechanizmów zakładających, że skasowany
wiersz znika. Faza 02 dołożyła **dwa kolejne** — oba spoza kodu, który
zmienialiśmy:

| # | Mechanizm | Jak się objawił |
|---|---|---|
| 8 | `django-easy-audit` | pobiera poprzedni wiersz przez `sender.objects` → `restore()` leci `DoesNotExist`. **Błąd ZASTANY** — `Zgloszenie_Publikacji` było nieprzywracalne na `dev` już przed fazą 02 |
| 9 | odwrotne `OneToOne` | `autor.praca_habilitacyjna` idzie przez `_base_manager` (nieprzefiltrowany) → skasowana habilitacja nadal osiągalna, widok zwracał 200 zamiast 404 |

**Wniosek dla fazy 03:** szukaj konsumentów NIE tylko w kodzie, który
zmieniasz, i NIE tylko w tym repo. Kronikę zweryfikowaliśmy dopiero po
sprawdzeniu repozytoriów siostrzanych (`bpp-deploy` faktycznie ją
referencuje — na szczęście tylko w komentarzach i jednej kontrolce).

---

## 3. Co faza 03 dziedziczy — i czego NIE ma dziedziczyć

### 3.1 `xfail(strict=True)`, który sam się upomni

`test_kanarek_orm_join_po_publikacji_ma_predykat_deleted_at` jest
`xfail(strict=True)` z powodem „faza 03". Gdy naprawisz wycieki, test
zacznie padać jako XPASS i **wymusi** zdjęcie markera. Nie „napraw testu" —
zdejmij marker.

Analogicznie działa `test_upstream_nadal_ma_blad_czyli_shim_jest_potrzebny`:
padnie, gdy upstream easyauditu scali poprawkę, i każe skasować
`src/bpp/easyaudit_shim.py`.

### 3.2 ⚠️ Tabelka 10 wycieków NIE jest gotową listą zadań

To najważniejsze zastrzeżenie całego handoffu. Kanarek ORM dopasowuje
**NAZWY**, nie modele. W fazie 01 działał świetnie, bo nazwy były
dystynktywne (`autorzy_set`). W fazie 02 to zwykłe słowa (`patent`,
`rekord`, `wydawnictwo_ciagle`) i precyzja się załamuje:

- lista 5 nazw daje 14 znalezisk,
- dołożenie `rekord` i `wydawnictwo_nadrzedne` daje **120**,
- z czego większość to fałszywe trafienia, bo `rekord` oznacza raz
  publikację, raz widok `Rekord` (**już przefiltrowany** przez `0497`),
  a raz parametr GET albo klucz formularza.

**Nie rozszerzaj listy `RELACJE` i nie triażuj 120 pozycji ręcznie.**
Zbuduj narzędzie **model-aware**: rozwiązujące ścieżkę lookupu wobec
`_meta` Django i pytające, czy faktycznie dochodzi do tabeli soft-delete —
czyli robiące dla ORM to, co kanarek katalogowy robi na `pg_depend`.

### 3.3 Klasa wycieku, której kanarek NIE MOŻE złapać

Dostęp **atrybutowy** do relacji (`autor.praca_habilitacyjna`,
`*.wydawnictwo_nadrzedne`) omija soft-delete i nie jest wywołaniem ORM, więc
AST-owy skaner go nie widzi. Potrzebny osobny przegląd. Naprawa centralna
odpada: `Meta.base_manager_name` na menedżer filtrujący jest przez Django
jawnie odradzany (rozwaliłby deserializację i `refresh_from_db`).

---

## 4. Fakty o kodzie, które w fazie 02 kosztowały rundę poprawek

- **`_base_manager` jest NIEprzefiltrowany** i Django tworzy go sam, gdy
  model nie ustawia `Meta.base_manager_name`. Ratuje to easyaudit i psuje
  trawersowanie relacji — ta sama właściwość, dwa przeciwne skutki.
- **`slug` zawiera `pk`** (`models/util.py:246-254`:
  `tytuł-źródło-autorzy-<content_type_pk>-<pk>`). Kolizja slugów jest
  konstrukcyjnie niemożliwa — dlatego Task 3 planu został świadomie
  niewykonany (patrz box w planie fazy 02).
- **`slugify_function` BPP NIE obniża wielkości liter.**
- **Menedżer w ciele klasy przesłania ten z bazy abstrakcyjnej.** Dlatego
  `Wydawnictwo_Ciagle.objects` pokazywało kosz aż do Taska 4, mimo że model
  dziedziczył `BppPublikacjaSoftDeleteMixin`.
- **`ManagerModeliZOplataZaPublikacjeMixin` NIE jest menedżerem** — to czysty
  mixin bez `get_queryset()`, więc kolejność baz w MRO menedżera NIE jest
  nośna (sprawdzone mutacyjnie). Nośna jest druga baza.
- **`DJANGO_EASY_AUDIT_REGISTERED_CLASSES`** obejmuje 5 modeli publikacji
  i `Zgloszenie_Publikacji`, ale NIE through-modele `*_Autor` — stąd faza 01
  nigdy nie trafiła na błąd easyauditu.
- **Denorm: tylko DWIE zależności celują w publikacje**, obie
  `("self", "wydawnictwo_nadrzedne")` bez `only=`. Brak `only=` = wszystkie
  kolumny w bramce, więc `deleted_at` wchodzi sam. Nie dokładaj
  `denorm_always_only` — byłby martwym kodem.
- **Widoki publikacji mają TRZY różne kształty** (patrz docstring `0497`).
  Wzorzec z `0489` pasuje tylko do dwóch z siedmiu.
- **Postgres normalizuje predykaty w definicjach widoków** — przy jednej
  tabeli w zasięgu usuwa kwalifikację. Wywróciło to najpierw asercję testu,
  potem funkcję `backward` migracji.

---

## 5. Jak pracować (co się sprawdziło)

### Mutacja jest tu jedynym dowodem, że test cokolwiek pilnuje

W fazie 02 mutacje obaliły **cztery** rzeczy — w tym dwie moje własne:

1. test kaskady przechodził częściowo przez efekt uboczny (odroczone
   ograniczenie fazy 01 + `baker` nadający obu autorstwom `kolejnosc=0`),
2. test na pułapkę agregatu był bezwartościowy — odpytywał **cache**, którego
   soft-delete autorstwa nie przelicza, więc nieświeży wiersz maskował
   zdegenerowany widok. Wyrocznią musi być **widok**,
3. test wymiaru publikacji w sumach przechodził mimo wyłączenia OBU migracji,
   bo kaskada `delete()` kasuje też autorstwa, a te są filtrowane od fazy 01.
   Trzeba było testu **izolującego wymiar** (surowy UPDATE),
4. docstring o kolejności baz w MRO menedżera brzmiał wiarygodnie i był
   nieprawdziwy.

**Zasada:** przy każdym teście zapytaj, co musisz zepsuć, żeby spadł na
czerwono — i zepsuj to naprawdę.

### Rozszerz kanarka NA STARCIE — to znowu się opłaciło

Inwentaryzacja widoków na starcie fazy zajęła **19 sekund** i dała pełną
listę 15 widoków w 5 kategoriach, w tym **zadanie, którego nie było w planie**
(Task 2d: 6 widoków agregujących, w planie tylko jako ostrzeżenie „sprawdź").
Kanarek fazy 01 dało się wywołać na rozszerzonej liście tabel BEZ zmiany
stałej modułowej — czyli bez commitowania czerwonego testu.

### Czego nie powtarzać

- ⚠️ **`ruff format` na całym katalogu** przeformatował 25 plików, których nie
  dotykałem. Formatuj TYLKO swoje pliki, inaczej PR staje się nieczytelny.
- ⚠️ **`git stash` przy czystym drzewie to cichy no-op** — do baseline'owania
  używaj `git checkout --detach <ref>`.
- ⚠️ **Zero zdarzeń audytu ≠ zepsuty kod.** Dwie niezależne bramki
  (`dont_log_anonymous_crud_events` bez requestu, brak `settings.TEST` →
  `on_commit` w rollbackowanej transakcji) dają ten sam objaw.
- ⚠️ Na tym hoście biegają cudze stacki. Kontenery ubijaj po ID, po
  sprawdzeniu, czy ryuk jest martwy.

---

## 6. Otwarte decyzje

| Sprawa | Stan |
|---|---|
| **PR upstream do easyauditu** | gałąź gotowa w `~/Programowanie/django-easy-audit` (`fix/175-use-base-manager-in-pre-save`), przetestowana na Django 5.2 i 6.1. **Nie wypchnięta** — czeka na decyzję o koncie/forku. Tekst zgłoszenia gotowy |
| **Strategia wydania** | rekomendacja z fazy 01 bez zmian: scalać fazami, **wydać dopiero po 04**. Faza 03 jest obowiązkowa razem z 02 (bez niej re-import tworzy duplikaty) |
| Pomiar `0492` i narzutu GiST na kopii produkcyjnej | wciąż nikt nie zmierzył (dług fazy 01) |
| `bpp-deploy`: kontrolka „kronika views: N" | po `0499` wypisze 0 i może zmylić operatora. Nieblokujące, opisane w docstringu `0499` |

## 7. Długi pozostałych faz

- **03**: decyzja #14 („pomiń + zaraportuj") niewpięta w taski 2-5; test ma
  literalny placeholder; `deduplikator_autorow/utils/merge.py`
  zrefaktoryzowany. **Plus wszystko z §3 tego dokumentu.**
- **04**: nikt nie przeplata `AutorManager`; `Autor.restore()` musi nadpisać
  `strict=False`; FK flips `CASCADE→PROTECT`. Uwaga: soft-skasowana
  publikacja NADAL trzyma referencję O2O PROTECT do autora, więc autora nie
  da się skasować — to zachowanie poprawne, ale faza 04 musi je obsłużyć w UI.
- **06**: `MetrykaAutora` trzyma listy ID prac w JSON-ach; Task 5 (shim
  `zakolejkuj_*`) martwy po ustaleniach fazy 05 — usunąć.
- **07**: admin (kosz / przywróć / usuń trwale) — konsument `user`/`reason`,
  które faza 02 już przepuszcza w sygnaturach.
