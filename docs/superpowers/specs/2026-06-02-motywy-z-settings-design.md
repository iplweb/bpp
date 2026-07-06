# Motywy front-endu: jedno źródło prawdy w `settings`, admin czyta z niego

Data: 2026-06-02
Gałąź: `feature/multi-hosted-config` (PR #189)

## Problem

Lista dostępnych motywów kolorystycznych front-endu jest dziś powtórzona
ręcznie w kilku źródłach prawdy i musi być trzymana w synchronie palcami:

1. `Gruntfile.js` — targety `sass:*` + `concurrent.themes.tasks` (build CSS),
2. `settings/base.py` → `COMPRESS_OFFLINE_CONTEXT` — lista ścieżek CSS,
3. `models/uczelnia.py` → `THEME_CHOICES` — `choices` pola `theme_name`
   (gatuje dropdown w adminie; każda zmiana = nowa migracja).

Skutek: dziś istniały zbudowane motywy (`app-vizja`, `app-mwsl`, `app-uafm`),
których nie dało się wybrać w adminie, bo brakowało ich w `THEME_CHOICES`.

## Zakres tego kroku ("na początek")

Zredukować punkty 2 i 3 do **jednej** listy w `settings`, z której korzysta
admin. **Gruntfile zostaje ręczny** (świadoma decyzja użytkownika). Auto-detekcja
motywów z dysku (glob po `.scss`) to ewentualny osobny krok 2, NIE tutaj.

## Projekt

### 1. Kanoniczna lista w `settings/base.py`

```python
BPP_THEMES = [
    ("app-green", "Zielony"),
    ("app-blue", "Niebieski"),
    ("app-orange", "Pomarańczowy"),
    ("app-vizja", "Bursztynowo-granatowy (VIZJA)"),
    ("app-mwsl", "Pomarańczowo-granatowy (MWSL)"),
    ("app-uafm", "Czerwono-błękitny (UAFM)"),
]
```

Jedyne miejsce, gdzie żyje lista motywów (wartość = nazwa pliku SCSS bez
rozszerzenia + etykieta = schemat kolorystyczny, a po nim nazwa własna
uczelni w nawiasie).

### 2. `COMPRESS_OFFLINE_CONTEXT` wyliczany z `BPP_THEMES`

```python
COMPRESS_OFFLINE_CONTEXT = [
    {"THEME_NAME": f"scss/{value}.css", "STATIC_URL": STATIC_URL, "LANGUAGE_CODE": "pl"}
    for value, _label in BPP_THEMES
]
```

Likwiduje drugą, równoległą listę.

### 3. Model: zdjęcie `choices=`

`Uczelnia.theme_name` → zwykły `CharField` (zostaje `default="app-green"`,
`max_length=50`, `verbose_name`). Usunięcie martwej stałej `THEME_CHOICES`.
Walidacja wartości przenosi się z modelu do formularza admina, dzięki czemu
zmiana listy motywów **nie wymaga już migracji**.

Migracja `0422_*` (`AlterField` zdejmujący `choices`) — ostatnia migracja
motywów. No-op na poziomie kolumny DB. Append do historii (reguła: nie ruszamy
istniejącej `0421`, która jest już wypchnięta na remote).

### 4. Admin: `theme_name` jako `ChoiceField` z settings

Nowy `UczelniaAdminForm(forms.ModelForm)`:
- pole `theme_name = forms.ChoiceField(...)` (bo model nie daje już `choices`,
  domyślny widget byłby `TextInput`),
- `choices` ustawiane w `__init__` z `settings.BPP_THEMES`.

`UczelniaAdmin.form = UczelniaAdminForm`.

## Komponenty i granice

- `settings.BPP_THEMES` — dane (jedno źródło prawdy).
- `COMPRESS_OFFLINE_CONTEXT` — pochodna danych (czysta transformacja).
- `UczelniaAdminForm` — adapter danych → widżet UI + walidacja wyboru.
- Model — przechowuje surowy string, nie zna już dozwolonej listy.

## Obsługa błędów / brzegi

- Wartość spoza listy zapisana w bazie (np. po usunięciu motywu z settings):
  context processor i tak skleja ścieżkę `scss/<wartość>.css`; jeśli plik nie
  istnieje, `{% static %}` zwróci 404 na arkuszu — degradacja kosmetyczna, nie
  wywrotka. Admin przy edycji takiej uczelni pokaże wybór z aktualnej listy
  (stara wartość nie będzie zaznaczona) — akceptowalne dla tego kroku.

## Test (pytest)

1. `Uczelnia._meta.get_field("theme_name").choices is None` — model bez choices.
2. `UczelniaAdminForm().fields["theme_name"].choices == settings.BPP_THEMES`.
3. `len(COMPRESS_OFFLINE_CONTEXT) == len(BPP_THEMES)` i zbiór `THEME_NAME`
   pokrywa się z `scss/<value>.css` dla każdego motywu.

## Poza zakresem

- Auto-detekcja motywów z dysku (glob `.scss`).
- Zmiany w `Gruntfile.js`.
- `--admin-hover-bg` (zostaje jak jest).
