// Linki [data-przewin-do="<id>"] (np. „Pokaż wszystkie prace” na podstronie
// autora) przewijają do sekcji o tym id przez window.bpp.scrollToVisible —
// samo #kotwica chowałoby nagłówek sekcji pod sticky belką. Po przewinięciu
// fokus trafia na pierwszy element z tabindex w sekcji (nagłówek), żeby
// klawiatura i czytnik ekranu „wylądowały” tam, gdzie wzrok.
//
// Bez JS działa zwykła kotwica w href.

function przewin(zdarzenie) {
    const link = zdarzenie.target.closest("[data-przewin-do]");
    if (!link) return;
    const cel = document.getElementById(link.dataset.przewinDo);
    if (!cel) return; // brak sekcji → zostaw domyślną nawigację po kotwicy
    zdarzenie.preventDefault();
    window.bpp.scrollToVisible(cel);
    history.replaceState(null, "", "#" + cel.id);
    const fokus = cel.querySelector("[tabindex='-1']") || cel;
    fokus.focus({ preventScroll: true });
}

if (typeof document !== "undefined") {
    document.addEventListener("click", przewin);
}
