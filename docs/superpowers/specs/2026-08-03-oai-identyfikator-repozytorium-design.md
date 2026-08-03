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

Namespace rozstrzygany **raz na request**, w `BPPOAIDatabase`:

```python
def _repository_identifier(self):
    uczelnia = Uczelnia.objects.get_for_request(self.request)
    if uczelnia is not None:
        return uczelnia.oai_repository_identifier()
    return self.request.get_host().split(":")[0]
```

Rozstrzygnięcie raz per request (a nie per wiersz) gwarantuje spójny
namespace w całej odpowiedzi.

Gałąź `uczelnia is None` jest osiągalna i musi zwracać sensowną wartość:
`scope_rekord_do_uczelni(qs, None)` to świadomy no-op
(`src/bpp/util/uczelnia_scope.py:29`), więc bez ustalonej uczelni rekordy
nadal są wydawane. Host requestu jest wtedy najbliższym sensownym
przybliżeniem.

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
- Brak uczelni z requestu → namespace = host requestu.

## Poza zakresem

- Pozostałe punkty audytu euroCRIS (eksport CERIF-XML, sety OpenAIRE,
  identyfikatory ROR) — osobne zadanie.
- Migracja danych wypełniająca nowe pole — niepotrzebna dzięki fallbackowi.
