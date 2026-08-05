# euroCRIS: encje Projekt i Finansowanie — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zapełnić sety CERIF `openaire_cris_projects` i `openaire_cris_funding` realnymi danymi, dodając do BPP encje projektu badawczego, jego zespołu, finansowania i instytucji finansującej.

**Architecture:** Nowe modele w `bpp` (`Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`, `Finansowanie`); `Grant` zostaje etykietą numeru grantu z FK do projektu, dzięki czemu istniejąca generyczna relacja `Grant_Rekordu` staje się wymaganą przez CERIF relacją publikacja↔projekt. Warstwa eksportu dostaje dwa nowe providery i dwa buildery XML, a set OrgUnits zostaje rozszerzony o instytucje finansujące (wymóg integralności referencyjnej — `Funding/Funder` musi wskazywać na OrgUnit obecny w harveście).

**Tech Stack:** Django, PostgreSQL, lxml, pytest + model_bakery, taggit, OAI-PMH/CERIF-XML.

**Spec:** `docs/superpowers/specs/2026-08-05-eurocris-projekt-finansowanie-design.md`
**Gałąź:** `feat/eurocris-projekty` (odbita od `feat/cerif-mapowania`)
**Issues:** #701 (Project), #702 (Funding)

## Global Constraints

- Wszystkie polecenia Pythona przez `uv run`. Nigdy gołe `python`/`pytest`.
- Max długość linii: 88 znaków (ruff).
- **Nie wolno modyfikować istniejących migracji** w `src/*/migrations/`.
- Testy: pytest, funkcje bez klas, `@pytest.mark.django_db`, `baker.make`. Nigdy `unittest.TestCase`.
- Żadnych `except: pass` ani `except Exception: pass` — każdy `except` loguje, re-raise'uje albo zwraca sensowny błąd.
- Nazewnictwo modeli po polsku, przez-modele jako `Model_Model` (wzorce: `Patent_Autor`, `Grant_Rekordu`).
- Źródło prawdy o formacie XML: `src/cerif_export/tests/xsd/openaire-cerif-profile.xsd` + `includes/` + `vocabularies/`. Przy wątpliwości — czytaj XSD, nie dokumentację z pamięci.
- Reguła pakietu `cerif_export.cerif`: **serializer nie dotyka bazy**. Wolno czytać pola załadowanego obiektu, pola `*_id` i relacje zadeklarowane przez provider jako prefetch. Widoczność encji sąsiadujących rozstrzyga wyłącznie `KontekstSerializacji.id_dla`.
- **Nie uruchamiaj `make baseline-update`** w trakcie prac — baseline odświeżamy raz, przy scalaniu gałęzi.
- Newsfragmenty trafiają do `src/bpp/newsfragments/` (nie `changes/`).

---

### Task 1: Modele danych i migracja schematu

Fundament — wszystkie pozostałe zadania z niego korzystają. Wykonywane **sekwencyjnie, jako pierwsze** (jedna migracja schematu, żeby równoległe zadania nie kolidowały numeracją).

**Files:**
- Create: `src/bpp/models/projekt.py`
- Modify: `src/bpp/models/__init__.py`, `src/bpp/models/grant.py`, `src/bpp/models/uczelnia.py`, `src/bpp/system.py`
- Create: `src/bpp/tests/test_projekt.py`
- Create (przez `makemigrations`): `src/bpp/migrations/XXXX_projekt_finansowanie.py`

**Interfaces:**
- Produces: modele `Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`, `Finansowanie` w `bpp.models`; stałe `Projekt.STATUS_*`, `Projekt_Autor.ROLA_KIEROWNIK`, `Finansowanie.TYP_*`; pola `Grant.projekt`, `Uczelnia.eksport_cerif_kwoty`.

- [ ] **Step 1: Napisz testy modeli (najpierw czerwone)**

Utwórz `src/bpp/tests/test_projekt.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from model_bakery import baker

from bpp.models import (
    Finansowanie,
    Grant,
    Instytucja_Finansujaca,
    Projekt,
    Projekt_Autor,
)


@pytest.mark.django_db
def test_projekt_data_zakonczenia_przed_rozpoczeciem(jednostka):
    projekt = Projekt(
        tytul="Testowy",
        jednostka=jednostka,
        data_rozpoczecia="2026-01-01",
        data_zakonczenia="2025-12-31",
    )
    with pytest.raises(ValidationError):
        projekt.clean()


@pytest.mark.django_db
def test_finansowanie_kwota_bez_waluty(jednostka):
    projekt = baker.make(Projekt, jednostka=jednostka)
    instytucja = baker.make(Instytucja_Finansujaca)
    finansowanie = Finansowanie(
        projekt=projekt,
        instytucja=instytucja,
        typ=Finansowanie.TYP_GRANT,
        kwota=1000,
        waluta="",
    )
    with pytest.raises(ValidationError):
        finansowanie.clean()


@pytest.mark.django_db
def test_tylko_jeden_kierownik_projektu(jednostka, autor_jan_nowak, autor_jan_kowalski):
    projekt = baker.make(Projekt, jednostka=jednostka)
    Projekt_Autor.objects.create(
        projekt=projekt, autor=autor_jan_nowak, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    with pytest.raises(IntegrityError):
        Projekt_Autor.objects.create(
            projekt=projekt,
            autor=autor_jan_kowalski,
            rola=Projekt_Autor.ROLA_KIEROWNIK,
        )


@pytest.mark.django_db
def test_kasowanie_projektu_zostawia_grant(jednostka):
    projekt = baker.make(Projekt, jednostka=jednostka)
    grant = baker.make(Grant, numer_projektu="ABC/123", projekt=projekt)
    projekt.delete()
    grant.refresh_from_db()
    assert grant.pk is not None
    assert grant.projekt is None
```

Fixture'y `jednostka`, `autor_jan_nowak`, `autor_jan_kowalski` istnieją w `src/fixtures/` — sprawdź ich nazwy przez `grep -rn "def jednostka\b" src/fixtures/` i użyj tych, które faktycznie są.

- [ ] **Step 2: Uruchom testy, potwierdź czerwone**

Run: `uv run pytest src/bpp/tests/test_projekt.py -v`
Expected: FAIL — `ImportError: cannot import name 'Projekt'`.

- [ ] **Step 3: Napisz `src/bpp/models/projekt.py`**

```python
"""Encje projektu badawczego i jego finansowania.

Modele odpowiadają encjom CERIF ``Project`` i ``Funding`` z profilu
OpenAIRE Guidelines for CRIS Managers 1.2.0. Dziedziczenie po
``ModelZAdnotacjami`` nie jest kosmetyczne: daje ``ostatnio_zmieniony``,
na którym ``cerif_export.providers.base.z_datestampem`` buduje keysetowy
kursor przyrostowego harvestu OAI-PMH.
"""

from django.core.exceptions import ValidationError
from django.db import models

from bpp.models.abstract import ModelZAdnotacjami, ModelZeSlowamiKluczowymi


class Projekt(ModelZAdnotacjami, ModelZeSlowamiKluczowymi):
    STATUS_PLANOWANY = "planowany"
    STATUS_W_TRAKCIE = "w-trakcie"
    STATUS_ZAKONCZONY = "zakonczony"
    STATUS_PRZERWANY = "przerwany"

    STATUSY = [
        (STATUS_PLANOWANY, "planowany"),
        (STATUS_W_TRAKCIE, "w trakcie"),
        (STATUS_ZAKONCZONY, "zakończony"),
        (STATUS_PRZERWANY, "przerwany"),
    ]

    tytul = models.TextField(verbose_name="Tytuł")
    tytul_en = models.TextField(
        verbose_name="Tytuł (angielski)", blank=True, default=""
    )
    akronim = models.CharField(max_length=50, blank=True, default="")
    data_rozpoczecia = models.DateField(
        verbose_name="Data rozpoczęcia", null=True, blank=True
    )
    data_zakonczenia = models.DateField(
        verbose_name="Data zakończenia", null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUSY, default=STATUS_W_TRAKCIE
    )
    abstrakt = models.TextField(blank=True, default="")
    abstrakt_en = models.TextField(
        verbose_name="Abstrakt (angielski)", blank=True, default=""
    )
    dyscypliny = models.ManyToManyField(
        "bpp.Dyscyplina_Naukowa", blank=True, verbose_name="Dyscypliny"
    )
    # Jednostka jest wymagana, bo jest jedynym nośnikiem przynależności
    # projektu do uczelni (tenanta). Provider CERIF filtruje po
    # ``jednostka__uczelnia``; pole nullable po cichu wypychałoby projekty
    # z eksportu.
    jednostka = models.ForeignKey(
        "bpp.Jednostka",
        models.PROTECT,
        verbose_name="Jednostka realizująca",
    )
    strona_www = models.URLField(blank=True, default="")

    class Meta:
        verbose_name = "projekt"
        verbose_name_plural = "projekty"
        ordering = ["-data_rozpoczecia", "tytul"]

    def __str__(self):
        if self.akronim:
            return f"{self.akronim} — {self.tytul}"
        return self.tytul

    def clean(self):
        if (
            self.data_rozpoczecia
            and self.data_zakonczenia
            and self.data_zakonczenia < self.data_rozpoczecia
        ):
            raise ValidationError(
                {"data_zakonczenia": "Data zakończenia jest wcześniejsza "
                                     "niż data rozpoczęcia."}
            )


class Projekt_Autor(models.Model):
    ROLA_KIEROWNIK = "kierownik"
    ROLA_WYKONAWCA = "wykonawca"
    ROLA_WSPOLWYKONAWCA = "wspolwykonawca"

    ROLE = [
        (ROLA_KIEROWNIK, "kierownik"),
        (ROLA_WYKONAWCA, "wykonawca"),
        (ROLA_WSPOLWYKONAWCA, "współwykonawca"),
    ]

    projekt = models.ForeignKey(Projekt, models.CASCADE)
    autor = models.ForeignKey("bpp.Autor", models.PROTECT)
    rola = models.CharField(max_length=20, choices=ROLE, default=ROLA_WYKONAWCA)
    od = models.DateField(null=True, blank=True)
    do = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "osoba w projekcie"
        verbose_name_plural = "osoby w projekcie"
        unique_together = [("projekt", "autor", "rola")]
        constraints = [
            # Jeden kierownik na projekt — wymuszone w bazie, bo ``clean()``
            # przy dwóch nowych wierszach dodanych naraz w inline widzi
            # wyłącznie stan zapisany, więc drugiego kierownika by przepuścił.
            models.UniqueConstraint(
                fields=["projekt"],
                condition=models.Q(rola="kierownik"),
                name="projekt_jeden_kierownik",
            )
        ]

    def __str__(self):
        return f"{self.autor} ({self.get_rola_display()})"


class Instytucja_Finansujaca(ModelZAdnotacjami):
    """Grantodawca. Eksportowana jako CERIF ``OrgUnit`` (rola Funder)."""

    nazwa = models.TextField()
    nazwa_en = models.TextField(
        verbose_name="Nazwa (angielska)", blank=True, default=""
    )
    akronim = models.CharField(max_length=50, blank=True, default="")
    kraj = models.CharField(
        max_length=2,
        default="PL",
        help_text="Kod ISO 3166-1 alpha-2. Pole wewnętrzne — profil "
                  "OpenAIRE nie ma elementu Country w encji OrgUnit.",
    )
    ror_id = models.CharField(
        verbose_name="Identyfikator ROR", max_length=200, blank=True, default=""
    )
    fundref_id = models.CharField(
        verbose_name="Crossref Funder ID",
        max_length=50,
        blank=True,
        default="",
        help_text="Identyfikator z Crossref Funder Registry, np. 501100004281.",
    )
    strona_www = models.URLField(blank=True, default="")

    class Meta:
        verbose_name = "instytucja finansująca"
        verbose_name_plural = "instytucje finansujące"
        ordering = ["nazwa"]

    def __str__(self):
        if self.akronim:
            return f"{self.akronim} — {self.nazwa}"
        return self.nazwa


class Finansowanie(ModelZAdnotacjami):
    """Źródło finansowania projektu. Encja CERIF ``Funding``."""

    TYP_FUNDING_PROGRAMME = "FundingProgramme"
    TYP_CALL = "Call"
    TYP_TENDER = "Tender"
    TYP_GIFT = "Gift"
    TYP_INTERNAL_FUNDING = "InternalFunding"
    TYP_CONTRACT = "Contract"
    TYP_AWARD = "Award"
    TYP_GRANT = "Grant"

    TYPY = [
        (TYP_FUNDING_PROGRAMME, "program finansowania"),
        (TYP_CALL, "konkurs"),
        (TYP_TENDER, "przetarg"),
        (TYP_GIFT, "darowizna"),
        (TYP_INTERNAL_FUNDING, "finansowanie wewnętrzne"),
        (TYP_CONTRACT, "umowa"),
        (TYP_AWARD, "nagroda"),
        (TYP_GRANT, "grant"),
    ]

    projekt = models.ForeignKey(Projekt, models.CASCADE)
    typ = models.CharField(max_length=30, choices=TYPY, default=TYP_GRANT)
    instytucja = models.ForeignKey(Instytucja_Finansujaca, models.PROTECT)
    nazwa_programu = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Nazwa programu lub konkursu, np. „OPUS 24”.",
    )
    numer_umowy = models.CharField(max_length=200, blank=True, default="")
    kwota = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    waluta = models.CharField(max_length=3, blank=True, default="PLN")
    grant_doi = models.CharField(
        verbose_name="DOI grantu", max_length=200, blank=True, default=""
    )

    class Meta:
        verbose_name = "finansowanie"
        verbose_name_plural = "finansowania"

    def __str__(self):
        return f"{self.instytucja} — {self.get_typ_display()}"

    def clean(self):
        if self.kwota is not None and not self.waluta:
            raise ValidationError(
                {"waluta": "Kwota bez waluty jest niejednoznaczna."}
            )
```

Sprawdź nazwy importów miksinów: `grep -rn "ModelZAdnotacjami\|ModelZeSlowamiKluczowymi" src/bpp/models/abstract/__init__.py`. Jeśli nie są reeksportowane z `bpp.models.abstract`, importuj z modułów źródłowych (`bpp.models.abstract.metadata`, `bpp.models.abstract.keywords`).

- [ ] **Step 4: Wepnij moduł do `src/bpp/models/__init__.py`**

Dopisz w kolejności alfabetycznej, obok istniejącego `from .grant import *`:

```python
from .projekt import *  # noqa
```

- [ ] **Step 5: Dodaj `Grant.projekt` i `Uczelnia.eksport_cerif_kwoty`**

W `src/bpp/models/grant.py`, w klasie `Grant`:

```python
    projekt = models.ForeignKey(
        "bpp.Projekt",
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Projekt",
        help_text="Projekt badawczy, w ramach którego przyznano ten grant.",
    )
```

`SET_NULL`, bo skasowanie projektu nie może kasować historycznych numerów grantów przypiętych do publikacji.

W `src/bpp/models/uczelnia.py`, obok `eksport_cerif_osoby`:

```python
    eksport_cerif_kwoty = models.BooleanField(
        verbose_name="Eksport CERIF: kwoty finansowania",
        default=False,
        help_text="Czy w eksporcie CERIF-XML wystawiać kwoty finansowania "
                  "projektów. Domyślnie wyłączone — kwoty zostają w bazie "
                  "do użytku wewnętrznego.",
    )
```

- [ ] **Step 6: Dopisz modele do uprawnień grupy „wprowadzanie danych"**

W `src/bpp/system.py` znajdź listy pod kluczem `GR_WPROWADZANIE_DANYCH` (są dwie — około linii 159 i 219; obejrzyj obie i ustal, która czemu odpowiada, po sąsiadujących wpisach `Grant` i `Grant_Rekordu`). Dodaj `Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`, `Finansowanie` analogicznie do tego, jak wpisany jest tam `Grant`, wraz z importem modeli na górze pliku.

- [ ] **Step 7: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp --name projekt_finansowanie`
Expected: jeden nowy plik w `src/bpp/migrations/` z czterema `CreateModel`, dwoma `AddField` i `AddConstraint`.

Obejrzyj wygenerowany plik. Jeśli `makemigrations` zapyta o wartość domyślną dla nienullowalnego pola — to znaczy, że coś jest nie tak z modelem; popraw model, nie migrację.

- [ ] **Step 8: Uruchom testy**

Run: `uv run pytest src/bpp/tests/test_projekt.py -v`
Expected: PASS (4 testy).

- [ ] **Step 9: Sprawdź, że nic nie zepsuło istniejących testów grantu i uczelni**

Run: `uv run pytest src/bpp/tests/ -k "grant or uczelnia" -q`
Expected: PASS.

- [ ] **Step 10: Lint i commit**

```bash
ruff format src/bpp/models/projekt.py src/bpp/tests/test_projekt.py
ruff check src/bpp/models/projekt.py src/bpp/tests/test_projekt.py
git add src/bpp/models/ src/bpp/tests/test_projekt.py src/bpp/system.py src/bpp/migrations/
git commit -m "feat(projekty): modele Projekt, Projekt_Autor, Instytucja_Finansujaca, Finansowanie (#701, #702)"
```

---

### Task 2: Admin — wprowadzanie danych przez redakcję

**Wymaga:** Task 1. **Równoległe z:** Task 3, Task 4.

**Files:**
- Create: `src/bpp/admin/projekt.py`
- Modify: `src/bpp/admin/__init__.py`, `src/bpp/admin/grant.py`, `src/bpp/admin/uczelnia.py`
- Create: `src/bpp/tests/test_admin_projekt.py`

**Interfaces:**
- Consumes: modele z Taska 1 (`Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`, `Finansowanie`, `Projekt_Autor.ROLA_KIEROWNIK`), walidator ROR z `bpp/util/ror.py` (ustal dokładną nazwę funkcji: `grep -rn "^def " src/bpp/util/ror.py`).
- Produces: `ProjektAdmin`, `Instytucja_FinansujacaAdmin`.

- [ ] **Step 1: Napisz test walidacji formsetu (czerwony)**

Utwórz `src/bpp/tests/test_admin_projekt.py`:

```python
import pytest
from django.contrib.admin.sites import AdminSite
from model_bakery import baker

from bpp.admin.projekt import ProjektAdmin, Projekt_AutorInline
from bpp.models import Projekt, Projekt_Autor


@pytest.mark.django_db
def test_inline_odrzuca_dwoch_kierownikow(
    jednostka, autor_jan_nowak, autor_jan_kowalski, rf
):
    projekt = baker.make(Projekt, jednostka=jednostka)
    inline = Projekt_AutorInline(Projekt, AdminSite())
    FormSet = inline.get_formset(rf.get("/"), projekt)
    dane = {
        "bpp-projekt_autor-projekt-TOTAL_FORMS": "2",
        "bpp-projekt_autor-projekt-INITIAL_FORMS": "0",
        "bpp-projekt_autor-projekt-0-autor": str(autor_jan_nowak.pk),
        "bpp-projekt_autor-projekt-0-rola": Projekt_Autor.ROLA_KIEROWNIK,
        "bpp-projekt_autor-projekt-1-autor": str(autor_jan_kowalski.pk),
        "bpp-projekt_autor-projekt-1-rola": Projekt_Autor.ROLA_KIEROWNIK,
    }
    formset = FormSet(dane, instance=projekt)
    assert not formset.is_valid()


@pytest.mark.django_db
def test_projekt_admin_ma_search_fields():
    # Bez ``search_fields`` autocomplete w innych adminach nie zadziała.
    assert ProjektAdmin.search_fields
```

Prefiks formsetu (`bpp-projekt_autor-projekt`) zależy od nazw modeli — jeśli test wywala się na kluczach, wypisz `FormSet.get_default_prefix()` i użyj tego, co faktycznie zwraca.

- [ ] **Step 2: Uruchom test, potwierdź czerwony**

Run: `uv run pytest src/bpp/tests/test_admin_projekt.py -v`
Expected: FAIL — `ModuleNotFoundError: bpp.admin.projekt`.

- [ ] **Step 3: Napisz `src/bpp/admin/projekt.py`**

```python
from django import forms
from django.contrib import admin

from bpp.models import (
    Finansowanie,
    Instytucja_Finansujaca,
    Projekt,
    Projekt_Autor,
)


class Projekt_AutorFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        kierownicy = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("rola") == Projekt_Autor.ROLA_KIEROWNIK:
                kierownicy += 1
        if kierownicy > 1:
            raise forms.ValidationError(
                "Projekt może mieć tylko jednego kierownika."
            )


class Projekt_AutorInline(admin.TabularInline):
    model = Projekt_Autor
    formset = Projekt_AutorFormSet
    extra = 0
    autocomplete_fields = ["autor"]


class FinansowanieInline(admin.TabularInline):
    model = Finansowanie
    extra = 0
    autocomplete_fields = ["instytucja"]


@admin.register(Projekt)
class ProjektAdmin(admin.ModelAdmin):
    list_display = [
        "tytul",
        "akronim",
        "status",
        "data_rozpoczecia",
        "data_zakonczenia",
        "jednostka",
    ]
    list_filter = ["status", "jednostka", "dyscypliny"]
    search_fields = ["tytul", "tytul_en", "akronim", "abstrakt"]
    autocomplete_fields = ["jednostka"]
    filter_horizontal = ["dyscypliny"]
    inlines = [Projekt_AutorInline, FinansowanieInline]


@admin.register(Instytucja_Finansujaca)
class Instytucja_FinansujacaAdmin(admin.ModelAdmin):
    list_display = ["nazwa", "akronim", "kraj", "ror_id", "fundref_id"]
    search_fields = ["nazwa", "nazwa_en", "akronim", "ror_id", "fundref_id"]
```

Walidacja `ror_id` jest już na poziomie pola modelu, jeśli Task 1 podpiął walidator; jeśli nie — dodaj `validators=[...]` do pola w modelu (nie w adminie), żeby obowiązywała też przy imporcie. Sprawdź, jak zrobiono to dla `Jednostka.ror_id` na tej gałęzi (`grep -rn "ror" src/bpp/models/jednostka.py`) i powiel wzorzec.

- [ ] **Step 4: Wepnij admin i rozszerz istniejące**

W `src/bpp/admin/__init__.py`, wśród pozostałych importów:

```python
from .projekt import Instytucja_FinansujacaAdmin, ProjektAdmin  # noqa
```

W `src/bpp/admin/grant.py`, w `GrantAdmin`:

```python
    list_display = [
        "nazwa_projektu",
        "numer_projektu",
        "rok",
        "zrodlo_finansowania",
        "projekt",
    ]
    list_filter = ["projekt"]
    autocomplete_fields = ["projekt"]
```

W `src/bpp/admin/uczelnia.py` (okolice linii 174) dopisz `"eksport_cerif_kwoty"` do tego samego fieldsetu, w którym jest `"eksport_cerif_osoby"`.

- [ ] **Step 5: Uruchom testy**

Run: `uv run pytest src/bpp/tests/test_admin_projekt.py -v`
Expected: PASS.

- [ ] **Step 6: Sprawdź spójność adminów Django**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`. Błędy `admin.E040` oznaczają brak `search_fields` w adminie modelu użytego w `autocomplete_fields`.

- [ ] **Step 7: Lint i commit**

```bash
ruff format src/bpp/admin/projekt.py src/bpp/tests/test_admin_projekt.py
ruff check src/bpp/admin/ src/bpp/tests/test_admin_projekt.py
git add src/bpp/admin/ src/bpp/tests/test_admin_projekt.py
git commit -m "feat(projekty): admin projektów, finansowania i instytucji finansujących (#701)"
```

---

### Task 3: Migracja danych — seed instytucji finansujących

**Wymaga:** Task 1. **Równoległe z:** Task 2, Task 4.

**Files:**
- Create: `src/bpp/migrations/XXXX_seed_instytucje_finansujace.py`
- Create: `src/bpp/tests/test_seed_instytucji.py`

**Interfaces:**
- Consumes: model `Instytucja_Finansujaca` z Taska 1.
- Produces: wiersze słownika grantodawców w bazie.

- [ ] **Step 1: Zweryfikuj identyfikatory w rejestrach**

**Nie wpisuj identyfikatorów z pamięci.** Dla każdej instytucji sprawdź Crossref Funder Registry (`https://api.crossref.org/funders?query=<nazwa>`) i rejestr ROR (`https://api.ror.org/organizations?query=<nazwa>`). Zakres: Narodowe Centrum Nauki, Narodowe Centrum Badań i Rozwoju, Ministerstwo Nauki i Szkolnictwa Wyższego, Fundacja na rzecz Nauki Polskiej, Narodowa Agencja Wymiany Akademickiej, Agencja Badań Medycznych, Komisja Europejska.

Zapisz znalezione wartości; instytucja, dla której **nie ma** potwierdzonego identyfikatora, wchodzi do seeda **bez niego** — nigdy ze zmyślonym.

- [ ] **Step 2: Napisz test seeda (czerwony)**

Utwórz `src/bpp/tests/test_seed_instytucji.py`:

```python
import pytest

from bpp.models import Instytucja_Finansujaca


@pytest.mark.django_db
def test_seed_zawiera_ncn():
    ncn = Instytucja_Finansujaca.objects.filter(akronim="NCN").first()
    assert ncn is not None
    assert ncn.kraj == "PL"


@pytest.mark.django_db
def test_seed_bez_zmyslonych_identyfikatorow():
    # FundRef ID Crossrefa to sam ciąg cyfr (bez URL-a i bez prefiksu).
    for instytucja in Instytucja_Finansujaca.objects.exclude(fundref_id=""):
        assert instytucja.fundref_id.isdigit(), instytucja.nazwa
```

- [ ] **Step 3: Uruchom test, potwierdź czerwony**

Run: `uv run pytest src/bpp/tests/test_seed_instytucji.py -v`
Expected: FAIL — brak wiersza NCN.

- [ ] **Step 4: Napisz migrację danych**

Obejrzyj `src/bpp/migrations/0483_*.py` jako wzorzec (migracja danych z komentarzem uzasadniającym). Utwórz analogiczną:

```python
"""Seed słownika instytucji finansujących.

Identyfikatory FundRef pochodzą z Crossref Funder Registry, ROR-y
z rejestru ROR — zweryfikowane w rejestrach przy pisaniu migracji, nie
przepisane z pamięci. Instytucja bez potwierdzonego identyfikatora wchodzi
bez niego: pusty identyfikator jest brakiem danych, a zmyślony jest
błędem, który wycieknie do OpenAIRE i sklei nasze publikacje z cudzym
profilem grantodawcy.

Idempotentna: ``get_or_create`` po ``fundref_id`` tam, gdzie jest, po
``nazwa`` w przeciwnym razie. Odwrotna operacja jest no-opem — kasowanie
grantodawców przy cofaniu migracji mogłoby zerwać FK z ``Finansowanie``.
"""

from django.db import migrations

INSTYTUCJE = [
    # (nazwa, nazwa_en, akronim, kraj, fundref_id, ror_id)
    # UZUPEŁNIJ zweryfikowanymi wartościami ze Stepu 1.
]


def seed(apps, schema_editor):
    Instytucja_Finansujaca = apps.get_model("bpp", "Instytucja_Finansujaca")
    for nazwa, nazwa_en, akronim, kraj, fundref_id, ror_id in INSTYTUCJE:
        klucz = (
            {"fundref_id": fundref_id} if fundref_id else {"nazwa": nazwa}
        )
        Instytucja_Finansujaca.objects.get_or_create(
            defaults={
                "nazwa": nazwa,
                "nazwa_en": nazwa_en,
                "akronim": akronim,
                "kraj": kraj,
                "fundref_id": fundref_id,
                "ror_id": ror_id,
            },
            **klucz,
        )


class Migration(migrations.Migration):
    dependencies = [("bpp", "XXXX_projekt_finansowanie")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

Podmień `XXXX_projekt_finansowanie` na faktyczną nazwę migracji z Taska 1 i wypełnij `INSTYTUCJE` danymi ze Stepu 1.

- [ ] **Step 5: Uruchom testy**

Run: `uv run pytest src/bpp/tests/test_seed_instytucji.py -v`
Expected: PASS.

- [ ] **Step 6: Sprawdź idempotentność**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py migrate bpp`
Expected: brak błędów przy ponownym przejściu (migracja jest już zastosowana; test z `--fake` nie jest potrzebny — idempotentność zapewnia `get_or_create`).

- [ ] **Step 7: Lint i commit**

```bash
ruff format src/bpp/migrations/ src/bpp/tests/test_seed_instytucji.py
ruff check src/bpp/migrations/ src/bpp/tests/test_seed_instytucji.py
git add src/bpp/migrations/ src/bpp/tests/test_seed_instytucji.py
git commit -m "feat(projekty): seed słownika instytucji finansujących (#702)"
```

---

### Task 4: Fundament eksportu — stałe, identyfikatory, słownik typów, funder jako OrgUnit

**Wymaga:** Task 1. **Równoległe z:** Task 2, Task 3.

**Files:**
- Modify: `src/cerif_export/const.py`, `src/cerif_export/identyfikatory.py`, `src/cerif_export/providers/jednostki.py`, `src/cerif_export/cerif/orgunit.py`
- Create: `src/cerif_export/slowniki/typy_finansowania.py`
- Create: `src/cerif_export/tests/test_funderzy_orgunit.py`

**Interfaces:**
- Consumes: modele z Taska 1.
- Produces: `const.TYP_PROJECT`, `const.TYP_FUNDING`, `const.SCHEMAT_STATUSU_PROJEKTU`, `const.SCHEMAT_DYSCYPLIN`; wpisy `pj`/`fn`/`if` w `identyfikatory._REJESTR`; `slowniki.typy_finansowania.uri_typu(typ) -> str | None`; `Instytucja_Finansujaca` w secie OrgUnits.

- [ ] **Step 1: Napisz test funderów w secie OrgUnits (czerwony)**

Utwórz `src/cerif_export/tests/test_funderzy_orgunit.py`. Najpierw przeczytaj istniejący `src/cerif_export/tests/` i użyj tamtejszych fixture'ów oraz sposobu wołania providera — poniższy szkielet zakłada, że provider ma metodę `strona()`, ale sprawdź faktyczną sygnaturę w `providers/base.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Finansowanie, Instytucja_Finansujaca, Projekt
from cerif_export.providers.jednostki import ProviderJednostek


@pytest.mark.django_db
def test_funder_bez_finansowania_nie_wychodzi(uczelnia, jednostka):
    baker.make(Instytucja_Finansujaca, nazwa="Niepowiązana")
    provider = ProviderJednostek()
    qs = provider.queryset(uczelnia, Instytucja_Finansujaca)
    assert not qs.exists()


@pytest.mark.django_db
def test_funder_z_finansowaniem_wychodzi(uczelnia, jednostka):
    instytucja = baker.make(Instytucja_Finansujaca, nazwa="NCN", akronim="NCN")
    projekt = baker.make(Projekt, jednostka=jednostka)
    baker.make(Finansowanie, projekt=projekt, instytucja=instytucja)
    provider = ProviderJednostek()
    qs = provider.queryset(uczelnia, Instytucja_Finansujaca)
    assert list(qs) == [instytucja]
```

Fixture `uczelnia` i `jednostka` — sprawdź, jak nazywają się w `src/fixtures/` i czy `jednostka` jest powiązana z `uczelnia`.

- [ ] **Step 2: Uruchom test, potwierdź czerwony**

Run: `uv run pytest src/cerif_export/tests/test_funderzy_orgunit.py -v`
Expected: FAIL — provider odrzuca nieznany model.

- [ ] **Step 3: Dodaj stałe do `const.py`**

Obejrzyj plik i dopisz obok istniejących `TYP_*`:

```python
TYP_PROJECT = "Project"
TYP_FUNDING = "Funding"

# Schematy klasyfikacji własnych. ``cfGenericURIClassification__Type``
# wymaga atrybutu ``scheme`` (anyURI) i wartości będącej URI, a profil
# OpenAIRE nie dostarcza słownika ani dla statusu projektu, ani dla
# polskich dyscyplin naukowych. Własny schemat jawnie nazywa pochodzenie
# wartości — lepiej niż pominięcie danych i lepiej niż podszywanie się pod
# cudzy słownik.
SCHEMAT_STATUSU_PROJEKTU = "https://bpp.iplweb.pl/vocab/StatusProjektu"
SCHEMAT_DYSCYPLIN = "https://bpp.iplweb.pl/vocab/DyscyplinaNaukowa"
```

Sprawdź, czy dokładne wartości `TYP_PROJECT`/`TYP_FUNDING` zgadzają się z nazwami elementów w XSD (`grep -n 'name="Project"\|name="Funding"' src/cerif_export/tests/xsd/openaire-cerif-profile.xsd`) — te stałe trafiają do identyfikatorów OAI i muszą pasować do reguły walidatora opisanej w docstringu `cerif/wspolne.py`.

- [ ] **Step 4: Dopisz wpisy do rejestru identyfikatorów**

W `src/cerif_export/identyfikatory.py`, w `_REJESTR`:

```python
    "bpp.Projekt": (const.TYP_PROJECT, "pj"),
    "bpp.Finansowanie": (const.TYP_FUNDING, "fn"),
    "bpp.Instytucja_Finansujaca": (const.TYP_ORGUNIT, "if"),
```

Instytucja finansująca dostaje typ **OrgUnit**, nie własny — jest eksportowana w secie `openaire_cris_orgunits`.

- [ ] **Step 5: Napisz słownik typów finansowania**

Utwórz `src/cerif_export/slowniki/typy_finansowania.py` wzorem `slowniki/coar.py`. Dozwolone wartości i ich URI odczytaj z `src/cerif_export/tests/xsd/vocabularies/openaire_funding_types.xsd` — osiem wartości: FundingProgramme, Call, Tender, Gift, InternalFunding, Contract, Award, Grant. Moduł eksportuje:

```python
def uri_typu(typ: str) -> str | None:
    """Zwróć URI typu finansowania albo ``None`` dla nieznanej wartości."""
```

- [ ] **Step 6: Rozszerz provider OrgUnits o funderów**

W `src/cerif_export/providers/jednostki.py`:

```python
from bpp.models import Instytucja_Finansujaca
```

w `ProviderJednostek`:

```python
    modele = [Jednostka, Uczelnia, Instytucja_Finansujaca]
```

i w `queryset()` dodatkowa gałąź:

```python
        if model is Instytucja_Finansujaca:
            # Wychodzą wyłącznie grantodawcy realnie finansujący projekty
            # tej uczelni. Seed słownika ma kilkanaście pozycji; wypchnięcie
            # ich wszystkich pokazywałoby OpenAIRE instytucje, z którymi
            # uczelnia nie ma nic wspólnego.
            return Instytucja_Finansujaca.objects.filter(
                finansowanie__projekt__jednostka__uczelnia=uczelnia
            ).distinct()
```

Nazwa odwrotnej relacji (`finansowanie__`) zależy od `related_name` — jeśli go nie ustawiono w Tasku 1, Django użyje `finansowanie`. Zweryfikuj przez `uv run python src/manage.py shell -c "..."` albo po prostu uruchom test.

- [ ] **Step 7: Rozszerz serializer OrgUnit**

W `src/cerif_export/cerif/orgunit.py` dodaj gałąź serializującą `Instytucja_Finansujaca`: `Acronym`, `Name` (pl + en jako `cfMLangString__Type`, wzorem tego, jak plik robi wielojęzyczność dla jednostek), `RORID`, `FundRefID`, `ElectronicAddress`.

`RORID` i `FundRefID` to **dedykowane elementy** z `includes/orgunit-identifiers.xsd`, nie generyczne `Identifier` — sprawdź ich dokładne nazwy i kolejność: `grep -n "name=" src/cerif_export/tests/xsd/includes/orgunit-identifiers.xsd`.

Kraj **nie wychodzi** — sekwencja OrgUnit w profilu nie ma elementu Country.

- [ ] **Step 8: Uruchom testy**

Run: `uv run pytest src/cerif_export/tests/test_funderzy_orgunit.py -v`
Expected: PASS.

- [ ] **Step 9: Uruchom istniejące testy eksportu (regresja)**

Run: `uv run pytest src/cerif_export/tests/ -q`
Expected: PASS — rozszerzenie setu OrgUnits nie może zmienić tego, co wychodzi dla jednostek i uczelni.

- [ ] **Step 10: Lint i commit**

```bash
ruff format src/cerif_export/
ruff check src/cerif_export/
git add src/cerif_export/
git commit -m "feat(cerif): instytucje finansujące jako OrgUnit + fundament dla Project/Funding (#702)"
```

---

### Task 5: Buildery `Project` i `Funding` oraz ich providery

**Wymaga:** Task 4 (stałe, identyfikatory, słownik typów).

**Files:**
- Create: `src/cerif_export/cerif/funding.py`, `src/cerif_export/cerif/project.py`
- Create: `src/cerif_export/providers/finansowanie.py`, `src/cerif_export/providers/projekty.py`
- Modify: `src/cerif_export/providers/puste.py`, plus miejsce rejestracji providerów (znajdź je: `grep -rn "ProviderProjektow\|ProviderPusty" src/cerif_export/`)
- Create: `src/cerif_export/tests/test_eksport_projektow.py`

**Interfaces:**
- Consumes: wszystko z Tasków 1 i 4.
- Produces: `cerif.funding.serializuj(finansowanie, ctx) -> etree.Element`, `cerif.project.serializuj(projekt, ctx) -> etree.Element`, `ProviderProjektow`, `ProviderFinansowania`.

**Zanim zaczniesz — przeczytaj:**
- `src/cerif_export/cerif/event.py` (najprostszy builder) i `cerif/patent.py` (builder z referencjami do osób),
- `src/cerif_export/cerif/wspolne.py` (helpery `element`, `dodaj`, `tekst`, `data_iso`, `ustaw_id_rekordu`; reguła „serializer nie dotyka bazy"),
- `src/cerif_export/providers/konferencje.py` i `providers/patenty.py` (wzorce providera i `zbiory_widocznosci`),
- XSD: sekwencja `Project` (linie 238–450) i `Funding` (od linii ~460).

- [ ] **Step 1: Napisz testy serializacji (czerwone)**

Utwórz `src/cerif_export/tests/test_eksport_projektow.py`. Wzoruj się na istniejących testach eksportu co do sposobu budowania kontekstu (`KontekstSerializacji`) — poniżej treść merytoryczna asercji:

```python
import pytest
from model_bakery import baker

from bpp.models import Finansowanie, Instytucja_Finansujaca, Projekt


@pytest.mark.django_db
def test_funding_ma_typ_zawsze(uczelnia, jednostka):
    # Funding/Type jest w profilu obowiązkowy.
    ...
    assert el.find("Type") is not None


@pytest.mark.django_db
def test_kwota_tylko_przy_wlaczonym_przelaczniku(uczelnia, jednostka):
    # eksport_cerif_kwoty=False -> brak <Amount>; True -> jest, z currency.
    ...


@pytest.mark.django_db
def test_funded_by_to_referencja_a_as_osadza_funding(uczelnia, jednostka):
    # Project/Funded/By  -> referencja do OrgUnit-a findera
    # Project/Funded/As  -> osadzony pełny <Funding>
    ...


@pytest.mark.django_db
def test_projekt_bez_finansowania_serializuje_sie(uczelnia, jednostka):
    # Funded ma minOccurs="0" — brak finansowania jest poprawny.
    ...


@pytest.mark.django_db
def test_team_znika_przy_wylaczonym_eksporcie_osob(uczelnia, jednostka):
    # eksport_cerif_osoby=False -> brak PrincipalInvestigator i Member,
    # bo osoby nie ma w secie i referencja byłaby wisząca.
    ...
```

Uzupełnij `...` faktycznym budowaniem obiektów i wołaniem serializera — wzorem istniejących testów eksportu w tym katalogu. Testy mają być kompletne, nie szkicowe.

- [ ] **Step 2: Uruchom testy, potwierdź czerwone**

Run: `uv run pytest src/cerif_export/tests/test_eksport_projektow.py -v`
Expected: FAIL — brak modułów `cerif.project` / `cerif.funding`.

- [ ] **Step 3: Napisz `cerif/funding.py`**

Builder musi być wywoływalny w **dwóch kontekstach**: jako samodzielny rekord setu `openaire_cris_funding` i jako element osadzony w `Project/Funded/As`. Zrób jedną funkcję `serializuj(finansowanie, ctx)` zwracającą element `<Funding>` — osadzenie polega na doczepieniu tego samego elementu w innym miejscu drzewa.

Kolejność elementów z XSD. `Amount` z atrybutem `currency` tylko gdy `ctx` niesie zgodę na kwoty (przełącznik `Uczelnia.eksport_cerif_kwoty` — dołóż go do kontekstu tam, gdzie `kontekst.py` trzyma `eksport_cerif_osoby`). `GrantDOI` to dedykowany element z `includes/funding-identifiers.xsd`. `Funder` to referencja do OrgUnit-a — przez `ctx.id_dla(...)`, nigdy przez zapytanie do bazy.

- [ ] **Step 4: Napisz `cerif/project.py`**

Kolejność z XSD: `Type`, `Acronym`, `Title`, `Identifier`, `StartDate`, `EndDate`, `Consortium` (→ `Coordinator` = OrgUnit jednostki), `Team` (→ `PrincipalInvestigator` dla roli kierownik, `Member` dla pozostałych), `Funded` (→ `By` = referencja do OrgUnit-a findera, `As` = osadzone `<Funding>`), `Subject`, `Keyword`, `Abstract`, `Status`.

`Status` i `Subject` wymagają atrybutu `scheme` — użyj `const.SCHEMAT_STATUSU_PROJEKTU` i `const.SCHEMAT_DYSCYPLIN` z Taska 4, a wartość zbuduj jako URI (schemat + `/` + kod).

`Team` emituj **tylko wtedy**, gdy osoby są widoczne (`ctx.id_dla` dla autora zwraca identyfikator) — inaczej powstanie referencja do rekordu nieobecnego w harveście.

- [ ] **Step 5: Napisz providery**

`providers/projekty.py` i `providers/finansowanie.py` wzorem `providers/konferencje.py`:

```python
class ProviderProjektow(ProviderEncji):
    set_spec = const.SET_PROJECTS
    typ_cerif = const.TYP_PROJECT
    modele = [Projekt]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Projekt:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return (
            Projekt.objects.filter(jednostka__uczelnia=uczelnia)
            .select_related("jednostka")
            .prefetch_related(
                "projekt_autor_set__autor",
                "finansowanie_set__instytucja",
                "dyscypliny",
                "slowa_kluczowe",
            )
        )
```

Nazwy odwrotnych relacji zweryfikuj — jeśli test wywali się na `AttributeError`, sprawdź faktyczne `related_name`. `zbiory_widocznosci()` musi prekomputować widoczność autorów, jednostki i instytucji finansujących — inaczej serializer nie miałby czym rozstrzygać referencji bez chodzenia do bazy.

- [ ] **Step 6: Posprzątaj `puste.py`**

Usuń `ProviderProjektow` i `ProviderFinansowania`; zostają `ProviderProduktow` i `ProviderAparatury`. **Popraw docstring modułu** — dziś twierdzi, że BPP „nie prowadzi ewidencji produktów badawczych, aparatury, projektów ani finansowania". Po tej zmianie zdanie musi wymieniać tylko produkty i aparaturę.

Zaktualizuj miejsce rejestracji providerów, żeby wskazywało na nowe klasy.

- [ ] **Step 7: Uruchom testy**

Run: `uv run pytest src/cerif_export/tests/test_eksport_projektow.py -v`
Expected: PASS.

- [ ] **Step 8: Pełny przebieg testów eksportu**

Run: `uv run pytest src/cerif_export/ -q`
Expected: PASS. Testy walidujące wobec XSD wyłapią złą kolejność elementów — jeśli coś pada na `xs:sequence`, popraw kolejność w builderze, nie test.

- [ ] **Step 9: Lint i commit**

```bash
ruff format src/cerif_export/
ruff check src/cerif_export/
git add src/cerif_export/
git commit -m "feat(cerif): eksport setów openaire_cris_projects i openaire_cris_funding (#701, #702)"
```

---

### Task 6: `OriginatesFrom` — łańcuch publikacja ↔ projekt ↔ finansowanie

**Wymaga:** Task 5.

To jest ogniwo, dla którego całe przedsięwzięcie ma sens. Pełne sety
`openaire_cris_projects` i `openaire_cris_funding` bez tego elementu dają
agregatorowi dwie rozłączne listy: osobno publikacje, osobno projekty.
Walidator przejdzie, wartość merytoryczna będzie zerowa.

**Files:**
- Modify: `src/cerif_export/cerif/publication.py`, `src/cerif_export/cerif/patent.py`, `src/cerif_export/providers/publikacje.py`, `src/cerif_export/providers/patenty.py`
- Create: `src/cerif_export/tests/test_originates_from.py`

**Interfaces:**
- Consumes: `cerif.project.serializuj` z Taska 5, `Grant_Rekordu` (generyczna relacja publikacja↔grant), `Grant.projekt` z Taska 1.

- [ ] **Step 1: Przeczytaj definicję elementu w XSD**

Run: `sed -n '695,715p' src/cerif_export/tests/xsd/openaire-cerif-profile.xsd`

Zwróć uwagę: `OriginatesFrom` **osadza** element z grupy podstawień
`ProjectFunding__SubstitutionGroupHead` (czyli pełne `<Project>` albo
`<Funding>`), a nie samą referencję. `maxOccurs="unbounded"`,
`minOccurs="0"` — publikacja bez projektu jest poprawna.

- [ ] **Step 2: Napisz test (czerwony)**

Utwórz `src/cerif_export/tests/test_originates_from.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Grant, Grant_Rekordu, Projekt


@pytest.mark.django_db
def test_publikacja_z_grantem_bez_projektu_nie_ma_originates_from(
    uczelnia, jednostka, wydawnictwo_ciagle
):
    grant = baker.make(Grant, numer_projektu="BEZ/PROJEKTU", projekt=None)
    Grant_Rekordu.objects.create(rekord=wydawnictwo_ciagle, grant=grant)
    # ... zbuduj kontekst i zserializuj publikację jak w istniejących testach
    assert el.find("OriginatesFrom") is None


@pytest.mark.django_db
def test_publikacja_z_projektem_osadza_project(
    uczelnia, jednostka, wydawnictwo_ciagle
):
    projekt = baker.make(Projekt, jednostka=jednostka, tytul="Badany projekt")
    grant = baker.make(Grant, numer_projektu="Z/PROJEKTEM", projekt=projekt)
    Grant_Rekordu.objects.create(rekord=wydawnictwo_ciagle, grant=grant)
    # ...
    osadzony = el.find("OriginatesFrom")
    assert osadzony is not None
    assert osadzony.find("Project") is not None


@pytest.mark.django_db
def test_ta_sama_zasada_dla_patentu(uczelnia, jednostka, patent):
    # Patent/OriginatesFrom (XSD linia 871) ma identyczną strukturę.
    ...
```

Uzupełnij `...` wzorem istniejących testów eksportu publikacji — testy
mają być kompletne, nie szkicowe.

- [ ] **Step 3: Uruchom testy, potwierdź czerwone**

Run: `uv run pytest src/cerif_export/tests/test_originates_from.py -v`
Expected: FAIL — brak elementu `OriginatesFrom`.

- [ ] **Step 4: Wciągnij granty do providerów publikacji i patentów**

W `providers/publikacje.py` i `providers/patenty.py` dołóż prefetch
generycznej relacji `Grant_Rekordu` wraz z `grant__projekt` (i tym, czego
`cerif.project.serializuj` potrzebuje: `grant__projekt__jednostka`,
`grant__projekt__finansowanie_set__instytucja`).

`Grant_Rekordu` jest `GenericForeignKey`, więc prefetch idzie od strony
publikacji przez `GenericRelation` — jeśli modele publikacji jej nie mają,
dodaj `GenericRelation(Grant_Rekordu)` do miksina publikacji w `bpp`
(to zmiana bez migracji — `GenericRelation` nie tworzy kolumny).

`zbiory_widocznosci()` musi objąć projekty i instytucje finansujące, bo
serializer nie wolno mu chodzić do bazy.

- [ ] **Step 5: Dodaj `OriginatesFrom` do builderów**

W `cerif/publication.py` i `cerif/patent.py`, w miejscu wymuszonym przez
`xs:sequence` (sprawdź w XSD, gdzie dokładnie `OriginatesFrom` wypada
w kolejności), dla każdego grantu publikacji mającego przypisany projekt:

```python
    for projekt in projekty_publikacji:
        pochodzenie = dodaj_element(el, "OriginatesFrom")
        pochodzenie.append(cerif_project.serializuj(projekt, ctx))
```

Nazwy helperów dobierz do tych, których faktycznie używa dany plik
(`element`, `dodaj` z `cerif/wspolne.py`). Deduplikuj projekty — dwa granty
tego samego projektu przypięte do jednej publikacji nie mogą dać dwóch
identycznych `OriginatesFrom`.

- [ ] **Step 6: Uruchom testy**

Run: `uv run pytest src/cerif_export/tests/test_originates_from.py -v`
Expected: PASS.

- [ ] **Step 7: Regresja całego eksportu + kontrola zapytań**

Run: `uv run pytest src/cerif_export/ -q`
Expected: PASS. Osadzanie projektu w każdej publikacji to naturalny
kandydat na N+1 — jeśli w katalogu są testy liczące zapytania
(`django_assert_num_queries`), upewnij się, że nadal przechodzą; jeśli
liczba zapytań rośnie z liczbą publikacji na stronie, brakuje prefetcha
z Stepu 4.

- [ ] **Step 8: Lint i commit**

```bash
ruff format src/cerif_export/ src/bpp/
ruff check src/cerif_export/ src/bpp/
git add src/cerif_export/ src/bpp/
git commit -m "feat(cerif): OriginatesFrom — powiązanie publikacji i patentów z projektami (#701)"
```

---

### Task 7: Integralność referencyjna, domknięcie

**Wymaga:** Tasków 2, 3, 5, 6.

**Files:**
- Create: `src/cerif_export/tests/test_integralnosc_projektow.py`
- Create: `src/bpp/newsfragments/701.feature.rst`, `src/bpp/newsfragments/702.feature.rst`
- Modify: `docs/deweloper/eurocris-co-jeszcze.md`

- [ ] **Step 1: Napisz test integralności referencyjnej**

To najważniejszy test tej zmiany — klasa błędu, która inaczej wychodzi dopiero na żywym endpoincie pod walidatorem OpenAIRE.

Utwórz `src/cerif_export/tests/test_integralnosc_projektow.py`: zbuduj uczelnię z jednostką, projektem, zespołem (kierownik + wykonawca), finansowaniem, instytucją finansującą oraz publikacją przypiętą do projektu przez `Grant_Rekordu`, po czym zharvestuj **wszystkie** sety i sprawdź, że każdy identyfikator referowany z `<Project>`, `<Funding>` i z osadzonego `Publication/OriginatesFrom` (Coordinator, PrincipalInvestigator, Member, Funded/By, Funder) występuje jako `@id` rekordu w odpowiednim secie.

Test musi przejść w **obu** stanach `Uczelnia.eksport_cerif_osoby` — przy `False` referencje do osób mają zniknąć, a nie zawisnąć.

- [ ] **Step 2: Uruchom test**

Run: `uv run pytest src/cerif_export/tests/test_integralnosc_projektow.py -v`
Expected: PASS. Jeśli FAIL — to prawdziwy błąd w builderach z Taska 5, nie w teście.

- [ ] **Step 3: Napisz newsfragmenty**

`src/bpp/newsfragments/701.feature.rst`:

```rst
Nowa encja "projekt badawczy" wraz z zespołem projektu. Numery grantów
można teraz przypiąć do projektu, a projekty wychodzą w eksporcie
CERIF-XML w zestawie ``openaire_cris_projects``.
```

`src/bpp/newsfragments/702.feature.rst`:

```rst
Nowa encja "finansowanie" wraz ze słownikiem instytucji finansujących
(z identyfikatorami ROR i Crossref Funder ID). Finansowanie projektów
wychodzi w eksporcie CERIF-XML w zestawie ``openaire_cris_funding``.
Kwoty są eksportowane wyłącznie po włączeniu opcji w ustawieniach uczelni.
```

- [ ] **Step 4: Zaktualizuj dokument euroCRIS**

W `docs/deweloper/eurocris-co-jeszcze.md` sekcje A1 i A2 opisują Project i Funding jako niezrobione. Przepisz je na stan faktyczny: co zostało zaimplementowane, co świadomie pominięto (partnerzy zewnętrzni, front, API) i że `Status`/`Subject` używają własnych schematów klasyfikacji.

- [ ] **Step 5: Pełny przebieg testów bez Playwrighta**

Run: `make tests-without-playwright`
Expected: PASS. To trwa kilka minut — nie przerywaj.

- [ ] **Step 6: Commit**

```bash
git add src/cerif_export/tests/ src/bpp/newsfragments/ docs/
git commit -m "test(cerif): integralność referencyjna projektów i finansowania (#701, #702)"
```

- [ ] **Step 7: Krok akceptacyjny (poza CI, do wykonania przez człowieka)**

Uruchom `openaire-cris-validator` 2.1.1 na żywym endpoincie z dumpem produkcyjnym, jak przy #699. Automatyczne testy sprawdzają zgodność ze schematem i integralność wewnątrz jednego harvestu; walidator sprawdza całość protokołu.

---

## Po wykonaniu wszystkich zadań

- `make baseline-update` — **raz**, przy scalaniu gałęzi (nie wcześniej).
- Commit obu plików: `baseline-sql/baseline.sql` i `baseline-sql/baseline.meta.json`.
