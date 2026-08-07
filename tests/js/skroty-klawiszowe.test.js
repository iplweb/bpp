// @vitest-environment jsdom
//
// Preferencja skrotow jednoznakowych (WCAG 2.1.4). Kryterium wymaga, zeby
// uzytkownik mogl skrot wylaczyc — BPP w czesci publicznej nie ma kont, wiec
// preferencja siedzi w localStorage. Domyslka to "wlaczone": brak wpisu nie
// moze zmieniac zachowania nikomu, kto nic nie ustawil.

import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const ZRODLO = readFileSync(
    resolve(__dirname, "../../src/bpp/static/bpp/js/skroty-klawiszowe.js"),
    "utf-8"
);

function zaladuj() {
    // Modul jest skryptem window-globalnym (IIFE), nie modulem ESM —
    // wykonujemy go na biezacym window jsdom.
    new Function(ZRODLO).call(window);
    return window;
}

beforeEach(() => {
    // Polyfill localStorage jeśli nie jest dostępny (jsdom 25+)
    if (!window.localStorage) {
        const store = {};
        window.localStorage = {
            getItem: (key) => store[key] || null,
            setItem: (key, value) => {
                store[key] = String(value);
            },
            removeItem: (key) => {
                delete store[key];
            },
            clear: () => {
                Object.keys(store).forEach((key) => delete store[key]);
            },
            key: (index) => Object.keys(store)[index] || null,
            get length() {
                return Object.keys(store).length;
            },
        };
    }
    window.localStorage.clear();
    delete window.bppSkrotyWlaczone;
    delete window.bppUstawSkroty;
    delete window.bppPodepnijPrzelacznikSkrotow;
});

describe("bppSkrotyWlaczone", () => {
    it("domyslnie wlaczone gdy brak wpisu", () => {
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it('"0" wylacza', () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "0");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(false);
    });

    it('"1" wlacza', () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "1");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it("smiec w localStorage traktowany jak brak wpisu", () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "tak");
        expect(zaladuj().bppSkrotyWlaczone()).toBe(true);
    });

    it("nie rzuca gdy localStorage niedostepny", () => {
        const oryginalny = window.localStorage.getItem;
        window.localStorage.getItem = () => {
            throw new Error("SecurityError");
        };
        const w = zaladuj();
        expect(w.bppSkrotyWlaczone()).toBe(true);
        window.localStorage.getItem = oryginalny;
    });
});

describe("bppUstawSkroty", () => {
    it("zapisuje wylaczenie i zwraca nowy stan", () => {
        const w = zaladuj();
        expect(w.bppUstawSkroty(false)).toBe(false);
        expect(window.localStorage.getItem("bpp.skrotyJednoznakowe")).toBe("0");
        expect(w.bppSkrotyWlaczone()).toBe(false);
    });

    it("zapisuje wlaczenie", () => {
        const w = zaladuj();
        w.bppUstawSkroty(false);
        expect(w.bppUstawSkroty(true)).toBe(true);
        expect(window.localStorage.getItem("bpp.skrotyJednoznakowe")).toBe("1");
    });

    it("nie rzuca gdy zapis niemozliwy", () => {
        const oryginalny = window.localStorage.setItem;
        window.localStorage.setItem = () => {
            throw new Error("QuotaExceededError");
        };
        const w = zaladuj();
        expect(() => w.bppUstawSkroty(false)).not.toThrow();
        window.localStorage.setItem = oryginalny;
    });

    it("fallback: gdy setItem rzuca, stan trzyma się w sesji (nie w localStorage)", () => {
        const oryginalny = window.localStorage.setItem;
        window.localStorage.setItem = () => {
            throw new Error("QuotaExceededError");
        };
        const w = zaladuj();
        w.bppUstawSkroty(false);
        // localStorage jest puste (zapis się nie powiódł)
        expect(window.localStorage.getItem("bpp.skrotyJednoznakowe")).toBe(null);
        // ale bppSkrotyWlaczone() zwraca false (z fallback-u w pamięci)
        expect(w.bppSkrotyWlaczone()).toBe(false);
        window.localStorage.setItem = oryginalny;
    });

    it("fallback: przełącznik działa w sesji nawet bez localStorage", () => {
        const oryginalny = window.localStorage.setItem;
        window.localStorage.setItem = () => {
            throw new Error("QuotaExceededError");
        };
        const w = zaladuj();
        const el = window.document.createElement("button");
        window.document.body.appendChild(el);
        w.bppPodepnijPrzelacznikSkrotow(el);
        // Initialnie włączone
        expect(el.getAttribute("aria-pressed")).toBe("true");
        // Klik wyłącza
        el.click();
        expect(el.getAttribute("aria-pressed")).toBe("false");
        expect(el.textContent).toContain("wyłączone");
        // Drugi klik włącza
        el.click();
        expect(el.getAttribute("aria-pressed")).toBe("true");
        expect(el.textContent).toContain("włączone");
        window.localStorage.setItem = oryginalny;
    });
});

describe("bppPodepnijPrzelacznikSkrotow", () => {
    function przycisk() {
        const el = window.document.createElement("button");
        window.document.body.appendChild(el);
        return el;
    }

    it("ustawia stan poczatkowy na wlaczony", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        expect(el.getAttribute("aria-pressed")).toBe("true");
        expect(el.textContent).toContain("włączone");
    });

    it("klik wylacza skroty i aktualizuje etykiete", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        el.click();
        expect(w.bppSkrotyWlaczone()).toBe(false);
        expect(el.getAttribute("aria-pressed")).toBe("false");
        expect(el.textContent).toContain("wyłączone");
    });

    it("drugi klik wraca do stanu wyjsciowego", () => {
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        el.click();
        el.click();
        expect(w.bppSkrotyWlaczone()).toBe(true);
        expect(el.getAttribute("aria-pressed")).toBe("true");
    });

    it("odzwierciedla stan zapisany wczesniej", () => {
        window.localStorage.setItem("bpp.skrotyJednoznakowe", "0");
        const w = zaladuj();
        const el = przycisk();
        w.bppPodepnijPrzelacznikSkrotow(el);
        expect(el.getAttribute("aria-pressed")).toBe("false");
    });
});
