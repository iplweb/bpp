/* Spinacz UX dla widoku „Szukaj zapytaniem" (bpp.views.zapytanie).
 *
 * Wpina prymitywy djangoql 0.25 (completion / multiline / highlight) do
 * strony: autocomplete (z wartościami w listach `in (...)`), nakładka z
 * kolorowaniem składni + czerwona falka w miejscu błędu, przyciski
 * „Sformatuj" i „Wyjaśnij liczby" (endpointy /format/ i /explain/).
 *
 * Nic tutaj nie jest częścią djangoql — to sposób, w jaki TEN widok używa
 * biblioteki (wzorzec z djangoql/example_project, demo.js). „Szukaj" zostaje
 * pełnym przeładowaniem strony (wyniki renderuje serwer); AJAX-em idą tylko
 * formatowanie i rozbicie na żądanie.
 */
(function () {
  "use strict";

  function readConfig() {
    var el = document.getElementById("zapytanie-config");
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      // Bez configu nie ma jak złożyć URL-i endpointów — zaloguj i odpuść
      // (autocomplete i tak nie zadziała), nie maskuj błędu po cichu.
      if (window.console) {
        console.error("zapytanie: niepoprawny #zapytanie-config", e);
      }
      return null;
    }
  }

  var cfg = readConfig();
  if (!cfg || !window.DjangoQL) {
    return;
  }

  function currentModelKey() {
    var checked = document.querySelector('input[name="model"]:checked');
    return checked ? checked.value : cfg.modelKey || "rekord";
  }

  // --- Kotwiczenie popupu autocomplete przy kursorze ----------------------
  // Bundlowany widget kładzie popup w lewym-dolnym rogu textarea; przy wysokim
  // wieloliniowym polu (i body BPP z position:relative+min-height:100vh) ląduje
  // to daleko od kursora. Liczymy pozycję kursora techniką „mirror div" i
  // doczepiamy popup tuż pod nim (współrzędne dokumentu, position:absolute —
  // dlatego bez nasłuchu scrolla: absolutny popup sam jedzie z treścią).
  var MIRROR_PROPS = [
    "boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom",
    "paddingLeft", "borderTopWidth", "borderRightWidth", "borderBottomWidth",
    "borderLeftWidth", "fontStyle", "fontVariant", "fontWeight", "fontStretch",
    "fontSize", "lineHeight", "fontFamily", "textAlign", "textTransform",
    "textIndent", "letterSpacing", "wordSpacing", "tabSize"
  ];

  function caretCoordinates(el) {
    var cs = window.getComputedStyle(el);
    var mirror = document.createElement("div");
    var s = mirror.style;
    s.position = "absolute";
    s.visibility = "hidden";
    s.whiteSpace = "pre-wrap";
    s.overflowWrap = "break-word";
    s.overflow = "hidden";
    for (var i = 0; i < MIRROR_PROPS.length; i++) {
      s[MIRROR_PROPS[i]] = cs[MIRROR_PROPS[i]];
    }
    var rect = el.getBoundingClientRect();
    s.left = window.pageXOffset + rect.left + "px";
    s.top = window.pageYOffset + rect.top + "px";
    var pos = Math.min(el.selectionStart || 0, el.value.length);
    mirror.textContent = el.value.slice(0, pos);
    var marker = document.createElement("span");
    marker.textContent = el.value.slice(pos) || ".";
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    // offsetLeft/Top są liczone od padding-edge mirrora; dodajemy bordery
    // textarea, żeby trafić w jej outer-box.
    var bl = parseFloat(cs.borderLeftWidth) || 0;
    var bt = parseFloat(cs.borderTopWidth) || 0;
    var x = window.pageXOffset + rect.left + bl + marker.offsetLeft - el.scrollLeft;
    var y = window.pageYOffset + rect.top + bt + marker.offsetTop - el.scrollTop;
    var lineHeight = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4;
    document.body.removeChild(mirror);
    return { x: x, y: y, lineHeight: lineHeight };
  }

  function positionPopupAtCaret(ta, popup) {
    if (!ta || !popup) {
      return;
    }
    var c = caretCoordinates(ta);
    var docEl = document.documentElement;
    var left = c.x + 2;
    var maxLeft = window.pageXOffset + docEl.clientWidth - popup.offsetWidth - 8;
    if (left > maxLeft) {
      left = Math.max(window.pageXOffset + 8, maxLeft);
    }
    popup.style.position = "absolute";
    popup.style.left = left + "px";
    popup.style.top = c.y + c.lineHeight + "px";
  }

  DjangoQL.DOMReady(function () {
    var textarea = document.getElementById("id_query");
    if (!textarea) {
      return;
    }
    var errorEl = document.getElementById("zapytanie-error");
    var explainPanel = document.getElementById("zapytanie-explain-panel");
    var explainTree = document.getElementById("zapytanie-explain-tree");

    // Nakładka highlight — doczepiamy JAWNIE (nie przez klasę .djangoql-highlight),
    // żeby zatrzymać uchwyt i móc oznaczać miejsce błędu (czerwona falka).
    var overlay = window.DjangoQLHighlight
      ? DjangoQLHighlight.attachOverlay(textarea)
      : null;

    var dql = null;

    // Tab-completion: pozwól Tab-em wstawić pierwszą podpowiedź. DOM Level 3 —
    // listenery AT_TARGET odpalają w kolejności rejestracji, więc rejestrujemy
    // NASZ keydown PRZED djangoql (które robi to w konstruktorze) i ustawiamy
    // selected=0 zanim handler djangoql zrobi selectCompletion+preventDefault.
    textarea.addEventListener("keydown", function (e) {
      if (!dql) {
        return;
      }
      if (e.keyCode !== 9 || e.shiftKey) {
        return;
      }
      if (!dql.completionEnabled) {
        return;
      }
      if (!dql.suggestions || dql.suggestions.length === 0) {
        return;
      }
      if (dql.selected === null) {
        dql.selected = 0;
      }
    });

    dql = DjangoQL.init({
      introspections: cfg.introspect[currentModelKey()],
      selector: textarea,
      autoResize: false
    });

    // Po oryginalnym renderze popupu — przesuń go pod kursor.
    var origRender = dql.renderCompletion.bind(dql);
    dql.renderCompletion = function (t) {
      origRender(t);
      if (dql.completion && dql.completion.style.display !== "none") {
        positionPopupAtCaret(dql.textarea, dql.completion);
      }
    };

    // Zmiana modelu (radio) → przeładuj introspekcję pod nowy schemat.
    document.querySelectorAll('input[name="model"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (!this.checked) {
          return;
        }
        dql.loadIntrospections(cfg.introspect[this.value]);
      });
    });

    // --- Błędy + falka -----------------------------------------------------
    function clearError() {
      if (errorEl) {
        errorEl.hidden = true;
        errorEl.textContent = "";
      }
      if (overlay) {
        overlay.clearError();
      }
    }

    function showError(data) {
      var msg = (data && data.error) || "Błąd zapytania";
      if (errorEl) {
        errorEl.textContent = msg;
        errorEl.hidden = false;
      }
      if (overlay && data && data.line && data.column) {
        if (data.mark === "token") {
          // Nieznane pole/wartość: oznacz tylko ten token.
          overlay.setErrorAt(data.line, data.column);
        } else {
          // Błąd składni: podświetl ogon od kolumny błędu do końca.
          overlay.setErrorFrom(data.line, data.column);
        }
      }
    }

    function post(url) {
      return fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": cfg.csrfToken,
          "X-Requested-With": "XMLHttpRequest"
        },
        body: new URLSearchParams({ q: textarea.value })
      }).then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      });
    }

    function repaintOverlay() {
      // highlight.js przemalowuje nakładkę na zdarzenie 'input'.
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    }

    // --- Sformatuj (pretty-print) -----------------------------------------
    function format() {
      clearError();
      post(cfg.format[currentModelKey()]).then(function (res) {
        if (!res.ok) {
          showError(res.data);
          return;
        }
        if (res.data.formatted) {
          textarea.value = res.data.formatted;
          textarea.rows = Math.max(4, res.data.formatted.split("\n").length);
          repaintOverlay();
        }
      });
    }

    // --- Wyjaśnij liczby (rozbicie na gałęzie) -----------------------------
    function renderNode(node) {
      var li = document.createElement("li");
      li.className = "node role-" + node.role;
      li.title = node.count + " rekord(ów) pasuje do tej gałęzi";
      var count = document.createElement("span");
      count.className = "node-count";
      count.textContent = node.count;
      var label = document.createElement("span");
      label.className = "node-label";
      // Ten sam tokenizer/paleta co pole zapytania. renderHtml jest XSS-safe
      // (escapuje wartość każdego tokenu).
      if (window.DjangoQLHighlight) {
        label.innerHTML = DjangoQLHighlight.renderHtml(node.text);
      } else {
        label.textContent = node.text;
      }
      li.appendChild(count);
      li.appendChild(label);
      if (node.children && node.children.length) {
        var ul = document.createElement("ul");
        node.children.forEach(function (child) {
          ul.appendChild(renderNode(child));
        });
        li.appendChild(ul);
      }
      return li;
    }

    function explain() {
      clearError();
      post(cfg.explain[currentModelKey()]).then(function (res) {
        if (!res.ok) {
          showError(res.data);
          return;
        }
        if (!explainPanel || !explainTree) {
          return;
        }
        explainTree.innerHTML = "";
        if (!res.data.tree) {
          explainPanel.hidden = true;
          return;
        }
        var ul = document.createElement("ul");
        ul.className = "zapytanie-explain-tree";
        ul.appendChild(renderNode(res.data.tree));
        explainTree.appendChild(ul);
        if (res.data.tree.truncated) {
          var note = document.createElement("p");
          note.className = "zapytanie-explain-trunc";
          note.textContent =
            "(pokazano tylko warunki najwyższego poziomu — zapytanie zbyt " +
            "złożone, by rozbić w całości)";
          explainTree.appendChild(note);
        }
        explainPanel.hidden = false;
      });
    }

    var formatBtn = document.getElementById("zapytanie-format");
    if (formatBtn) {
      formatBtn.addEventListener("click", format);
    }
    var explainBtn = document.getElementById("zapytanie-explain");
    if (explainBtn) {
      explainBtn.addEventListener("click", explain);
    }

    // Błąd z przeładowania „Szukaj" (serwer podał miejsce) — zaznacz falkę na
    // już-wpisanym zapytaniu.
    if (cfg.errorLocation && cfg.errorLocation.line && cfg.errorLocation.column) {
      showError({
        line: cfg.errorLocation.line,
        column: cfg.errorLocation.column,
        mark: cfg.errorLocation.mark
      });
      // Komunikat tekstowy pokazuje już serwerowy callout — schowaj duplikat.
      if (errorEl) {
        errorEl.hidden = true;
      }
    }
  });
})();
