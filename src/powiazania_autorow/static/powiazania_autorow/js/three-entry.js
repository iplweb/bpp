// Entry esbuild dla widoku 3D sieci powiązań. Buduje OSOBNY bundle
// (dist/three-bundle.js) ładowany TYLKO na stronie 3D — Three.js +
// 3d-force-graph to spory ciężar (~150 kB gzip), nie ma go na domyślnej
// (2D) stronie ani w globalnym bundlu.
import ForceGraph3D from "3d-force-graph";

import { init } from "./siec3d/index.js";

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
        init(ForceGraph3D);
    });
} else {
    init(ForceGraph3D);
}
