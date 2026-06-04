// Eksplorator sieci współautorstwa — Cytoscape.js.
// Dane z endpointu bpp:browse_autor_powiazania_dane (per autor).
//
// Układ jest radialny i PRZYROSTOWY: autor centralny w środku, jego
// współautorzy w pierścieniu wokół niego, a każde rozwinięcie kolejnego
// węzła "zakwita" własnym pączkiem współautorów wokół KLIKNIĘTEGO węzła.
// Istniejące węzły nigdy nie są przesuwane — dzięki temu rozwijanie obrzeży
// nie nadpisuje głównego wykresu ani nie tworzy plątaniny.
//
// Dwa suwaki sterują widokiem (oba przeładowują sieć z serwera):
//   * "Maks. współautorów na węzeł" (top-N) — ilu najsilniejszych (najwięcej
//     wspólnych publikacji) sąsiadów rozwijamy na każdym węźle,
//   * "Głębokość sieci" — na ile poziomów BFS auto-rozwinąć wianuszek bez
//     klikania (endpoint siec.json liczy to po stronie serwera).
// Klik w węzeł nadal lokalnie dowija jego współautorów (pączek) ponad to.
//
// Stan mutowalny + referencje DOM żyją w obiekcie `ctx` (state.js),
// przekazywanym do funkcji pozostałych modułów zamiast domknięcia.
import { utworzKontekst } from "./state.js";
import { podepnijZdarzenia } from "./controls.js";
import { zaladujSiec } from "./loaders.js";

export function init() {
    const ctx = utworzKontekst();
    if (!ctx) {
        return; // brak kontenera lub Cytoscape — nic nie robimy
    }

    podepnijZdarzenia(ctx);

    // --- start: tylko sieć do bieżącej głębokości ---
    // Listę źródeł/wydawców ładujemy LENIWIE — dopiero przy pierwszym
    // otwarciu szuflady "Wszystkie źródła" (siedzi w schowanych "Opcje
    // zaawansowane"), więc nie płacimy za dwa GROUP BY-e, gdy nikt jej
    // nie otwiera. Patrz handler graf-zrodla-toggle w controls.js.
    zaladujSiec(ctx);
}
