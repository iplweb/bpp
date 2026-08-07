# Runbook wdrożeniowy — soft-delete, faza 01 (autorstwa)

> Dotyczy migracji `bpp/0488` … `bpp/0495` oraz
> `rozbieznosci_dyscyplin/0022`. Przeczytaj **przed** wdrożeniem na produkcję.
>
> Powstał 2026-08-06 z ustaleń finalnej recenzji gałęzi. Zastrzeżenia niżej
> nie blokują scalenia, ale **muszą** być znane osobie wdrażającej.

## Co ta faza zmienia

`delete()` na trzech modelach autorstwa (`Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`, `Patent_Autor`) przestaje fizycznie usuwać wiersz
— ustawia `deleted_at`. **Nie ma feature flagi: zmiana obowiązuje od pierwszej
sekundy po starcie nowego kodu.**

Konsekwencja dla wdrożenia: migracje muszą się domknąć **zanim** nowy kod
zacznie serwować ruch (patrz §3).

---

## 1. `0492` wymaga OKNA SERWISOWEGO

`0492_autor_excl_rekord_kolejnosc` zakłada `ExclusionConstraint` (GiST):

```sql
ALTER TABLE bpp_wydawnictwo_ciagle_autor
  ADD CONSTRAINT wc_autor_excl_rekord_kolejnosc
  EXCLUDE USING gist (rekord_id WITH =, kolejnosc WITH =)
  WHERE (deleted_at IS NULL) DEFERRABLE INITIALLY DEFERRED;
```

- bierze **`ACCESS EXCLUSIVE`** — blokuje także **odczyty**, nie tylko zapisy;
- trwa tyle, ile budowa indeksu **GiST**, który na parze `(int, int)` jest
  wielokrotnie wolniejszy od btree;
- **nie istnieje wariant współbieżny.** `EXCLUDE` nie da się dodać przez
  `CREATE INDEX CONCURRENTLY` + `USING INDEX` — to ograniczenie PostgreSQL,
  nie przeoczenie.

Dotyczy trzech największych tabel systemu.

> **DO ZROBIENIA PRZED WDROŻENIEM:** zmierzyć czas `0492` na kopii bazy
> produkcyjnej. To jedyna operacja w tej serii bez planu B.

Ustaw `lock_timeout` + retry — jeden długi `SELECT` na tabeli `*_autor`
zatrzyma migrację i wszystko za nią (kolejka blokad).

## 2. Procedura po PRZERWANEJ migracji z serii `0490`–`0493`

Te cztery migracje mają `atomic = False` (świadomie — żeby blokady nie
kumulowały się do jednego `COMMIT`). Cena: **awaria w środku kroku nie cofa
się sama.**

Objaw: obiekt istnieje w bazie, ale wpisu w `django_migrations` nie ma →
ponowny `migrate` pada na „already exists" (albo, dla `0493`, na
„Found wrong number (0) of constraints").

Naprawa — usuń ręcznie obiekty z częściowo wykonanego kroku, potem powtórz
`migrate`. Nazwy (prefiks `wc_` / `wz_` / `pat_` per tabela):

| Krok | Obiekty do sprawdzenia |
|---|---|
| `0490` | indeksy `*_autor_rekord_id_*` |
| `0491` | `*_autor_uniq_rekord_autor_typ` |
| `0492` | `*_autor_excl_rekord_kolejnosc` |
| `0493` | (same `DROP`-y metadanowe — praktycznie nie pada) |

```sql
-- przykład diagnostyki przed retry
SELECT conname FROM pg_constraint
 WHERE conrelid = 'bpp_wydawnictwo_ciagle_autor'::regclass;
SELECT indexname FROM pg_indexes
 WHERE tablename = 'bpp_wydawnictwo_ciagle_autor';
```

## 3. Kolejność: migracje PRZED startem nowego kodu

Między `0492` a `0493` obowiązuje **jeszcze stare, bezwarunkowe**
`UNIQUE (rekord_id, kolejnosc)`. Jeśli w tym oknie nowy kod zdąży zrobić
soft-delete i wstawić wiersz zastępczy, dostanie `IntegrityError`.

Migracje idą z entrypointu przed startem aplikacji, więc domyślnie jest to
spełnione — ale przy ręcznym wdrożeniu lub rolling-restarcie trzeba tego
przypilnować.

## 4. Rollback: cofać KOD I MIGRACJE razem

**Cofnięcie samych migracji nie zadziała, jeśli nowy kod został na dysku.**

`django-denorm` buduje triggery z modeli Pythona przy sygnale `post_migrate`.
Modele po tej fazie mają `deleted_at` w `denorm_always_only`, więc po
cofnięciu `0488` (usunięcie kolumny) najbliższy `post_migrate` próbuje
zbudować trigger odwołujący się do nieistniejącej kolumny:

```
ProgrammingError: kolumna old.deleted_at nie istnieje
```

To jedyny nieudany rewers w całej serii — pozostałe wracają do stanu
wyjściowego bit-w-bit (zweryfikowane zrzutem katalogu przed/po).

Dodatkowo: rewers `0493` przywraca **bezwarunkowe** `UNIQUE (rekord_id,
kolejnosc)`, które padnie, jeśli ktokolwiek zdążył skorzystać z soft-delete
(soft-deletowane wiersze wyglądają wtedy jak duplikaty). Rollback po realnym
użyciu funkcji wymaga ręcznego wyczyszczenia kosza.

## 5. Maszyny deweloperskie na tej gałęzi

Kto zaaplikował **starą** wersję `0490_autor_warunkowy_unique` (plik został
skasowany, a numer użyty ponownie przy rozbiciu na `0490`–`0493`), ma
osierocony wpis w `django_migrations`. Dotyczy wyłącznie maszyn, na których
ta gałąź była wdrażana w trakcie prac — nie produkcji.

Naprawa: `DELETE FROM django_migrations WHERE app='bpp' AND name LIKE
'0490_autor_warunkowy_unique';` i ponowny `migrate`, albo świeża baza.

---

## Znane, świadomie zaakceptowane zachowania

Nie są błędami do naprawy w tej fazie, ale warto je znać przy zgłoszeniach
od użytkowników.

- **`Rekord.liczba_autorow` jest *eventually consistent*.** Odświeża się
  dopiero, gdy flush `django-denorm` dotknie wiersza publikacji, podczas gdy
  `bpp_autorzy_mat` aktualizuje się natychmiast (trigger). Mechanizm jest
  identyczny jak przy twardym kasowaniu, ale rozjazd między dwoma cache'ami
  bywa chwilowo widoczny.
- **Soft-delete nie przenumerowuje `kolejnosc`.** Skasowanie autora ze środka
  listy zostawia dziurę. Kryterium multiseeka „Ostatnie nazwisko i imię"
  (`kolejnosc ∈ [liczba_autorow-1, liczba_autorow)`) może w tę dziurę trafić
  i zwrócić pusty wynik. Zachowanie identyczne jak przy twardym kasowaniu
  (admin przenumerowuje przy zapisie formsetu, deduplikator nie).
- **Narzut GiST.** Btree `UNIQUE (rekord_id, kolejnosc)` zastąpiono indeksem
  GiST. Każdy `INSERT`/`UPDATE` na najgorętszych tabelach (import publikacji,
  PBN, deduplikator) płaci teraz za jego utrzymanie. `0490` dokłada btree po
  `rekord_id`, co część kosztu łagodzi. **Nikt tego nie zmierzył** — testy
  z definicji tego nie wykryją.
- **Trzy martwe widoki** `bpp_kronika_{wydawnictwo_ciagle,wydawnictwo_zwarte,
  patent}_view` czytają surowe tabele bez filtra. Zweryfikowano brak
  konsumentów (kod, szablony, modele) — są jawnym wyjątkiem w kanarku
  katalogowym. Do skasowania przy okazji.

## Weryfikacja po wdrożeniu

```bash
# 1. soft-delete znika z obu cache'y
#    (autorzy_set, bpp_autorzy_mat ORAZ liczba_autorow muszą się zgadzać)

# 2. kanarek katalogowy — żaden widok nie czyta tabeli soft-delete
#    bez zależności od jej deleted_at
uv run pytest src/bpp/tests/test_soft_delete/test_kanarek_katalogowy.py -q

# 3. spójność cache
uv run pytest src/bpp/tests/test_soft_delete/ src/bpp/tests/test_cache/ -q
```
