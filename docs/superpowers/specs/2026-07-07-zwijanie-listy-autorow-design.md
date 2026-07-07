# Konfigurowalne zwijanie długich list autorów + usunięcie podświetlenia „naszych"

Data: 2026-07-07
Gałąź: `feat/zwijanie-listy-autorow` (worktree `~/Programowanie/bpp-zwijanie-autorow`, baza `dev`)

## Kontekst / stan zastany

Zwijanie długiej listy autorów na stronie pojedynczego rekordu **już istnieje**
i jest zawsze włączone (hardcoded on):

- Próg `PROG_SKRACANIA_AUTOROW = 25` oraz `LICZBA_PIERWSZYCH_AUTOROW = 5` w
  `src/bpp/models/util.py`.
- Metoda `ModelZOpisemBibliograficznym.autorzy_dla_opisu_skrocony(self, uczelnia=None)`
  (`src/bpp/models/util.py`) buduje słownik z kluczem
  `"skrocony": len(wszyscy) > PROG_SKRACANIA_AUTOROW`.
- Template tag `autorzy_skrocony(praca, uczelnia=None)`
  (`src/bpp/templatetags/prace.py`), wołany jako
  `{% autorzy_skrocony praca uczelnia as box %}`.
- Render w `src/bpp/templates/browse/praca_tabela_mono.html` (NIE w
  `praca_tabela.html`); zwinięcie/rozwinięcie jest client-side (JS toggle na
  `[data-toggle-authors]`).

Podświetlenie „naszych" autorów pochodzi z klasy
`.praca-mono__author-name--nasz` w `src/bpp/static/scss/praca_detail.scss`
(~linia 1189): `font-weight:700` (pogrubienie) + `color:$primary-color`
(kolor akcentu) + `text-shadow` (glow). Klasę nakłada tag `{% autor_nazwa %}`
na podstawie flagi `czy_nasz` (liczonej w `autorzy_dla_opisu_skrocony`).

Ustawienia per-uczelnia to `BooleanField` na modelu `Uczelnia`
(`src/bpp/models/uczelnia.py`), wstrzykiwane do szablonów context processorem
jako `{{ uczelnia.<pole> }}`. Ustawienia per-user to pola prosto na modelu
`BppUser` (`src/bpp/models/profile.py`, np. `per_page`, `multiseek_format`).

## Cel

1. Uczynić zwijanie **konfigurowalnym per-uczelnia**, domyślnie **włączonym**,
   z help-textem zgodnym z aktualnym zachowaniem (próg 25).
2. Pozwolić **zalogowanemu użytkownikowi** nadpisać to indywidualnie na stronie
   własnego profilu (`profil/`).
3. Usunąć **efekt podświetlenia** z nazwisk „naszych" autorów, zostawiając
   **samo pogrubienie**.

Próg 25 pozostaje hardcoded — nie robimy go konfigurowalnym (YAGNI).

## Decyzje projektowe (zatwierdzone)

- Worktree z `dev`; przełącznik per-user na stronie **profilu zalogowanego
  użytkownika** (`profil/`, `ProfilUzytkownikaView`), nie na publicznej stronie
  autora (preferencja czytelnika, nie per-autor).
- Semantyka per-user: **trójstan** (dziedzicz z uczelni / zawsze / nigdy),
  zaimplementowany jako `IntegerField` z `IntegerChoices` (czytelniejsze
  etykiety niż `BooleanField(null=True)`, brak dwuznaczności null/False).
- Podświetlenie: usunąć **glow i kolor akcentu**, zostawić **tylko
  `font-weight:700`**.

## Projekt

### 1. Modele (app `bpp`, jedna migracja na oba pola)

`Uczelnia.zwijaj_dlugie_listy_autorow` (`src/bpp/models/uczelnia.py`):

```python
zwijaj_dlugie_listy_autorow = models.BooleanField(
    "Zwijaj długie listy autorów na stronie rekordu",
    default=True,
    help_text=(
        "Gdy lista autorów publikacji przekracza 25 nazwisk, domyślnie "
        "zwijaj ją na stronie rekordu (widoczni pierwsi autorzy oraz autorzy "
        "z naszej uczelni; resztę użytkownik rozwija przyciskiem). "
        "Ustawienie domyślne dla całej uczelni — zalogowany użytkownik może "
        "je nadpisać we własnym profilu."
    ),
)
```

→ dopisane do fieldsetu „Strona wizualna" w `UczelniaAdmin`
(`src/bpp/admin/uczelnia.py`).

`BppUser.zwijaj_dlugie_listy_autorow` (`src/bpp/models/profile.py`):

```python
class ZwijanieAutorow(models.IntegerChoices):
    DOMYSLNE = 0, "Jak ustawienie uczelni"
    ZAWSZE = 1, "Zawsze zwijaj"
    NIGDY = 2, "Nigdy nie zwijaj"

zwijaj_dlugie_listy_autorow = models.IntegerField(
    "Zwijanie długich list autorów",
    choices=ZwijanieAutorow.choices,
    default=ZwijanieAutorow.DOMYSLNE,
    help_text=(
        "Czy na stronie rekordu zwijać listy autorów dłuższe niż 25 nazwisk. "
        "„Jak ustawienie uczelni" stosuje domyślne ustawienie Twojej uczelni."
    ),
)
```

### 2. Rozstrzyganie efektywnej wartości

Helper obok progu w `src/bpp/models/util.py`:

```python
def czy_zwijac_liste_autorow(request, uczelnia):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        pref = user.zwijaj_dlugie_listy_autorow
        if pref == ZwijanieAutorow.ZAWSZE:
            return True
        if pref == ZwijanieAutorow.NIGDY:
            return False
        # DOMYSLNE → dziedziczymy z uczelni
    return bool(getattr(uczelnia, "zwijaj_dlugie_listy_autorow", True))
```

Kolejność: **user (jeśli zdecydował) → uczelnia → True (fallback)**. Anonim
zawsze dziedziczy z uczelni.

### 3. Wpięcie w istniejącą metodę (minimalna zmiana)

`autorzy_dla_opisu_skrocony(self, uczelnia=None, zwijaj=True)` — jedyna zmiana
w linii decydującej:

```python
"skrocony": zwijaj and len(wszyscy) > PROG_SKRACANIA_AUTOROW,
```

Gdy `zwijaj=False` → `skrocony=False` → szablon renderuje pełną listę bez
przycisku. `pierwsi`, `nasi_dalej`, `liczba` bez zmian.

Template tag `autorzy_skrocony` → `takes_context=True`, czyta `request` z
kontekstu, liczy `zwijaj` helperem i przekazuje do metody. **Call site w
`praca_tabela_mono.html` bez zmian.**

### 4. Profil zalogowanego użytkownika (`profil/`)

`ProfilUzytkownikaView` jest teraz read-only `TemplateView`. Najpierw sprawdzić,
jak edytowane jest istniejące `per_page` (czy istnieje user-settings form):
- jeśli tak → dołożyć pole do istniejącego formularza,
- jeśli nie → dodać mały `ModelForm` na to jedno pole z obsługą POST na tej
  stronie (bez nowych URL-i, jeśli się da).

### 5. Usunięcie podświetlenia „naszych"

`src/bpp/static/scss/praca_detail.scss` (~1189):

```scss
.praca-mono__author-name--nasz {
    font-weight: 700;   // zostaje SAMO pogrubienie
}
```

Usunąć `color: $primary-color` i `text-shadow` + zaktualizować komentarz nad
regułą. Potem `grunt build` regeneruje 6× `app-*.css` (nie edytować
zminifikowanych ręcznie). Klasa `--nasz` zostaje jako hook; Python/szablon bez
zmian.

### 6. Migracja + baseline

Jedna migracja w `bpp` (oba pola). `make baseline-update` **przy scalaniu**, nie
w branchu (reguła o równoległych branchach).

### 7. Testy (TDD)

- `autorzy_dla_opisu_skrocony`: `zwijaj=False` ⇒ `skrocony=False` mimo >25;
  `zwijaj=True` + >25 ⇒ `skrocony=True`; ≤25 ⇒ `skrocony=False`.
- `czy_zwijac_liste_autorow`: macierz anonim/zalogowany ×
  ZAWSZE/NIGDY/DOMYSLNE × uczelnia True/False.
- Rozszerzenie istniejącego
  `src/bpp/tests/test_models/test_autorzy_dla_opisu_skrocony.py`.

## Poza zakresem

- Konfigurowalność samego progu 25.
- Zmiany na publicznej stronie autora (`browse/autor.html`).
- Integracja z gałęzią `feature/profil-autora`.
