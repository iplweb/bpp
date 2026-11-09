// @vitest-environment jsdom
//
// Selektor lat „od–do” na podstronie autora (zakres-lat.js).
import { describe, expect, it } from "vitest";

import {
    czyMac,
    inicjujZakresLat,
    kliknij,
    lataWZakresie,
    podzielNaZakresy,
} from "../../src/bpp/static/bpp/js/zakres-lat.js";

const LATA = [2024, 2023, 2021, 2020, 2018];

describe("kliknij (czysta logika)", () => {
    const pusty = { zaznaczone: new Set(), poczatek: null };

    it("pierwszy klik ustawia początek i zaznacza tylko ten rok", () => {
        const s = kliknij(pusty, 2021, { lata: LATA });
        expect([...s.zaznaczone]).toEqual([2021]);
        expect(s.poczatek).toBe(2021);
    });

    it("drugi klik zaznacza zakres tylko z lat na liście", () => {
        const s1 = kliknij(pusty, 2024, { lata: LATA });
        const s2 = kliknij(s1, 2020, { lata: LATA });
        expect([...s2.zaznaczone].sort()).toEqual([2020, 2021, 2023, 2024]);
        expect(s2.poczatek).toBeNull();
    });

    it("kolejność kliknięć nie ma znaczenia", () => {
        const s = kliknij(kliknij(pusty, 2018, { lata: LATA }), 2021, { lata: LATA });
        expect([...s.zaznaczone].sort()).toEqual([2018, 2020, 2021]);
    });

    it("trzeci klik zaczyna nowy zakres", () => {
        let s = kliknij(pusty, 2024, { lata: LATA });
        s = kliknij(s, 2020, { lata: LATA });
        s = kliknij(s, 2018, { lata: LATA });
        expect([...s.zaznaczone]).toEqual([2018]);
    });

    it("pojedynczo dokłada i zdejmuje rok, nie ruszając reszty", () => {
        let s = kliknij(kliknij(pusty, 2024, { lata: LATA }), 2023, { lata: LATA });
        s = kliknij(s, 2018, { pojedynczo: true, lata: LATA });
        expect([...s.zaznaczone].sort()).toEqual([2018, 2023, 2024]);
        s = kliknij(s, 2023, { pojedynczo: true, lata: LATA });
        expect([...s.zaznaczone].sort()).toEqual([2018, 2024]);
    });

    it("lataWZakresie i czyMac", () => {
        expect(lataWZakresie(LATA, 2023, 2019)).toEqual([2023, 2021, 2020]);
        expect(czyMac("MacIntel")).toBe(true);
        expect(czyMac("Linux x86_64")).toBe(false);
    });
});

function kontener() {
    document.body.innerHTML = `
        <div data-zakres-lat>
            <p class="autor-page__lata-podpowiedz" hidden>
                <kbd data-zakres-lat-klawisz>Ctrl</kbd>
                <a href="#" data-zakres-lat-wyczysc>Wyczyść</a>
            </p>
            ${LATA.map(
                (r) =>
                    `<label><input type="checkbox" name="rok" value="${r}"/>` +
                    `<span>${r}</span></label>`,
            ).join("")}
        </div>`;
    return document.querySelector("[data-zakres-lat]");
}

function klik(k, rok, opcje = {}) {
    const span = [...k.querySelectorAll("span")].find((s) => s.textContent == rok);
    span.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true, detail: 1, ...opcje }),
    );
}

const zaznaczone = (k) =>
    [...k.querySelectorAll("input:checked")].map((i) => Number(i.value)).sort();

describe("inicjujZakresLat (DOM)", () => {
    it("dwa kliknięcia zaznaczają zakres, środek dostaje klasę", () => {
        const k = kontener();
        inicjujZakresLat(k, { platforma: "Linux" });
        klik(k, 2024);
        klik(k, 2020);
        expect(zaznaczone(k)).toEqual([2020, 2021, 2023, 2024]);
        const srodek = k.querySelector("input[value='2023']").closest("label");
        expect(srodek.classList.contains("autor-page__chip--w-zakresie")).toBe(true);
    });

    it("Ctrl na Linuksie i ⌘ na Macu przełączają pojedynczy rok", () => {
        const k = kontener();
        inicjujZakresLat(k, { platforma: "Linux" });
        klik(k, 2024);
        klik(k, 2023);
        klik(k, 2018, { ctrlKey: true });
        expect(zaznaczone(k)).toEqual([2018, 2023, 2024]);

        const m = kontener();
        inicjujZakresLat(m, { platforma: "MacIntel" });
        expect(m.querySelector("kbd").textContent).toBe("⌘");
        klik(m, 2018, { metaKey: true });
        klik(m, 2024, { metaKey: true });
        expect(zaznaczone(m)).toEqual([2018, 2024]);
    });

    it("podpowiedź odkryta, „Wyczyść” odznacza wszystko", () => {
        const k = kontener();
        inicjujZakresLat(k, { platforma: "Linux" });
        expect(k.querySelector("p").hidden).toBe(false);
        klik(k, 2024);
        klik(k, 2018);
        k.querySelector("[data-zakres-lat-wyczysc]").click();
        expect(zaznaczone(k)).toEqual([]);
    });
});

describe("podzielNaZakresy", () => {
    it("sąsiednie na liście lata to zakres, samotne zostają pojedyncze", () => {
        // 2022 i 2019 nie ma na liście — nie przerywają zakresu.
        expect(podzielNaZakresy(LATA, new Set([2024, 2023, 2021, 2018]))).toEqual({
            zakresy: [[2021, 2024]],
            pojedyncze: [2018],
        });
        expect(podzielNaZakresy(LATA, new Set([2024, 2021]))).toEqual({
            zakresy: [],
            pojedyncze: [2024, 2021],
        });
        expect(podzielNaZakresy(LATA, new Set())).toEqual({ zakresy: [], pojedyncze: [] });
    });
});

describe("wysyłka formularza", () => {
    it("zakres idzie jako zakres_lat, pojedyncze lata jako rok", () => {
        document.body.innerHTML = `<form>${kontener().outerHTML}</form>`;
        const k = document.querySelector("[data-zakres-lat]");
        inicjujZakresLat(k, { platforma: "Linux" });
        klik(k, 2024);
        klik(k, 2021);
        klik(k, 2018, { ctrlKey: true });
        // jsdom nie odpala `formdata` przy new FormData(form) (przeglądarki
        // tak) — wysyłamy zdarzenie ręcznie, jak zrobiłaby to przeglądarka.
        const form = document.querySelector("form");
        const fd = new FormData(form);
        const zdarzenie = new Event("formdata");
        zdarzenie.formData = fd;
        form.dispatchEvent(zdarzenie);
        expect(fd.getAll("zakres_lat")).toEqual(["[2021,2024]"]);
        expect(fd.getAll("rok")).toEqual(["2018"]);
        // DOM nietknięty — checkboxy zakresu dalej zaznaczone.
        expect(zaznaczone(k)).toEqual([2018, 2021, 2023, 2024]);
    });
});

describe("kompresja przy dokliknięciu brakującego roku", () => {
    it("2020 + 2022–2025, potem Ctrl+2021 → jeden zakres 2020–2025", () => {
        const lata = [2025, 2024, 2023, 2022, 2021, 2020];
        let s = { zaznaczone: new Set(), poczatek: null };
        s = kliknij(s, 2025, { lata });
        s = kliknij(s, 2022, { lata });
        s = kliknij(s, 2020, { pojedynczo: true, lata });
        expect(podzielNaZakresy(lata, s.zaznaczone)).toEqual({
            zakresy: [[2022, 2025]],
            pojedyncze: [2020],
        });
        s = kliknij(s, 2021, { pojedynczo: true, lata });
        expect(podzielNaZakresy(lata, s.zaznaczone)).toEqual({
            zakresy: [[2020, 2025]],
            pojedyncze: [],
        });
    });
});
