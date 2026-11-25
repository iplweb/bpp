// @vitest-environment jsdom
//
// admin_cofnij.js — przycisk „Cofnij” na liście przemapowań źródeł
// (standalone skrypt z Django Media, globalne IIFE). Pilnujemy, że tekst
// potwierdzenia jest brany z data-potwierdzenie DOSŁOWNIE (nazwa źródła
// z apostrofem/cudzysłowem nie psuje potwierdzenia ani nie jest wykonywana)
// i że potwierdzenie wysyła POST z tokenem CSRF (FD#508).
import { describe, test, expect, beforeAll, beforeEach, vi } from "vitest";

const NAZWA = `O'Reilly "Journal"'); window.zhakowano = 1; ('`;

let wyslane;

beforeAll(async () => {
    await import(
        "../../src/przemapuj_zrodlo/static/przemapuj_zrodlo/admin_cofnij.js"
    );
});

beforeEach(() => {
    vi.restoreAllMocks();
    wyslane = [];
    delete window.zhakowano;
    document.body.innerHTML = `
        <input type="hidden" name="csrfmiddlewaretoken" value="tok123">
        <a href="/przemapuj-zrodlo/cofnij/7/" class="przemapowanie-cofnij">
            <span class="ikona"></span> Cofnij
        </a>
        <a href="/inny/" class="inny">Inny</a>`;
    document
        .querySelector("a.przemapowanie-cofnij")
        .setAttribute("data-potwierdzenie", `Cofnąć do „${NAZWA}”?`);
    HTMLFormElement.prototype.submit = function () {
        wyslane.push(this);
    };
});

function klik(selektor) {
    const ev = new MouseEvent("click", { bubbles: true, cancelable: true });
    document.querySelector(selektor).dispatchEvent(ev);
    return ev;
}

describe("przycisk Cofnij", () => {
    test("pyta dosłownym tekstem i po potwierdzeniu wysyła POST z CSRF", () => {
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);

        // Klik w ikonę wewnątrz linku też ma zadziałać.
        const ev = klik("a.przemapowanie-cofnij .ikona");

        expect(ev.defaultPrevented).toBe(true);
        expect(confirm).toHaveBeenCalledWith(`Cofnąć do „${NAZWA}”?`);
        expect(window.zhakowano).toBeUndefined();
        expect(wyslane).toHaveLength(1);
        const form = wyslane[0];
        expect(form.method.toUpperCase()).toBe("POST");
        expect(form.getAttribute("action")).toBe("/przemapuj-zrodlo/cofnij/7/");
        expect(form.querySelector("[name=csrfmiddlewaretoken]").value).toBe(
            "tok123",
        );
    });

    test("bez potwierdzenia nic nie wysyła, a link nie nawiguje", () => {
        vi.spyOn(window, "confirm").mockReturnValue(false);

        const ev = klik("a.przemapowanie-cofnij");

        expect(ev.defaultPrevented).toBe(true);
        expect(wyslane).toHaveLength(0);
    });

    test("drugi klik po wysłaniu nie wysyła ponownie", () => {
        vi.spyOn(window, "confirm").mockReturnValue(true);

        klik("a.przemapowanie-cofnij");
        klik("a.przemapowanie-cofnij");

        expect(wyslane).toHaveLength(1);
    });

    test("inne linki zostają w spokoju", () => {
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);

        const ev = klik("a.inny");

        expect(ev.defaultPrevented).toBe(false);
        expect(confirm).not.toHaveBeenCalled();
    });
});
