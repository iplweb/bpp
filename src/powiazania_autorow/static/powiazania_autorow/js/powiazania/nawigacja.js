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

// Mapuje zdarzenie keydown na akcje nawigacji po grafie (WCAG 2.1.1).
// Zwraca true, jesli klawisz zostal obsluzony — wolajacy uzywa tego, zeby
// zdecydowac, czy wywolac preventDefault (WYLACZNIE dla obsluzonych
// klawiszy; inaczej Tab zostalby zablokowany w grafie — pulapka
// klawiaturowa, zlamanie 2.1.2).
//
// Skroty z modyfikatorem naleza do przegladarki, nie do nas: Ctrl/Cmd +/-
// to zoom strony (WCAG 1.4.4 Resize Text), Alt+strzalka to nawigacja
// wstecz/wprzod, Ctrl+Home to przewijanie na gore. Przechwycenie ich
// zlamaloby funkcje wazniejsze niz nawigacja po grafie — stad wczesne
// wyjscie. `shiftKey` NIE wchodzi do tego warunku: na wielu ukladach
// klawiatury `+` wymaga Shift, wiec jego zablokowanie zepsuloby
// przyblizanie grafu tej samej klawiszologii, ktora ma dzialac.
export function obsluzKlawisz(cy, e) {
    if (e.ctrlKey || e.metaKey || e.altKey) {
        return false;
    }

    switch (e.key) {
        case "ArrowUp":
            przesun(cy, "gora");
            return true;
        case "ArrowDown":
            przesun(cy, "dol");
            return true;
        case "ArrowLeft":
            przesun(cy, "lewo");
            return true;
        case "ArrowRight":
            przesun(cy, "prawo");
            return true;
        case "+":
        case "=":
            zoomuj(cy, 1.2);
            return true;
        case "-":
        case "_":
            zoomuj(cy, 1 / 1.2);
            return true;
        case "Home":
            dopasuj(cy);
            return true;
        default:
            return false;
    }
}
