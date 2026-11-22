// Dart Sass (czysty JS) dla konfiguratora wyglądu: kompiluje motyw
// w przeglądarce z tych samych plików SCSS co build. Ładowany wyłącznie
// przez worker konfiguratora (motyw-kompilator-worker.js), nie globalnie.
import * as sass from "sass";

self.BppSass = sass;
