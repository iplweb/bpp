// Wielkość węzła = wybrana metryka (prace / IF / PK), znormalizowana
// do maksimum w grafie. Surowe wartości siedzą w danych węzła, więc
// zmiana metryki nie wymaga ponownego pobrania.

// Wartość bieżącej metryki dla węzła.
export function wartoscMetryki(ctx, node) {
    if (ctx.metryka === "if") { return node.data("if_sum") || 0; }
    if (ctx.metryka === "pk") { return node.data("pk_sum") || 0; }
    return node.data("works") || 0;
}

// Średnica węzła [px] dla wartości metryki `v` przy maksimum `max` w grafie:
// skala pierwiastkowa (różnice na małych wartościach lepiej widoczne) +
// clamp do 12..46. Czysta funkcja — jedyne źródło wzoru dla obu wariantów
// (skokowego i animowanego).
export function srednica(v, max) {
    const d = 12 + 34 * Math.sqrt(v / max);
    return Math.max(12, Math.min(46, d));
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
            n.data("rozmiar", srednica(wartoscMetryki(ctx, n), maxV));
        });
    });
}

// Jak przeliczRozmiary, ale PŁYNNIE: interpoluje "rozmiar" każdego węzła od
// bieżącej do docelowej wartości w pętli rAF (easeInOutCubic). Używane przy
// zmianie metryki, żeby kółka nie skakały, tylko urosły/zmalały przez ~`czas`
// ms. Znacznik czasu z rAF (bez Date.now). Uchwyt animacji trzymamy na ctx,
// żeby kolejna zmiana metryki anulowała poprzednią.
export function przeliczRozmiaryAnim(ctx, czas) {
    const cy = ctx.cy;
    let maxV = 1;
    cy.nodes().forEach(function (n) {
        const v = wartoscMetryki(ctx, n);
        if (v > maxV) { maxV = v; }
    });
    const cel = {};
    const start = {};
    cy.nodes().forEach(function (n) {
        cel[n.id()] = srednica(wartoscMetryki(ctx, n), maxV);
        start[n.id()] = n.data("rozmiar") || 20;
    });

    if (ctx._rozmiarRaf) {
        cancelAnimationFrame(ctx._rozmiarRaf);
        ctx._rozmiarRaf = null;
    }
    let t0 = null;
    function krok(teraz) {
        if (t0 === null) { t0 = teraz; }
        const t = Math.min(1, (teraz - t0) / czas);
        const e = t < 0.5
            ? 4 * t * t * t
            : 1 - Math.pow(-2 * t + 2, 3) / 2; // easeInOutCubic
        cy.batch(function () {
            cy.nodes().forEach(function (n) {
                const a = start[n.id()];
                const b = cel[n.id()];
                if (a === undefined || b === undefined) { return; }
                n.data("rozmiar", a + (b - a) * e);
            });
        });
        if (t < 1) {
            ctx._rozmiarRaf = requestAnimationFrame(krok);
        } else {
            ctx._rozmiarRaf = null;
        }
    }
    ctx._rozmiarRaf = requestAnimationFrame(krok);
}
