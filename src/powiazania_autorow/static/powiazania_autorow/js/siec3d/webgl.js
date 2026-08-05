// Wykrywanie WebGL-a i komunikat zastępczy dla widoku 3D sieci powiązań.
//
// Rollbar #4006: `new THREE.WebGLRenderer` rzuca "Error creating WebGL
// context." u klientów bez działającego GPU. W praktyce trafia to w:
//   * crawlery renderujące JS w headless Chrome bez GPU (meta-externalagent
//     — źródło wszystkich 70 zgłoszeń, "Sandboxed = yes"),
//   * sesje zdalnego pulpitu i maszyny wirtualne,
//   * przeglądarki z wyłączoną akceleracją sprzętową lub GPU na liście blokad,
//   * karty, które wyczerpały limit żywych kontekstów WebGL (~16).
//
// Bez tego modułu wyjątek szedł w górę jako uncaught, a użytkownik dostawał
// czarny prostokąt bez wyjaśnienia. Testy: tests/js/siec3d-webgl.test.js.

// Kolejność prób: WebGL 2 (tego używa Three.js r15x), potem WebGL 1.
const KONTEKSTY = ["webgl2", "webgl"];

// Czy da się w ogóle utworzyć kontekst WebGL.
//
// Sonda jest jednorazowa: kontekst od razu oddajemy przez WEBGL_lose_context,
// bo karta ma twardy limit żywych kontekstów i szkoda zabierać slot
// rendererowi, który powstanie sekundę później.
//
// `dok` wstrzykiwany zamiast globalnego `document` — dzięki temu funkcja jest
// testowalna i nie zakłada środowiska przeglądarki w momencie importu.
export function czyWebglDostepny(dok) {
    let canvas;
    try {
        canvas = dok.createElement("canvas");
    } catch (e) {
        // Dokument bez createElement (nie-przeglądarka) — nie ma czym rysować.
        return false;
    }

    for (let i = 0; i < KONTEKSTY.length; i++) {
        let ctx = null;
        try {
            ctx = canvas.getContext(KONTEKSTY[i]);
        } catch (e) {
            // Część przeglądarek z twardo zablokowanym WebGL-em rzuca
            // SecurityError zamiast zwrócić null. Próbujemy dalej.
            continue;
        }
        if (ctx) {
            zwolnijKontekst(ctx);
            return true;
        }
    }
    return false;
}

// Oddaj kontekst sondy. Rozszerzenie bywa niedostępne — wtedy nic nie robimy
// (kontekst i tak zniknie z canvasem przy najbliższym GC).
function zwolnijKontekst(ctx) {
    if (typeof ctx.getExtension !== "function") { return; }
    let ext = null;
    try {
        ext = ctx.getExtension("WEBGL_lose_context");
    } catch (e) {
        return;
    }
    if (ext && typeof ext.loseContext === "function") {
        ext.loseContext();
    }
}

function akapit(dok, tekst, style) {
    const p = dok.createElement("p");
    p.textContent = tekst;
    p.style.cssText = style;
    return p;
}

// Zastąp zawartość kontenera 3D czytelnym komunikatem o braku WebGL-a.
//
// Opcje:
//   url2d     — adres widoku 2D tej samej sieci (wyjście awaryjne); bez niego
//               link się nie renderuje,
//   szczegoly — komunikat sterownika/przeglądarki; DANE NIEZAUFANE, wchodzą
//               do DOM wyłącznie przez textContent.
//
// Wszystko budowane przez API DOM — zero innerHTML, tak jak reszta modułu 3D.
export function pokazBrakWebgl(el, opcje) {
    const opts = opcje || {};
    // Ten sam dokument, w którym żyje kontener — spójnie z `czyWebglDostepny`
    // nie sięgamy po globalne `document`.
    const dok = el.ownerDocument;

    el.textContent = "";

    const box = dok.createElement("div");
    box.style.cssText = "display: flex; flex-direction: column;"
        + " align-items: center; justify-content: center; height: 100%;"
        + " padding: 24px; text-align: center; color: #e8ecf5;"
        + " font-size: 14px; line-height: 1.5;";

    box.appendChild(akapit(
        dok,
        "Widok 3D jest niedostępny w tej przeglądarce.",
        "margin: 0 0 8px; font-size: 17px; font-weight: bold; color: #fff;"
    ));
    box.appendChild(akapit(
        dok,
        "Rysowanie sieci w 3D wymaga WebGL-a, którego nie udało się tutaj"
        + " uruchomić. Najczęstsze przyczyny to wyłączona akceleracja"
        + " sprzętowa, praca przez zdalny pulpit albo starsza karta graficzna.",
        "margin: 0 0 16px; max-width: 460px; color: #b9c3d6;"
    ));

    if (opts.url2d) {
        const a = dok.createElement("a");
        a.href = opts.url2d;
        a.textContent = "Przejdź do widoku 2D";
        a.className = "button small";
        a.style.cssText = "margin: 0;";
        box.appendChild(a);
    }

    if (opts.szczegoly) {
        box.appendChild(akapit(
            dok,
            String(opts.szczegoly),
            "margin: 16px 0 0; font-size: 11px; color: #7c879b;"
            + " max-width: 460px; word-break: break-word;"
        ));
    }

    el.appendChild(box);
}
