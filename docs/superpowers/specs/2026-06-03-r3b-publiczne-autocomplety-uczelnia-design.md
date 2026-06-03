# R3b — publiczne autocomplety zawężone per-uczelnia

Spec. Gałąź `feature/multi-hosted-config`. Data 2026-06-03.
Powiązane: `docs/superpowers/2026-06-03-audyty-multihosted-4x.md`, R3a (widoki).
Para: R3a — widoki listujące. Ten spec realizuje „limitowanie dropdownów" w
publicznych formularzach (Multiseek, ranking).

## Problem

Publiczne autocomplety jednostka/wydział/autor zwracają byty WSZYSTKICH uczelni.
Na domenie uczelni B użytkownik w Multiseeku/rankingu podpowiada sobie jednostki,
wydziały i autorów uczelni A. To jest też wybrany przez usera mechanizm zawężania
multiwyszukiwarki (zamiast filtrowania wyników — patrz R3a #5): jeśli pickery są
ograniczone do uczelni, typowe wyszukiwanie „autor + jednostka" samo się limituje.

## Klucz: zawężamy TYLKO klasy używane publicznie

Warianty publiczne są ODRĘBNE od adminowych/edytorskich — admin zachowuje pełen
dostęp. Klasy faktycznie używane przez publiczne pola (zweryfikowane w URL-ach
i `multiseek_registry/fields/`):

| byt | klasa (plik) | używana przez | współdzielona z edytorem? |
|---|---|---|---|
| jednostka | `WidocznaJednostkaAutocomplete` (`autocomplete/units.py:26`) | pole jednostki Multiseek (`unit_fields.py:46,84` → `jednostka-widoczna-autocomplete`) | **NIE** (tylko Multiseek) |
| wydział | `PublicWydzialAutocomplete` (`autocomplete/simple.py:199`) | `public-wydzial-autocomplete` (`unit_fields.py:158`) | NIE (publiczny) |
| autor | `PublicAutorAutocomplete` (`autocomplete/authors.py:182`) | `public-autor-autocomplete` (`author_fields.py:70`) | NIE (publiczny) |

Każdą zawężamy **w miejscu** w `get_queryset` — bez nowych klas/URL-i, bez ryzyka
dla formularzy redakcyjnych (admin używa innych: `JednostkaAutocomplete`,
`WydzialAutocomplete`, `AutorAutocomplete`).

## Reguły zawężania (z guardem single-install)

Wszystkie używają `uczelnia = Uczelnia.objects.get_for_request(self.request)`
(dostępny `self.request`) oraz wspólnego guardu `tylko_jedna_uczelnia()` z R3a
(`bpp/util/uczelnia_scope.py`). No-op gdy `uczelnia is None` lub jedna uczelnia.

### Jednostka — `WidocznaJednostkaAutocomplete`
`uczelnia.jednostka_set` / bezpośredni FK: `qs.filter(uczelnia=U)`.
Tani filtr po indeksowanym FK; guard daje zerowy narzut na single-install
(autocomplete strzela przy każdym znaku).

### Wydział — `PublicWydzialAutocomplete`
`Wydzial.uczelnia` to bezpośredni FK (`wydzial.py:24`): `qs.filter(uczelnia=U)`.

### Autor — `PublicAutorAutocomplete` (semantyka „kiedykolwiek związany")
Decyzja usera: w Multiseeku szukamy autora **obecnie LUB w przeszłości**
związanego z uczelnią X. „Obecnie" = aktualna jednostka w U; „w przeszłości" =
dowolna jednostka w historii (`Autor_Jednostka`) w U. Filtr = OR obu lookupów
+ `.distinct()`:
```python
qs.filter(
    Q(aktualna_jednostka__uczelnia=U)
    | Q(autor_jednostka__jednostka__uczelnia=U)
).distinct()
```
Dlaczego OR, a nie sam `autor_jednostka`: `AutorAutocompleteBase.get_queryset`
(`authors.py:42-87`) JUŻ rozróżnia grupę „nasza uczelnia" (`aktualna_jednostka`)
od „historycznie" (`autor_jednostka`) — model dopuszcza obecnego pracownika
BEZ wiersza historii, więc sam `autor_jednostka` mógłby go zgubić. OR = dokładnie
grupy 1+2 z istniejącego grupowania (zewnętrzni = grupa 3 odpadają). To NIE samo
`aktualna_jednostka__uczelnia` (tamto = wyłącznie „aktualnie zatrudniony",
potrzebne np. w rankingu R3a).

### Dwie semantyki autora (do utrwalenia w kodzie/komentarzu)
| semantyka | lookup | gdzie |
|---|---|---|
| aktualnie zatrudniony | `aktualna_jednostka__uczelnia=U` | ranking (R3a), miejsca „nasz pracownik" |
| obecnie LUB w przeszłości związany | `Q(aktualna_jednostka__uczelnia=U) \| Q(autor_jednostka__jednostka__uczelnia=U)` `.distinct()` | PublicAutorAutocomplete (ten spec) |

## Niezmienniki i przypadki brzegowe
- **Single-install:** guard `tylko_jedna_uczelnia()` → wszystkie trzy autocomplety
  bez filtra, podpowiedzi i wydajność identyczne jak dziś.
- **`uczelnia is None`:** brak filtra (zachowanie obecne).
- `.distinct()` dla autora (join przez `autor_jednostka` mnoży wiersze).
- Filtry NIE dotykają warstwy admin/edytor (inne klasy).

## Testy
- 2 uczelnie, rozłączne jednostki/wydziały/autorzy:
  - jednostka autocomplete na domenie A podpowiada tylko jednostki A.
  - wydział analogicznie.
  - autor: podpowiada autora związanego z A (historyczna jednostka w A) nawet
    jeśli `aktualna_jednostka` jest gdzie indziej / None; NIE podpowiada autora
    związanego tylko z B.
- **Invariant single-install:** przy 1 uczelni wszystkie trzy autocomplety
  zwracają to samo co przed zmianą (guard no-op).
- Regresja: admin autocomplety (`JednostkaAutocomplete` etc.) nietknięte —
  szybki test/asercja że nie filtrują po uczelni.

## Poza zakresem
- Filtrowanie wyników Multiseeka (świadomie — R3a #5).
- Inne autocomplety nie-uczelniane (źródło, wydawca, konferencja, tag).
- Federacja optymalizacji (olana).
