# Dane demo (`create_demo_data`)

Generator syntetycznych danych demo z wymiennymi motywami.

## Szybki start

```bash
uv run python src/manage.py create_demo_data \
    --motyw wiedzmin \
    --autorow 200 --ile-ciaglych 1000 --ile-zwartych 500 \
    --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

## Motywy (`--motyw`)

- `realistyczny` (domyślny) — polskie dane akademickie
- `lem` — Stanisław Lem
- `wiedzmin` — Wiedźmin
- `harry-potter` — Harry Potter
- `disney` — Disney

## Wybrane flagi

- `--bez-prefiksu` — pełny realizm (bez markera „Demo —")
- `--procent-ze-streszczeniem 70` — odsetek prac ze streszczeniem
- `--od-roku 2020 --do-roku 2026` — zakres lat prac
- `--seed 123` — deterministyczny wynik

## Sprzątanie

Manifest zapisany przy tworzeniu (np. `demo_data_manifest_*.json`):

```bash
uv run python src/manage.py cleanup_demo_data \
    --manifest <plik.json> --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

> Cleanup usuwa wyłącznie obiekty z manifestu (po PK) — bezpieczny dla
> istniejących danych. Po `create_demo_data` uruchom `denorm_flush`, by
> wypełnić cache opisów bibliograficznych.
