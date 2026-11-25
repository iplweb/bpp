/* Podpowiedzi DjangoQL: tekst podpowiedzi to dane, nie HTML.
 *
 * Widżet podpowiedzi (djangoql/js/completion.js z pakietu djangoql-iplweb)
 * wypełnia listę przez `li.innerHTML = highlight(tekst, prefiks)`, a jego
 * `highlight()` niczego nie escapuje. Tekstem podpowiedzi bywają nazwy
 * obiektów z bazy (charakter formalny, źródło, jednostka…) wpisane przez
 * redaktorów — znaczniki w takiej nazwie przeglądarka potraktowałaby jak
 * znaczniki. Ten plik podmienia `highlight()` na wersję, która escapuje
 * etykietę, wpisany prefiks i dopisek (`<i>…</i>` dodawany przez sam widżet),
 * a od siebie dokłada wyłącznie `<b>` (dopasowanie) i `<i>` (dopisek).
 *
 * `renderCompletion()` widżetu szuka `highlight` na prototypie w chwili
 * rysowania, więc podmiana działa niezależnie od tego, czy widżet został już
 * utworzony. Plik MUSI być ładowany po completion.js.
 *
 * Docelowo to samo robi sam widżet (djangoql-iplweb, flaga
 * `highlight.escapesSuggestions`) — wtedy ten plik nic nie zmienia i można
 * go usunąć razem z miejscami, które go ładują.
 */
(function () {
  "use strict";

  var ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return ESCAPES[c];
    });
  }

  // Dopisek to `<i>…</i>` doklejany przez widżet: na samym końcu i bez
  // znaczników w środku. Wszystko inne, co wygląda jak znacznik, to dane.
  var HINT = /<i>([^<]*)<\/i>$/;

  function splitSuggestion(suggestionText) {
    var text = String(suggestionText == null ? "" : suggestionText);
    var m = HINT.exec(text);
    if (!m) {
      return { label: text, hint: null };
    }
    return { label: text.slice(0, m.index), hint: m[1] };
  }

  function markPrefix(label, prefix, caseSensitive) {
    if (!prefix) {
      return escapeHtml(label);
    }
    var haystack = caseSensitive ? label : label.toLowerCase();
    var needle = caseSensitive ? prefix : prefix.toLowerCase();
    if (!needle || haystack.length !== label.length) {
      // toLowerCase() zmieniło długość (zdarza się dla kilku liter Unicode),
      // więc pozycje z `haystack` nie pasują do `label` — bez wyróżnienia.
      return escapeHtml(label);
    }
    var out = "";
    var pos = 0;
    var found = haystack.indexOf(needle, pos);
    while (found !== -1) {
      out += escapeHtml(label.slice(pos, found));
      out +=
        "<b>" + escapeHtml(label.slice(found, found + needle.length)) + "</b>";
      pos = found + needle.length;
      found = haystack.indexOf(needle, pos);
    }
    return out + escapeHtml(label.slice(pos));
  }

  function suggestionMarkup(suggestionText, prefix, caseSensitive) {
    var parts = splitSuggestion(suggestionText);
    var html = markPrefix(parts.label, prefix, caseSensitive);
    if (parts.hint !== null) {
      html += "<i>" + escapeHtml(parts.hint) + "</i>";
    }
    return html;
  }

  function install(DjangoQL) {
    if (!DjangoQL || !DjangoQL.prototype) {
      return false;
    }
    var current = DjangoQL.prototype.highlight;
    if (current && current.escapesSuggestions) {
      return false; // widżet escapuje już sam
    }
    DjangoQL.prototype.highlight = function (text, prefix) {
      return suggestionMarkup(text, prefix, this.highlightCaseSensitive);
    };
    DjangoQL.prototype.highlight.escapesSuggestions = true;
    return true;
  }

  // Czyste funkcje na namespace — testowalne jednostkowo bez widżetu.
  window.bppDjangoQLCompletionEscape = {
    escapeHtml: escapeHtml,
    splitSuggestion: splitSuggestion,
    markPrefix: markPrefix,
    suggestionMarkup: suggestionMarkup,
    install: install,
  };

  if (!install(window.DjangoQL) && !window.DjangoQL) {
    // Widżet jeszcze się nie załadował (ten plik trafił przed completion.js).
    // Podmiana działa też po fakcie, więc spróbuj raz jeszcze, gdy strona
    // będzie gotowa — zanim ktokolwiek zdąży otworzyć listę podpowiedzi.
    document.addEventListener("DOMContentLoaded", function () {
      install(window.DjangoQL);
    });
  }
})();
