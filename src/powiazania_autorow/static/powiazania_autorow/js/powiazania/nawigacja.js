// Nawigacja po grafie bez przeciagania (WCAG 2.5.7 Dragging Movements) oraz
// z klawiatury (2.1.1 Keyboard). Kryterium 2.5.7 wymaga, zeby funkcje
// dostepna przez przeciaganie dalo sie wykonac pojedynczym wskaznikiem —
// stad przyciski. Te same funkcje obsluguja klawiature.
//
// Modul operuje wylacznie na publicznym API Cytoscape, wiec da sie go
// przetestowac na atrapie, bez uruchamiania biblioteki.

// Krok przesuniecia jako UDZIAL rozmiaru widoku, nie stala w pikselach:
// przy duzym przyblizeniu stala byla by ledwo zauwazalna, przy oddaleniu
// przeskakiwala by caly graf.
const UDZIAL_KROKU = 0.2;

export function przesun(cy, kierunek) {
    const dx = cy.width() * UDZIAL_KROKU;
    const dy = cy.height() * UDZIAL_KROKU;

    // Znaki sa odwrocone wzgledem intuicji: `panBy` przesuwa PLOTNO,
    // a przyciski opisuja ruch WIDOKU. "w prawo" = plotno w lewo.
    switch (kierunek) {
        case "prawo":
            cy.panBy({ x: -dx, y: 0 });
            break;
        case "lewo":
            cy.panBy({ x: dx, y: 0 });
            break;
        case "dol":
            cy.panBy({ x: 0, y: -dy });
            break;
        case "gora":
            cy.panBy({ x: 0, y: dy });
            break;
        default:
            break;
    }
}

export function zoomuj(cy, wspolczynnik) {
    // Limity czytamy z instancji (utworzCy ustawia minZoom 0.1, maxZoom 4),
    // zeby nie duplikowac ich w dwoch miejscach.
    const docelowy = Math.min(
        Math.max(cy.zoom() * wspolczynnik, cy.minZoom()),
        cy.maxZoom()
    );

    cy.zoom({
        level: docelowy,
        renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
    });
}

export function dopasuj(cy) {
    cy.fit();
}
