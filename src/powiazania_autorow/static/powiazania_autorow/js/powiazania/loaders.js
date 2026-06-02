// Ładowanie danych z serwera: cała sieć (BFS) oraz lista źródeł/wydawców
// do szuflady. Oba używają tokenu sekwencji żądań — szybkie zmiany
// suwaków/filtrów odpalają kilka fetch-y, a wolniejsza wcześniejsza
// odpowiedź mogłaby nadpisać nowszy render (out-of-order). Każde żądanie
// zapamiętuje swój numer; render aplikuje się tylko, gdy numer jest nadal
// bieżący (== ctx.seq / ctx.seqZrodla).
import { siecUrl, zrodlaUrl, wybraneZrodla } from "./urls.js";
import { renderujSiec } from "./graph.js";
import { wyczysc } from "./dom.js";

export function zaladujSiec(ctx) {
    const moj = ++ctx.seq;
    fetch(siecUrl(ctx, ctx.autorId, ctx.glebokosc, ctx.topN))
        .then(function (r) {
            if (!r.ok) { throw new Error("HTTP " + r.status); }
            return r.json();
        })
        .then(function (data) {
            // Ignoruj przestarzałą odpowiedź — nowszy fetch już wystartował.
            if (moj !== ctx.seq) { return; }
            renderujSiec(ctx, data);
        })
        .catch(function (e) {
            if (moj !== ctx.seq) { return; }
            if (ctx.emptyEl) {
                ctx.emptyEl.textContent = "Błąd: " + e.message;
                ctx.emptyEl.style.display = "block";
            }
        });
}

export function naglowekGrupyZrodel(txt) {
    const h = document.createElement("div");
    h.textContent = txt;
    h.style.fontWeight = "bold";
    h.style.fontSize = "12px";
    h.style.color = "#666";
    h.style.margin = "6px 0 2px";
    return h;
}

export function pozycjaZrodla(x, prefiks, zaznaczone) {
    const lab = document.createElement("label");
    lab.style.display = "block";
    lab.style.fontSize = "13px";
    lab.style.padding = "1px 0";
    lab.style.whiteSpace = "nowrap";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = prefiks + x.id;
    cb.style.marginRight = "6px";
    if (zaznaczone[cb.value]) { cb.checked = true; }
    lab.appendChild(cb);
    lab.appendChild(
        document.createTextNode(x.nazwa + " (" + x.n + ")")
    );
    return lab;
}

export function aktualizujLabelZrodla(ctx) {
    if (!ctx.btnZrodlaToggle) { return; }
    const sel = wybraneZrodla(ctx);
    const n = sel.z.length + sel.w.length;
    ctx.btnZrodlaToggle.textContent =
        (n === 0 ? "Wszystkie źródła" : n + " wybrane") + " ▾";
}

export function filtrujListeZrodel(ctx) {
    if (!ctx.listaZrodla || !ctx.filterZrodla) { return; }
    const q = ctx.filterZrodla.value.trim().toLowerCase();
    const etykiety = ctx.listaZrodla.querySelectorAll("label");
    Array.prototype.forEach.call(etykiety, function (lab) {
        const pasuje = !q || lab.textContent.toLowerCase().indexOf(q) !== -1;
        lab.style.display = pasuje ? "block" : "none";
    });
}

// Zwrotna lista źródeł/wydawców centrum (z filtrem roku) do szuflady.
// Zaznaczenia przeżywają przeładowanie listy (po roku) — po value.
export function zaladujZrodla(ctx) {
    if (!ctx.listaZrodla || !ctx.zrodlaUrlTemplate) { return; }
    const moj = ++ctx.seqZrodla;
    fetch(zrodlaUrl(ctx, ctx.autorId))
        .then(function (r) {
            if (!r.ok) { throw new Error("HTTP " + r.status); }
            return r.json();
        })
        .then(function (data) {
            // Ignoruj przestarzałą odpowiedź (np. po szybkiej zmianie roku).
            if (moj !== ctx.seqZrodla) { return; }
            const sel = wybraneZrodla(ctx);
            const zaznaczone = {};
            sel.z.forEach(function (id) { zaznaczone["z" + id] = true; });
            sel.w.forEach(function (id) { zaznaczone["w" + id] = true; });

            wyczysc(ctx.listaZrodla);
            if (data.zrodla && data.zrodla.length) {
                ctx.listaZrodla.appendChild(naglowekGrupyZrodel("Źródła"));
                data.zrodla.forEach(function (x) {
                    ctx.listaZrodla.appendChild(
                        pozycjaZrodla(x, "z", zaznaczone)
                    );
                });
            }
            if (data.wydawcy && data.wydawcy.length) {
                ctx.listaZrodla.appendChild(naglowekGrupyZrodel("Wydawcy"));
                data.wydawcy.forEach(function (x) {
                    ctx.listaZrodla.appendChild(
                        pozycjaZrodla(x, "w", zaznaczone)
                    );
                });
            }
            aktualizujLabelZrodla(ctx);
            filtrujListeZrodel(ctx);
        })
        .catch(function (e) {
            console.error("Nie udało się pobrać listy źródeł:", e);
        });
}
