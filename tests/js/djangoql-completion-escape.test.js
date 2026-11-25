// @vitest-environment jsdom
//
// djangoql-completion-escape.js to standalone skrypt Media (globalne IIFE):
// ładujemy go dla efektu ubocznego w jsdom i testujemy czyste funkcje
// wystawione na window.bppDjangoQLCompletionEscape oraz samą podmianę
// `highlight` na atrapie widżetu.
import { describe, test, expect, beforeAll } from "vitest";

const ZNACZNIK = "<img src=x onerror=alert(1)>";

let api;

beforeAll(async () => {
    await import("../../src/bpp/static/bpp/js/djangoql-completion-escape.js");
    api = window.bppDjangoQLCompletionEscape;
});

describe("suggestionMarkup — tekst podpowiedzi to dane, nie HTML", () => {
    test("znaczniki w etykiecie są escapowane", () => {
        const html = api.suggestionMarkup(ZNACZNIK, "", true);
        expect(html).toBe("&lt;img src=x onerror=alert(1)&gt;");
        expect(html).not.toContain("<img");
    });

    test("wyróżnienie prefiksu nie psuje escapowania", () => {
        expect(api.suggestionMarkup(ZNACZNIK, "img", true)).toBe(
            "&lt;<b>img</b> src=x onerror=alert(1)&gt;",
        );
    });

    test("wpisany prefiks też jest escapowany", () => {
        expect(api.suggestionMarkup("x<u>y", "<u>", true)).toBe(
            "x<b>&lt;u&gt;</b>y",
        );
    });

    test("dopisek widżetu <i>…</i> zostaje elementem", () => {
        expect(api.suggestionMarkup("!=<i>nie równa się</i>", "", true)).toBe(
            "!=<i>nie równa się</i>",
        );
        expect(api.suggestionMarkup("Artykuł <i>#12</i>", "Art", true)).toBe(
            "<b>Art</b>ykuł <i>#12</i>",
        );
    });

    test("znaczniki przed dopiskiem są escapowane", () => {
        expect(api.suggestionMarkup(ZNACZNIK + " <i>#7</i>", "", true)).toBe(
            "&lt;img src=x onerror=alert(1)&gt; <i>#7</i>",
        );
    });

    test("dopisek nie przemyci znaczników", () => {
        const html = api.suggestionMarkup("x<i>" + ZNACZNIK + "</i>", "", true);
        expect(html).not.toContain("<img");
        expect(html).not.toContain("<i>");
    });

    test("wyróżnienie bez rozróżniania wielkości liter", () => {
        expect(api.suggestionMarkup("Polska", "po", false)).toBe(
            "<b>Po</b>lska",
        );
        expect(api.suggestionMarkup("Polska", "po", true)).toBe("Polska");
    });

    test("zwykły tekst bez zmian", () => {
        expect(api.suggestionMarkup("rok", "", true)).toBe("rok");
        expect(api.suggestionMarkup("", "", true)).toBe("");
        expect(api.suggestionMarkup(null, "", true)).toBe("");
    });
});

describe("install — podmiana highlight() widżetu", () => {
    function Atrapa() {}
    Atrapa.prototype.highlight = function (text) {
        return text; // jak w widżecie: bez escapowania
    };

    test("podmienia highlight i wstawiony HTML nie tworzy elementów", () => {
        expect(api.install(Atrapa)).toBe(true);
        const widzet = new Atrapa();
        widzet.highlightCaseSensitive = true;
        const li = document.createElement("li");
        li.innerHTML = widzet.highlight("Zły " + ZNACZNIK + " <i>#5</i>", "Z");
        expect(li.querySelector("img")).toBeNull();
        expect(li.textContent).toBe("Zły " + ZNACZNIK + " #5");
        expect(li.querySelector("i").textContent).toBe("#5");
        expect(li.querySelector("b").textContent).toBe("Z");
    });

    test("nie podmienia drugi raz ani widżetu, który escapuje sam", () => {
        expect(api.install(Atrapa)).toBe(false);
    });

    test("brak widżetu na stronie nie jest błędem", () => {
        expect(api.install(undefined)).toBe(false);
    });
});
