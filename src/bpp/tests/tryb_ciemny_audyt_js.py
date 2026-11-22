"""Skrypt audytu trybu ciemnego (JS uruchamiany w stronie przez Playwright).

Wspólny dla `bin/tryb-ciemny-audyt.py` i testu `test_tryb_ciemny.py` — leży
w `src/`, bo obraz testowy w CI nie zawiera katalogu `bin/`.
"""

JS_AUDYT = r"""
([progLuminancji, minRozmiar, korzen]) => {
  function parsujKolory(tekst) {
    const wynik = [];
    const re = /rgba?\(([^)]+)\)/g;
    let m;
    while ((m = re.exec(tekst)) !== null) {
      const cz = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat);
      wynik.push({r: cz[0], g: cz[1], b: cz[2], a: cz.length > 3 ? cz[3] : 1});
    }
    return wynik;
  }
  function lum(c) {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function nasycony(c) {
    const max = Math.max(c.r, c.g, c.b), min = Math.min(c.r, c.g, c.b);
    return max > 0 && (max - min) / max > 0.25;
  }
  function kontrast(a, b) {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function nalozenie(gora, dol) {
    const a = gora.a;
    return {
      r: gora.r * a + dol.r * (1 - a),
      g: gora.g * a + dol.g * (1 - a),
      b: gora.b * a + dol.b * (1 - a),
      a: 1,
    };
  }
  function opis(el) {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    const kl = (typeof el.className === "string" ? el.className : "")
      .trim().split(/\s+/).filter(Boolean).slice(0, 3);
    if (kl.length) s += "." + kl.join(".");
    const rodzic = el.parentElement;
    if (rodzic && rodzic !== document.body) {
      let p = rodzic.tagName.toLowerCase();
      if (rodzic.id) p += "#" + rodzic.id;
      const k2 = (typeof rodzic.className === "string" ? rodzic.className : "")
        .trim().split(/\s+/).filter(Boolean).slice(0, 2);
      if (k2.length) p += "." + k2.join(".");
      s = p + " > " + s;
    }
    return s;
  }
  function widoczny(el, st) {
    if (st.visibility === "hidden" || st.display === "none") return false;
    if (parseFloat(st.opacity) < 0.1) return false;
    let e = el;
    while (e && e !== document.documentElement) {
      const s = getComputedStyle(e);
      if (s.display === "none" || s.visibility === "hidden"
          || parseFloat(s.opacity) < 0.1) return false;
      e = e.parentElement;
    }
    return true;
  }
  // Efektywne tło: składamy warstwy od elementu w górę drzewa.
  function tloEfektywne(el) {
    const warstwy = [];
    let e = el;
    let obraz = false;
    while (e) {
      const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== "none") {
        const k = parsujKolory(s.backgroundImage);
        if (k.length) {
          warstwy.push(k[0]);
          if (k[0].a >= 0.95) break;
        } else {
          obraz = true;
        }
      }
      const c = parsujKolory(s.backgroundColor)[0];
      if (c && c.a > 0) {
        warstwy.push(c);
        if (c.a >= 0.95) break;
      }
      e = e.parentElement;
    }
    let wynik = {r: 255, g: 255, b: 255, a: 1};  // płótno przeglądarki
    if (!e) {
      // Doszliśmy do korzenia bez kryjącego tła: płótno wg color-scheme.
      const cs = getComputedStyle(document.documentElement).colorScheme || "";
      if (cs.includes("dark")) wynik = {r: 18, g: 18, b: 18, a: 1};
    }
    for (let i = warstwy.length - 1; i >= 0; i--) {
      wynik = nalozenie(warstwy[i], wynik);
    }
    return {kolor: wynik, obraz: obraz};
  }

  const plamy = [];
  const kontrastLista = [];
  const widziane = new Set();
  // `korzen` (opcjonalny selektor) zawęża audyt do jednego poddrzewa — np.
  // wiersza tabeli w stanie :hover. Sam korzeń też jest sprawdzany.
  const start = korzen ? document.querySelector(korzen) : document.body;
  if (!start) return {plamy: [], kontrast: []};
  const wszystkie = korzen
    ? [start, ...start.querySelectorAll("*")]
    : document.querySelectorAll("body *");
  for (const el of wszystkie) {
    if (["SCRIPT", "STYLE", "NOSCRIPT", "BR", "OPTION"].includes(el.tagName)) {
      continue;
    }
    const st = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (!widoczny(el, st)) continue;

    // 1) Plamy: własne tło elementu.
    if (r.width > minRozmiar && r.height > minRozmiar
        && !["IMG", "CANVAS", "VIDEO", "IFRAME"].includes(el.tagName)) {
      let kolory = parsujKolory(st.backgroundColor).filter((c) => c.a >= 0.5);
      // Tło wykresów SVG (Plotly: rect.bg) to `fill` prostokąta.
      if (el.tagName === "rect" && st.fillOpacity !== "0") {
        kolory = kolory.concat(parsujKolory(st.fill).filter((c) => c.a >= 0.5));
      }
      if (st.backgroundImage && st.backgroundImage.includes("gradient")) {
        const zGradientu = parsujKolory(st.backgroundImage).filter((c) => c.a >= 0.5);
        // Gradient z wyraźnie barwnym kolorem to skala danych (plakietki
        // „temperatury” PKDaut), nie tło pod treścią — pomijamy.
        if (!zGradientu.some(nasycony)) kolory = kolory.concat(zGradientu);
      }
      for (const c of kolory) {
        const l = lum(c);
        if (l > progLuminancji) {
          plamy.push({
            element: opis(el),
            rozmiar: Math.round(r.width) + "x" + Math.round(r.height),
            tlo: `rgb(${c.r},${c.g},${c.b})`,
            luminancja: Math.round(l * 100) / 100,
          });
          break;
        }
      }
    }

    // 2) Kontrast tekstu (tylko elementy z własnym, niepustym tekstem).
    let maTekst = false;
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim().length > 1) {
        maTekst = true;
        break;
      }
    }
    if (!maTekst) continue;
    // Tekst SVG (wykresy Plotly itp.) ma kolor w `fill`, nie w `color`.
    const svgTekst = el.namespaceURI === "http://www.w3.org/2000/svg";
    const kolorTekstu = parsujKolory(svgTekst ? st.fill : st.color)[0];
    if (!kolorTekstu || kolorTekstu.a < 0.3) continue;
    const tlo = tloEfektywne(el);
    if (tlo.obraz) continue;  // tło z obrazka — nie umiemy ocenić
    const tekst = nalozenie(kolorTekstu, tlo.kolor);
    const k = kontrast(tekst, tlo.kolor);
    const rozmiar = parseFloat(st.fontSize);
    const gruby = parseInt(st.fontWeight, 10) >= 700;
    const duzy = rozmiar >= 24 || (gruby && rozmiar >= 18.66);
    const prog = duzy ? 3 : 4.5;
    if (k < prog) {
      const klucz = opis(el) + "|" + st.color;
      if (widziane.has(klucz)) continue;
      widziane.add(klucz);
      kontrastLista.push({
        element: opis(el),
        tekst: el.textContent.trim().replace(/\s+/g, " ").slice(0, 40),
        kolor: svgTekst ? st.fill : st.color,
        tlo: `rgb(${Math.round(tlo.kolor.r)},${Math.round(tlo.kolor.g)},`
          + `${Math.round(tlo.kolor.b)})`,
        kontrast: Math.round(k * 100) / 100,
      });
    }
  }
  return {plamy: plamy, kontrast: kontrastLista};
}
"""
