# Vendorowane schematy XSD profilu OpenAIRE CERIF 1.2

Testy serializerów (`src/cerif_export/tests/test_serializery.py`) walidują
wygenerowany XML względem schematów profilu. Schematy są **vendorowane**,
żeby testy działały offline i deterministycznie — `lxml` dostaje resolver
odcinający ruch sieciowy (patrz `zbuduj_schemat()` w pliku testów).

## Skąd pochodzą

| | |
|---|---|
| Repozytorium | <https://github.com/openaire/guidelines-cris-managers> |
| Tag | `v1.2.0` |
| Commit | `cb96b925159655adfd97fb11c4a93f3d20c8cbef` |
| Katalog źródłowy | `schemas/` |
| Pobrano | 2026-08-03 |
| Licencja | CC BY 4.0 (patrz nagłówek `openaire-cerif-profile.xsd`) |

Polecenie odtwarzające pobranie:

```bash
curl -sSL \
  https://codeload.github.com/openaire/guidelines-cris-managers/tar.gz/refs/tags/v1.2.0 \
  | tar xz
# skopiuj guidelines-cris-managers-1.2.0/schemas/{openaire-cerif-profile.xsd,
#   includes/*.xsd, vocabularies/*.xsd, cached/xml.xsd} tutaj
```

**Uwaga:** spec projektu (`docs/superpowers/specs/2026-08-03-cerif-export-design.md`)
wskazywała jako źródło `EuroCRIS/openaire-cris-validator`. To repozytorium
vendoruje **profil 1.1** (`src/main/resources/schemas/cerif_profile_1_1/`) —
nie ma tam wersji 1.2. Kanonicznym wydawcą schematów profilu 1.2 jest
`openaire/guidelines-cris-managers` i stamtąd pochodzą pliki tutaj.
Walidator EuroCRIS pobiera schemat 1.2 z sieci
(`https://www.openaire.eu/schema/cris/1.2/openaire-cerif-profile.xsd`),
czego w testach jednostkowych nie chcemy.

## Co jest w komplecie

- `openaire-cerif-profile.xsd` — schemat główny (namespace
  `https://www.openaire.eu/cerif-profile/1.2/`),
- `includes/` — 8 plików wciąganych przez `xsd:include` (wspólne typy CERIF
  i grupy identyfikatorów per encja),
- `vocabularies/` — 8 słowników wciąganych przez `xsd:import` (typy COAR dla
  publikacji / patentów / produktów, COAR Access Rights, typy medium ISSN,
  typy finansowania i kompatybilności OpenAIRE),
- `cached/xml.xsd` — schemat namespace `xml:` (dla atrybutu `xml:lang`).

Katalog `vocabularies/00-preparations/` z repozytorium źródłowego **nie**
został skopiowany — to materiały robocze do generowania słowników, nie są
importowane przez żaden schemat.

## Jedyna referencja sieciowa

`includes/cerif-commons.xsd` importuje namespace `xml:` przez absolutny URL:

```xml
<xs:import namespace="http://www.w3.org/XML/1998/namespace"
           schemaLocation="http://www.w3.org/2001/xml.xsd"/>
```

Resolver w testach mapuje ten URL na lokalne `cached/xml.xsd`. Pozostałe
`schemaLocation` w komplecie są **względne**, więc rozwiązują się po ścieżkach
w tym katalogu. Resolver dodatkowo podnosi wyjątek przy każdej innej próbie
sięgnięcia po `http(s)://` — gdyby przyszła wersja profilu dołożyła zależność
sieciową, test padnie z czytelnym komunikatem zamiast po cichu zależeć od
internetu.

## Aktualizacja przy podbiciu wersji profilu

1. Pobierz nowy tag z repozytorium wyżej.
2. Podmień pliki, zaktualizuj tabelkę (tag + commit + data).
3. Zaktualizuj `NS_CERIF` i pozostałe namespace'y w `cerif_export/const.py`.
4. Uruchom `uv run pytest src/cerif_export/tests/test_serializery.py` —
   niezgodność kolejności elementów w sekwencjach XSD wyjdzie od razu.
