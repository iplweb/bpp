// @vitest-environment jsdom
//
// Strona startu eksportu: „Generuj” widoczny dopiero po weryfikacji ALTCHA.
import { describe, expect, it } from "vitest";

import { inicjujFormularz } from "../../src/bpp/static/bpp/js/eksport-autora-altcha.js";

function formularz(stanPoczatkowy) {
    document.body.innerHTML = `
        <form>
            <altcha-widget></altcha-widget>
            <button type="submit" hidden data-czeka-na-altcha>Generuj</button>
        </form>`;
    const form = document.querySelector("form");
    const widget = form.querySelector("altcha-widget");
    if (stanPoczatkowy) widget.getState = () => stanPoczatkowy;
    return { form, widget, przycisk: form.querySelector("button") };
}

function zmienStan(widget, state) {
    widget.dispatchEvent(new CustomEvent("statechange", { detail: { state } }));
}

describe("eksport-autora-altcha", () => {
    it("przycisk ukryty do weryfikacji, pokazany po 'verified'", () => {
        const { form, widget, przycisk } = formularz();
        inicjujFormularz(form);
        expect(przycisk.hidden).toBe(true);
        zmienStan(widget, "verifying");
        expect(przycisk.hidden).toBe(true);
        zmienStan(widget, "verified");
        expect(przycisk.hidden).toBe(false);
    });

    it("wygaśnięcie weryfikacji znowu ukrywa przycisk", () => {
        const { form, widget, przycisk } = formularz();
        inicjujFormularz(form);
        zmienStan(widget, "verified");
        zmienStan(widget, "expired");
        expect(przycisk.hidden).toBe(true);
    });

    it("widget zweryfikowany przed inicjalizacją → przycisk od razu widoczny", () => {
        const { form, przycisk } = formularz("verified");
        inicjujFormularz(form);
        expect(przycisk.hidden).toBe(false);
    });
});
