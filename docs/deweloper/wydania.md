# Wydania (staging-release → promote)

Wydanie jest dwufazowe i sterowane z CLI (`gh`). Build raz, promocja przepina
metadane tagu — produkcja dostaje DOKŁADNIE obraz przetestowany na stagingu.

## Wymóg jednorazowy: staging pulluje `:staging`

Serwer staging musi ciągnąć tag `:staging` (NIE `:latest`) wszystkich 6 obrazów:
`bpp_base`, `bpp_appserver`, `bpp_workerserver`, `bpp_beatserver`,
`bpp_authserver`, `bpp_denorm_queue`. Produkcja zostaje na `:latest`.

## Cykl

```bash
# 1) Utnij kandydata → buduje obrazy, przesuwa :staging
gh workflow run release-candidate.yml --ref dev

# … staging pulluje :staging, testujesz …

# 2a) OK → promuj (finalizacja + :latest, bez rebuildu)
gh workflow run promote.yml

# 2b) „kupa" → fix na dev, ponów cut-RC (kolejny -rcN, numer finalny niespalony)
gh workflow run release-candidate.yml --ref dev
```

Podgląd: `gh run watch $(gh run list --workflow=promote.yml -L1 --json databaseId --jq '.[0].databaseId')`.

## Dowód build-once-promote

Po promote `:latest` ma ten sam digest co przetestowany RC:

```bash
docker buildx imagetools inspect iplweb/bpp_appserver:latest
docker buildx imagetools inspect iplweb/bpp_appserver:202606.1392rc1   # ten sam digest
```

## Uwagi

- Gałąź `release/v<BASE>` żyje od cut-RC do promote (stan numeru RC); promote ją kasuje.
- `push:master` NIE przebudowuje już obrazów — każda zmiana prod idzie przez promote.
- Awaryjny build ad-hoc: `gh workflow run build-docker-images.yml --ref <branch>`.
