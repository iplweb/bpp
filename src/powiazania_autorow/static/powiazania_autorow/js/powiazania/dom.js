// Drobne helpery DOM budowane bez innerHTML — etykiety pochodzą z nazwisk
// autorów (dane z bazy), więc nie wstrzykujemy ich jako HTML (XSS-safe).

// Usuwa wszystkie dzieci elementu.
export function wyczysc(el) {
    while (el.firstChild) {
        el.removeChild(el.firstChild);
    }
}

// Tworzy link akcji (blokowy). `zewnetrzny` -> nowa karta + rel=noopener.
export function linkAkcja(href, text, zewnetrzny) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.style.display = "block";
    a.style.marginTop = "4px";
    if (zewnetrzny) {
        a.target = "_blank";
        a.rel = "noopener";
    }
    return a;
}

// Wymusza pobranie pliku spod `href` pod nazwą `nazwa`.
export function pobierzPlik(href, nazwa) {
    const a = document.createElement("a");
    a.href = href;
    a.download = nazwa;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
