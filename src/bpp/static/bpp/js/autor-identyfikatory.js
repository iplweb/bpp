// Kafle identyfikatorów na podstronie autora: kopiowanie do schowka.
//
// Każdy kafel ma przycisk [data-kopiuj] (dostępny z klawiatury). Klik w
// dowolne miejsce kafla POZA linkiem przekazujemy do tego przycisku — więc
// „klik w kafel kopiuje, klik w link przenosi na stronę docelową”.

const CZAS_KOMUNIKATU_MS = 1500;

async function kopiuj(przycisk) {
    const status = przycisk.querySelector(".autor-page__id-kopiuj-status");
    const kafel = przycisk.closest("[data-id-kafel]");
    try {
        await navigator.clipboard.writeText(przycisk.dataset.kopiuj);
    } catch (blad) {
        // Schowek bywa niedostępny (brak HTTPS, odmowa uprawnień) — informujemy,
        // zamiast udawać sukces.
        console.error("Nie udało się skopiować identyfikatora", blad);
        if (status) status.textContent = "Nie udało się skopiować";
        return;
    }
    if (status) status.textContent = "Skopiowano";
    if (kafel) kafel.classList.add("autor-page__id-card--skopiowano");
    setTimeout(() => {
        if (status) status.textContent = "";
        if (kafel) kafel.classList.remove("autor-page__id-card--skopiowano");
    }, CZAS_KOMUNIKATU_MS);
}

export function inicjujKafel(kafel) {
    const przycisk = kafel.querySelector("[data-kopiuj]");
    if (!przycisk) return;
    przycisk.addEventListener("click", (zdarzenie) => {
        zdarzenie.stopPropagation();
        kopiuj(przycisk);
    });
    kafel.addEventListener("click", (zdarzenie) => {
        // Klik w link → zwykła nawigacja, bez kopiowania.
        if (zdarzenie.target.closest("a")) return;
        kopiuj(przycisk);
    });
}

function inicjujWszystkie() {
    document.querySelectorAll("[data-id-kafel]").forEach(inicjujKafel);
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicjujWszystkie);
    } else {
        inicjujWszystkie();
    }
}
