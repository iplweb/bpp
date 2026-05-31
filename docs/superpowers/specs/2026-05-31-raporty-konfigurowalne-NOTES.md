# Konfigurowalna lista raportów — NOTATKI (jeszcze nie zaprojektowane)

Data: 2026-05-31
Status: **surowe wymagania, do osobnego brainstormingu** — NIE zaczynać
implementacji przed designem.

To temat 2, świadomie odłożony do osobnego cyklu po dowiezieniu tematu 1
(przyjazny komunikat przy braku definicji raportu).

## Cel

Zachować obecną listę raportów (raport autorów, jednostek, uczelni, wydziałów),
ale **uczynić ją konfigurowalną** — żeby dało się dodawać/edytować pozycje
(tytuł, slug, itp.) bez zmian w kodzie.

## Wymagania zebrane od użytkownika

1. **Konfigurowalna lista raportów.** Wpisujemy tytuł raportu, slug, itp.
   Dziś jest 4 zahardkodowane warianty: każdy ma własny `*FormView`,
   `*FormForm`, mixin autoryzacji, URL pattern i `report_slug` w
   `src/nowe_raporty/views.py`. Docelowo lista ma być danymi, nie kodem.

2. **Dynamiczne, cache'owane menu.** Menu w `top_bar.html` jest budowane
   dynamicznie i **cache'owane**; ma się przebudowywać przy edycji listy
   raportów (inwalidacja cache na zapis konfiguracji raportu).

3. **Przeprojektowanie uprawnień pod multi-tenant.** Dziś część logiki widoczności
   siedzi na obiekcie `Uczelnia` jako flagi `pokazuj_raport_*`
   (`pokazuj_raport_autorow`, `pokazuj_raport_jednostek`, `pokazuj_raport_uczelni`,
   `pokazuj_raport_wydzialow`) + `OpcjaWyswietlaniaField`
   (POKAZUJ_ZAWSZE / POKAZUJ_NIGDY / POKAZUJ_ZALOGOWANYM / POKAZUJ_GDY_W_ZESPOLE)
   oraz grupa `GR_RAPORTY_WYSWIETLANIE`. To, że uprawnienia są na uczelni, jest
   OK jako kierunek, ale:
   - Plan: **kilka uczelni na jednej instalacji** (multi-tenant).
   - Trzeba rozsądnie ubrać przypadki:
     - jeden raport widoczny **tylko na jednej uczelni**,
     - jeden raport widoczny **na wszystkich uczelniach DLA ZALOGOWANYCH**,
     - i analogiczne kombinacje (per-uczelnia × poziom dostępu).

## Obszary kodu do przejrzenia przy brainstormingu

- `src/nowe_raporty/views.py` — 4 zahardkodowane view/form/mixin + `report_slug`.
- `src/nowe_raporty/urls.py` — URL patterns per raport.
- `src/nowe_raporty/forms.py` — formularze per raport.
- `src/bpp/views/mixins.py` — `UczelniaSettingRequiredMixin`
  (`OpcjaWyswietlaniaField`, `group_required`).
- `Uczelnia.pokazuj_raport_*` — flagi widoczności na modelu uczelni.
- `top_bar.html` — dynamiczne, cache'owane menu raportów (znaleźć mechanizm
  cache + punkt inwalidacji).
- `flexible_reports.Report` — istniejący model definicji raportu (slug, title,
  elementy). Pytanie projektowe: czy konfiguracja BPP-owa (widoczność, powiązanie
  z typem obiektu autor/jednostka/wydział/uczelnia, uprawnienia per-uczelnia)
  ma być nowym modelem BPP wskazującym na `Report`, czy rozszerzeniem `Report`.

## Otwarte pytania projektowe (na brainstorming)

- Model danych: nowy `KonfiguracjaRaportu`/`PozycjaMenuRaportu` (BPP) ↔ FK do
  `flexible_reports.Report`? Jak powiązać z typem obiektu bazowego
  (autor/jednostka/wydział/uczelnia) i `get_base_queryset`?
- Jak generycznie zastąpić 4 zahardkodowane `get_base_queryset` /
  `form_valid` (różne sygnatury URL — uczelnia nie ma `obiekt.pk` w URL)?
- Multi-tenant: czy widoczność to M2M `Raport`↔`Uczelnia` z poziomem dostępu na
  relacji, czy osobny model reguł? Jak to wpina się w obecny
  `get_for_request(request)` / rozpoznawanie uczelni.
- Cache menu: gdzie żyje, czym keyowany (per-uczelnia? per-user-auth?), gdzie
  inwalidować.
- Migracja danych: zachować istniejące 4 raporty i ich obecne flagi
  `pokazuj_raport_*` → nowy model (data migration).

## Powiązanie z tematem 1

Temat 1 dorzuca przyjazny komunikat „raport nieskonfigurowany". Gdy temat 2
uczyni listę w pełni konfigurowalną, partial `_brak_definicji_raportu.html`
i tak zostaje użyteczny (pozycja menu istnieje, ale `Report` jeszcze nie
wypełniony). Latentny bug 500 w eksporcie najlepiej domknąć w temacie 2.
