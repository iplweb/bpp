// @vitest-environment jsdom
//
// djangoql-pretty.js to standalone skrypt <script> (multiseek) — globalne
// IIFE bez guardu. Ładujemy w jsdom, czyste funkcje render/esc/tokenText
// są wystawione na window.djangoqlPretty. Lexer NIE jest potrzebny —
// testujemy render() bezpośrednio na tablicach tokenów.
import { describe, test, expect, beforeAll } from "vitest";

let render;
let esc;
let tokenText;

beforeAll(async () => {
    await import("../../src/bpp/static/bpp/js/djangoql-pretty.js");
    ({ render, esc, tokenText } = window.djangoqlPretty);
});

const tok = (name, value) => ({ name, value });

describe("esc", () => {
    test("escapuje &, <, >, \"", () => {
        expect(esc('<a>&"')).toBe("&lt;a&gt;&amp;&quot;");
    });
});

describe("tokenText", () => {
    test("STRING_VALUE jest owijany w cudzysłowy", () => {
        expect(tokenText(tok("STRING_VALUE", "foo"))).toBe('"foo"');
    });

    test("pozostałe tokeny dosłownie", () => {
        expect(tokenText(tok("NAME", "rok"))).toBe("rok");
    });
});

describe("render", () => {
    test("proste wyrażenie: tokeny rozdzielone spacją, z klasami CSS", () => {
        const html = render([
            tok("NAME", "rok"),
            tok("EQUALS", "="),
            tok("INT_VALUE", "2020"),
        ]);
        expect(html).toBe(
            '<span class="dql-name">rok</span> ' +
            '<span class="dql-op">=</span> ' +
            '<span class="dql-num">2020</span>'
        );
    });

    test("kropka klei się do sąsiadów bez spacji (ścieżka pola)", () => {
        const html = render([
            tok("NAME", "autor"),
            tok("DOT", "."),
            tok("NAME", "rok"),
        ]);
        expect(html).toBe(
            '<span class="dql-name">autor</span>' +
            '<span class="dql-dot">.</span>' +
            '<span class="dql-name">rok</span>'
        );
    });

    test("nawias otwiera wcięcie + nową linię, zamknięcie je cofa", () => {
        const html = render([
            tok("PAREN_L", "("),
            tok("NAME", "a"),
            tok("PAREN_R", ")"),
        ]);
        expect(html).toBe(
            '<span class="dql-paren">(</span>\n  ' +
            '<span class="dql-name">a</span>\n' +
            '<span class="dql-paren">)</span>'
        );
    });

    test("and/or zaczyna nową linię na bieżącym wcięciu", () => {
        const html = render([
            tok("NAME", "a"),
            tok("AND", "and"),
            tok("NAME", "b"),
        ]);
        expect(html).toBe(
            '<span class="dql-name">a</span>\n' +
            '<span class="dql-keyword">and</span> ' +
            '<span class="dql-name">b</span>'
        );
    });
});
