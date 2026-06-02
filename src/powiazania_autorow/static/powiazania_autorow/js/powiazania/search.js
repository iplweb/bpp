// Wyszukiwanie po nazwisku: trafione węzły jaskrawe i na wierzch, ich
// krawędzie czerwone, reszta przygaszona. Pusty tekst -> reset.
export function szukaj(ctx, q) {
    const cy = ctx.cy;
    q = (q || "").trim().toLowerCase();
    cy.batch(function () {
        cy.elements().removeClass(
            "znaleziony przygaszony powiazana-szukana"
        );
        if (!q) {
            return;
        }
        const trafione = cy.nodes().filter(function (n) {
            return (n.data("label") || "").toLowerCase().indexOf(q) !== -1;
        });
        if (trafione.empty()) {
            return;
        }
        cy.elements().addClass("przygaszony");
        trafione.removeClass("przygaszony").addClass("znaleziony");
        const kraw = trafione.connectedEdges();
        kraw.removeClass("przygaszony").addClass("powiazana-szukana");
        kraw.connectedNodes().removeClass("przygaszony");
    });
}
