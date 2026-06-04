# Skracanie długiej listy autorów na stronie rekordu

Data: 2026-06-03
Branch/worktree: `worktree-skracanie-autorow` (`~/Programowanie/bpp-skracanie-autorow`)

## Problem

Strona rekordu (`/bpp/rekord/<slug>/`, szablon
`browse/praca_tabela_mono.html`) renderuje pełną listę autorów server-side,
zawsze i w całości. Dla prac wieloautorskich (badania kliniczne, setki
autorów) blok „AUT." zalewa górę strony i spycha resztę treści w dół.
Dodatkowo „opis bibliograficzny" bywa bardzo długi. „Nasi" autorzy
(pracownicy uczelni) giną w masie autorów obcych — a to oni są sensem BPP.

W szablonie jest już **martwy** przycisk „Pokaż wszystkich autorów"
(linie 48–54) i zaślepka JS (linie ~1035–1039: `// Implementation for
show more authors would go here`). Logiki nigdy nie dopisano.

## Cel

Gdy autorów jest dużo (> 25), domyślnie pokazuj **skrócony** widok i
odsłaniaj pełną listę na żądanie; przy tym od razu wyławiaj „naszych"
autorów. Skróć też wizualnie długi opis bibliograficzny.

## Zachowanie

### Lista autorów — widok skrócony (gdy liczba autorów > 25)

```
AUT.  Salek David, Belada David, Song Yuqin, Jurczak Wojciech (4.), Kahl Brad S.
      … Lech-Marańda Ewa (264.), Grosicki Sebastian (198.)   [Pokaż wszystkich (264)]
```

- **Pierwszych 5** autorów w kolejności bibliograficznej.
- `…`
- **Nasi autorzy spoza pierwszej piątki** — każdy z 1-based numerem
  pozycji w nawiasie, małym drukiem: `(264.)`.
- Nasi autorzy **podświetleni** także wśród pierwszych 5 (jeśli któryś
  tam wpada — nie dublujemy go po wielokropku).
- Przycisk **„Pokaż wszystkich (N)"** → rozwija pełną listę (w pełnej
  „Zwiń").
- Gdy autorów ≤ 25 → render jak dziś, bez guzika.
- Gdy brak naszych poza piątką → `pierwszych 5 … [Pokaż wszystkich (N)]`
  (bez sekcji naszych).

„Nasz" autor = wpis odpowiedzialności, którego
`jednostka.skupia_pracownikow == True` (niezależnie od `afiliuje`).
Pozycja = 1-based indeks na liście `autorzy_dla_opisu` (nie surowe pole
`kolejnosc`, które bywa zerowe/nieciągłe).

### Opis bibliograficzny

CSS `line-clamp` (np. 3 linie) + przycisk „rozwiń". JS pokazuje przycisk
**tylko gdy treść faktycznie się nie mieści** (`scrollHeight >
clientHeight`). String `opis_bibliograficzny_cache` nietknięty (używany
też w eksportach, wyszukiwarce, rekordach powiązanych). Kontrolka
„rozwiń" nie może wyzwalać istniejącego „kliknij aby skopiować" na
kontenerze opisu.

## Architektura (małe, izolowane jednostki)

### 1. Metoda modelu — `autorzy_dla_opisu_skrocony()`

Plik: `src/bpp/models/util.py`, klasa `ModelZOpisemBibliograficznym`
(obok istniejącej `autorzy_dla_opisu()`). Dziedziczą ją
Wydawnictwo_Ciagle / Wydawnictwo_Zwarte / Patent oraz (przez
Wydawnictwo_Zwarte_Baza) Praca_Doktorska / Praca_Habilitacyjna — te
ostatnie mają 1 (fałszywego) autora, więc `skrocony=False` i działają
jak dziś.

Stałe modułowe:
- `LICZBA_PIERWSZYCH_AUTOROW = 5`
- `PROG_SKRACANIA_AUTOROW = 25`

Metoda materializuje `self.autorzy_dla_opisu()` **raz** (dokłada
`select_related("jednostka")`, żeby uniknąć N+1), nadaje każdemu wpisowi
atrybuty `.pozycja` (1-based) i `.czy_nasz`
(`jednostka.skupia_pracownikow`), i zwraca słownik:

```python
{
    "skrocony": bool,         # liczba > PROG_SKRACANIA_AUTOROW
    "wszyscy": [...],         # pełna lista z .pozycja/.czy_nasz
    "pierwsi": wszyscy[:5],   # pierwszych N
    "nasi_dalej": [a for a in wszyscy[5:] if a.czy_nasz],
    "liczba": len(wszyscy),
}
```

Brak migracji, brak denorm — czysta metoda prezentacyjna.

### 2. Szablon `browse/praca_tabela_mono.html`

`{% with box=praca.autorzy_dla_opisu_skrocony %}` raz, potem:
- **pełną listę** renderuj z `box.wszyscy` (zamiast ponownie wołać
  `praca.autorzy_dla_opisu`) — jeden zestaw danych, podświetlenie
  naszych za darmo;
- gdy `box.skrocony`: dodatkowy blok skrócony (`pierwsi` + `…` +
  `nasi_dalej`) widoczny domyślnie, pełna lista `hidden`; przycisk
  „Pokaż wszystkich (N)"/„Zwiń";
- gdy nie `skrocony`: tylko pełna lista, bez guzika (jak dziś).

Oba bloki w DOM → kopiowanie / druk / SEO / czytniki widzą pełną listę.

### 3. JavaScript

Zastępuje martwą zaślepkę. Podpina istniejący `[data-toggle-authors]`:
przełącza skrócony⇄pełny (pokaż/ukryj, `aria-expanded`), bez AJAX-a.
Osobny handler dla „rozwiń" opisu bibliograficznego z pomiarem
przepełnienia i `stopPropagation`.

### 4. SCSS — `src/bpp/static/scss/praca_detail.scss`

- klasa „nasz autor" (pogrubienie + delikatny akcent kolorystyczny),
- styl `(poz.)` — mały, wyszarzony,
- widoczność skrócony/pełny + `@media print` (zawsze pełna lista),
- `line-clamp` + „rozwiń" dla opisu.

Po zmianie: `grunt build`.

## Testy (pytest, model_bakery, `@pytest.mark.django_db`)

Plik: `src/bpp/tests/test_models/test_autorzy_dla_opisu_skrocony.py`.

- 30 autorów, nasi na poz. 4 i 28 → `pierwsi` ma 5 (poz. 4 z
  `czy_nasz=True`), `nasi_dalej == [poz.28]`, `skrocony is True`,
  `liczba == 30`.
- 10 autorów → `skrocony is False`.
- Brak naszych → `nasi_dalej == []`.
- Nasz tylko wśród pierwszej piątki (poz. 3), > 25 łącznie →
  `nasi_dalej == []`, flaga w `pierwsi`.
- Pozycje są 1-based i ciągłe niezależnie od pola `kolejnosc`.

Fixtures: `wydawnictwo_ciagle`, `jednostka` (nasza,
`skupia_pracownikow=True`), `obca_jednostka`
(`skupia_pracownikow=False`); autorzy przez `baker.make(Autor)` +
`wydawnictwo_ciagle.dodaj_autora(...)`.

## Realizacja

Worktree poza repo: `~/Programowanie/bpp-skracanie-autorow`
(branch `worktree-skracanie-autorow`). Newsfragment towncrier
(`.feature`). Na końcu: `grunt build`, testy modelu, podgląd w
`run-site`.
