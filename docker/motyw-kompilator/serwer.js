/*
 * Kompilator motywów konfiguratora wyglądu BPP — osobny, odizolowany serwis.
 *
 * Dlaczego osobny kontener: kompilacja to wykonanie dużego kodu JS (dart-sass)
 * na danych od użytkownika. Ewentualna dziura w silniku JS nie daje dostępu
 * do appservera (baza, sekrety) — kontener nie ma bazy, sekretów, dostępu
 * do internetu ani zapisu na dysk (patrz bpp-deploy).
 *
 * Uruchamia DOKŁADNIE te same pliki co podgląd w przeglądarce, w kontekście
 * `vm` bez API Node'a (bez `require`, `process`, systemu plików):
 *   - dist/sass-przegladarka.js   (dart-sass, Grunt: shell:esbuildSass),
 *   - motyw-konfig.js, motyw-kompilator.js,
 *   - dist/motyw-zrodla-scss.json (pliki SCSS, Grunt: motywyZrodla).
 * Na wejściu wyłącznie dane (ustawienia motywu), nigdy kod.
 *
 * API:
 *   GET  /zdrowie   → 200 "ok"
 *   POST /kompiluj  {konfig, czcionkiUrl} → 200 text/css
 *                                          | 400 {blad, bledy} | 413 | 500
 * Tryb jednorazowy (dev/testy, bez serwera): `node serwer.js --jednorazowo`
 * czyta JSON z stdin, CSS na stdout, błąd → kod 1 i JSON na stderr.
 *
 * Zmienne środowiskowe: BPP_MOTYW_JS (katalog motyw-*.js), BPP_MOTYW_DIST
 * (katalog dist/), PORT (domyślnie 8095).
 */
"use strict";

const fs = require("fs");
const http = require("http");
const path = require("path");
const vm = require("vm");

const KATALOG_JS = process.env.BPP_MOTYW_JS || "/app/js";
const KATALOG_DIST = process.env.BPP_MOTYW_DIST || "/app/dist";
const PORT = Number(process.env.PORT || 8095);
// Ustawienia z obrazkiem tła (data URL do ~700 KB) mieszczą się z zapasem.
const MAKS_ZAPYTANIE = 2 * 1024 * 1024;
const LIMIT_CZASU_MS = 60000;
// Kompilacja jest synchroniczna i blokuje jedyny wątek — zlecenia idą zawsze
// PO KOLEI. Ile ich naraz przychodzi, ogranicza appserver (blokada w cache,
// bpp/motyw_kompilator.py), nie ten serwis.

function czytaj(katalog, plik) {
    return fs.readFileSync(path.join(katalog, plik), "utf8");
}

// Kontekst bez API Node'a — jak web worker w przeglądarce. dart-sass widzi
// brak `process` i działa w trybie przeglądarkowym.
function zbudujKontekst() {
    const piaskownica = {
        URL: URL,
        console: console,
        location: { href: "file:///" },
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        queueMicrotask: queueMicrotask,
    };
    piaskownica.self = piaskownica;
    piaskownica.globalThis = piaskownica;
    const ctx = vm.createContext(piaskownica);
    vm.runInContext(czytaj(KATALOG_DIST, "sass-przegladarka.js"), ctx);
    vm.runInContext(czytaj(KATALOG_JS, "motyw-konfig.js"), ctx);
    vm.runInContext(czytaj(KATALOG_JS, "motyw-kompilator.js"), ctx);
    ctx.ZRODLA = JSON.parse(czytaj(KATALOG_DIST, "motyw-zrodla-scss.json"));
    return ctx;
}

const ctx = zbudujKontekst();

class BladUstawien extends Error {
    constructor(bledy) {
        super(bledy.map((b) => b.komunikat).join(" "));
        this.bledy = bledy;
    }
}

function kompiluj(dane) {
    if (!dane || typeof dane !== "object" || typeof dane.konfig !== "object" || !dane.konfig) {
        throw new BladUstawien([{ pole: "konfig", komunikat: "Brak ustawień motywu." }]);
    }
    // Dane przechodzą do kontekstu jako JSON (kopia), nie jako obiekty Node'a.
    ctx.__wejscie = JSON.stringify({
        konfig: dane.konfig,
        czcionkiUrl: typeof dane.czcionkiUrl === "string" ? dane.czcionkiUrl : "",
    });
    const bledy = JSON.parse(
        vm.runInContext(
            "JSON.stringify(BppMotywKonfig.waliduj(JSON.parse(__wejscie).konfig, {bezNazwy: true}))",
            ctx,
            { timeout: LIMIT_CZASU_MS },
        ),
    );
    if (bledy.length) throw new BladUstawien(bledy);
    return vm.runInContext(
        "(function () { var w = JSON.parse(__wejscie);" +
            " return BppMotywKompilator.kompiluj(ZRODLA, w.konfig, {czcionkiUrl: w.czcionkiUrl}); })()",
        ctx,
        { timeout: LIMIT_CZASU_MS },
    );
}

function odpowiedzBledem(res, status, blad, bledy) {
    res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ blad: blad, bledy: bledy || [] }));
}

function obsluz(req, res) {
    if (req.method === "GET" && req.url === "/zdrowie") {
        res.writeHead(200, { "Content-Type": "text/plain" });
        res.end("ok");
        return;
    }
    if (req.method !== "POST" || req.url !== "/kompiluj") {
        odpowiedzBledem(res, 404, "Nieznany adres.");
        return;
    }

    const kawalki = [];
    let rozmiar = 0;
    let przerwane = false;
    req.on("data", (k) => {
        rozmiar += k.length;
        if (rozmiar > MAKS_ZAPYTANIE && !przerwane) {
            przerwane = true;
            odpowiedzBledem(res, 413, "Ustawienia są za duże.");
            req.destroy();
            return;
        }
        kawalki.push(k);
    });
    req.on("end", () => {
        if (przerwane) return;
        let dane;
        try {
            dane = JSON.parse(Buffer.concat(kawalki).toString("utf8"));
        } catch (e) {
            if (!(e instanceof SyntaxError)) throw e;
            odpowiedzBledem(res, 400, "Niepoprawny JSON.");
            return;
        }
        try {
            const css = kompiluj(dane);
            res.writeHead(200, { "Content-Type": "text/css; charset=utf-8" });
            res.end(css);
        } catch (e) {
            if (e instanceof BladUstawien) {
                odpowiedzBledem(res, 400, e.message, e.bledy);
                return;
            }
            // Błąd kompilacji / limit czasu: zgłaszamy, serwis działa dalej.
            console.error("Błąd kompilacji motywu:", e);
            odpowiedzBledem(res, 500, "Kompilacja motywu nie powiodła się: " + String(e.message || e).split("\n")[0]);
        }
    });
}

function trybJednorazowy() {
    const wejscie = fs.readFileSync(0, "utf8");
    try {
        process.stdout.write(kompiluj(JSON.parse(wejscie)));
    } catch (e) {
        const bledy = e instanceof BladUstawien ? e.bledy : [];
        process.stderr.write(JSON.stringify({ blad: String(e.message || e).split("\n")[0], bledy: bledy }));
        process.exitCode = 1;
    }
}

if (process.argv.includes("--jednorazowo")) {
    trybJednorazowy();
} else {
    http.createServer(obsluz).listen(PORT, () => {
        console.log("Kompilator motywów BPP nasłuchuje na porcie " + PORT);
    });
}
