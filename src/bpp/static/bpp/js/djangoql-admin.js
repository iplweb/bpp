/* Nakładka highlight + czerwona falka błędu w pasku wyszukiwania DjangoQL
 * w adminie.
 *
 * BppDjangoQLSearchMixin wyłącza wbudowane completion_admin_highlight.js
 * (djangoql_highlight=False) i ładuje highlight.js + ten plik. Sami dołączamy
 * nakładkę, dzięki czemu TRZYMAMY jej uchwyt i możemy narysować TRWAŁĄ falkę
 * błędu (`setError` przeżywa przemalowania nakładki; samo malowanie backdropu
 * jest kasowane przy autoResize po załadowaniu strony).
 *
 * Lokalizację błędu czytamy z ukrytego markera `.bpp-dql-error-loc`
 * (wstrzykiwanego serwerowo przez djangoql_error_message): błąd składni niesie
 * line+column (podświetlamy ogon), błąd schematu — value (lokalizujemy token).
 * Falka znika sama, gdy użytkownik zacznie edytować pole.
 */
(function () {
  "use strict";

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // 0-based offset tokenu nieznanego pola/wartości (jak _locate_token: całe
  // słowo z granicami nie-słownymi, bez kropki z lewej; fallback do podciągu).
  function locateValue(text, value) {
    var m = new RegExp("(?:^|[^\\w.])(" + escapeRe(value) + ")(?![\\w])").exec(text);
    if (m) {
      return text.indexOf(m[1], m.index);
    }
    return text.indexOf(value);
  }

  // 0-based offset → 1-based (line, column) dla setErrorAt.
  function lineColFromOffset(text, offset) {
    var before = text.slice(0, offset);
    var line = (before.match(/\n/g) || []).length + 1;
    var column = offset - before.lastIndexOf("\n"); // brak \n: -1 → offset+1
    return { line: line, column: column };
  }

  // Czyste helpery lokalizacji błędu (string→offset, offset→line/column)
  // wystawiamy na namespace, żeby były jednostkowo testowalne bez DOM ani
  // DjangoQL. To jedyna funkcja tego eksportu — `wire()`/DOMReady poniżej
  // wymagają DjangoQL i odpalają się wyłącznie w przeglądarce.
  window.bppDjangoQLAdmin = {
    escapeRe: escapeRe,
    locateValue: locateValue,
    lineColFromOffset: lineColFromOffset,
  };

  var H = window.DjangoQLHighlight;
  if (!window.DjangoQL || !H) {
    return;
  }

  function wire() {
    var textarea = document.querySelector("textarea[name=q]");
    if (!textarea) {
      return;
    }
    // Jedyne miejsce, które dołącza nakładkę w adminie — mamy uchwyt.
    var overlay = H.attachOverlay(textarea);
    if (!overlay) {
      return;
    }
    var loc = document.querySelector(".bpp-dql-error-loc");
    if (!loc) {
      return;
    }
    var line = parseInt(loc.getAttribute("data-line"), 10);
    var column = parseInt(loc.getAttribute("data-column"), 10);
    if (line && column) {
      // błąd składni/leksera — podświetl ogon od kolumny błędu do końca
      overlay.setErrorFrom(line, column);
      return;
    }
    var val = loc.getAttribute("data-value");
    if (!val) {
      return;
    }
    var start = locateValue(textarea.value, val);
    if (start < 0) {
      return;
    }
    var lc = lineColFromOffset(textarea.value, start);
    overlay.setErrorAt(lc.line, lc.column); // nieznane pole — oznacz ten token
  }

  // completion_admin.js tworzy textarę też na DOMReady, a kolejność skryptów z
  // Media bywa taka, że nasz ładuje się WCZEŚNIEJ — odraczamy o jedną klatkę,
  // aż wszystkie callbacki DOMReady się wykonają i textarea będzie istnieć.
  DjangoQL.DOMReady(function () {
    if (window.requestAnimationFrame) {
      window.requestAnimationFrame(wire);
    } else {
      wire();
    }
  });
})();
