// @vitest-environment jsdom
//
// Wykrywanie WebGL-a i komunikat zastępczy dla widoku 3D sieci powiązań.
//
// Kontekst: Rollbar #4006 — `new THREE.WebGLRenderer` rzuca "Error creating
// WebGL context." u klientów bez GPU (crawlery w headless Chrome, sesje
// zdalnego pulpitu, maszyny z zablokowaną akceleracją). Nieobsłużony wyjątek
// zostawiał użytkownikowi czarny prostokąt bez słowa wyjaśnienia.
//
// jsdom NIE implementuje WebGL-a — `getContext("webgl")` zwraca tam `null`.
// To wygodne: przypadek negatywny testujemy na PRAWDZIWYM dokumencie, bez
// żadnej atrapy. Dla przypadków pozytywnych podmieniamy
// `HTMLCanvasElement.prototype.getContext` — to jedyny sposób, bo w jsdom
// nie da się uzyskać prawdziwego kontekstu WebGL.
import { describe, test, expect, afterEach, vi } from "vitest";
import {
    czyWebglDostepny,
    pokazBrakWebgl,
} from "../../src/powiazania_autorow/static/powiazania_autorow/js/siec3d/webgl.js";

const oryginalnyGetContext = HTMLCanvasElement.prototype.getContext;

afterEach(() => {
    HTMLCanvasElement.prototype.getContext = oryginalnyGetContext;
});

// Podmienia getContext na funkcję sterowaną mapą {nazwa: kontekst|null}.
// Zwraca listę zapytanych nazw — do sprawdzenia kolejności prób.
function zasymulujKonteksty(mapa) {
    const zapytania = [];
    HTMLCanvasElement.prototype.getContext = function (nazwa) {
        zapytania.push(nazwa);
        return Object.prototype.hasOwnProperty.call(mapa, nazwa)
            ? mapa[nazwa]
            : null;
    };
    return zapytania;
}

describe("czyWebglDostepny", () => {
    test("jsdom bez WebGL-a (getContext → null) → false", () => {
        // Bez żadnej atrapy: to realne zachowanie środowiska bez WebGL-a.
        // jsdom przy okazji woła console.error("Not implemented: ...") —
        // wyciszamy TEN JEDEN znany komunikat, żeby log testów został czysty.
        const cichy = vi.spyOn(console, "error").mockImplementation(() => {});
        try {
            expect(czyWebglDostepny(document)).toBe(false);
        } finally {
            cichy.mockRestore();
        }
    });

    test("dostępny webgl2 → true", () => {
        zasymulujKonteksty({ webgl2: {} });
        expect(czyWebglDostepny(document)).toBe(true);
    });

    test("brak webgl2, jest webgl → true (fallback na WebGL 1)", () => {
        zasymulujKonteksty({ webgl: {} });
        expect(czyWebglDostepny(document)).toBe(true);
    });

    test("getContext rzuca wyjątek → false, wyjątek nie ucieka", () => {
        // Przeglądarki z twardo zablokowanym WebGL-em potrafią rzucić
        // SecurityError zamiast zwrócić null.
        HTMLCanvasElement.prototype.getContext = function () {
            throw new Error("SecurityError: WebGL is disabled");
        };
        expect(czyWebglDostepny(document)).toBe(false);
    });

    test("probe zwalnia kontekst przez WEBGL_lose_context", () => {
        // Karta ma twardy limit ~16 żywych kontekstów WebGL; kontekst
        // testowy MUSI zostać oddany, inaczej sami odbieramy slot
        // rendererowi, który za chwilę powstanie.
        let zwolniony = false;
        const ctx = {
            getExtension(nazwa) {
                if (nazwa !== "WEBGL_lose_context") { return null; }
                return { loseContext() { zwolniony = true; } };
            },
        };
        zasymulujKonteksty({ webgl2: ctx });

        czyWebglDostepny(document);

        expect(zwolniony).toBe(true);
    });

    test("brak rozszerzenia WEBGL_lose_context → nadal true, bez wyjątku", () => {
        zasymulujKonteksty({ webgl2: { getExtension: () => null } });
        expect(czyWebglDostepny(document)).toBe(true);
    });
});

describe("pokazBrakWebgl", () => {
    function kontener() {
        const el = document.createElement("div");
        el.textContent = "resztki poprzedniej sceny";
        document.body.appendChild(el);
        return el;
    }

    test("czyści kontener i wstawia komunikat o braku WebGL-a", () => {
        const el = kontener();

        pokazBrakWebgl(el, { url2d: "/bpp/autor/7/powiazania/" });

        expect(el.textContent).not.toContain("resztki poprzedniej sceny");
        expect(el.textContent).toContain("WebGL");
    });

    test("daje wyjście awaryjne: link do widoku 2D", () => {
        const el = kontener();

        pokazBrakWebgl(el, { url2d: "/bpp/autor/7/powiazania/" });

        const link = el.querySelector("a");
        expect(link).not.toBeNull();
        expect(link.getAttribute("href")).toBe("/bpp/autor/7/powiazania/");
    });

    test("bez url2d nie renderuje linku (ale komunikat zostaje)", () => {
        const el = kontener();

        pokazBrakWebgl(el, {});

        expect(el.querySelector("a")).toBeNull();
        expect(el.textContent).toContain("WebGL");
    });

    test("szczegóły techniczne trafiają do DOM jako tekst, nie jako HTML", () => {
        // Komunikat sterownika idzie prosto z przeglądarki — traktujemy go
        // jak dane niezaufane (reszta modułu 3D trzyma ten sam standard).
        const el = kontener();

        pokazBrakWebgl(el, { szczegoly: "<img src=x onerror=alert(1)>" });

        expect(el.querySelector("img")).toBeNull();
        expect(el.textContent).toContain("<img src=x onerror=alert(1)>");
    });
});
