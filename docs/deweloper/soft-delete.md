# Soft-delete (kosz): co jest kasowane miękko, a co nie

!!! info "Dla kogo"
    Strona dla dewelopera i agenta AI. Opisuje stan po całym stosie PR-ów
    soft-delete (#312 → #745 → #755 → #767 → #792). Szczegółowe uzasadnienia
    decyzji są w specu
    `docs/superpowers/specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`
    (katalog `docs/superpowers/` nie wchodzi do zbudowanej dokumentacji —
    czytaj go w repozytorium) i w planach faz `docs/superpowers/plans/2026-06-04-soft-delete-0*.md`.
    Ta strona jest **mapą**: co ma kolumnę `deleted_at`, czego celowo nie ma
    i co się dzieje z danymi powiązanymi.

## Mechanizm w jednym akapicie

Modele soft-delete dziedziczą `SoftDeleteModel` z pakietu
[`django-soft-delete`](https://pypi.org/project/django-soft-delete/)
(`django_softdelete`) — tego samego, którego od dawna używają
`Element_Repozytorium` i `Zgloszenie_Publikacji`. Model dostaje pola
`deleted_at`, `restored_at`, `transaction_id` i trzy menedżery:

| Menedżer | Co widzi | Kiedy używać |
|---|---|---|
| `objects` (domyślny) | tylko żywe wiersze | wyświetlanie, eksport, liczenie, ewaluacja — „kategoria A" |
| `global_objects` | żywe + kosz | import, deduplikacja, dopasowanie po `pbn_uid`/DOI, scalanie autorów — „kategoria B" (inaczej powstają duplikaty) |
| `deleted_objects` | tylko kosz | kosz w adminie, nagrobki, `/api/v1/usuniete/` |

`obj.delete()` to `UPDATE ... SET deleted_at = now()` (przez
`save(update_fields=...)`), `obj.restore()` czyści znacznik,
`obj.hard_delete()` naprawdę kasuje wiersz. Wspólny kod BPP siedzi w
`src/bpp/models/soft_delete.py` (menedżery z blokadą
`.update(deleted_at=...)`, mixiny `BppPublikacjaSoftDeleteMixin` i
`BppAutorstwoSoftDeleteMixin`, guard `raise_if_has_protected_children`),
receivery w `src/bpp/receivers/soft_delete.py`, audyt w
`src/bpp/models/soft_delete_log.py` (`SoftDeleteLog`), kontekst
użytkownika/powodu w `src/bpp/models/soft_delete_context.py`.

Zasada ogólna: **soft-delete dostają rekordy, które operator świadomie
„wyrzuca" i może chcieć odzyskać** (publikacje, puste rekordy autorów).
**Nie dostają go** słowniki, struktura uczelni, tabele cache i wiersze
pochodne, które da się odtworzyć albo które żyją i umierają razem z
rodzicem.

## Tabela: model → soft-delete?

Legenda kolumny „Soft-delete": **TAK** — model ma `deleted_at`;
**NIE** — kasowanie twarde (jak dotąd) albo w ogóle niedotykane;
**?** — otwarte pytanie (patrz niżej).

### Publikacje

| Model | Soft-delete | Dlaczego | Co się dzieje przy `delete()` | Co się dzieje przy `restore()` | PBN | Przyszły django-reversion |
|---|---|---|---|---|---|---|
| `Wydawnictwo_Ciagle` | **TAK** | Rekord bibliograficzny — kasowanie bywa pomyłką; trzeba móc odzyskać i trzeba móc powiedzieć konsumentom (OAI-PMH/CERIF/API), że rekord zniknął | Znika z `objects`, z `bpp_rekord_mat` (trigger), z ewaluacji (`Cache_Punktacja_*` kasowane receiverem), z API/OAI (nagrobek). Wiersze `*_Autor` idą do kosza z tym samym `transaction_id` (wąska kaskada). Dzieci nie-soft (`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`, `Nagroda`, `Element_Repozytorium`) zostają nietknięte. `ostatnio_zmieniony` jest podbijany. Wpis `SoftDeleteLog` | Wracają autorstwa z tym samym `transaction_id` (autorstwo skasowane wcześniej osobno zostaje w koszu), wiersz wraca do `_mat`, `Cache_Punktacja_*` przeliczane, `SoftDeleteLog` | `delete` → wpis kolejki `WYCOFANIE` (kasuje **oświadczenia naszej instytucji**, obiektu publikacji w PBN nie rusza — jest współdzielony); `restore` → `WYSYLKA` | Pola `deleted_at`/`restored_at`/`transaction_id` **nie powinny** być wersjonowane (przywrócenie wersji nie może omijać kosza); „recover deleted" dotyczy tylko `hard_delete` i musi iść przez superusera |
| `Wydawnictwo_Zwarte` | **TAK** | jw. | jw. + **guard**: książka z rozdziałami (`wydawnictwo_nadrzedne`, liczone także w koszu) → `ProtectedError`; FK rozdział→książka to `PROTECT` | jw. | jw. | jw. |
| `Patent` | **TAK** | jw. | jw. (autorstwa w `Patent_Autor`) | jw. | Patentów nie wysyłamy do PBN — kolejka praktycznie nie ma czego wycofać | jw. |
| `Praca_Doktorska` | **TAK** | Jest publikacją (trafia do `Rekord`, API, OAI) | Autor leży na wierszu pracy (FK `PROTECT`), więc nie ma kaskady autorstw | Zwykłe przywrócenie | jw. jak publikacje | jw. |
| `Praca_Habilitacyjna` | **TAK** | jw. | jw.; `Publikacja_Habilitacyjna` (lista prac wchodzących w habilitację) zostaje nietknięta. `autor` zamieniony z `OneToOne` na `FK` + warunkowy unique „jedna **żywa** habilitacja na autora" | Zwykłe przywrócenie; konflikt, jeśli autor ma już drugą żywą habilitację | jw. | jw. |

### Powiązania autor ↔ publikacja (tabele łączące)

| Model | Soft-delete | Dlaczego | `delete()` | `restore()` | PBN | reversion |
|---|---|---|---|---|---|---|
| `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` | **TAK (stan obecny) — ? (do decyzji)** | Obecny powód (faza 01): ~89 miejsc w kodzie czyta `*_Autor.objects` bezpośrednio (głównie `ewaluacja_optymalizacja`); domyślny menedżer ukrywający kosz sprawił, że skasowana publikacja automatycznie przestaje się liczyć. Koszt: warunkowe `UniqueConstraint` + `ExclusionConstraint` (GiST) zamiast `unique_together`, migracje z oknem serwisowym, a **usunięcie autora z inline'a w adminie też ląduje w koszu** (wiersze-śmieci) | Soft (także przy edycji inline'a) | Tylko razem z publikacją (`transaction_id`); pojedynczo — `restore()` w kodzie, brak UI | Nie wysyłamy osobno; zmiana składu autorów idzie z publikacją | Jeśli zostaną soft-delete: wykluczyć pola kosza z wersji. Jeśli nie: zwykłe `follow` z publikacji |
| `Zgloszenie_Publikacji_Autor` | **NIE** | Część zgłoszenia (`Zgloszenie_Publikacji` ma własny, starszy soft-delete) | FK `autor` zmieniony na `PROTECT` (faza 05) | — | — | — |

!!! question "Rekomendacja dla tabel łączących"
    Właściciel projektu skłania się do tego, żeby tabele łączące **nie**
    miały `deleted_at`. Rozsądny wariant: `*_Autor` bez własnego kosza,
    a domyślny menedżer `objects` filtruje po rodzicu
    (`rekord__deleted_at__isnull=True`), trigger `bpp_autorzy_mat`
    reaguje na `deleted_at` publikacji, edycja autorów w adminie zostaje
    twardym kasowaniem. Zachowuje to ochronę ~89 miejsc w ewaluacji bez
    warunkowych constraintów. Zmiana dotyka fazy 01 (migracje
    0509–0514 + widoki 0510/0515/0516), więc decyzja musi zapaść **przed**
    scaleniem #312. Szczegóły w raporcie z przeglądu (PR #312).

### Autorzy i struktura

| Model | Soft-delete | Dlaczego | `delete()` | `restore()` | PBN | reversion |
|---|---|---|---|---|---|---|
| `Autor` | **TAK, ale tylko „pusty" autor** | Realny przypadek to duplikaty, literówki, husk po scaleniu. Autor z pracami nie jest kasowany wcale | **Guard**: jakiekolwiek autorstwo (także w koszu), doktorat, habilitacja albo udział w projekcie → `ProtectedError` z komunikatem. Bez prac → do kosza. Dzieci nie-soft (`Autor_Jednostka`, `Autor_Dyscyplina`, `Autor_Absencja`, `WybranaPublikacjaAutora`…) zostają nietknięte — `Autor.delete()` celowo nie woła kaskady pakietu (ta kasowałaby je **twardo**) | Zwykłe przywrócenie | Autora nie wycofujemy z PBN | `Autor` jest już wersjonowany na `dev` (`bpp/wersjonowanie.py`); pola kosza są wykluczone z wersji |
| `Autor_Jednostka`, `Autor_Dyscyplina`, `Autor_Absencja`, `Projekt_Autor` | **NIE** | Dane kadrowe/ewaluacyjne autora; żyją z autorem | Bez zmian (twardo, gdy edytowane) | — | — | — |
| `Jednostka`, `Wydzial`, `Uczelnia` | **NIE** | Struktura, rzadko kasowana | Twardo, jak dotąd. Uwaga: `*_Autor.jednostka` ma `CASCADE` — kasowanie jednostki kasuje **twardo** autorstwa z pominięciem kosza, logu i PBN | — | — | — |

### Słowniki, cache, integracje

| Model | Soft-delete | Dlaczego / co się dzieje |
|---|---|---|
| `Zrodlo`, `Wydawca`, `Konferencja`, `Seria_Wydawnicza`, `Charakter_Formalny`, `Jezyk`, `Typ_KBN`, … | **NIE** | Słowniki. Kasowanie twarde. `Konferencja`/`Seria_Wydawnicza` mają `CASCADE` do publikacji — ich skasowanie twardo kasuje publikacje z pominięciem kosza (znana luka). Nagrobki OAI dla słowników biorą się wyłącznie z „dopełnienia ekspozycji" |
| `*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`, `Nagroda`, `Publikacja_Habilitacyjna`, `Element_Repozytorium` (ma własny, starszy soft-delete), `WybranaPublikacjaAutora` | **NIE** (poza `Element_Repozytorium`) | Dzieci publikacji. Nie są ruszane przy `delete()`/`restore()` — wracają razem z rodzicem bez żadnej pracy. Każde miejsce, które czyta je **bez przejścia przez rodzica** (API sub-zasoby, „ostatnie streszczenia", wyróżnione prace na profilu autora przez GenericFK), musi samo odfiltrować `rekord__deleted_at` |
| `bpp_rekord_mat`, `bpp_autorzy_mat` (`Rekord`, `Autorzy`) | **NIE** | Tabele cache. Trigger usuwa wiersz przy soft-delete i odtwarza go z widoku przy restore. Widoki źródłowe i pochodne filtrują `deleted_at IS NULL` (pilnuje tego test `test_kanarek_katalogowy.py`) |
| `Cache_Punktacja_Autora`, `Cache_Punktacja_Dyscypliny` | **NIE** | Kasowane receiverem przy soft-delete, przeliczane przy restore |
| `PBN_Export_Queue` | **NIE** | Kolejka; dostała pole `operacja` (`WYSYLKA`/`WYCOFANIE`) |
| `SentData` | **NIE** | Dostała `withdrawn_at` (oświadczenia wycofane) |
| `SoftDeleteLog` | **NIE** | Audyt „kto, kiedy, dlaczego, status PBN" dla delete/restore/hard_delete |
| `pbn_api.*` (lustro PBN) | **NIE** | Dane z PBN; kosz BPP ich nie dotyczy |
| `Zgloszenie_Publikacji` | **TAK (od dawna, osobno)** | Własny mechanizm zgłoszeń; receivery stosu logują go tak jak resztę |

## Zasady dla kodu, który dopisujesz

1. **Czytasz publikacje/autorów do wyświetlenia, eksportu, liczenia** →
   `objects` / `Rekord` (kosz jest ukryty).
2. **Dopasowujesz rekordy przy imporcie, deduplikacji, scalaniu** →
   `global_objects` i zdecyduj jawnie, co zrobić z trafieniem w kosz
   (spec §2.5, decyzja #14).
3. **Czytasz dziecko publikacji bez przechodzenia przez rodzica**
   (`*_Streszczenie.objects`, GenericFK, surowy JOIN po `*_autor`) →
   dołóż `rekord__deleted_at__isnull=True`.
4. **Nowy widok SQL czytający tabele publikacji lub `*_autor`** → filtr
   `deleted_at IS NULL` na **każdej** czytanej tabeli soft-delete;
   `test_kanarek_katalogowy.py` padnie, jeśli zapomnisz.
5. **Nigdy** `queryset.update(deleted_at=...)` — tylko `.delete()` /
   `.restore()` per instancja (inaczej omijasz sygnały, `SoftDeleteLog`,
   PBN i przyszły reversion).
6. **`hard_delete()`** wyłącznie z kosza i wyłącznie świadomie (superuser);
   kaskady Django przy twardym kasowaniu słowników omijają cały ten
   przepływ.

## Otwarte pytania

Lista do rozstrzygnięcia przez właściciela przed scaleniem stosu jest
w raporcie z przeglądu stosu (listopad 2026); najważniejsze:

- czy tabele łączące `*_Autor` mają mieć własny kosz (patrz ramka wyżej),
- czy import PBN ma **wskrzeszać** rekordy z kosza (tak jest dziś w
  `pbn_integrator/kosz.py`), czy je pomijać i raportować (spec §2.5),
- co z twardymi kaskadami ze słowników (`Konferencja`, `Seria_Wydawnicza`,
  `Jednostka`) — `PROTECT` czy świadome obejście kosza,
- czy wyróżnione prace (`WybranaPublikacjaAutora`) skasowanej publikacji
  mają znikać z profilu autora.
