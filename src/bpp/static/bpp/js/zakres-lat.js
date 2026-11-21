// Selektor lat jako zakres „od–do” (jak kalendarz na booking.com).
//
// Kontener [data-zakres-lat] zawiera chipy: <label><input type=checkbox
// value=ROK><span>ROK</span></label>. Zachowanie:
//   - zwykły klik: pierwszy rok = początek, drugi = koniec; zaznaczają się
//     wszystkie lata pomiędzy (tylko te z listy). Kolejny klik zaczyna od nowa.
//     Po wybraniu początku najechanie myszą podświetla przyszły zakres.
//   - Ctrl+klik (⌘+klik na Macu): przełącza pojedynczy rok, nie ruszając
//     reszty — jak zaznaczanie plików w menedżerze plików.
//   - klawiatura (spacja na fokusowanym chipie): przełącza pojedynczy rok —
//     zakres myszą nie ma odpowiednika „bez patrzenia”, więc nie zgadujemy.
//
// Bez JS zostają zwykłe checkboxy (każdy rok osobno) — formularz działa tak samo.

export const KLASA_ZAKRES = "autor-page__chip--w-zakresie";
export const KLASA_PODGLAD = "autor-page__chip--podglad";
export const KLASA_POCZATEK = "autor-page__chip--poczatek";

export function czyMac(platforma) {
    return /Mac|iPhone|iPad|iPod/i.test(platforma || "");
}

// Czysta logika: nowy zbiór zaznaczonych lat po kliknięciu.
// `stan` = { zaznaczone: Set<number>, poczatek: number|null }.
// Zwraca nowy stan (nie mutuje wejścia).
export function kliknij(stan, rok, { pojedynczo = false, lata = [] } = {}) {
    const zaznaczone = new Set(stan.zaznaczone);
    if (pojedynczo) {
        if (zaznaczone.has(rok)) zaznaczone.delete(rok);
        else zaznaczone.add(rok);
        return { zaznaczone, poczatek: null };
    }
    if (stan.poczatek === null) {
        return { zaznaczone: new Set([rok]), poczatek: rok };
    }
    return {
        zaznaczone: new Set(lataWZakresie(lata, stan.poczatek, rok)),
        poczatek: null,
    };
}

export function lataWZakresie(lata, a, b) {
    const od = Math.min(a, b);
    const doRoku = Math.max(a, b);
    return lata.filter((r) => r >= od && r <= doRoku);
}

// Zaznaczone lata → { zakresy: [[od, do], ...], pojedyncze: [rok, ...] }.
// Zakres = co najmniej dwa SĄSIEDNIE na liście `lata` zaznaczone lata (rok
// bez prac autora nie ma chipa, więc nie przerywa zakresu). `od`/`do` to
// skrajne lata zakresu — lata pomiędzy bez prac nic nie zmieniają w wynikach.
export function podzielNaZakresy(lata, zaznaczone) {
    const zakresy = [];
    const pojedyncze = [];
    let biezacy = [];
    const zamknij = () => {
        if (biezacy.length >= 2) {
            zakresy.push([Math.min(...biezacy), Math.max(...biezacy)]);
        } else {
            pojedyncze.push(...biezacy);
        }
        biezacy = [];
    };
    for (const rok of lata) {
        if (zaznaczone.has(rok)) biezacy.push(rok);
        else zamknij();
    }
    zamknij();
    return { zakresy, pojedyncze };
}

export function inicjujZakresLat(kontener, { platforma } = {}) {
    const chipy = Array.from(kontener.querySelectorAll("input[type=checkbox]"));
    const lata = chipy.map((c) => Number(c.value));
    const poRoku = new Map(chipy.map((c) => [Number(c.value), c]));
    let stan = {
        zaznaczone: new Set(chipy.filter((c) => c.checked).map((c) => Number(c.value))),
        poczatek: null,
    };

    const mac = czyMac(
        platforma ?? (typeof navigator !== "undefined" ? navigator.platform : ""),
    );
    kontener
        .querySelectorAll(".autor-page__lata-podpowiedz")
        .forEach((el) => (el.hidden = false));
    kontener
        .querySelectorAll("[data-zakres-lat-klawisz]")
        .forEach((el) => (el.textContent = mac ? "⌘" : "Ctrl"));

    function etykieta(rok) {
        return poRoku.get(rok).closest("label");
    }

    function rysuj(podgladDo = null) {
        for (const [rok, input] of poRoku) {
            input.checked = stan.zaznaczone.has(rok);
            const l = etykieta(rok);
            l.classList.toggle(KLASA_POCZATEK, stan.poczatek === rok);
            l.classList.remove(KLASA_PODGLAD);
        }
        if (stan.poczatek !== null && podgladDo !== null) {
            for (const r of lataWZakresie(lata, stan.poczatek, podgladDo)) {
                etykieta(r).classList.add(KLASA_PODGLAD);
            }
        }
        // „Środek” zakresu jaśniejszy, końce pełnym kolorem — jak w kalendarzu.
        // Sąsiedztwo liczymy po kolejności na liście (lata bez prac nie
        // przerywają zakresu).
        chipy.forEach((input, i) => {
            const zaz = (j) => chipy[j] && chipy[j].checked;
            etykieta(Number(input.value)).classList.toggle(
                KLASA_ZAKRES,
                input.checked && zaz(i - 1) && zaz(i + 1),
            );
        });
    }

    kontener.addEventListener("click", (e) => {
        const label = e.target.closest("label");
        if (!label || !kontener.contains(label)) return;
        const input = label.querySelector("input[type=checkbox]");
        if (!input) return;
        // preventDefault na kliku w <label> blokuje też syntetyczny klik na
        // <input> (i natywne przełączenie) — stan checkboxów ustawia rysuj().
        e.preventDefault();
        const klawiatura = e.detail === 0;
        const pojedynczo = klawiatura || (mac ? e.metaKey : e.ctrlKey);
        stan = kliknij(stan, Number(input.value), { pojedynczo, lata });
        rysuj();
    });

    kontener.addEventListener("mouseover", (e) => {
        if (stan.poczatek === null) return;
        const input = e.target.closest("label")?.querySelector("input");
        if (input) rysuj(Number(input.value));
    });
    kontener.addEventListener("mouseleave", () => rysuj());

    const wyczysc = kontener.querySelector("[data-zakres-lat-wyczysc]");
    if (wyczysc) {
        wyczysc.addEventListener("click", (e) => {
            e.preventDefault();
            stan = { zaznaczone: new Set(), poczatek: null };
            rysuj();
        });
    }

    // Wysyłka: ciągłe zakresy jako pola „Zakres lat” (`zakres_lat=[od,do]`),
    // reszta jako pojedyncze „Rok” — w multiseeku zamiast „2020 lub 2021 lub
    // 2022…” widać jedno „Zakres lat 2020–2024”. Podmieniamy tylko FormData
    // (zdarzenie `formdata`), checkboxy w DOM zostają nietknięte — po
    // powrocie „Wstecz” formularz wygląda tak samo jak przed wysyłką.
    const form = kontener.closest("form");
    if (form) {
        form.addEventListener("formdata", (e) => {
            const { zakresy, pojedyncze } = podzielNaZakresy(lata, stan.zaznaczone);
            e.formData.delete("rok");
            e.formData.delete("zakres_lat");
            for (const [od, doRoku] of zakresy) {
                e.formData.append("zakres_lat", JSON.stringify([od, doRoku]));
            }
            for (const rok of pojedyncze) e.formData.append("rok", String(rok));
        });
    }

    rysuj();
    return { stan: () => stan };
}

if (typeof document !== "undefined") {
    const start = () =>
        document
            .querySelectorAll("[data-zakres-lat]")
            .forEach((k) => inicjujZakresLat(k));
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
