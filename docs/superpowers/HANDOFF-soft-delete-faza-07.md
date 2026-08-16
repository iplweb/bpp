# Handoff: soft-delete, start fazy 07

> Po zamknięciu **fazy 06** (`SoftDeleteLog` + receivery sygnałów + atrybucja
> usera), 2026-08-16. Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Stan fazy 06 | gałąź `feat/soft-delete-06`, odbita od `feat/soft-delete-05b` |
| Plan fazy 06 | [`plans/2026-06-04-soft-delete-06-softdeletelog.md`](plans/2026-06-04-soft-delete-06-softdeletelog.md) — wykonany, z odstępstwami opisanymi w §3 |
| Migracja fazy 06 | `bpp/0503_softdeletelog` (jedna, tylko `CreateModel`) |
| Task 5 planu | **POMINIĘTY** zgodnie z handoffem fazy 06 — `zakolejkuj_*` istnieją z fazy 05a |

### Stos PR-ów

```
#312  feat/soft-delete       -> dev
#745  feat/soft-delete-04    -> feat/soft-delete
#755  feat/soft-delete-05    -> feat/soft-delete-04
#767  feat/soft-delete-05b   -> feat/soft-delete-05
      feat/soft-delete-06    -> feat/soft-delete-05b   (faza 06, ta praca)
```

⚠️ Żaden PR ze stosu nie jest scalony. Faza 06 dziedziczy commity 05b.

⚠️ **Baseline (`baseline-sql/`) nadal NIEŚWIEŻY** — stoi na `bpp/0487`.
Doszła `0503`. Odświeżenie robi się **raz, przy scalaniu** całego
`feat/soft-delete` do `dev`.

⚠️ **CI NIE URUCHAMIA SIĘ na PR-ach do gałęzi `feat/soft-delete*`** — bez
zmian. Jedyną weryfikacją jest przebieg lokalny.

---

## 2. Co faza 06 dostarcza (kontrakt dla fazy 07)

```python
from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.soft_delete_log import SoftDeleteLog
```

| Element | Gdzie | Uwaga |
|---|---|---|
| `SoftDeleteLog` | `bpp/models/soft_delete_log.py` | GFK + `akcja`/`user`/`powod` + `pbn_queue_entry`/`pbn_status` |
| `soft_delete_context(user=, reason=)` | `bpp/models/soft_delete_context.py` | thread-local; **pominięty argument DZIEDZICZY** (patrz §3.3) |
| `current_soft_delete_user/reason()` | tamże | akcesory dla receiverów |
| Trzy receivery | `bpp/receivers/soft_delete.py` | podpięte BEZ `sender=`, w `BppConfig.ready()` |
| `BppPkPrzedHardDeleteMixin` | `bpp/models/soft_delete.py` | **każdy** model soft-delete MUSI go mieć |
| `pk_dla_audytu(instance)` | tamże | pk po twardym skasowaniu; głośny `RuntimeError` bez mixinu |
| `BppPublikacjaSoftDeleteMixin.uczelnia_rekordu()` | tamże | atrybucja tenanta bez requestu |
| `hard_delete_per_instancja(queryset)` | tamże | queryset-owy `hard_delete()` z sygnałami |

**Realne API atrybucji to `delete(user=, reason=)` / `restore(user=)`** —
fazy 02/04 przyjmowały te argumenty i je porzucały; faza 06 domknęła
obietnicę. Faza 07 (admin) ma po prostu przekazywać `request.user`.

---

## 3. ⚠️ Cztery miejsca, w których plan rozjechał się z kodem

Wszystkie wykryte PRZED napisaniem kodu albo przez padający test — nie po
fakcie. Trzy pierwsze to błędy rzeczowe w planie, nie zmiany zakresu.

### 3.1 `Autor` MA `pbn_uid` (blokujące)

Plan §„Detekcja publikacja z `pbn_uid`" twierdził — jako fakt zweryfikowany —
że „`Autor` i `*_Autor` nie mają `pbn_uid`", i na tym opierał uniwersalny gate
`getattr(instance, "pbn_uid_id", None)`. `Autor.pbn_uid` **istnieje** (FK do
`pbn_api.Scientist`, `autor.py`). Gate z planu wstawiłby **autora** do kolejki
eksportu **publikacji** i odpalił dla niego wysyłkę do PBN.

Sam `pbn_uid` nie wystarczyłby też od drugiej strony: `zakolejkuj_wysylke`
świadomie NIE MA gate'u na `pbn_uid` (faza 05a), więc przy RESTORE przyjęłaby
każdy wiersz `*_Autor` przywracany kaskadą — publikacja z N autorami dałaby
N zbędnych zleceń.

**Rozstrzygnięcie:** gate po typie —
`isinstance(instance, BppPublikacjaSoftDeleteMixin)`. Oba testy są w
`test_receivers.py`.

### 3.2 Fazy 02/04 nie mogły wpiąć kontekstu tak, jak plan zakładał

Plan zakładał, że owijają `super().delete()`. One **nie wołają
`super().delete()` w ogóle** — świadomie, żeby uniknąć refleksyjnej kaskady
pakietu (skasowałaby twardo `Autor_Jednostka`, `Autor_Dyscyplina` itd.). Same
ustawiają `deleted_at` i same wysyłają sygnał. Faza 06 zakłada więc kontekst
w czterech metodach (publikacje `delete`/`restore`, `Autor` `delete`/`restore`),
obejmując CAŁE ciało — kaskada `*_Autor` ma dziedziczyć atrybucję.

### 3.3 Dwa sposoby atrybucji z planu wykluczały się nawzajem

Wykryte przez padający test **z samego planu**. `delete()` zakłada kontekst
ZAWSZE, więc wywołanie bez `user=` wewnątrz jawnego
`soft_delete_context(user=X)` zerowało X i operacja szła do logu jako niczyja.

**Reguła:** pominięty argument **dziedziczy**, nie zeruje. Siedzi w samym
context managerze, nie w czterech miejscach wywołań — inaczej następny model
soft-delete zgubiłby usera po cichu. Uzasadnienie: `None` znaczy „nie wiem",
a nie „wiem, że nikt".

### 3.4 Gate punktacji obejmuje TRZY modele, nie pięć

Plan (Task 6b) mówił „tylko 5 modeli publikacji".
`przelicz_punkty_dyscyplin()` mają wyłącznie `Wydawnictwo_Ciagle`,
`Wydawnictwo_Zwarte` i `Patent` — dziedziczą `ModelZPrzeliczaniemDyscyplin`.
Prace dyplomowe **nie mają tej metody**, więc gate „5 modeli" wywaliłby się
na `AttributeError` przy kasowaniu doktoratu.

---

## 4. Szósty model soft-delete, o którym nie wiedział nikt

Asercja testowa „każdy `SoftDeleteModel` ma `BppPkPrzedHardDeleteMixin`"
(nad `apps.get_models()`) natychmiast wykryła
**`zglos_publikacje.Zgloszenie_Publikacji`** — model soft-delete
**niezależny od faz 01–04**, używający pakietu od dawna na własne potrzeby.
Nie było go na żadnej liście: ani w planie, ani w handoffach faz 02/04/05.

To powtórka lekcji z handoffu fazy 05a §4.2 (faza 04 pominęła czwartego
dziedzica abstraktu). **Nauka: wyliczanka modeli z głowy jest niepełna;
asercja nad `apps.get_models()` nie jest.**

**Skutek do odnotowania:** operacje na `Zgloszenie_Publikacji` trafiają teraz
do `SoftDeleteLog`. Bez skutków PBN (gate z §3.1 obejmuje wyłącznie
publikacje). Jeśli to niepożądane, zawężenie jest jednolinijkowe — ale
domyślnie audyt jest szerszy, nie węższy.

---

## 5. Fakt o pakiecie utrwalony testem

`post_hard_delete` leci **po** `Model.delete()`, a kolektor Django zeruje
wtedy `pk` instancji. Receiver dostaje więc `instance.pk is None`. Naiwny
zapis dałby `object_id=None` → `IntegrityError` **w receiverze** → wywrócone
`hard_delete()`: audyt zepsułby operację, którą ma tylko obserwować.

Stąd `BppPkPrzedHardDeleteMixin`. Test-sonda
(`test_pakiet_zeruje_pk_przed_wyslaniem_post_hard_delete`) pilnuje tego
założenia — gdy aktualizacja pakietu je zmieni, zapali się tam, a nie
w postaci logów czytających pole zapasowe.

---

## 6. Czego faza 06 NIE domyka (świadomie)

- **`pbn_status=""` jest dwuznaczne.** Nie odróżnia „nie było czego
  kolejkować" od „pominięto, bo rekord już czeka w kolejce" — obie funkcje
  kolejkujące zwracają `None` i receiver nie ma ich jak rozróżnić bez
  dodatkowego zapytania. Praktyczna konsekwencja: szybkie „usuń i cofnij"
  zostawia w kolejce samo WYCOFANIE, a log RESTORE pokazuje pusty status.
  Udokumentowane testem
  `test_restore_przy_niezakonczonym_wycofaniu_nie_dubluje_wpisu`.
- **`uczelnia_rekordu()` zwraca `None` przy dwuznaczności** (praca
  współautorska między uczelniami). Wpis kolejki degraduje wtedy do
  zachowania sprzed fazy 06: jedna uczelnia w bazie → działa, kilka →
  głośny błąd. Wybranie „pierwszej z brzegu" wysłałoby wycofanie przez konto
  PBN cudzego tenanta, więc to celowo nie jest zgadywane.
- **Reguła przynależności jest zduplikowana.** `uczelnia_rekordu()` odwraca
  `naleza_wydawnictwa`/`naleza_prace` z `cerif_export` (faza 05b). Nie da się
  jej wołać wprost, bo `cerif_export` zależy od `bpp`, nie odwrotnie. Gdy
  tamta się zmieni, ta MUSI pójść za nią — dziś pilnują tego tylko testy
  po obu stronach.
- **Brak UI dla logu.** `SoftDeleteLog` nie ma admina ani widoku — faza 07.
- **`SoftDeleteLog` nie niesie `pbn_uid`.** Dług z handoffu 05a §6 (twarde
  skasowanie publikacji zostawia oświadczenia w PBN na zawsze) NIE jest
  domknięty: log zapisuje `object_id`, nie PBN UID. Domknięcie wymaga
  dołożenia pola i wypełnienia go w receiverze HARD_DELETE.

---

## 7. Wskazówki wprost dla fazy 07 (admin kosza)

- **Masowe przywracanie potrzebuje zadania w tle.** Zmierzone: `restore()`
  z przeliczeniem punktacji to **46,7 ms** dla rekordu z 2 autorami. Poniżej
  progu 1 s z planu, więc bez eskalacji — ale koszt jest liniowy: 100
  rekordów ≈ 4,7 s w jednym żądaniu HTTP.
- **Masowe twarde kasowanie jest teraz N zapytań, nie jedno.**
  `hard_delete()` na querysecie iteruje per instancja, żeby leciały sygnały
  (Task 8). Świadomy koszt — ale akcja admina nad dużym zaznaczeniem to
  kandydat na zadanie w tle.
- **Admin ma request, więc ma tenanta.** Jeśli faza 07 zechce, żeby wpisy
  kolejki niosły uczelnię z requestu zamiast wyprowadzanej z rekordu
  (dokładniejsze dla prac współautorskich), naturalne miejsce to
  rozszerzenie `soft_delete_context` o `uczelnia=`. Właściciel świadomie
  wybrał wyprowadzanie z rekordu, bo działa też dla CLI i celery.

---

## 8. Dług nadal otwarty (z faz 01–05b)

| Sprawa | Stan |
|---|---|
| **Asymetria gate'u `.update(deleted_at=...)`** | `BppSoftDeleteQuerySet` blokuje, `BppDeletedQuerySet` **nie** — `Autor.deleted_objects...update(deleted_at=...)` rzuca, to samo na `Wydawnictwo_Ciagle` przechodzi. Wygląda na przeoczenie 05b, nie decyzję |
| **Kaskada `Jednostka` → `Autor`** | `aktualna_jednostka`/`aktualna_funkcja` nadal `CASCADE` |
| **`Autor.slug` `unique=True` bezwarunkowo** | husk trzyma slug zarezerwowany |
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | bez zmian |
| **PR upstream `django-easy-audit`** | [#348](https://github.com/soynatan/django-easy-audit/pull/348) |
| **Brak UI dla `ProtectedError`** | w adminie gołe 500; faza 07 |
| **`Autor` nie ma kosza w adminie** | faza 07 |
| **`hard_delete()` na querysecie bez sygnału** | **ZAMKNIĘTE w fazie 06** (Task 8) |
| Słowniki (`Zrodlo`, `Konferencja`, `Projekt`, `Jednostka`) bez soft-delete | bez zmian |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył |
| **Strategia wydania** | bramka na fazie 07 |

---

## 9. Proces — co się sprawdziło w fazie 06

- **Weryfikacja planu przed kodowaniem zwróciła się natychmiast.** Trzy
  z czterech rozjazdów z §3 to błędy RZECZOWE w planie, a nie zmiany
  zakresu. Najgroźniejszy (`Autor.pbn_uid`) był oznaczony w planie jako
  „zweryfikowane" — etykieta wiarygodności nie zastępuje sprawdzenia.
- **Asercja nad `apps.get_models()` bije wyliczankę.** Znalazła szósty model
  soft-delete w pierwszym uruchomieniu (§4). Ten sam błąd — lista modeli
  z pamięci — wystąpił już w fazie 04.
- **Mutacja jako dowód, nie rytuał.** Podmiana `global_objects` → `objects`
  w `uczelnia_rekordu()` wywaliła dokładnie dwa testy, które tego pilnują.
  Potwierdziło to empirycznie, że kolejność „kaskada przed sygnałem rodzica"
  jest realnym zagrożeniem, a nie teoretycznym.
- **Test z planu wykrył sprzeczność w samym planie.** `test_soft_delete_
  tworzy_log_z_userem` padł po wpięciu kontekstu i wymusił regułę
  dziedziczenia (§3.3). Gdyby go pominąć jako „oczywisty", sprzeczność
  wyszłaby dopiero w fazie 07.
