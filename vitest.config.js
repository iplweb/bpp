import { defineConfig } from "vitest/config";

// Jednostkowe testy CZYSTEJ logiki JS BPP (parsing, geometria grafu,
// budowanie URL-i, formatowanie DjangoQL). NIE testujemy tu DOM-glue ani
// kodu bibliotek — `notifications.js` zyje i jest testowany w pakiecie
// django-channels-broadcast (52 testy QUnit w jego CI).
//
// Domyslne srodowisko = node: moduly powiazania/*.js to czysty ESM (import
// wprost). Pliki djangoql-*.js to globalne IIFE (standalone Django Media,
// nie da sie ich importowac jako modul) — testy dla nich deklaruja u siebie
// `// @vitest-environment jsdom`, zeby dostac `window`, po czym IIFE samo
// wystawia czyste funkcje na namespace globalny.
export default defineConfig({
    test: {
        globals: true,
        environment: "node",
        include: ["tests/js/**/*.test.js"],
    },
});
