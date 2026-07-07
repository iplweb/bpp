# Bezpieczne kasowanie pustych jednostek (admin)

Data: 2026-07-07
Status: zaakceptowany (design, po adwersaryjnym self-review), do implementacji

## Problem

`JednostkaAdmin` bramkuje kasowanie wyłącznie po grupie
(`RestrictDeletionToAdministracjaGroupMixin`) — każdy członek grupy
`administracja` może usunąć jednostkę. Nie ma żadnego zabezpieczenia przed
tym, CO zniknie w kaskadzie.

Większość FK wskazujących na `Jednostka` ma `on_delete=CASCADE`
(`Autor_Jednostka`, `Jednostka_Rodzic`, cache `Autorzy`, MPTT `children`
przez self-FK `parent`, …). Skutek: dzisiejsze skasowanie jednostki **po
cichu kaskaduje** — kasuje powiązania autor-jednostka, historię przypisań,
wpisy cache, całe poddrzewo podjednostek. To utrata danych bez ostrzeżenia.

## Cel

Pozwolić skasować jednostkę **tylko wtedy, gdy jest w pełni pusta**:
ściśle zero referencji przez odwrotne, KONKRETNE i ZARZĄDZANE FK/M2M
i zero podjednostek. W przeciwnym razie odrzucić operację z czytelnym
komunikatem, który wymienia CO blokuje.

## Decyzje projektowe

1. **Definicja „pustej" — ściśle zero referencji z realnych tabel.**
   Blokuje jakikolwiek wiersz wskazujący na jednostkę przez odwrotny,
   konkretny FK/O2O lub przez model łączący M2M, o ile powiązany model jest
   ZARZĄDZANY (`_meta.managed is True`): podjednostki, `Autor_Jednostka`
   (nawet puste), własna historia `Jednostka_Rodzic`, cache `Autorzy`
   (realna tabela), PBN itd. **Nie rozróżniamy** „własnych artefaktów" od
   „realnych powiązań" wśród tabel — wszystko liczy się jako blokada.

   **NIE blokują** (świadomie, doprecyzowane po review):
   - **Niezarządzane widoki SQL** (`_meta.managed is False`, `DO_NOTHING`):
     `AutorzyView`, `Cache_Punktacja_Autora_*`, `Nowe_Sumy_View` itp. Widok
     nie przechowuje danych — jest wyliczany z tabel bazowych i sam się
     przelicza; fizycznie nie może „blokować" kasowania. Jednostka bez
     publikacji i tak nie ma wierszy w tych widokach.
   - **Relacje generyczne** (reversion `Version`, easyaudit, cacheops).
     Model `Jednostka` NIE ma żadnego `GenericRelation`, więc te obiekty nie
     pojawiają się w `_meta.related_objects` i nie są liczone. To jest
     pożądane — log audytu / rewizja historii nie powinny blokować kasowania
     świeżej, pustej jednostki.

   Innymi słowy: „ściśle zero" dotyczy konkretnych odwrotnych FK/M2M do
   **realnych, zarządzanych tabel** — nie widoków ani relacji generycznych.

2. **Mechanizm/UX — bramkuj standardowy delete + komunikat.** Zostaje zwykły
   przycisk „Usuń" Django. Gdy jednostka ma referencje, strona potwierdzenia
   wyświetla listę blokad (mechanizm `protected` z `get_deleted_objects`)
   i **nie pozwala potwierdzić**. Gdy pusta — kasuje normalnie.

   **Akcja masowa „Usuń wybrane" — blokada całej partii (natywne Django).**
   `delete_selected` liczy blokady dla CAŁEGO zaznaczenia; jeśli choć jedna
   zaznaczona jednostka jest niepusta, `protected` jest niepuste i Django
   **nie kasuje NICZEGO** (nawet pustych z zaznaczenia), pokazując listę
   blokad. To spójne z tym, jak Django traktuje `PROTECT` w akcji masowej —
   zero dodatkowego kodu. Użytkownik odznacza niepuste i ponawia.

3. **Bramka grupy `administracja` zostaje bez zmian.** Nowy warunek „pusta"
   jest DODATKOWY — nie zastępuje istniejącego `has_delete_permission`
   opartego o grupę. Aby skasować: trzeba być w grupie `administracja`
   ORAZ jednostka musi być pusta.

## Architektura (trzy warstwy)

### 1. Warstwa logiki — model `Jednostka`

Jedno źródło prawdy, testowalne bez admina. W `src/bpp/models/jednostka.py`:

```python
def przeszkody_w_kasowaniu(self) -> list[tuple[str, int]]:
    """Lista (etykieta, liczba) niepustych odwrotnych relacji FK/M2M
    do REALNYCH, zarządzanych tabel wskazujących na tę jednostkę.
    Pusta lista ⇔ jednostkę można skasować."""
```

Zasady iteracji (wynik adwersaryjnego review):

- Iteruj po `self._meta.related_objects` (odwrotne FK/O2O oraz odwrotne M2M).
- **Liczenie jednolicie przez POLE, nie akcesor** — kluczowe, bo:
  - odwrotny **O2O** (`Nowe_Sumy_View`, accessor `nowe_sumy_view`) NIE ma
    `.count()`, a samo dotknięcie akcesora rzuca `RelatedObjectDoesNotExist`;
  - dlatego licz: `rel.related_model._base_manager.filter(**{rel.field.name:
    self}).count()` — działa jednakowo dla FK, O2O i M2M-through.
- **Pomiń modele niezarządzane** (`rel.related_model._meta.managed is False`)
  — to widoki SQL (patrz decyzja 1), tanio je wyklucza i skraca listę
  z ~35 relacji do garstki realnych.
- **Pomiń zduplikowany odwrotny M2M**: `related_objects` zawiera i odwrotny
  M2M `autor` (accessor `autor_set`, `auto_created` przez `Autor.jednostki`),
  i FK modelu-łączącego `Autor_Jednostka`. Ta sama więź trafiłaby na listę
  dwa razy. Pomiń `rel.many_to_many and rel.field.auto_created` — model
  łączący (`Autor_Jednostka`) i tak pokrywa tę relację.
- Podjednostki (`children`, self-FK `parent`) pojawiają się tu naturalnie
  jako jedna z relacji — NIE ma osobnej gałęzi kodu „czy ma dzieci".
- Denorm self-FK `wydzial` (`related_name="+"`) jest HIDDEN i `related_objects`
  go POMIJA (nie ma go tam — wbrew pierwotnej, błędnej uwadze w tym specu).
  To nieszkodliwe dla „ściśle zero": węzeł, na który wskazuje cudzy `wydzial`,
  jest korzeniem z poddrzewem, więc blokuje go bezpośrednie `children`.
  NIE używać `get_fields(include_hidden=True)` — trafiłoby na akcesor `+`
  bez managera i crashowało.
- Etykieta krotki = `rel.related_model._meta.verbose_name_plural`
  (już zlokalizowane), zwracana dla każdej relacji z `count() > 0`.

Helper:

```python
def czy_mozna_skasowac(self) -> bool:
    return not self.przeszkody_w_kasowaniu()
```

### 2. Warstwa admina — `JednostkaAdmin`

Override `get_deleted_objects(self, objs, request)`:

- Woła `super().get_deleted_objects(objs, request)` →
  `(deletable_objects, model_count, perms_needed, protected)`. Potwierdzone:
  w Django 5.2 `protected` to lista renderowana w szablonie przez
  `{{ protected|unordered_list }}`; niepuste `protected` powoduje że zarówno
  `_delete_view` (`if request.POST and not protected`) jak i akcja
  `delete_selected` (`if request.POST.get("post") and not protected`)
  NIE wykonują kasowania i chowają przycisk potwierdzenia.
- Dla każdej `obj` w `objs`, jeśli `obj.przeszkody_w_kasowaniu()` nie jest
  puste, dokłada do `protected` czytelny, **zescapowany** wpis, np.:
  *„Jednostka «X» — nie można usunąć: 3× powiązania autor-jednostka,
  2× jednostki podrzędne"*.
  - `jednostka.nazwa` (do 512 znaków, dowolny tekst) trafia do HTML przez
    `unordered_list` — buduj wpis przez `format_html` / `escape`
    (i `gettext` na stałych fragmentach), by uniknąć XSS.
- Zwraca zmodyfikowaną krotkę. Ten sam kod obsługuje delete pojedynczy
  i akcję masową (obie ścieżki wołają `get_deleted_objects`); dla akcji
  masowej daje to natywną blokadę całej partii (decyzja 2).

Defense-in-depth — guard w `delete_model` (i ewentualnie `delete_queryset`):
- Skoro `protected` blokuje dojście do kasowania w ścieżce admina, guard
  jest **wyłącznie** siatką bezpieczeństwa dla wywołań programistycznych
  (skrypt, przyszły kod). Jeśli mimo wszystko trafi tam niepusta jednostka,
  odmów (`log` / wyjątek) zamiast po cichu kaskadować.
- **Nie** opisujemy guardu jako mechanizmu „częściowego" kasowania masowego —
  akcja masowa jest wszystko-albo-nic (decyzja 2), więc `delete_queryset`
  w praktyce dostaje albo same puste, albo nic.

`has_delete_permission` — **bez zmian** (istniejąca bramka grupy;
potwierdzone: żaden mixin w łańcuchu MRO `JednostkaAdmin` nie override'uje
`get_deleted_objects` / `delete_model` / `delete_queryset`, więc `super()`
trafia do `ModelAdmin`).

### 3. Testy (TDD, pytest + `model_bakery.baker`)

Model (`przeszkody_w_kasowaniu` / `czy_mozna_skasowac`):
- Pusta jednostka → `[]`, `czy_mozna_skasowac() is True`.
- Z jednym `Autor_Jednostka` → dokładnie jeden wpis, `czy_mozna_skasowac()`
  `is False`.
- Z podjednostką (`parent=jednostka`) → wpis „jednostki podrzędne".
- Z wpisem `Jednostka_Rodzic` (własna historia) → wpis blokujący
  (potwierdza semantykę „ściśle zero" dla realnych tabel).
- **Regresja O2O/widoki:** metoda NIE rzuca wyjątku dla jednostki bez
  wiersza w odwrotnym O2O (`Nowe_Sumy_View`) i NIE liczy niezarządzanych
  widoków jako blokad.

Admin (przez `client` zalogowany jako user w grupie `administracja`):
- POST delete na PUSTEJ jednostce → znika z bazy (`DoesNotExist`).
- GET/POST delete na NIEPUSTEJ → strona potwierdzenia zawiera wpis
  `protected`; obiekt NADAL istnieje po próbie.
- **Akcja masowa** „Usuń wybrane" na mieszance pusta+niepusta → cała partia
  zablokowana: NIC nie skasowane (także pusta), strona listuje blokady
  (spójne z decyzją 2). Osobny przypadek: same puste w zaznaczeniu → wszystkie
  skasowane.

Uwaga do testów (poboczne): `get_deleted_objects` przepuszcza kaskadowane
obiekty przez `has_delete_permission` ich adminów; brak uprawnień daje
`perms_needed`. Testy admina uruchamiać jako superuser/pełnoprawny członek
`administracja`, by nie mylić `perms_needed` z naszą blokadą `protected`.

## Świadomie poza zakresem (YAGNI)

- Brak zmian w API i management-commands — feature dotyczy wyłącznie admin UI.
- Brak „trybu wymuszonego kaskadowego kasowania" — jeśli coś wisi, użytkownik
  musi to najpierw ręcznie odpiąć/przenieść.
- Brak luzowania bramki grupy `administracja`.
- Brak częściowego kasowania w akcji masowej (decyzja 2: wszystko-albo-nic).

## Pliki

- `src/bpp/models/jednostka.py` — metody `przeszkody_w_kasowaniu`,
  `czy_mozna_skasowac`.
- `src/bpp/admin/jednostka.py` — override `get_deleted_objects`,
  guard `delete_model` (możliwe wydzielenie do mixinu w
  `src/bpp/admin/core.py`, jeśli okaże się reużywalne).
- Testy: `src/bpp/tests/` (model) + test admina obok istniejących testów
  `JednostkaAdmin`.
- Newsfragment towncriera (feature).

## Ślad po review

Adwersaryjny self-review (czysty subagent, Django 5.2.15) wykrył i naprawiono
w tym specu: sprzeczność akcji masowej z mechanizmem `protected` (→ decyzja 2
wszystko-albo-nic), crash na odwrotnym O2O `Nowe_Sumy_View` (→ liczenie przez
`rel.field.name`), błędną uwagę o `wydzial` w `related_objects` (relacja
hidden), przeobiecujące „ściśle zero wszystkiego" (→ tylko zarządzane tabele,
bez widoków i relacji generycznych), podwójne liczenie M2M `autor` vs
model-łączący, oraz ryzyko XSS w wpisach `protected` (→ escape/format_html).
