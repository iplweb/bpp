// @vitest-environment jsdom
// Zachowanie widgetu osadzania przy odpowiedziach bledych.
//
// Sedno: widget musi odroznic DECYZJE ADMINISTRATORA (404 z kluczem `powod`
// -> strona bez sladu, powod w komentarzu HTML) od ZWYKLEJ POMYLKI (404 bez
// `powod`: literowka w data-autor, autor ukryty, encja skasowana -> ramka
// bledu, bo ktos musi sie o niej dowiedziec).
//
// Widget to IIFE odpalane przy zaladowaniu i wymagajace
// `document.currentScript`, wiec plik importujemy DOPIERO po przygotowaniu
// DOM-u — stad dynamiczny import z unikalnym query, zeby ominac cache modulow.
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";

const SCIEZKA = "../../src/bpp/static/embed/bpp-publikacje.js";
let licznik = 0;

// Fabryki, nie gotowe promisy: promise odrzucony w chwili wywolania
// `odpowiedz(...)` nie mialby jeszcze handlera i Node zglosilby unhandled
// rejection, ktore vitest liczy jako blad przebiegu.
function odpowiedz(status, tresc, { json = true } = {}) {
    return () =>
        Promise.resolve({
            ok: status >= 200 && status < 300,
            status,
            json: () =>
                json
                    ? Promise.resolve(tresc)
                    : Promise.reject(new SyntaxError()),
        });
}

function odrzucenie(err) {
    return () => Promise.reject(err);
}

async function uruchomWidget(fabrykaOdpowiedzi) {
    document.head.innerHTML = "";
    document.body.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://bpp.example.org/static/embed/bpp-publikacje.js";
    script.setAttribute("data-autor", "jan-kowalski");
    script.setAttribute("data-no-css", "1");
    document.body.appendChild(script);
    Object.defineProperty(document, "currentScript", {
        value: script,
        configurable: true,
    });

    globalThis.fetch = vi.fn(fabrykaOdpowiedzi);
    vi.resetModules();
    await import(`${SCIEZKA}?v=${licznik++}`);

    // Widget konczy prace w mikrotaskach lancucha .then — czekamy na nie.
    await new Promise((r) => setTimeout(r, 0));

    return document.querySelector(".bpp-publikacje") || document.body;
}

describe("widget osadzania — odpowiedzi bledne", () => {
    beforeEach(() => {
        vi.spyOn(console, "warn").mockImplementation(() => {});
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    test("404 z powod: nic na stronie, powod w komentarzu HTML", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, {
                detail: "Ta czesc REST API zostala wylaczona.",
                powod: "grupa_wylaczona",
                grupa: "kafelki",
            })
        );

        expect(kontener.textContent.trim()).toBe("");
        expect(kontener.innerHTML).toContain("<!--");
        expect(kontener.innerHTML).toContain("wylaczona");
        expect(console.warn).toHaveBeenCalled();
    });

    test("404 bez powod: ramka bledu, bo to zwykla pomylka", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, { detail: "No Autor matches the given query." })
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(kontener.innerHTML).not.toContain("<!--");
        expect(console.warn).toHaveBeenCalled();
    });

    test("404 z trescia nie-JSON: ramka bledu", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(404, null, { json: false })
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(kontener.innerHTML).not.toContain("<!--");
        expect(console.warn).toHaveBeenCalled();
    });

    test("500 z powod: ramka bledu — cisza dotyczy WYLACZNIE 404", async () => {
        const kontener = await uruchomWidget(
            odpowiedz(500, { detail: "boom", powod: "api_wylaczone" })
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(console.warn).toHaveBeenCalled();
    });

    test("odrzucony fetch (brak CORS, siec): ramka bledu", async () => {
        const kontener = await uruchomWidget(
            odrzucenie(new TypeError("Failed to fetch"))
        );

        expect(kontener.textContent).toContain("Nie udało się załadować");
        expect(console.warn).toHaveBeenCalled();
    });
});
