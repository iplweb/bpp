// Strona startu eksportu BibTeX/RIS: przycisk „Generuj” pokazujemy dopiero,
// gdy widget ALTCHA zakończy weryfikację (proof-of-work). Wcześniej da się
// tylko wrócić na stronę autora — wysłanie formularza bez rozwiązania i tak
// zostałoby odrzucone przez serwer.

export function inicjujFormularz(form) {
    const przycisk = form.querySelector("[data-czeka-na-altcha]");
    const widget = form.querySelector("altcha-widget");
    if (!przycisk || !widget) return;

    widget.addEventListener("statechange", (zdarzenie) => {
        // Wygaśnięcie / błąd po wcześniejszej weryfikacji → znowu ukryj.
        przycisk.hidden = zdarzenie.detail?.state !== "verified";
    });

    // Widget z `auto="onload"` mógł skończyć, zanim podpięliśmy nasłuch.
    if (typeof widget.getState === "function") {
        przycisk.hidden = widget.getState() !== "verified";
    }
}

function inicjujWszystkie() {
    document
        .querySelectorAll("form")
        .forEach((form) => inicjujFormularz(form));
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicjujWszystkie);
    } else {
        inicjujWszystkie();
    }
}
