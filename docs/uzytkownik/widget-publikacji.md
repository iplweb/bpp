# Widget publikacji na stronie WWW

Widget pozwala wyświetlić listę najnowszych publikacji **autora** lub
**jednostki** (wydziału, katedry, zakładu — wraz z jej pod-jednostkami) na
dowolnej zewnętrznej stronie internetowej. Dane pobierane są na żywo z systemu
BPP — nie trzeba niczego kopiować ręcznie ani mieć konta w systemie.

Osadzenie sprowadza się do wklejenia **jednej linii** kodu:

```html
<script src="https://twoj-serwer-bpp/static/embed/bpp-publikacje.js"
        data-autor="Jan-Kowalski" async></script>
```

Skrypt sam pobierze publikacje i wyświetli je w miejscu wklejenia. Ponieważ kod
mieszka na serwerze BPP, wszelkie poprawki i ulepszenia widgetu docierają do
Twojej strony automatycznie — bez ponownego wklejania.

## Generator kodu

Wpisz swoje dane (autora po **slugu** z adresu profilu, np.
`Jan-Kowalski`, albo jednostkę po slugu), a generator zbuduje gotowy kod oraz
pokaże **podgląd na żywo**. Domyślnie wczytany jest przykład Uniwersytetu
Medycznego w Lublinie.

<div class="bpp-gen-wrap">
<form id="bpp-gen" onsubmit="return false;">
  <p>
    <label><input type="radio" name="g-typ-radio" value="autor" checked> Autor</label>
    &nbsp;&nbsp;
    <label><input type="radio" name="g-typ-radio" value="jednostka"> Jednostka</label>
    <input type="hidden" id="g-typ" value="autor">
  </p>
  <p>
    <label for="g-serwer"><strong>Serwer BPP</strong></label><br>
    <input type="text" id="g-serwer" value="https://bpp.umlub.pl" size="40">
  </p>
  <p>
    <label for="g-id"><strong>Slug (lub ID) autora / jednostki</strong></label><br>
    <input type="text" id="g-id" value="Kazimierz-Pasternak" size="40">
  </p>
  <p>
    <label for="g-limit">Liczba pozycji</label>
    <input type="number" id="g-limit" min="1" max="100" placeholder="25" style="width:6em">
    &nbsp;
    <label for="g-rok-od">Rok od</label>
    <input type="number" id="g-rok-od" placeholder="—" style="width:6em">
    &nbsp;
    <label for="g-rok-do">Rok do</label>
    <input type="number" id="g-rok-do" placeholder="—" style="width:6em">
  </p>
  <p>
    <label for="g-styl">Styl</label>
    <select id="g-styl">
      <option value="lista">lista</option>
      <option value="tabela">tabela</option>
    </select>
    &nbsp;&nbsp;
    <label><input type="checkbox" id="g-nocss"> bez domyślnych stylów (data-no-css)</label>
  </p>
</form>

<p><strong>Kod do wklejenia:</strong></p>
<pre><code id="g-snippet"></code></pre>
<p><button type="button" id="g-copy">Kopiuj kod</button></p>

<p><strong>Podgląd na żywo:</strong></p>
<div id="bpp-podglad" style="border:1px solid rgba(0,0,0,.15); padding:1em; border-radius:6px;"></div>
</div>

<script>
(function () {
  function init() {
    var form = document.getElementById("bpp-gen");
    if (!form || form.dataset.bound) { return; }
    form.dataset.bound = "1";

    var $ = function (id) { return document.getElementById(id); };

    var qs = new URLSearchParams(window.location.search);
    if (qs.get("serwer")) { $("g-serwer").value = qs.get("serwer"); }
    if (qs.get("autor")) {
      setTyp("autor");
      $("g-id").value = qs.get("autor");
    } else if (qs.get("jednostka")) {
      setTyp("jednostka");
      $("g-id").value = qs.get("jednostka");
    }

    function setTyp(typ) {
      $("g-typ").value = typ;
      var radios = form.querySelectorAll('input[name="g-typ-radio"]');
      radios.forEach(function (r) { r.checked = r.value === typ; });
    }

    function serwer() {
      return ($("g-serwer").value || "https://bpp.umlub.pl").replace(/\/+$/, "");
    }

    function buildSnippet() {
      var typ = $("g-typ").value;
      var id = ($("g-id").value || "").trim();
      var a = ['data-' + typ + '="' + id + '"'];
      if ($("g-limit").value) { a.push('data-limit="' + $("g-limit").value + '"'); }
      if ($("g-rok-od").value) { a.push('data-rok-od="' + $("g-rok-od").value + '"'); }
      if ($("g-rok-do").value) { a.push('data-rok-do="' + $("g-rok-do").value + '"'); }
      if ($("g-styl").value && $("g-styl").value !== "lista") {
        a.push('data-styl="' + $("g-styl").value + '"');
      }
      if ($("g-nocss").checked) { a.push("data-no-css"); }
      var src = serwer() + "/static/embed/bpp-publikacje.js";
      $("g-snippet").textContent =
        '<script src="' + src + '"\n        ' + a.join(" ") + " async><\/script>";
    }

    function renderPreview() {
      var prev = document.getElementById("bpp-preview-script");
      if (prev) { prev.remove(); }
      $("bpp-podglad").innerHTML = "";
      var typ = $("g-typ").value;
      var id = ($("g-id").value || "").trim();
      if (!id) { return; }
      var s = document.createElement("script");
      s.id = "bpp-preview-script";
      s.src = serwer() + "/static/embed/bpp-publikacje.js";
      s.setAttribute("data-" + typ, id);
      s.setAttribute("data-serwer", serwer());
      s.setAttribute("data-target", "#bpp-podglad");
      if ($("g-limit").value) { s.setAttribute("data-limit", $("g-limit").value); }
      if ($("g-rok-od").value) { s.setAttribute("data-rok-od", $("g-rok-od").value); }
      if ($("g-rok-do").value) { s.setAttribute("data-rok-do", $("g-rok-do").value); }
      if ($("g-styl").value) { s.setAttribute("data-styl", $("g-styl").value); }
      if ($("g-nocss").checked) { s.setAttribute("data-no-css", ""); }
      document.body.appendChild(s);
    }

    var t;
    function onChange() {
      buildSnippet();
      clearTimeout(t);
      t = setTimeout(renderPreview, 600);
    }

    form.querySelectorAll('input[name="g-typ-radio"]').forEach(function (r) {
      r.addEventListener("change", function () { setTyp(r.value); onChange(); });
    });
    form.addEventListener("input", onChange);
    form.addEventListener("change", onChange);
    $("g-copy").addEventListener("click", function () {
      navigator.clipboard.writeText($("g-snippet").textContent).then(function () {
        $("g-copy").textContent = "Skopiowano!";
        setTimeout(function () { $("g-copy").textContent = "Kopiuj kod"; }, 1500);
      });
    });

    buildSnippet();
    renderPreview();
  }

  // MkDocs Material z navigation.instant nie odpala ponownie <script> w treści
  // przy nawigacji SPA-like — podpinamy się pod obserwowalne document$.
  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(init);
  } else if (document.readyState !== "loading") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
</script>

!!! note "Podgląd zależy od zewnętrznej instancji"
    Live podgląd ładuje widget z podanego serwera BPP. Działa, gdy instancja
    jest dostępna przez **HTTPS** i ma wdrożoną tę wersję BPP (z plikiem
    `static/embed/bpp-publikacje.js`). Dokumentacja jest serwowana po HTTPS, więc
    serwer BPP również musi być po HTTPS (inaczej przeglądarka zablokuje
    *mixed-content*).

## Parametry (`data-*`)

| Atrybut | Znaczenie | Domyślnie |
| --- | --- | --- |
| `data-autor` | slug lub ID autora | — (wymagane jest `data-autor` **albo** `data-jednostka`) |
| `data-jednostka` | slug lub ID jednostki (z pod-jednostkami) | — |
| `data-serwer` | adres serwera BPP (gdy inny niż origin skryptu) | origin z `src` |
| `data-limit` | liczba pozycji (1–100) | 25 |
| `data-rok-od` | pokaż publikacje od roku | brak filtra |
| `data-rok-do` | pokaż publikacje do roku | brak filtra |
| `data-styl` | `lista` lub `tabela` | `lista` |
| `data-no-css` | gdy obecny — pomiń domyślne style (pełna customizacja) | style włączone |
| `data-target` | selektor istniejącego kontenera (zamiast wstawiania za skryptem) | — |

Dokładnie jeden z `data-autor` / `data-jednostka` jest wymagany. Identyfikator
może być slugiem (czytelny, zgodny z adresem profilu — np. `Jan-Kowalski`) albo
liczbowym ID.

## Customizacja wyglądu (klasy CSS)

Widget generuje czysty, semantyczny HTML z przewidywalnymi klasami. Nadpisz je
własnym CSS-em (wyższa specyficzność) albo wyłącz domyślne style przez
`data-no-css` i ostyluj wszystko od zera.

| Klasa | Element |
| --- | --- |
| `.bpp-publikacje` | kontener widgetu |
| `.bpp-publikacje__lista` | lista (`ol`) w wariancie `lista` |
| `.bpp-publikacje__item` | pozycja listy (`li`) |
| `.bpp-publikacje__tabela` | tabela w wariancie `tabela` |
| `.bpp-publikacje__wiersz` | wiersz tabeli (`tr`) |
| `.bpp-publikacje__opis` | opis bibliograficzny publikacji |
| `.bpp-publikacje__link` | link „[szczegóły]” do rekordu w BPP |
| `.bpp-publikacje__link-cell` | komórka linku (wariant tabeli) |
| `.bpp-publikacje__stopka` | stopka z licznikiem i linkiem do profilu |
| `.bpp-publikacje__empty` | komunikat „brak publikacji” |
| `.bpp-publikacje__loading` | stan ładowania |
| `.bpp-publikacje__error` | komunikat błędu |

Przykład — własne kolory i odstępy:

```css
.bpp-publikacje__item {
  margin-bottom: 1.2em;
}
.bpp-publikacje__link {
  color: #b30000;
  font-weight: bold;
}
.bpp-publikacje__stopka {
  font-size: 0.8em;
  opacity: 0.7;
}
```

## Uwagi techniczne

- **Bezpieczeństwo treści.** Opisy bibliograficzne są przed wyświetleniem
  sanityzowane (dozwolone tylko tagi formatujące `b`, `i`, `em`, `strong`,
  `sub`, `sup`, `u`; usuwane są wszystkie atrybuty i znaczniki wykonywalne).
- **Wiele widgetów na stronie.** Możesz wkleić kilka snippetów na jednej stronie
  (np. autor + jednostka) — każdy renderuje się niezależnie.
- **Brak zależności.** Widget to czysty JavaScript; nie wymaga jQuery ani innych
  bibliotek i działa na każdej stronie HTML.
- **Aktualizacje.** Kod ładuje się z serwera BPP, więc poprawki docierają
  automatycznie. Tempo propagacji zależy od nagłówków cache serwera BPP
  (ustawienie po stronie administratora instancji).
</content>
