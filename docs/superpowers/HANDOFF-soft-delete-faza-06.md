# Handoff: soft-delete, start fazy 06

> Po zamknięciu **fazy 05a** (wycofanie z PBN), 2026-08-12.
> Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Stan fazy 05a | gałąź `feat/soft-delete-05`, PR do `feat/soft-delete-04` (stacked) |
| Punkt startowy fazy 06 | `feat/soft-delete-05` |
| Migracje fazy 05a | `pbn_export_queue/0011` (pole `operacja`), `pbn_api/0080` (`SentData.withdrawn_at`), `zglos_publikacje/0028` (state-only, dług fazy 04) |
| **Zakres rozdzielony** | nagrobki OAI-PMH/CERIF/REST **wyszły do fazy 05b** (decyzja właściciela 2026-08-10) |

⚠️ **Faza 05 była w planie JEDNĄ fazą o dwóch niezależnych podsystemach.**
Wycofanie z PBN miało drobiazgowy plan (1286 linii); nagrobki miały baner
zakresu i **zero tasków**. Rozdzielone — patrz §5.

⚠️ **Baseline (`baseline-sql/`) nadal NIEŚWIEŻY** — stoi na `bpp/0487`.
Zgodnie z CLAUDE.md odświeżenie robi się **raz, przy scalaniu** całego
`feat/soft-delete` do `dev`. Doszły trzy migracje, więc będzie ich więcej
do nadgonienia.

⚠️ **CI NIE URUCHAMIA SIĘ na PR-ach do gałęzi `feat/soft-delete*`** — bez
zmian względem faz 02–05. Jedyną weryfikacją jest przebieg lokalny.

---

## 2. Co faza 05a dostarcza fazie 06

Kontrakt **PINNED** — faza 06 woła to z receiverów sygnałów:

```python
from pbn_export_queue.operacje import zakolejkuj_wycofanie, zakolejkuj_wysylke
```

| Element | Gdzie | Uwaga |
|---|---|---|
| `wycofaj_oswiadczenia(publikacja, client, uczelnia=None)` | `pbn_api/wycofanie.py` | JEDYNE miejsce wołające `delete_all_publication_statements` w kontekście soft-delete |
| `StatusWycofania` / `WynikWycofania` | `pbn_api/wycofanie.py` | `WYCOFANO` / `BRAK_OSWIADCZEN` / `POMINIETO` |
| `PBN_Export_Queue.Operacja` | `pbn_export_queue/models.py` | `WYSYLKA` (default) / `WYCOFANIE` |
| `zakolejkuj_wycofanie` / `zakolejkuj_wysylke` | `pbn_export_queue/operacje.py` | **funkcje modułowe**, nie metody managera |
| `pobierz_konto_techniczne()` / `NAZWA_KONTA_TECHNICZNEGO` | `pbn_export_queue/operacje.py` | `zamowil` dla operacji systemowych |
| `SentData.withdrawn_at` + `mark_as_withdrawn` | `pbn_api/models/sentdata.py` | per-uczelnia; `mark_as_successful` zeruje |

⇒ **Faza 06 POMIJA swój Task 5 (shim `operacje.py`)** — te funkcje już
istnieją pod ścieżką, której szuka jej check. Shim z planu 06 tworzył wpisy
gołym `PBN_Export_Queue.objects.create(...)`, więc omijałby
`sprobuj_utowrzyc_wpis` (TOCTOU, `uczelnia`, `operacja`).

### Rozstrzygnięcia, których plan 06 może się nie spodziewać

- **`zakolejkuj_wysylke` NIE ma gate'u na `pbn_uid`**, choć kontrakt PINNED
  planu 06 pisał „None gdy brak pbn_uid" dla OBU funkcji. Rekord, który
  nigdy nie poszedł do PBN, po przywróceniu i tak ma prawo pojechać —
  wysyłka dopiero nadaje PBN UID. Docstring mówi to wprost, żeby nikt nie
  „naprawił" tego pod opis z planu 06.
- **`zamowil` to konto techniczne, nie `None`.** Dług, który spec §4.2
  i plany 05/06 przerzucały między sobą, jest zamknięty.

---

## 3. ⚠️ DWA BLOKERY, których plan fazy 05 nie znał (i czego uczą)

Oba miały **jedną przyczynę**: `check_if_record_still_exists()`
(`pbn_export_queue/models.py:170`) nie wiedział, PO CO pytamy. Faza 02
dopisała do niego (commit `2e3b38611`):

```python
if getattr(obiekt, "deleted_at", None) is not None:
    return False
```

a wycofanie zlecamy **wyłącznie dla rekordów w koszu**.

| | Objaw | Wykrywalność |
|---|---|---|
| **#1** `send_to_pbn()` woła guard przed `_zajmij_atomowo()` | gałąź WYCOFANIE = martwy kod, wpis kończy `FINISHED_ERROR` | jest ślad w bazie |
| **#2** `kolejka_wyczysc_wpisy_bez_rekordow()` (`tasks.py:105`) ma ten sam guard za kryterium | **kasuje zlecenie wycofania**, oświadczenia zostają w PBN | **brak śladu** |

**Rozwiązanie:** guard świadomy operacji — odrzucenie soft-deleted
obowiązuje tylko dla `WYSYLKA`. Jedna zmiana, oba blokery, bo sprzątaczka
woła tę samą metodę na instancji. Rekord skasowany **twardo** nadal daje
`False` dla obu operacji (bez wiersza nie ma `pbn_uid`).

Mutacja potwierdzająca (cofnięcie warunku) wywala oba testy naraz.

**Nauka na przyszłe fazy:** predykat, który skleja „czy wiersz istnieje?"
(fakt o bazie) z „czy operator tego nie usunął?" (polityka), rozsypie się
przy wprowadzeniu drugiej operacji — i to w tylu miejscach, ilu ma
konsumentów. Ten miał trzech.

---

## 4. Miny w testach rozbrojone przy okazji (NIE były długiem fazy 05)

### 4.1 Testy e2e migracji wracały na zaszyty numer

`pbn_api/tests/test_migracja_{dyscypliny_uuid,publikacja_instytucji}_e2e.py`
cofały bazę `MigrationExecutor`-em i przywracały ją do **stałej**
(`0077` / `0079`). Cofnięcie odapplikowuje wszystko powyżej, więc powrót do
stałej zostawiał bazę o tyle migracji w tyle, ile ich przybyło.

Objaw po dodaniu `pbn_api/0080`: Playwrightowy test admina `SentData` padał
`UndefinedColumn` w miejscu bez związku z przyczyną. Reprodukcja
deterministyczna na dwóch plikach.

Poprawka: `przywroc_czubek_migracji()` w `pbn_api/tests/migracje_e2e_utils.py`
— `leaf_nodes()` **całego grafu**.

⚠️ **Zakres ma znaczenie i pierwsza wersja poprawki była za wąska.**
Przywracanie samego `pbn_api` zostawiało `pbn_integrator` bez tabel, bo
`pbn_integrator/0002` **zależy od `pbn_api/0079`**, a Django odapplikowuje
migracje zależne z innych aplikacji razem z tą, do której się cofamy.

### 4.2 Faza 04 pominęła czwartego dziedzica abstraktu

`makemigrations --check` był czerwony. Faza 04 przestawiła `autor` na
`PROTECT` w `BazaModeluOdpowiedzialnosciAutorow`, ale `bpp/0501` objęła
tylko modele z aplikacji `bpp`. **`zglos_publikacje.Zgloszenie_Publikacji_Autor`
dziedziczy ten sam abstrakt** — handoff fazy 04 mówił „dziedziczą 3 modele",
dziedziczy czwarty.

Ochrona **działała** (on_delete żyje w Pythonie); brakowało księgowości
stanu. Poprawka: `zglos_publikacje/0028`, state-only, wzorzec `bpp/0501`.

**Nauka:** zmiana `on_delete` na modelu ABSTRAKCYJNYM rozlewa się na
wszystkie aplikacje, które go dziedziczą, a `makemigrations` zgłasza to
per-aplikacja. Szukanie dziedziczących tylko w `bpp/` nie wystarcza.

---

## 5. Faza 05b — nagrobki (przed fazą 07, nie przed 06)

Wyszła z fazy 05 decyzją właściciela 2026-08-10. **Nie ma jeszcze specu ani
planu** — potrzebuje własnego cyklu brainstorming → spec → plan → PR.

Punkt startowy rozpoznany:

- `src/cerif_export/const.py:115` → **`DELETED_RECORD = "no"`**. To nie jest
  „brak funkcji", to **obietnica w `Identify`**: harvester ma prawo nie pytać
  przyrostowo o usunięcia. Zmiana na `persistent`/`transient` to zmiana
  kontraktu, nie dopisanie atrybutu.
- Emisja nagłówka: `oai/czasowniki.py` (`_naglowek()`), `Identify` w `:198`.
- **Architektura providerów jest gotowa**: `ProviderEncji.strona()`
  (`providers/base.py`) stronicuje keysetem po
  `(COALESCE(ostatnio_zmieniony, EPOKA), pk)`, a soft-delete bumpuje
  `ostatnio_zmieniony`. Husk wpadłby więc **naturalnie na właściwe miejsce
  w kursorze**. Brakuje wyłącznie poszerzenia `queryset()` o kosz i flagi
  „to nagrobek" na obiekcie.
- ⚠️ `z_datestampem()` niesie dwie zapisane blizny (`Trunc` do sekundy,
  `tzinfo=UTC`) — obie o duplikatach na granicy strony. Nagrobki muszą iść
  tą samą ścieżką.
- Modele soft-delete: publikacje (faza 02) + `Autor` (faza 04). Słowniki
  (`Zrodlo`, `Konferencja`, `Projekt`, `Jednostka`) — **nie**.

---

## 6. Czego faza 05a NIE domyka (świadomie)

- **Twarde skasowanie publikacji zostawia oświadczenia w PBN na zawsze.**
  Wycofanie czyta `pbn_uid` z rekordu, więc bez wiersza nie ma czego wołać —
  kończy się `FINISHED_ERROR` (głośno, ale bezradnie). Właściwe rozwiązanie:
  `SoftDeleteLog` fazy 06 niosący `pbn_uid` niezależnie od rekordu. Dziś
  teoretyczne, bo guardy faz 02/04 blokują twarde kasowanie publikacji.
- **Konto techniczne nie ma tokenu PBN**, więc systemowe wycofanie kończy się
  `FINISHED_ERROR` (`WillNotExportError`, błąd MERYTORYCZNY), dopóki
  administrator nie ustawi mu `przedstawiaj_w_pbn_jako` na konto z ważnym
  tokenem. To jest **udokumentowane i przetestowane jako GŁOŚNA porażka** —
  ale znaczy, że mechanizm nie zadziała „z pudełka" bez tej konfiguracji.
  Kandydat do UI/dokumentacji wdrożeniowej.
- **Brak receiverów sygnałów** — to zakres fazy 06. Faza 05a dostarcza
  mechanizm i funkcje, NIE podpina ich do `post_soft_delete`/`post_restore`.
- **Wycofanie nie jest widoczne w UI rekordu.** Operator widzi je tylko
  w kolejce eksportu (kolumna/filtr `operacja`).

---

## 7. Dług nadal otwarty (z faz 01–04, stan bez zmian)

| Sprawa | Stan |
|---|---|
| **Kaskada `Jednostka` → `Autor`** | `aktualna_jednostka`/`aktualna_funkcja` nadal `CASCADE`; skasowanie jednostki, w której autorzy nie mają prac, **twardo kasuje tych autorów**. Patrz handoff fazy 05, §3 |
| **`Autor.slug` `unique=True` bezwarunkowo** | husk trzyma slug zarezerwowany; zaboli w fazie 07 |
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | bez zmian |
| **PR upstream `django-easy-audit`** | [#348](https://github.com/soynatan/django-easy-audit/pull/348) |
| **Brak UI dla `ProtectedError`** | w adminie gołe 500; faza 07 |
| **`Autor` nie ma kosza w adminie** | faza 07 |
| **`hard_delete()` na querysecie nie emituje `post_hard_delete`** | faza 06 |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył |
| **Strategia wydania** | bramka na fazie 07 |

---

## 8. Proces — co się sprawdziło w fazie 05a

- **Przegląd planu przed kodowaniem zwrócił się natychmiast.** Plan powstał
  2026-06-04, rewizje 08-06 i 08-07 sprawdzały kolejkę i klienta PBN — żadna
  nie sprawdziła, co faza 02 dopisała do guardu. Gdyby Task 05.3 wykonać
  „zgodnie z literą", powstałby martwy kod i cicha utrata zleceń.
- **Test, który nie odtwarza scenariusza, nie jest testem.** Test z planu
  dla gałęzi WYCOFANIE **nie kasował rekordu**, więc przeszedłby także przed
  poprawką guardu. Jedna linia (`wydawnictwo_ciagle.delete()`) zmieniła go
  z ozdoby w regresję.
- **Mutacja jako dowód, nie jako rytuał.** Cofnięcie warunku na operacji
  wywaliło oba testy blokerów naraz — to potwierdziło empirycznie, że
  diagnoza „jedna przyczyna, dwa objawy" była trafna, a nie tylko wiarygodna.
- **Szeroka suita wykryła to, czego wąska nie mogła.** Obie miny z §4
  ujawniły się dopiero w pełnym przebiegu — jedna przez kolejność testów,
  druga przez `makemigrations --check`. Wąskie przebiegi per-app były
  zielone przez cały czas.
- **Host jest współdzielony.** W trakcie sesji równolegle biegły kontenery
  innych gałęzi (`fix-wcag`, `fix-bibtex`, `soft-delete-03`) i load sięgał 6+,
  co wywracało start testcontainerów na 120-sekundowym limicie.
  `make clean-testcontainers` **ubiłby cudzą pracę** — nie wolno go odpalać
  w ciemno.
