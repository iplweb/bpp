# Identyfikator repozytorium OAI-PMH per uczelnia

Data: 2026-08-03
Gałąź: `fix/oai-identyfikator-repozytorium`

## Cel

Identyfikatory wystawiane przez endpoint OAI-PMH (`/oai/`) mają postać
`oai:<repozytorium>:<id-lokalny>`, gdzie człon środkowy wskazuje repozytorium
źródłowe. Człon ten ma wynikać z konfiguracji uczelni rozstrzygniętej z
requestu, tak aby w instalacji multi-hosted każda uczelnia miała własną,
rozłączną przestrzeń identyfikatorów.

Dwa powody:

1. **Unikalność u harvestera.** Człon repozytorium jest częścią klucza, po
   którym agregatory (OpenAIRE, Primo, BASE) rozpoznają rekord. Wspólny
   człon dla kilku uczelni oznaczałby, że rekordy o tym samym lokalnym `pk`
   zlewają się w jeden.
2. **Poprawna atrybucja.** Wystawiony identyfikator wskazuje repozytorium, z
   którego rekord faktycznie pochodzi.

Wątek wypłynął przy audycie euroCRIS (`AUDYT-EUROCRIS-2026-08-03.md`) jako
warunek przejścia walidatora OpenAIRE.

## Rozwiązanie

Namespace pochodzi z `Uczelnia` rozstrzygniętej przez
`Uczelnia.objects.get_for_request`.

### Dostępność endpointu

Endpoint `/oai/` obsługuje wyłącznie żądania, dla których da się ustalić
uczelnię. Nowe pole `Uczelnia.oai_pmh_aktywny` (domyślnie włączone, żeby
istniejące wdrożenia nic nie traciły) pozwala go wyłączyć per uczelnia.

```python
uczelnia = Uczelnia.objects.get_for_request(request)
if uczelnia is None or not uczelnia.oai_pmh_aktywny:
    raise Http404(...)
```

Brak uczelni oznacza pustą bazę (przed konfiguracją) albo kilka uczelni bez
dopasowania domeny (błąd konfiguracji). Przy dokładnie jednej uczelni
`get_for_request` zawsze ją zwraca, więc żadne realne wdrożenie nie traci
endpointu. Wcześniej rozważany fallback na host requestu odpada — skoro nie
wiadomo, czyje to repozytorium, nie wystawiamy żadnego.

Dzięki temu `BPPOAIDatabase` dostaje uczelnię (a nie request) i nie musi
rozstrzygać jej po raz drugi ani obsługiwać `None`.

### Model

Nowe opcjonalne pole na `Uczelnia`:

```python
oai_identyfikator_repozytorium = models.CharField(
    "Identyfikator repozytorium OAI-PMH",
    max_length=255,
    blank=True,
    default="",
    help_text=...,
)
```

Metoda rozstrzygająca:

```python
def oai_repository_identifier(self):
    """Człon namespace identyfikatorów OAI-PMH tej uczelni."""
    return self.oai_identyfikator_repozytorium.strip() or self.site.domain
```

Dlaczego osobne pole, a nie samo `site.domain`: identyfikator OAI ma być
trwały. `Uczelnia.site` jest wymaganym `OneToOneField`
(`src/bpp/models/uczelnia.py:205`), więc `site.domain` zawsze istnieje i
stanowi dobry domyślny wybór — ale zmiana domeny serwisu (rebranding)
przenumerowałaby całe repozytorium. Osobne pole pozwala odpiąć tożsamość
repozytorium od bieżącego hostname'u.

Migracja: samo `AddField`. **Bez data-migration** — pusty default plus
fallback na `site.domain` zachowuje dotychczasowe identyfikatory istniejących
wdrożeń.

Pole widoczne w `UczelniaAdmin`.

### Generowanie identyfikatora

`get_dc_ident(model, obj_pk)` → `get_dc_ident(namespace, model, obj_pk)`.

Namespace rozstrzygany **raz na odpowiedź** (a nie per wiersz), co gwarantuje
jego spójność w całym wyniku:

```python
repository_identifier = self.uczelnia.oai_repository_identifier()
```

### Parsowanie identyfikatora (`GetRecord`)

Identyfikator z żądania porównujemy z rozstrzygniętym namespace'em. Przy
niezgodności `oai_query` kończy się bez wyniku, a moai emituje błąd
przewidziany protokołem:

> `moai/oai.py:100-101` — `if header is None: raise IdDoesNotExistError(...)`

Jako „brak rekordu" (a nie wyjątek) traktujemy:

- identyfikator z innego repozytorium,
- identyfikator o złej strukturze (brak `oai:`, brak `/`, za mało członów),
- nieznaną nazwę modelu (`ContentType.DoesNotExist`),
- niecałkowite `pk`.

## Testy

- `oai_repository_identifier()`: pole ustawione → pole; puste → `site.domain`;
  whitespace → strip.
- `ListRecords` na domenie uczelni zwraca `oai:<domena>:...`.
- Jawne pole wygrywa z domeną serwisu.
- Dwie uczelnie na dwóch domenach w jednej instalacji → dwa różne namespace'y.
- `GetRecord` z własnym identyfikatorem → 200 + rekord.
- `GetRecord` z identyfikatorem obcego repozytorium → `idDoesNotExist`.
- `GetRecord` z identyfikatorem o złej strukturze → `idDoesNotExist`.
- `oai_pmh_aktywny` domyślnie włączone.
- Brak uczelni z requestu → 404.
- `oai_pmh_aktywny=False` → 404, i tylko dla tej uczelni (druga nadal działa).

## Poza zakresem

- Pozostałe punkty audytu euroCRIS (eksport CERIF-XML, sety OpenAIRE,
  identyfikatory ROR) — osobne zadanie.
- Migracja danych wypełniająca nowe pole — niepotrzebna dzięki fallbackowi.
