// Fabryka instancji Cytoscape.js + komplet stylów grafu.
// Cytoscape udostępniany jest globalnie przez cytoscape-entry.js
// (window.cytoscape) — bundle esbuild ładuje go raz dla całej strony.

// Tablica stylów grafu: węzły (autorzy), krawędzie (współautorstwo),
// klasy stanu (centrum, rozwiniety, nowy do fade-in, wewnetrzna,
// znaleziony/powiazana-szukana dla wyszukiwarki, przygaszony).
const STYLE = [
    {
        selector: "node",
        style: {
            "label": "data(etykieta)",
            "background-color": "#4A90E2",
            "width": "data(rozmiar)",
            "height": "data(rozmiar)",
            "font-size": 10,
            "color": "#222",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 3,
            "min-zoomed-font-size": 7,
            "transition-property": "opacity",
            "transition-duration": "0.4s"
        }
    },
    {
        selector: "node.centrum",
        style: { "background-color": "#FF6B6B", "font-weight": "bold" }
    },
    {
        selector: "node.rozwiniety",
        style: { "border-width": 2, "border-color": "#2c6cb0" }
    },
    {
        selector: "edge",
        style: {
            "width": "mapData(shared, 1, 20, 1, 9)",
            "line-color": "#bbb",
            "curve-style": "haystack",
            "opacity": 0.55,
            "transition-property": "opacity",
            "transition-duration": "0.4s"
        }
    },
    {
        selector: "edge.podswietlona",
        style: { "line-color": "#2c6cb0", "opacity": 0.9 }
    },
    {
        // Świeżo dodane elementy startują niewidoczne; zdjęcie klasy
        // w następnej klatce uruchamia płynny fade-in (transition).
        selector: ".nowy",
        style: { "opacity": 0 }
    },
    {
        // Krawędzie "poprzeczne" (powiązania wewnątrz grupy) — żeby
        // odróżnić je od drzewa rozwijania: przerywane, pomarańczowe.
        selector: "edge.wewnetrzna",
        style: {
            "line-color": "#e08a3c",
            "line-style": "dashed",
            "opacity": 0.5,
            "width": "mapData(shared, 1, 20, 1, 5)"
        }
    },
    {
        // Wyszukiwanie: trafiony węzeł na wierzch, jaskrawy.
        selector: "node.znaleziony",
        style: {
            "background-color": "#FFD400",
            "border-width": 3,
            "border-color": "#c79100",
            "font-weight": "bold",
            "color": "#000",
            "z-index": 9999
        }
    },
    {
        selector: "edge.powiazana-szukana",
        style: {
            "line-color": "#d7263d",
            "opacity": 0.95,
            "width": "mapData(shared, 1, 20, 2, 9)",
            "z-index": 9998
        }
    },
    {
        // Reszta grafu przygaszona, gdy coś wyszukano.
        selector: ".przygaszony",
        style: { "opacity": 0.12 }
    }
];

// Tworzy instancję Cytoscape osadzoną w `container` z gotowymi stylami.
export function utworzCy(container) {
    const cytoscape = window.cytoscape;
    return cytoscape({
        container: container,
        minZoom: 0.1,
        maxZoom: 4,
        wheelSensitivity: 0.2,
        style: STYLE
    });
}
