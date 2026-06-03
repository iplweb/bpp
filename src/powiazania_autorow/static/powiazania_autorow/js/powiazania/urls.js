// Budowa URL-i do endpointów eksploratora + odczyt bieżącego filtra
// (rok od-do, zaznaczone źródła/wydawcy). Szablony URL mają placeholder
// "/0/" podmieniany na konkretne id autora.

// Zaznaczone w szufladzie źródła/wydawcy. Wartość checkboxa zakodowana:
// "z<id>" = źródło, "w<id>" = wydawca.
export function wybraneZrodla(ctx) {
    const z = [];
    const w = [];
    if (ctx.listaZrodla) {
        const cbs = ctx.listaZrodla.querySelectorAll(
            "input[type=checkbox]:checked"
        );
        Array.prototype.forEach.call(cbs, function (cb) {
            if (cb.value.charAt(0) === "w") { w.push(cb.value.slice(1)); }
            else { z.push(cb.value.slice(1)); }
        });
    }
    return { z: z, w: w };
}

// Parametry filtra (rok od-do + wiele źródeł/wydawców + tylko zatrudnieni)
// jako "&k=v...". Dokleja je i siecUrl, i daneUrl, więc auto-rozwijanie BFS
// oraz klik-rozwijanie pojedynczego węzła respektują ten sam filtr.
export function paramyFiltru(ctx) {
    let p = "";
    if (ctx.rokOdEl && ctx.rokOdEl.value) {
        p += "&rok_od=" + encodeURIComponent(ctx.rokOdEl.value);
    }
    if (ctx.rokDoEl && ctx.rokDoEl.value) {
        p += "&rok_do=" + encodeURIComponent(ctx.rokDoEl.value);
    }
    const sel = wybraneZrodla(ctx);
    sel.z.forEach(function (id) {
        p += "&zrodlo=" + encodeURIComponent(id);
    });
    sel.w.forEach(function (id) {
        p += "&wydawca=" + encodeURIComponent(id);
    });
    if (ctx.tylkoZatrudnieni) {
        p += "&tylko_zatrudnieni=1";
    }
    return p;
}

export function daneUrl(ctx, id) {
    const f = paramyFiltru(ctx);
    return ctx.urlTemplate.replace("/0/", "/" + id + "/")
        + (f ? "?" + f.slice(1) : "");
}

export function siecUrl(ctx, id, depth, topn) {
    return ctx.siecUrlTemplate.replace("/0/", "/" + id + "/")
        + "?depth=" + depth + "&topn=" + topn + paramyFiltru(ctx);
}

export function zrodlaUrl(ctx, id) {
    // lista źródeł zależy tylko od zakresu lat, nie od wyboru źródła
    let p = "";
    if (ctx.rokOdEl && ctx.rokOdEl.value) {
        p += "&rok_od=" + encodeURIComponent(ctx.rokOdEl.value);
    }
    if (ctx.rokDoEl && ctx.rokDoEl.value) {
        p += "&rok_do=" + encodeURIComponent(ctx.rokDoEl.value);
    }
    return ctx.zrodlaUrlTemplate.replace("/0/", "/" + id + "/")
        + (p ? "?" + p.slice(1) : "");
}

export function grafUrl(ctx, id) {
    return ctx.grafUrlTemplate.replace("/0/", "/" + id + "/");
}
