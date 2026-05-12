# `test_bpp` — aplikacja pomocnicza dla testów `long_running`

## ⚠️ NIE KASOWAĆ TEJ APLIKACJI

Mimo nazwy sugerującej, że to "aplikacja tylko do testów", `test_bpp` jest
**wymagana w `INSTALLED_APPS` bezwarunkowo** — również w produkcji.
Usunięcie jej albo przeniesienie do konfiguracji dostępnej tylko w testach
**zepsuje testy aplikacji `long_running`**, a także spowoduje rozjazd z
`baseline-sql/baseline.sql`, który oczekuje istnienia tabel tej
aplikacji.

## Po co to istnieje

Aplikacja `long_running` (`src/long_running/`) implementuje generyczny
mechanizm długotrwałych operacji Celery, który operuje na dowolnych modelach
Django przez `ContentType`. Kod produkcyjny robi mniej-więcej tak:

```python
ct = ContentType.objects.get_by_natural_key(app_label, model_name)
obj = ct.model_class().objects.get(pk=pk)
```

Żeby móc **przetestować** ten mechanizm end-to-end, potrzebne są realne
modele Django, które mają:

- prawdziwe tabele w bazie danych,
- swój wpis w tabeli `django_content_type`,
- swoje migracje.

Mocki nie wystarczą — `ContentType.objects.get_by_natural_key()` wymaga
istniejącego rekordu w bazie, a `model_class()` musi zwrócić prawdziwą klasę
Django zarejestrowaną przez `apps.get_model()`. Z tego powodu `test_bpp`
dostarcza dwa modele-doubles.

## Modele

### `TestOperation`

```python
class TestOperation(Operation):
    pass
```

Dziedziczy po `long_running.models.Operation`. Używane w:

- `src/long_running/tests/test_models.py` — testuje `get_redirect_prefix()`
  i pokrewne metody modelu bazowego.
- `src/long_running/tests/test_tasks.py` — testuje
  `perform_generic_long_running_task()` na realnie istniejącym modelu.
- `src/long_running/tests/test_views.py` — testy widoków (redirect,
  status, progress).
- `src/long_running/tests/conftest.py` — fikstura tworząca instancje
  przez `model_bakery.baker.make`.

### `TestObjectThatDoesNotExist`

Model, którego manager **zawsze** rzuca `DoesNotExist`:

```python
class TestObjectThatDoesNotExistManager(models.Manager):
    def get(self, *args, **kw):
        raise TestObjectThatDoesNotExist.DoesNotExist
```

Używany w `src/long_running/tests/test_tasks.py` do pokrycia ścieżki
"object not found" w `perform_generic_long_running_task()` — czyli
scenariusza, w którym Celery task dostaje `content_type_id` + `pk`
obiektu, który został w międzyczasie usunięty z bazy.

## Narzut w produkcji

Zero. Django ładuje `INSTALLED_APPS` raz przy starcie procesu. Tabele
`test_bpp_testoperation` oraz `test_bpp_testobjectthatdoesnotexist` istnieją
w produkcyjnej bazie (są w `baseline.sql`), ale pozostają puste i żaden kod
produkcyjny ich nie odczytuje ani nie zapisuje. Per-request overhead = 0.

## Historyczne pomyłki dotyczące nazwy

1. **`bin/drop-test-databases.sh`** używa prefiksu `test_bpp` — tu chodzi o
   **nazwę bazy danych** (`test_bpp`, `test_bpp_gw0`, `test_bpp_gw1` …),
   którą pytest-xdist tworzy dla workerów. Nie ma to nic wspólnego z tą
   aplikacją Django.

2. **`.circleci-disabled/config.yml`** zawiera `createdb test_bpp` —
   to również nazwa bazy danych, historyczna konfiguracja CI (już nieaktywna,
   stąd `-disabled`).

Zbieżność nazw jest niefortunna, ale nie należy jej używać jako argumentu
za usunięciem aplikacji.

## Rekomendacja dla code review

Jeśli ktoś (człowiek lub automatyczny recenzent) zasugeruje przeniesienie
`test_bpp` do "test-only settings" lub usunięcie jej z `INSTALLED_APPS`,
odpowiedź brzmi: **nie**. Uzasadnienie powyżej. Alternatywą byłoby
przepisanie testów `long_running`, żeby nie polegały na ContentType —
to jest jednak znacznie większa zmiana niż jest to warte, a i tak wymagałaby
jakichś realnych modeli-doubles (bo kod produkcyjny `long_running` używa
ContentType i to jest sens jego istnienia).
