/* Formatowanie + podświetlanie składni zapytania DjangoQL.
 *
 * Reużywa lexera DjangoQL (z zainicjowanej instancji: dql.lexer). Lexer JS
 * nie obsługuje newline'ów w regule whitespace, więc lexujemy zapytanie
 * JEDNOLINIOWE, a łamanie linii nakładamy na etapie renderu (po granicach
 * tokenów). HTML jest escapowany.
 */
(function () {
  "use strict";

  var TOKEN_CLASS = {
    AND: "dql-keyword", OR: "dql-keyword", NOT: "dql-keyword", IN: "dql-keyword",
    STARTSWITH: "dql-keyword", ENDSWITH: "dql-keyword",
    TRUE: "dql-bool", FALSE: "dql-bool", NONE: "dql-none",
    NAME: "dql-name", DOT: "dql-dot",
    STRING_VALUE: "dql-str", INT_VALUE: "dql-num", FLOAT_VALUE: "dql-num",
    PAREN_L: "dql-paren", PAREN_R: "dql-paren",
    EQUALS: "dql-op", NOT_EQUALS: "dql-op", GREATER: "dql-op",
    GREATER_EQUAL: "dql-op", LESS: "dql-op", LESS_EQUAL: "dql-op",
    CONTAINS: "dql-op", NOT_CONTAINS: "dql-op", COMMA: "dql-op",
  };

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tokenText(tok) {
    if (tok.name === "STRING_VALUE") return '"' + tok.value + '"';
    return tok.value;
  }

  function span(cls, text) {
    return '<span class="' + cls + '">' + esc(text) + "</span>";
  }

  function nl(depth) {
    return "\n" + "  ".repeat(depth);
  }

  // Łączy tokeny w sformatowany, podświetlony HTML. Zwraca jeden string.
  // Zasady łamania: '(' otwiera wcięcie i nową linię; ')' zamyka;
  // 'and'/'or' zaczynają nową linię na bieżącym wcięciu.
  function render(tokens) {
    var parts = [];
    var depth = 0;
    var atLineStart = true;

    function emit(html, glue) {
      if (!glue && !atLineStart) {
        parts.push(" ");
      }
      parts.push(html);
      atLineStart = false;
    }

    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i];
      var prev = tokens[i - 1];
      var cls = TOKEN_CLASS[t.name] || "dql-name";

      if (t.name === "PAREN_L") {
        emit(span("dql-paren", "("), false);
        depth += 1;
        parts.push(nl(depth));
        atLineStart = true;
        continue;
      }
      if (t.name === "PAREN_R") {
        depth = depth > 0 ? depth - 1 : 0;
        parts.push(nl(depth));
        atLineStart = true;
        emit(span("dql-paren", ")"), true);
        continue;
      }
      if (t.name === "AND" || t.name === "OR") {
        parts.push(nl(depth));
        atLineStart = true;
        emit(span(cls, t.value), true);
        continue;
      }
      // Kropka klei się do sąsiadów (ścieżka pola), bez spacji.
      var glue = t.name === "DOT" || (prev && prev.name === "DOT");
      emit(span(cls, tokenText(t)), glue);
    }
    return parts.join("");
  }

  function formatAndHighlight(query, lexer) {
    if (!query) return "";
    var tokens;
    try {
      tokens = lexer.setInput(query).lexAll();
    } catch (e) {
      return span("dql-name", query);
    }
    return render(tokens);
  }

  // `render`/`esc`/`tokenText` są czyste (token[]→HTML, bez DOM) — wystawiamy
  // je obok `formatAndHighlight` dla testów jednostkowych (vitest).
  window.djangoqlPretty = {
    formatAndHighlight: formatAndHighlight,
    render: render,
    esc: esc,
    tokenText: tokenText,
  };
})();
