// Wielkość węzła = wybrana metryka (prace / IF / PK), znormalizowana
// do maksimum w grafie. Surowe wartości siedzą w danych węzła, więc
// zmiana metryki nie wymaga ponownego pobrania.

// Wartość bieżącej metryki dla węzła.
export function wartoscMetryki(ctx, node) {
    if (ctx.metryka === "if") { return node.data("if_sum") || 0; }
    if (ctx.metryka === "pk") { return node.data("pk_sum") || 0; }
    return node.data("works") || 0;
}

// Przelicza średnice wszystkich węzłów: skala pierwiastkowa + clamp,
// żeby różne metryki o różnych zakresach dawały czytelny rozrzut.
export function przeliczRozmiary(ctx) {
    const cy = ctx.cy;
    let maxV = 1;
    cy.nodes().forEach(function (n) {
        const v = wartoscMetryki(ctx, n);
        if (v > maxV) { maxV = v; }
    });
    cy.batch(function () {
        cy.nodes().forEach(function (n) {
            const d = 12 + 34 * Math.sqrt(wartoscMetryki(ctx, n) / maxV);
            n.data("rozmiar", Math.max(12, Math.min(46, d)));
        });
    });
}
