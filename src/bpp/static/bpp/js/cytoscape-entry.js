// Entry esbuild dla strony eksploratora powiązań autorów.
// Buduje osobny bundle (dist/cytoscape-bundle.js) ładowany TYLKO na stronie
// grafu, żeby nie obciążać globalnego dist/bundle.js (~1.5 MB Cytoscape).
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import svg from "cytoscape-svg";

cytoscape.use(fcose);
cytoscape.use(svg); // eksport wektorowy (cy.svg())
window.cytoscape = cytoscape;
