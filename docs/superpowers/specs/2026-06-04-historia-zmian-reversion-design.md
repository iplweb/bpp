# Spec: Historia zmian rekordów (django-reversion) — z myślą o rozliczalności i soft-delete

> ⏳ **STATUS: USTALENIA ZATWIERDZONE, IMPLEMENTACJA ODŁOŻONA do po soft-delete.**
> Ten dokument utrwala decyzje z brainstormingu (2026-06-04) o tym, jak BPP ma
> trzymać **widoczną w adminie historię zmian** rekordów — przede wszystkim po
> to, by człowiek mógł wyjaśnić „kto usunął / zmienił to i to w tym rekordzie".
>
> Wdrożenie soft-delete (osobny, aktywny projekt:
> [`2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](2026-06-04-soft-delete-publikacje-i-autorzy-design.md))
> jest **w toku**. Część odwołań do kodu poniżej (nazwy mixinów admina, ścieżka
> `delete()/restore()`, model `SoftDeleteLog`) opisuje stan **docelowy** tego
> projektu — gdy soft-delete wyląduje, ten spec będzie wymagał aktualizacji
> referencji. **Decyzje i kontrakty integracyjne (sekcja 4) pozostają.**

**Cel:** Audytowalność edycji ludzkich. Operator wchodzi na rekord w adminie,
otwiera „Historię" i widzi ciągłą oś: kto utworzył, kto co zmienił (z
porównaniem pól), kto usunął i kto przywrócił — z możliwością cofnięcia do
wcześniejszej wersji. To narzędzie do **diagnozy błędów ludzi**, nie total-audyt
bazy.

**Architektura (jednozdaniowo):** Rozszerzamy istniejący w repo
`django-reversion` (`VersionAdmin` + `reversion-compare`, już używany na
`Uczelnia`) na zdefiniowany zbiór modeli najczęściej edytowanych ręcznie;
soft-delete i restore wpinamy w tę samą oś historii przez
`reversion.create_revision()`.

**Stack:** Django admin, `django-reversion>=6.2` + `django-reversion-compare`
(oba już w `pyproject.toml`), wbudowany `django.contrib.admin.models.LogEntry`
(już aktywny).

---

## 1. Motywacja i czego NIE robimy

Główne źródła problemów edycyjnych to **zgłoszenia publikacji** oraz **rekordy
wydawnictw**; do tego dochodzi struktura (`Uczelnia`, `Jednostka`, `Wydzial`)
i `Autor`. Potrzeba: wejść w rekord i wyjaśnić „kto to zrobił i kiedy", łącznie
z usunięciami.

Świadomie **nie** chcemy śledzić każdej zmiany w bazie na każdym poziomie
(bulk-importy, surowy SQL, triggery). To byłby total-audyt — inne narzędzie,
inny koszt, inny use-case.

## 2. Decyzja o narzędziu

| Narzędzie | Werdykt | Dlaczego |
|---|---|---|
| **django-reversion** (+ `reversion-compare`) | ✅ **wybrane** | Już w repo (na `Uczelnia` jako goły `VersionAdmin` = oś wersji + revert + „kto/kiedy/komentarz"; szablon historii już ostylowany). **Diff pól** (side-by-side) wymaga `CompareVersionAdmin` z `reversion-compare` — pakiet jest zainstalowany, ale **nie jest jeszcze wpięty w żaden admin** (grep: 0 trafień); to dorobimy. Zakres selektywny (per-model). |
| django-pghistory | ❌ | Triggerowy total-audyt DB (łapie bulk/SQL). Rozwiązuje *inny* problem niż „historia edycji w adminie"; jego admin to log zdarzeń, nie oś wersji z revertem. |
| django-simple-history | ❌ | Duplikuje każdą tabelę (`_historical`) — zła kombinacja z 5 dużymi tabelami publikacji; dubluje paradygmat, który już mamy w reversion; nie wykorzystalibyśmy jego głównej przewagi (compare mamy w reversion-compare). |

> Reversion „z pudełka" hookuje się w ORM (`post_save` / context rewizji), więc
> łapie **edycje przez admin** (+ jawne `create_revision`). Zmiany maszynowe
> (import, SQL) zostają niewidoczne — i to jest **akceptowalne**, bo celem jest
> rozliczalność ludzi, a nie total-audyt (sekcja 1).

**Zaleta wdrożeniowa:** włączenie reversion na kolejnym modelu **nie wymaga
migracji** — rejestracja jest runtime, a tabele `Revision`/`Version` już istnieją
(reversion działa w repo). Kontrast z simple-history (migracja + osobna tabela
`_historical` na każdy model).

## 3. Co BPP już ma (punkt wyjścia)

- **Warstwa 0 — wbudowany `LogEntry`.** Każda strona zmiany w adminie ma już
  link „Historia" z `add/change/delete` + user. BPP buduje na tym filtry
  (`src/bpp/admin/filters.py`: `OstatnioZmienionePrzezFilter`,
  `UtworzonePrzezFilter`). Ograniczenie: tylko akcje z admina, tylko opis
  tekstowy (które pola), bez wartości pól, bez revertu. **Zostaje jako druga
  siatka bezpieczeństwa.**
- **Warstwa 1 — reversion na `Uczelnia`.** `UczelniaAdmin(... VersionAdmin)`
  (`src/bpp/admin/uczelnia.py`, **goły `VersionAdmin`** z `reversion.admin`) —
  daje oś wersji + revert + „kto/kiedy/komentarz", ale **nie** diff pól (to
  `CompareVersionAdmin`, sekcja 4). Szablon historii
  `src/django_bpp/templates/reversion/object_history.html` jest już ostylowany
  (Grappelli). Koszt integracji częściowo zapłacony — UX historii gotowy, brakuje
  wpięcia compare.

## 4. Zakres — modele do objęcia `VersionAdmin`

Dziś wszystkie poniższe (poza `Uczelnia`) używają gołego `admin.ModelAdmin`.
Zmiana to dorzucenie do MRO **`CompareVersionAdmin`** (z `reversion_compare.admin`
— daje historię + revert **oraz** side-by-side diff pól; rozszerza `VersionAdmin`).
Goły `VersionAdmin` (jak dziś na `Uczelnia`) wystarcza, gdy diff pól niepotrzebny
— ale skoro celem jest „kto **co** zmienił", `CompareVersionAdmin` jest domyślnym
wyborem. (`Uczelnia` warto przy okazji podnieść z `VersionAdmin` na
`CompareVersionAdmin`.)

| Model | Admin | Baza dziś | Uwagi |
|---|---|---|---|
| `Zgloszenie_Publikacji` | `Zgloszenie_PublikacjiAdmin` (`src/zglos_publikacje/admin/zgloszenie_publikacji.py`) | `admin.ModelAdmin` | inline'y `_Autor`, `_Zalacznik` → `follow` |
| `Wydawnictwo_Ciagle` | `Wydawnictwo_CiagleAdmin` | `admin.ModelAdmin` | liczne inline'y (`_Autor`, `Zewnetrzna_Baza`…) → `follow` |
| `Wydawnictwo_Zwarte` | `Wydawnictwo_ZwarteAdmin` | `admin.ModelAdmin` | jw. |
| `Praca_Doktorska`, `Praca_Habilitacyjna`, `Patent` | (analogiczne) | `admin.ModelAdmin` | dla spójności całej rodziny publikacji |
| `Wydawca` | `WydawcaAdmin` (`src/bpp/admin/wydawca.py`) | `admin.ModelAdmin` | bez inline'ów |
| `Autor` | `AutorAdmin` (`src/bpp/admin/autor.py`) | `admin.ModelAdmin` | też w zakresie soft-delete |
| `Wydzial` | `WydzialAdmin` | `admin.ModelAdmin` | |
| `Jednostka` | `JednostkaAdmin` | `DraggableMPTTAdmin` ⚠️ | MRO `VersionAdmin`+MPTT — przetestować drzewo (drag&drop zmienia `lft/rght/level`) |
| `Uczelnia` | `UczelniaAdmin` | ✅ goły `VersionAdmin` | działa (oś+revert), bez diffa; opcjonalnie podnieść na `CompareVersionAdmin` |

> **Zgłoszenia publikacji** są **tworzone** przez userów (front-end:
> `src/zglos_publikacje/views.py`), a **edytowane w adminie** — więc reversion
> (admin) pokrywa edycję, czyli to, co nas interesuje. Niuans niskiej wagi: samo
> userowe *utworzenie* nie jest rewizją admina, więc historia rekordu zaczyna się
> od pierwszej zmiany w adminie (lub od `createinitialrevisions`). Jeśli kiedyś
> chcemy w historii także autora pierwotnego zgłoszenia — owinąć widok tworzenia
> w `create_revision()` (opcjonalne, nie blokuje).

## 5. Relacja do `SoftDeleteLog` — komplementarność, nie duplikacja

Aktywny design soft-delete wprowadza **`SoftDeleteLog`** (§5 tamtego dokumentu)
zasilany sygnałami `post_soft_delete`/`post_restore`/`post_hard_delete`. To dwa
różne narzędzia o różnym celu — **mają współistnieć**:

| | `SoftDeleteLog` (soft-delete design) | reversion (ten spec) |
|---|---|---|
| Co rejestruje | **zdarzenia** delete/restore/hard-delete | **pełną historię edycji pól** (każda zmiana) |
| Zakres | wszystkie soft-deletowalne typy | zdefiniowany zbiór najczęściej edytowanych ręcznie (sekcja 4) |
| Granularność | jeden wpis na zdarzenie kasowania | migawka stanu rekordu przy każdym zapisie |
| Pyta | „co/kto/dlaczego zniknęło + status PBN" | „jak ten rekord wyglądał w punkcie X i kto go zmieniał" |
| UX | widok „Kosz" | zakładka „Historia" + compare + revert |

`SoftDeleteLog` jest **centralnym, przekrojowym** rejestrem kasowań (i nośnikiem
statusu PBN). reversion jest **per-rekordową** osią całej edycji. Pierwszy
odpowiada „co dziś jest w koszu i czemu"; drugi — „prześledźmy ten konkretny
rekord od początku".

## 6. Kontrakty integracyjne z soft-delete (TO MUSI WEJŚĆ DO PRAC SOFT-DELETE)

To jest sedno utrwalone w tym spec-u. Bez tych trzech rzeczy soft-delete będzie
technicznie poprawny, ale **główny use-case („kto usunął, widoczne w Historii")
cicho nie zadziała**.

### 6.1 Soft-delete i restore MUSZĄ tworzyć rewizję reversion

`VersionAdmin` pokazuje w „Historii" **tylko rewizje reversion**. Soft-delete w
adminie idzie ścieżką `delete_view`→`delete_model`→`obj.delete()` (UPDATE
`deleted_at`), której reversion domyślnie **nie** owija w rewizję. Skutek bez
naprawy: usunięcie nie pojawi się w zakładce, w którą operator patrzy.

Naprawa — w adminie modeli objętych `VersionAdmin` owijamy soft-delete i restore
w rewizję, z atrybucją usera i komentarzem:

```python
import reversion

def delete_model(self, request, obj):
    # self.create_revision(request) = helper VersionAdmin; sam robi set_user(request.user)
    with self.create_revision(request):
        reversion.set_comment("Usunięto (soft-delete)")
        super().delete_model(request, obj)   # → obj.delete() = UPDATE deleted_at
# analogicznie delete_queryset() (akcja masowa) oraz akcja "Przywróć" → set_comment("Przywrócono")
```

> **Twardy warunek poprawności:** nadpisany w projekcie soft-delete
> `delete()`/`restore()` (§2.2 tamtego design) **musi nadal wołać `instance.save()`**.
> Zweryfikowane: pakietowy `delete()` robi `self.save(update_fields=[...])`
> (`django_softdelete/models.py:163`), na czym wisi `post_save`, który reversion
> przechwytuje w bloku rewizji. Gdyby ktoś „zoptymalizował" override na
> `queryset.update()` (bulk), `post_save` nie odpali i historia usunięć **po cichu
> zniknie**.

Ponieważ soft-delete utrzymuje wiersz, oś czasu reversion pozostaje **ciągła**:
`utworzono → edycje → usunięto → przywrócono → edycje` w jednej zakładce. (To
działa lepiej niż reversion na twardym delete, gdzie obiekt znika.)

### 6.2 Atrybucja „kto" — jeden punkt dla reversion i `SoftDeleteLog`

Oba mechanizmy potrzebują `request.user` z warstwy admina:
- `SoftDeleteLog` — przez jawne `delete(user=...)` (§5 soft-delete design),
- reversion — przez `reversion.set_user(request.user)` w `create_revision`.

Sygnały pakietu nie niosą requestu (§5 soft-delete design, „niuans kto"). Punkt
wstrzyknięcia usera w adminie powinien **zasilić oba** naraz — to ten sam
moment akcji superusera.

### 6.3 `VersionAdmin` musi komponować się z mixinem soft-delete admina; ukryć „recover deleted"

- MRO: admin łączy `VersionAdmin` z mixinami soft-delete (kosz/filtr/przywróć,
  `get_queryset → global_objects`) — zweryfikować kolejność.
- **`get_queryset → global_objects`** jest już w planie soft-delete (§6 tamtego
  design: admin świadomie używa `global_objects`/`deleted_objects` + filtr
  „Pokaż skasowane"). To **odpowiada na pytanie „czy admin obejrzy usunięte"**:
  tak — dzięki temu usunięty rekord da się otworzyć i przeczytać jego Historię.
  reversion tu nic nie zmienia, tylko korzysta z tego, że wiersz jest osiągalny.
- **Ukryć reversion „recover deleted".** Lista recover bierze wersje, których
  wiersz już **nie istnieje** (`Version.objects.get_deleted`). Soft-deletowany
  rekord wiersz **ma** (`deleted_at` ustawione) → w recover-liście się **nie
  pojawi**, więc dla soft-delete jest po prostu pusta. Realny problem to
  **`hard_delete`**: usuwa wiersz, więc reversion-recover mógłby go wskrzesić
  *poza* przepływem (bez `WYSYLKA` w `pbn_export_queue`, bez `SoftDeleteLog`,
  z ryzykiem złamania warunkowego unique na `slug`). Dlatego recover ukrywamy.

## 7. Pozostałe punkty (mniejszej wagi, ale realne)

- **Inline'y → `follow` (automatyczne).** `VersionAdmin`/`CompareVersionAdmin`
  **samo** rejestruje i `follow`-uje modele inline zadeklarowane w `self.inlines`
  (`reversion/admin.py:145-154`) — autorzy/załączniki `Zgloszenie_Publikacji` i
  wydawnictw wejdą do rewizji bez dodatkowej pracy. Realny caveat: relacje
  edytowane **spoza** zadeklarowanych inline'ów nie są objęte — wtedy `follow`
  trzeba dodać ręcznie.
- **Szablon historii a compare.** Ostylowany `object_history.html` renderuje
  płaską tabelę bez kontrolek wyboru wersji do porównania. `CompareVersionAdmin`
  potrzebuje w historii radio-inputów do wskazania pary wersji — szablon trzeba
  rozszerzyć o ten selektor (albo użyć `compare_history` z `reversion_compare`).
  Banał, ale konieczny, żeby diff był klikalny.
- **Backfill historii (decyzja otwarta).** Reversion zna tylko zmiany *po*
  wdrożeniu. Pierwsza wersja starego rekordu powstaje przy pierwszej edycji albo
  jednorazowo przez `manage.py createinitialrevisions <app.Model>`. Na 5 dużych
  tabelach to ciężka operacja — rozstrzygnąć: backfill czy „historia od teraz".
- **Wolumen i retencja.** Gorące tabele (wydawnictwa) → `reversion_version`
  rośnie. Z czasem rozważyć `deleterevisions --days=N` albo świadomie trzymać
  wszystko. (Symetrycznie do retencji soft-delete: tam „brak auto-czyszczenia".)
- **MPTT (`Jednostka`).** Drag&drop zmienia `lft/rght/level`; zdecydować czy te
  zmiany mają trafiać do historii i przetestować MRO `VersionAdmin`+MPTT-admin.

## 8. Kolejność prac (gdy ruszymy — po/obok soft-delete)

> Szczegółowy plan TDD → `superpowers:writing-plans`. To tylko szkic kolejności.

1. **Podpięcie `VersionAdmin`** pod modele bez soft-delete i bez inline'ów
   (`Wydawca`, `Wydzial`) — najprostsze, weryfikacja UX na `run-site`.
2. **Modele z inline'ami** (`Zgloszenie_Publikacji`, wydawnictwa) — z naciskiem
   na `follow` (autorzy/załączniki w rewizji).
3. **Kontrakty integracyjne z soft-delete** (sekcja 6) — owinięcie
   `delete_model`/restore w rewizję, wspólny punkt usera, ukrycie recover.
   **Wymaga koordynacji z pracami soft-delete** (admin tych modeli powstaje tam).
4. **`Jednostka` (MPTT)** — na końcu, osobny test drzewa.
5. **Decyzja o backfillu** (`createinitialrevisions`) i retencji rewizji.
6. **Testy:** Historia pokazuje delete/restore z userem; compare; revert;
   usunięty rekord otwieralny i czytelny.

## 9. Decyzje rozstrzygnięte (brainstorming 2026-06-04)

1. **Narzędzie:** `django-reversion` + `CompareVersionAdmin` z `reversion-compare`
   (rozszerzenie istniejącego; diff pól). pghistory i simple-history odrzucone
   (sekcja 2).
2. **Zakres:** edycje ludzkie przez admin na zdefiniowanym zbiorze modeli
   (sekcja 4); **nie** total-audyt bazy.
3. **Soft-delete w historii:** usunięcie i restore mają być rewizjami reversion
   (sekcja 6.1), żeby „kto usunął" był widoczny w zakładce Historia — obok
   wpisu w `SoftDeleteLog`.
4. **Komplementarność z `SoftDeleteLog`:** współistnieją (sekcja 5).
5. **Widoczność usuniętych w adminie:** zapewnia ją `get_queryset →
   global_objects` z projektu soft-delete (sekcja 6.3); recover reversion ukryty.

## 10. Otwarte decyzje

1. Czy `Autor` i `Jednostka` na pewno w zakresie compare/revert (oba są
   „ciężkie": Autor — w zakresie soft-delete; Jednostka — MPTT).
2. Backfill `createinitialrevisions` na 5 dużych tabelach: tak / „od teraz".
3. Polityka retencji rewizji (`deleterevisions`) — czy i po ilu dniach.
4. Czy zmiany pozycji w drzewie `Jednostka` (MPTT) mają być wersjonowane.

## 11. Precedensy w repo

- `django-reversion>=6.2.0` + `django-reversion-compare>=0.19.2` —
  `pyproject.toml`. Uwaga: `reversion_compare` jest w `INSTALLED_APPS`, ale
  **żaden admin nie używa `CompareVersionAdmin`** (grep: 0 trafień) — compare
  jest do wpięcia od zera.
- `src/bpp/admin/uczelnia.py` — goły `VersionAdmin` w akcji (wzorzec MRO; bez diffa).
- `src/django_bpp/templates/reversion/object_history.html` — gotowy, ostylowany
  szablon historii (nie trzeba robić od zera).
- `src/bpp/admin/filters.py` — filtry na wbudowanym `LogEntry` (warstwa 0).
- [`2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](2026-06-04-soft-delete-publikacje-i-autorzy-design.md)
  — aktywny projekt soft-delete; sekcje 5 (`SoftDeleteLog`) i 6 (Admin) są
  punktami styku tego spec-u.
