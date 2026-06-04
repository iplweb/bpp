# Usprawnienia admina/UI integracji DSpace

Data: 2026-06-04
Status: projekt zaakceptowany w brainstormingu (wszystkie decyzje potwierdzone
przez użytkownika), do implementacji.

Kontynuacja [2026-06-03-dspace-export-design.md](2026-06-03-dspace-export-design.md).
Dotyczy istniejącej app `src/dspace_api/`.

## 1. Cel

Trzy usprawnienia ergonomii + dwa rozdziały dokumentacji:

A. **Domyślna uczelnia** w formularzu dodawania `Mapowanie_DSpace`.
B. **Picker kolekcji DSpace** zamiast ręcznego wpisywania UUID.
C. **Link „zobacz w repozytorium"** dla rekordów wysłanych do DSpace.
D. **Dokumentacja**: rozdział dla administratora („Integracja z DSpace")
   i dla redaktora/użytkownika („Eksportowanie do DSpace").

## 2. Decyzje (potwierdzone)

| Temat | Decyzja |
|---|---|
| Źródło listy kolekcji | **Live** przy renderowaniu (bez cache), krótki timeout (~4 s) |
| Reakcja pickera na uczelnię | **AJAX** zależny od wybranej uczelni (obsługa wielu uczelni) |
| Zakres domyślnej uczelni | **Tylko** `Mapowanie_DSpace` |
| Identyfikator linku | **handle** (trwały), zapisywany na `SentToDSpace` |
| Baza linku | **lokalny** resolver `{endpoint−/server/api}/handle/{handle}` |
| Miejsca linku | admin `SentToDSpace` + admin rekordu publikacji + **publiczna** strona rekordu (link zewnętrzny, widoczny dla wszystkich) |

## 3. Feature A — domyślna uczelnia w `Mapowanie_DSpace`

`Mapowanie_DSpaceAdmin.get_changeform_initial_data(request)` ustawia
`uczelnia` na `Uczelnia.objects.get_for_request(request).pk`, o ile nie jest
już w danych initial. `get_for_request` zwraca `request._uczelnia` (multi-tenant),
a w jego braku `get_default()` = jedyna/pierwsza uczelnia. Jedna uczelnia →
zawsze ona; wiele → uczelnia z requestu. **Server-side, bez JS.**

Pole `collection_uuid` modelu bez zmian (UUIDField, walidacja UUID zostaje).

## 4. Feature B — picker kolekcji (live, AJAX per uczelnia)

### 4.1 Klient
`DSpaceClient.fetch_collections(timeout=4)` (w `src/dspace_api/client.py`):
- nakłada domyślny timeout na sesję `requests` raw-klienta (wrap
  `session.request` przez `functools.partial(..., timeout=timeout)`),
- `authenticate()`, następnie iteruje `get_collections_iter()` (paginacja
  leniwa, każdy page = osobny request objęty timeoutem),
- zwraca `list[dict]`: `[{"uuid": str, "name": str}, ...]`.

### 4.2 Endpoint AJAX
W `Mapowanie_DSpaceAdmin.get_urls()` dodać trasę
`collections/<int:uczelnia_id>/` → widok owinięty `self.admin_site.admin_view`
(wymaga zalogowanego stafa). Widok:
- pobiera `Uczelnia`, woła `DSpaceClient(uczelnia).fetch_collections()`,
- sukces → `JsonResponse({"collections": [...]})`,
- każdy wyjątek (timeout, auth, sieć) → `logger.warning(..., exc_info=True)`
  + `JsonResponse({"error": "<komunikat PL>", "collections": []})` ze
  statusem **200** (żeby JS mógł pokazać fallback bez traktowania tego jak
  twardy błąd HTTP).

### 4.3 Formularz + widżet
Custom `Mapowanie_DSpaceForm(forms.ModelForm)`:
- `collection_uuid` jako `forms.UUIDField` z widżetem `Select`,
- na `<select>` atrybuty `data-collections-url` (baza URL endpointu, bez id),
  `data-uczelnia-field` (id selecta uczelni), `data-current` (zapisany UUID).

JS `src/dspace_api/static/dspace_api/dspace_collection_picker.js`
(dołączony przez `Media`):
- na load i przy zmianie pola `uczelnia`: fetch listy kolekcji dla wybranej
  uczelni, wypełnij `<option>` (label `name`, value `uuid`); zaznacz
  `data-current` (i dodaj go jako opcję, jeśli nie ma go w liście — żeby nie
  zgubić zapisanej wartości),
- gdy uczelnia niewybrana → select pusty/disabled,
- gdy odpowiedź ma `error` lub pustą listę → **podmień select na zwykłe pole
  tekstowe UUID** (zachowaj `name` i `data-current`), żeby admin mógł wpisać
  ręcznie (fallback). Komunikat o błędzie obok pola.

## 5. Feature C — link „zobacz w repozytorium" (handle)

### 5.1 Model
Nowe pole `SentToDSpace.dspace_handle = CharField(max_length=255, blank=True,
default="")`. Migracja `0004_*`.

### 5.2 Zapis handle
- `DSpaceClient.create_item(...)` zwraca `(uuid, handle)` zamiast samego uuid
  (`getattr(created, "handle", "")`).
- `DSpaceClient.fetch_handle(uuid)` — `get_item(uuid).handle` (backfill).
- `SentToDSpaceManager.mark_as_successful(..., dspace_handle=None)` zapisuje
  handle, gdy podany.
- `eksport._eksportuj_do_uczelni`: na ścieżce **create** bierze handle z
  `create_item`; na ścieżce **update** (oraz dla starych rekordów bez handle)
  robi backfill `fetch_handle(item_uuid)`, jeśli `sent.dspace_handle` puste.
  Backfill w try/except — błąd backfillu nie wywraca synchronizacji (handle
  to dodatek), tylko `logger.warning(exc_info=True)`.

### 5.3 Builder linku
`src/dspace_api/links.py`:
- `public_url_for_sent(sent) -> str | None`: gdy `sent.dspace_handle` i
  endpoint niepusty → `"{base}/handle/{handle}"`, gdzie `base` = endpoint po
  usunięciu sufiksu `/server/api` i prawych `/`. Inaczej `None`.
- `public_links_for_rec(rec) -> list[(Uczelnia, str)]`: dla każdego
  `SentToDSpace` rekordu z `submitted_successfully` i niepustym handle.

### 5.4 Miejsca prezentacji
1. **Admin `SentToDSpace`**: kolumna w `list_display` (`format_html` link „🔗")
   + readonly pole na change form. Brak handle → „—".
2. **Admin rekordu** (`Wydawnictwo_Ciagle/_Zwarte`, `Patent`,
   `Praca_Doktorska`, `Praca_Habilitacyjna`): wspólny `DSpaceLinkAdminMixin`
   (w `dspace_api/admin_mixins.py`, wstawiany jako **pierwsza** baza).
   **Decyzja implementacyjna:** zamiast `change_form_template`/object-tool
   (ryzyko clobberowania istniejących per-model `change_form.html` dla
   `patent`/`wydawnictwo_ciagle`/`wydawnictwo_zwarte`) mixin **dokłada
   readonly-fieldset „Repozytorium DSpace"** przez `get_fieldsets` +
   `get_readonly_fields`. Pole dodawane tylko gdy istnieje udana wysyłka
   z handle (więc nie ma go na formularzu dodawania ani na rekordach
   niewysłanych); guard `_fieldsets_contain` zapobiega dublowaniu, gdy admin
   nie ma jawnych fieldsetów (Django auto-dokłada readonly). Wartość: metoda
   `dspace_repo_link` zwraca link(i) `format_html_join`.
3. **Publiczna strona rekordu** (`browse/praca_tabela_mono.html`, karta
   „Linki zewnętrzne”): nowy `external-link-item` „Repozytorium DSpace”
   (link zewnętrzny, `target=_blank`), widoczny dla wszystkich. Dane z
   context processora albo z metody na rekordzie — patrz 5.5.

### 5.5 Dostarczenie linku do publicznego szablonu
Najmniej inwazyjnie: prosty tag/filtr w `bpp` (np. `{% dspace_link rekord %}`)
albo metoda pomocnicza wołana w widoku szczegółów. Wybór pinowany w
implementacji po obejrzeniu widoku `praca`/kontekstu (preferencja: filtr w
istniejącej bibliotece tagów, bez dotykania widoku).

## 6. Dokumentacja (Feature D)

- `docs/administrator/integracja-dspace.md` — „Integracja z DSpace":
  konfiguracja na obiekcie Uczelnia (endpoint/login/hasło/aktywność),
  mapowania `(Charakter_Formalny → kolekcja)` z pickerem kolekcji, pojęcia
  (kolekcja, bitstream, handle). Wpis w `mkdocs.yml` nav (sekcja
  „Instrukcja administratora") + link w `docs/index.md`.
- `docs/uzytkownik/eksportowanie-do-dspace.md` — „Eksportowanie do DSpace":
  jak redaktor wysyła rekord akcją w adminie, co znaczą statusy wyniku,
  gdzie znaleźć link „zobacz w repozytorium". Wpis w nav + `index.md`.

## 7. Testy

- `tests/test_admin.py` (nowy): initial-data uczelni; endpoint kolekcji
  (sukces zmockowany + ścieżka błędu → `error`+200).
- `tests/test_client.py`: `fetch_collections` (mock raw), `create_item`
  zwraca `(uuid, handle)`, `fetch_handle`.
- `tests/test_links.py` (nowy): `public_url_for_sent` (handle jest/brak,
  obcięcie `/server/api`), `public_links_for_rec`.
- `tests/test_eksport.py`: rozszerzyć — handle zapisany przy create, backfill
  przy update.
- `tests/test_sentdata.py`: `mark_as_successful` zapisuje handle.

## 8. Poza zakresem (YAGNI)

- Cache listy kolekcji (świadomie odrzucone — wybrano live).
- Domyślna uczelnia w innych adminach niż `Mapowanie_DSpace`.
- Globalny resolver `hdl.handle.net` (wybrano lokalny).
- Konfigurowalny osobny `dspace_frontend_url` (derive z endpointu wystarcza).

## 9. Changelog

Fragment towncrier (`src/bpp/newsfragments/`) typu `feature`.
