// OGMA Visualization of Author Connections
// Generated from powiazania_autorow database
// Total authors: 150, Total connections: 588

// This script assumes OGMA is loaded (either via CDN or local installation)
// Example CDN: <script src="https://cdn.jsdelivr.net/npm/@linkurious/ogma@4/dist/ogma.min.js"></script>

(async function() {
  // Check if OGMA is available
  if (typeof Ogma === 'undefined') {
    console.error('OGMA library is not loaded. Please include OGMA before this script.');
    return;
  }

  // Create container if it doesn't exist
  let container = document.getElementById('graph-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'graph-container';
    container.style.width = '100%';
    container.style.height = '800px';
    container.style.border = '1px solid #ccc';
    document.body.appendChild(container);
  }

  // Initialize OGMA
  const ogma = new Ogma({
    container: 'graph-container',
    options: {
      backgroundColor: '#ffffff'
    }
  });

  // Graph data
  const graphData = {
    nodes: [
  {
    "id": 0,
    "attributes": {
      "text": "Ma\u0142gorzata Juszkiewicz",
      "x": 500.0,
      "y": 0.0,
      "radius": 10
    }
  },
  {
    "id": 1,
    "attributes": {
      "text": "Jacek Karamon",
      "x": 499.56,
      "y": 20.94,
      "radius": 10
    }
  },
  {
    "id": 2,
    "attributes": {
      "text": "Agnieszka Nawrocka",
      "x": 498.25,
      "y": 41.84,
      "radius": 10
    }
  },
  {
    "id": 3,
    "attributes": {
      "text": "Beata Kozak",
      "x": 496.06,
      "y": 62.67,
      "radius": 10
    }
  },
  {
    "id": 4,
    "attributes": {
      "text": "Joanna Maj-Paluch",
      "x": 493.0,
      "y": 83.38,
      "radius": 10
    }
  },
  {
    "id": 5,
    "attributes": {
      "text": "Magdalena Stachnik",
      "x": 489.07,
      "y": 103.96,
      "radius": 10
    }
  },
  {
    "id": 6,
    "attributes": {
      "text": "Katarzyna Dudek",
      "x": 484.29,
      "y": 124.34,
      "radius": 10
    }
  },
  {
    "id": 7,
    "attributes": {
      "text": "Miros\u0142aw R\u00f3\u017cycki",
      "x": 478.66,
      "y": 144.52,
      "radius": 10
    }
  },
  {
    "id": 8,
    "attributes": {
      "text": "Joanna Sajewicz-Krukowska",
      "x": 472.19,
      "y": 164.43,
      "radius": 10
    }
  },
  {
    "id": 9,
    "attributes": {
      "text": "Dariusz Bednarek",
      "x": 464.89,
      "y": 184.06,
      "radius": 10
    }
  },
  {
    "id": 10,
    "attributes": {
      "text": "Marcin Smreczak",
      "x": 456.77,
      "y": 203.37,
      "radius": 10
    }
  },
  {
    "id": 11,
    "attributes": {
      "text": "Olimpia Kursa",
      "x": 447.86,
      "y": 222.32,
      "radius": 10
    }
  },
  {
    "id": 12,
    "attributes": {
      "text": "Anna Gajda",
      "x": 438.15,
      "y": 240.88,
      "radius": 10
    }
  },
  {
    "id": 13,
    "attributes": {
      "text": "Monika Szyma\u0144ska - Czerwi\u0144ska",
      "x": 427.68,
      "y": 259.01,
      "radius": 10
    }
  },
  {
    "id": 14,
    "attributes": {
      "text": "Aneta Be\u0142cik",
      "x": 416.46,
      "y": 276.7,
      "radius": 10
    }
  },
  {
    "id": 15,
    "attributes": {
      "text": "Artur Rze\u017cutka",
      "x": 404.51,
      "y": 293.89,
      "radius": 10
    }
  },
  {
    "id": 16,
    "attributes": {
      "text": "Agnieszka Jasik",
      "x": 391.85,
      "y": 310.57,
      "radius": 10
    }
  },
  {
    "id": 17,
    "attributes": {
      "text": "Hanna Czekaj",
      "x": 378.5,
      "y": 326.71,
      "radius": 10
    }
  },
  {
    "id": 18,
    "attributes": {
      "text": "Tomasz \u015aniegocki",
      "x": 364.48,
      "y": 342.27,
      "radius": 10
    }
  },
  {
    "id": 19,
    "attributes": {
      "text": "Jerzy Rola",
      "x": 349.83,
      "y": 357.24,
      "radius": 10
    }
  },
  {
    "id": 20,
    "attributes": {
      "text": "Andrzej Posyniak",
      "x": 334.57,
      "y": 371.57,
      "radius": 10
    }
  },
  {
    "id": 21,
    "attributes": {
      "text": "Sylwia Stypu\u0142a-Tr\u0119bas",
      "x": 318.71,
      "y": 385.26,
      "radius": 10
    }
  },
  {
    "id": 22,
    "attributes": {
      "text": "Piotr Jedziniak",
      "x": 302.3,
      "y": 398.26,
      "radius": 10
    }
  },
  {
    "id": 23,
    "attributes": {
      "text": "Ma\u0142gorzata Pomorska-M\u00f3l",
      "x": 285.36,
      "y": 410.57,
      "radius": 10
    }
  },
  {
    "id": 24,
    "attributes": {
      "text": "Jacek Sroka",
      "x": 267.91,
      "y": 422.16,
      "radius": 10
    }
  },
  {
    "id": 25,
    "attributes": {
      "text": "Katarzyna Podg\u00f3rska",
      "x": 250.0,
      "y": 433.01,
      "radius": 10
    }
  },
  {
    "id": 26,
    "attributes": {
      "text": "Krzysztof \u015amietanka",
      "x": 231.65,
      "y": 443.1,
      "radius": 10
    }
  },
  {
    "id": 27,
    "attributes": {
      "text": "Anna Szczotka-Bochniarz",
      "x": 212.89,
      "y": 452.41,
      "radius": 10
    }
  },
  {
    "id": 28,
    "attributes": {
      "text": "Weronika Piotrowska",
      "x": 193.76,
      "y": 460.93,
      "radius": 10
    }
  },
  {
    "id": 29,
    "attributes": {
      "text": "Anna Kycko",
      "x": 174.29,
      "y": 468.64,
      "radius": 10
    }
  },
  {
    "id": 30,
    "attributes": {
      "text": "Monika Przenios\u0142o-Siwczy\u0144ska",
      "x": 154.51,
      "y": 475.53,
      "radius": 10
    }
  },
  {
    "id": 31,
    "attributes": {
      "text": "Weronika Koza",
      "x": 134.46,
      "y": 481.58,
      "radius": 10
    }
  },
  {
    "id": 32,
    "attributes": {
      "text": "Marcin Weiner",
      "x": 114.18,
      "y": 486.79,
      "radius": 10
    }
  },
  {
    "id": 33,
    "attributes": {
      "text": "Agnieszka P\u0119kala-Safi\u0144ska",
      "x": 93.69,
      "y": 491.14,
      "radius": 10
    }
  },
  {
    "id": 34,
    "attributes": {
      "text": "Micha\u0142 Reichert",
      "x": 73.04,
      "y": 494.64,
      "radius": 10
    }
  },
  {
    "id": 35,
    "attributes": {
      "text": "Zbigniew Sieradzki",
      "x": 52.26,
      "y": 497.26,
      "radius": 10
    }
  },
  {
    "id": 36,
    "attributes": {
      "text": "Tomasz Grenda",
      "x": 31.4,
      "y": 499.01,
      "radius": 10
    }
  },
  {
    "id": 37,
    "attributes": {
      "text": "Sebastian Maszewski",
      "x": 10.47,
      "y": 499.89,
      "radius": 10
    }
  },
  {
    "id": 38,
    "attributes": {
      "text": "Justyna Opolska",
      "x": -10.47,
      "y": 499.89,
      "radius": 10
    }
  },
  {
    "id": 39,
    "attributes": {
      "text": "Artur Jab\u0142o\u0144ski",
      "x": -31.4,
      "y": 499.01,
      "radius": 10
    }
  },
  {
    "id": 40,
    "attributes": {
      "text": "Natalia Sty\u015b-Fijo\u0142",
      "x": -52.26,
      "y": 497.26,
      "radius": 10
    }
  },
  {
    "id": 41,
    "attributes": {
      "text": "Jadwiga Piskorska-Pliszczy\u0144ska",
      "x": -73.04,
      "y": 494.64,
      "radius": 10
    }
  },
  {
    "id": 42,
    "attributes": {
      "text": "Grzegorz Wo\u017aniakowski",
      "x": -93.69,
      "y": 491.14,
      "radius": 10
    }
  },
  {
    "id": 43,
    "attributes": {
      "text": "Ewelina Szacawa",
      "x": -114.18,
      "y": 486.79,
      "radius": 10
    }
  },
  {
    "id": 44,
    "attributes": {
      "text": "Monika Olszewska-Tomczyk",
      "x": -134.46,
      "y": 481.58,
      "radius": 10
    }
  },
  {
    "id": 45,
    "attributes": {
      "text": "Ewa Bilska-Zaj\u0105c",
      "x": -154.51,
      "y": 475.53,
      "radius": 10
    }
  },
  {
    "id": 46,
    "attributes": {
      "text": "Magdalena Zaj\u0105c",
      "x": -174.29,
      "y": 468.64,
      "radius": 10
    }
  },
  {
    "id": 47,
    "attributes": {
      "text": "Ewelina Czy\u017cewska-Dors",
      "x": -193.76,
      "y": 460.93,
      "radius": 10
    }
  },
  {
    "id": 48,
    "attributes": {
      "text": "Zbigniew Osi\u0144ski",
      "x": -212.89,
      "y": 452.41,
      "radius": 10
    }
  },
  {
    "id": 49,
    "attributes": {
      "text": "Anna Piku\u0142a",
      "x": -231.65,
      "y": 443.1,
      "radius": 10
    }
  },
  {
    "id": 50,
    "attributes": {
      "text": "Jacek \u017bmudzki",
      "x": -250.0,
      "y": 433.01,
      "radius": 10
    }
  },
  {
    "id": 51,
    "attributes": {
      "text": "Karolina Tarasiuk",
      "x": -267.91,
      "y": 422.16,
      "radius": 10
    }
  },
  {
    "id": 52,
    "attributes": {
      "text": "Monika Krajewska-W\u0119dzina",
      "x": -285.36,
      "y": 410.57,
      "radius": 10
    }
  },
  {
    "id": 53,
    "attributes": {
      "text": "Lidia Radko",
      "x": -302.3,
      "y": 398.26,
      "radius": 10
    }
  },
  {
    "id": 54,
    "attributes": {
      "text": "Wojciech Socha",
      "x": -318.71,
      "y": 385.26,
      "radius": 10
    }
  },
  {
    "id": 55,
    "attributes": {
      "text": "Tomasz Cencek",
      "x": -334.57,
      "y": 371.57,
      "radius": 10
    }
  },
  {
    "id": 56,
    "attributes": {
      "text": "\u0141ukasz Bocian",
      "x": -349.83,
      "y": 357.24,
      "radius": 10
    }
  },
  {
    "id": 57,
    "attributes": {
      "text": "Maciej Kochanowski",
      "x": -364.48,
      "y": 342.27,
      "radius": 10
    }
  },
  {
    "id": 58,
    "attributes": {
      "text": "Anna Lisowska",
      "x": -378.5,
      "y": 326.71,
      "radius": 10
    }
  },
  {
    "id": 59,
    "attributes": {
      "text": "Szczepan Miko\u0142ajczyk",
      "x": -391.85,
      "y": 310.57,
      "radius": 10
    }
  },
  {
    "id": 60,
    "attributes": {
      "text": "Ma\u0142gorzata Samorek-Pier\u00f3g",
      "x": -404.51,
      "y": 293.89,
      "radius": 10
    }
  },
  {
    "id": 61,
    "attributes": {
      "text": "Jacek Ku\u017amak",
      "x": -416.46,
      "y": 276.7,
      "radius": 10
    }
  },
  {
    "id": 62,
    "attributes": {
      "text": "Kinga Wieczorek",
      "x": -427.68,
      "y": 259.01,
      "radius": 10
    }
  },
  {
    "id": 63,
    "attributes": {
      "text": "Aleksandra \u015amia\u0142owska-W\u0119gli\u0144ska",
      "x": -438.15,
      "y": 240.88,
      "radius": 10
    }
  },
  {
    "id": 64,
    "attributes": {
      "text": "Marek Pajurek",
      "x": -447.86,
      "y": 222.32,
      "radius": 10
    }
  },
  {
    "id": 65,
    "attributes": {
      "text": "Aleksandra Grelik",
      "x": -456.77,
      "y": 203.37,
      "radius": 10
    }
  },
  {
    "id": 66,
    "attributes": {
      "text": "Krzysztof Szulowski",
      "x": -464.89,
      "y": 184.06,
      "radius": 10
    }
  },
  {
    "id": 67,
    "attributes": {
      "text": "Nina Kozie\u0142",
      "x": -472.19,
      "y": 164.43,
      "radius": 10
    }
  },
  {
    "id": 68,
    "attributes": {
      "text": "Edyta \u015awi\u0119to\u0144",
      "x": -478.66,
      "y": 144.52,
      "radius": 10
    }
  },
  {
    "id": 69,
    "attributes": {
      "text": "Ewelina Skrzypiec",
      "x": -484.29,
      "y": 124.34,
      "radius": 10
    }
  },
  {
    "id": 70,
    "attributes": {
      "text": "Agnieszka Stolarek",
      "x": -489.07,
      "y": 103.96,
      "radius": 10
    }
  },
  {
    "id": 71,
    "attributes": {
      "text": "Maciej Frant",
      "x": -493.0,
      "y": 83.38,
      "radius": 10
    }
  },
  {
    "id": 72,
    "attributes": {
      "text": "Katarzyna Gr\u0105dziel-Krukowska",
      "x": -496.06,
      "y": 62.67,
      "radius": 10
    }
  },
  {
    "id": 73,
    "attributes": {
      "text": "Anna Weiner",
      "x": -498.25,
      "y": 41.84,
      "radius": 10
    }
  },
  {
    "id": 74,
    "attributes": {
      "text": "Pawe\u0142 Tr\u0119bas",
      "x": -499.56,
      "y": 20.94,
      "radius": 10
    }
  },
  {
    "id": 75,
    "attributes": {
      "text": "Renata Kwit",
      "x": -500.0,
      "y": 0.0,
      "radius": 10
    }
  },
  {
    "id": 76,
    "attributes": {
      "text": "Joanna D\u0105browska",
      "x": -499.56,
      "y": -20.94,
      "radius": 10
    }
  },
  {
    "id": 77,
    "attributes": {
      "text": "Anna Lalak",
      "x": -498.25,
      "y": -41.84,
      "radius": 10
    }
  },
  {
    "id": 78,
    "attributes": {
      "text": "Dariusz Wasyl",
      "x": -496.06,
      "y": -62.67,
      "radius": 10
    }
  },
  {
    "id": 79,
    "attributes": {
      "text": "Katarzyna Doma\u0144ska-Blicharz",
      "x": -493.0,
      "y": -83.38,
      "radius": 10
    }
  },
  {
    "id": 80,
    "attributes": {
      "text": "Jolanta Zdybel",
      "x": -489.07,
      "y": -103.96,
      "radius": 10
    }
  },
  {
    "id": 81,
    "attributes": {
      "text": "Magdalena Goldsztejn",
      "x": -484.29,
      "y": -124.34,
      "radius": 10
    }
  },
  {
    "id": 82,
    "attributes": {
      "text": "Arkadiusz Dors",
      "x": -478.66,
      "y": -144.52,
      "radius": 10
    }
  },
  {
    "id": 83,
    "attributes": {
      "text": "Emilia Mikos-Wojewoda",
      "x": -472.19,
      "y": -164.43,
      "radius": 10
    }
  },
  {
    "id": 84,
    "attributes": {
      "text": "Ewelina Patyra",
      "x": -464.89,
      "y": -184.06,
      "radius": 10
    }
  },
  {
    "id": 85,
    "attributes": {
      "text": "Dominika Wojdat",
      "x": -456.77,
      "y": -203.37,
      "radius": 10
    }
  },
  {
    "id": 86,
    "attributes": {
      "text": "Wojciech Kozdru\u0144",
      "x": -447.86,
      "y": -222.32,
      "radius": 10
    }
  },
  {
    "id": 87,
    "attributes": {
      "text": "Kinga Zar\u0119ba-Marchewka",
      "x": -438.15,
      "y": -240.88,
      "radius": 10
    }
  },
  {
    "id": 88,
    "attributes": {
      "text": "Ma\u0142gorzata Warenik-Bany",
      "x": -427.68,
      "y": -259.01,
      "radius": 10
    }
  },
  {
    "id": 89,
    "attributes": {
      "text": "Anna Zi\u0119tek-Barszcz",
      "x": -416.46,
      "y": -276.7,
      "radius": 10
    }
  },
  {
    "id": 90,
    "attributes": {
      "text": "Ewelina Iwan",
      "x": -404.51,
      "y": -293.89,
      "radius": 10
    }
  },
  {
    "id": 91,
    "attributes": {
      "text": "Weronika Korpysa-Dzirba",
      "x": -391.85,
      "y": -310.57,
      "radius": 10
    }
  },
  {
    "id": 92,
    "attributes": {
      "text": "Jowita Samanta Niczyporuk",
      "x": -378.5,
      "y": -326.71,
      "radius": 10
    }
  },
  {
    "id": 93,
    "attributes": {
      "text": "Ewelina Antolak",
      "x": -364.48,
      "y": -342.27,
      "radius": 10
    }
  },
  {
    "id": 94,
    "attributes": {
      "text": "Zygmunt Pejsak",
      "x": -349.83,
      "y": -357.24,
      "radius": 10
    }
  },
  {
    "id": 95,
    "attributes": {
      "text": "Marek Matras",
      "x": -334.57,
      "y": -371.57,
      "radius": 10
    }
  },
  {
    "id": 96,
    "attributes": {
      "text": "Krzysztof Niemczuk",
      "x": -318.71,
      "y": -385.26,
      "radius": 10
    }
  },
  {
    "id": 97,
    "attributes": {
      "text": "Anna Or\u0142owska",
      "x": -302.3,
      "y": -398.26,
      "radius": 10
    }
  },
  {
    "id": 98,
    "attributes": {
      "text": "Magdalena Larska",
      "x": -285.36,
      "y": -410.57,
      "radius": 10
    }
  },
  {
    "id": 99,
    "attributes": {
      "text": "Marek Lipiec",
      "x": -267.91,
      "y": -422.16,
      "radius": 10
    }
  },
  {
    "id": 100,
    "attributes": {
      "text": "Paulina Pasim",
      "x": -250.0,
      "y": -433.01,
      "radius": 10
    }
  },
  {
    "id": 101,
    "attributes": {
      "text": "Krzysztof Kwiatek",
      "x": -231.65,
      "y": -443.1,
      "radius": 10
    }
  },
  {
    "id": 102,
    "attributes": {
      "text": "Karolina Piekarska",
      "x": -212.89,
      "y": -452.41,
      "radius": 10
    }
  },
  {
    "id": 103,
    "attributes": {
      "text": "Iwona Matraszek-\u017buchowska",
      "x": -193.76,
      "y": -460.93,
      "radius": 10
    }
  },
  {
    "id": 104,
    "attributes": {
      "text": "Maja Chy\u0142ek-Purcha\u0142a",
      "x": -174.29,
      "y": -468.64,
      "radius": 10
    }
  },
  {
    "id": 105,
    "attributes": {
      "text": "Pawe\u0142 Ma\u0142agocki",
      "x": -154.51,
      "y": -475.53,
      "radius": 10
    }
  },
  {
    "id": 106,
    "attributes": {
      "text": "Wojciech Pietro\u0144",
      "x": -134.46,
      "y": -481.58,
      "radius": 10
    }
  },
  {
    "id": 107,
    "attributes": {
      "text": "Jacek Osek",
      "x": -114.18,
      "y": -486.79,
      "radius": 10
    }
  },
  {
    "id": 108,
    "attributes": {
      "text": "Magdalena Skar\u017cy\u0144ska",
      "x": -93.69,
      "y": -491.14,
      "radius": 10
    }
  },
  {
    "id": 109,
    "attributes": {
      "text": "Milena Sk\u00f3ra",
      "x": -73.04,
      "y": -494.64,
      "radius": 10
    }
  },
  {
    "id": 110,
    "attributes": {
      "text": "Ewa Borzym",
      "x": -52.26,
      "y": -497.26,
      "radius": 10
    }
  },
  {
    "id": 111,
    "attributes": {
      "text": "Monika Olech",
      "x": -31.4,
      "y": -499.01,
      "radius": 10
    }
  },
  {
    "id": 112,
    "attributes": {
      "text": "Krzysztof Wyrostek",
      "x": -10.47,
      "y": -499.89,
      "radius": 10
    }
  },
  {
    "id": 113,
    "attributes": {
      "text": "Marek Walczak",
      "x": 10.47,
      "y": -499.89,
      "radius": 10
    }
  },
  {
    "id": 114,
    "attributes": {
      "text": "Ma\u0142gorzata Gbylik-Sikorska",
      "x": 31.4,
      "y": -499.01,
      "radius": 10
    }
  },
  {
    "id": 115,
    "attributes": {
      "text": "Arkadiusz Bomba",
      "x": 52.26,
      "y": -497.26,
      "radius": 10
    }
  },
  {
    "id": 116,
    "attributes": {
      "text": "Teresa K\u0142ape\u0107",
      "x": 73.04,
      "y": -494.64,
      "radius": 10
    }
  },
  {
    "id": 117,
    "attributes": {
      "text": "Angelina W\u00f3jcik-Fatla",
      "x": 93.69,
      "y": -491.14,
      "radius": 10
    }
  },
  {
    "id": 118,
    "attributes": {
      "text": "Krzysztof Anusz",
      "x": 114.18,
      "y": -486.79,
      "radius": 10
    }
  },
  {
    "id": 119,
    "attributes": {
      "text": "Anna Didkowska",
      "x": 134.46,
      "y": -481.58,
      "radius": 10
    }
  },
  {
    "id": 120,
    "attributes": {
      "text": "Blanka Or\u0142owska",
      "x": 154.51,
      "y": -475.53,
      "radius": 10
    }
  },
  {
    "id": 121,
    "attributes": {
      "text": "Violetta Zaj\u0105c",
      "x": 174.29,
      "y": -468.64,
      "radius": 10
    }
  },
  {
    "id": 122,
    "attributes": {
      "text": "Jacek Dutkiewicz",
      "x": 193.76,
      "y": -460.93,
      "radius": 10
    }
  },
  {
    "id": 123,
    "attributes": {
      "text": "Micha\u0142 Krzysiak",
      "x": 212.89,
      "y": -452.41,
      "radius": 10
    }
  },
  {
    "id": 124,
    "attributes": {
      "text": "Jan Wi\u015bniewski",
      "x": 231.65,
      "y": -443.1,
      "radius": 10
    }
  },
  {
    "id": 125,
    "attributes": {
      "text": "Wanda Olech-Piasecka",
      "x": 250.0,
      "y": -433.01,
      "radius": 10
    }
  },
  {
    "id": 126,
    "attributes": {
      "text": "Bo\u017cena Jarosz",
      "x": 267.91,
      "y": -422.16,
      "radius": 10
    }
  },
  {
    "id": 127,
    "attributes": {
      "text": "Robert Kieszko",
      "x": 285.36,
      "y": -410.57,
      "radius": 10
    }
  },
  {
    "id": 128,
    "attributes": {
      "text": "Pawe\u0142 Krawczyk",
      "x": 302.3,
      "y": -398.26,
      "radius": 10
    }
  },
  {
    "id": 129,
    "attributes": {
      "text": "Janusz Milanowski",
      "x": 318.71,
      "y": -385.26,
      "radius": 10
    }
  },
  {
    "id": 130,
    "attributes": {
      "text": "Anna Rolska-Kopi\u0144ska",
      "x": 334.57,
      "y": -371.57,
      "radius": 10
    }
  },
  {
    "id": 131,
    "attributes": {
      "text": "Micha\u0142 Szczyrek",
      "x": 349.83,
      "y": -357.24,
      "radius": 10
    }
  },
  {
    "id": 132,
    "attributes": {
      "text": "Izabela Chmielewska",
      "x": 364.48,
      "y": -342.27,
      "radius": 10
    }
  },
  {
    "id": 133,
    "attributes": {
      "text": "Tomasz Kucharczyk",
      "x": 378.5,
      "y": -326.71,
      "radius": 10
    }
  },
  {
    "id": 134,
    "attributes": {
      "text": "Anna Grenda",
      "x": 391.85,
      "y": -310.57,
      "radius": 10
    }
  },
  {
    "id": 135,
    "attributes": {
      "text": "Ma\u0142gorzata Fr\u0105k",
      "x": 404.51,
      "y": -293.89,
      "radius": 10
    }
  },
  {
    "id": 136,
    "attributes": {
      "text": "Anna Kloc",
      "x": 416.46,
      "y": -276.7,
      "radius": 10
    }
  },
  {
    "id": 137,
    "attributes": {
      "text": "Ewa Cisak",
      "x": 427.68,
      "y": -259.01,
      "radius": 10
    }
  },
  {
    "id": 138,
    "attributes": {
      "text": "Anna Sawczyn-Doma\u0144ska",
      "x": 438.15,
      "y": -240.88,
      "radius": 10
    }
  },
  {
    "id": 139,
    "attributes": {
      "text": "Piotr Skowron",
      "x": 447.86,
      "y": -222.32,
      "radius": 10
    }
  },
  {
    "id": 140,
    "attributes": {
      "text": "Grzegorz Siebielec",
      "x": 456.77,
      "y": -203.37,
      "radius": 10
    }
  },
  {
    "id": 141,
    "attributes": {
      "text": "Tamara Jadczyszyn",
      "x": 464.89,
      "y": -184.06,
      "radius": 10
    }
  },
  {
    "id": 142,
    "attributes": {
      "text": "Ewa Augustynowicz-Kope\u0107",
      "x": 472.19,
      "y": -164.43,
      "radius": 10
    }
  },
  {
    "id": 143,
    "attributes": {
      "text": "Piotr Domaradzki",
      "x": 478.66,
      "y": -144.52,
      "radius": 10
    }
  },
  {
    "id": 144,
    "attributes": {
      "text": "Wojciech Bielecki",
      "x": 484.29,
      "y": -124.34,
      "radius": 10
    }
  },
  {
    "id": 145,
    "attributes": {
      "text": "Mariusz Florek",
      "x": 489.07,
      "y": -103.96,
      "radius": 10
    }
  },
  {
    "id": 146,
    "attributes": {
      "text": "Piotr Ska\u0142ecki",
      "x": 493.0,
      "y": -83.38,
      "radius": 10
    }
  },
  {
    "id": 147,
    "attributes": {
      "text": "Marek Kowalczyk",
      "x": 496.06,
      "y": -62.67,
      "radius": 10
    }
  },
  {
    "id": 148,
    "attributes": {
      "text": "Agnieszka Kaliniak-Dziura",
      "x": 498.25,
      "y": -41.84,
      "radius": 10
    }
  },
  {
    "id": 149,
    "attributes": {
      "text": "Sylwia Brzezi\u0144ska",
      "x": 499.56,
      "y": -20.94,
      "radius": 10
    }
  }
],
    edges: [
  {
    "source": 1,
    "target": 55,
    "attributes": {
      "width": 5.0,
      "color": "rgba(100, 100, 100, 0.8)",
      "label": "73 publikacji"
    }
  },
  {
    "source": 45,
    "target": 55,
    "attributes": {
      "width": 3.89,
      "color": "rgba(100, 100, 100, 0.6520547945205479)",
      "label": "55 publikacji"
    }
  },
  {
    "source": 24,
    "target": 55,
    "attributes": {
      "width": 3.77,
      "color": "rgba(100, 100, 100, 0.6356164383561644)",
      "label": "53 publikacji"
    }
  },
  {
    "source": 1,
    "target": 24,
    "attributes": {
      "width": 3.58,
      "color": "rgba(100, 100, 100, 0.6109589041095891)",
      "label": "50 publikacji"
    }
  },
  {
    "source": 62,
    "target": 107,
    "attributes": {
      "width": 3.52,
      "color": "rgba(100, 100, 100, 0.6027397260273972)",
      "label": "49 publikacji"
    }
  },
  {
    "source": 1,
    "target": 45,
    "attributes": {
      "width": 3.46,
      "color": "rgba(100, 100, 100, 0.5945205479452055)",
      "label": "48 publikacji"
    }
  },
  {
    "source": 7,
    "target": 55,
    "attributes": {
      "width": 3.09,
      "color": "rgba(100, 100, 100, 0.5452054794520548)",
      "label": "42 publikacji"
    }
  },
  {
    "source": 84,
    "target": 101,
    "attributes": {
      "width": 2.9,
      "color": "rgba(100, 100, 100, 0.5205479452054795)",
      "label": "39 publikacji"
    }
  },
  {
    "source": 24,
    "target": 45,
    "attributes": {
      "width": 2.78,
      "color": "rgba(100, 100, 100, 0.5041095890410959)",
      "label": "37 publikacji"
    }
  },
  {
    "source": 12,
    "target": 114,
    "attributes": {
      "width": 2.72,
      "color": "rgba(100, 100, 100, 0.49589041095890407)",
      "label": "36 publikacji"
    }
  },
  {
    "source": 7,
    "target": 45,
    "attributes": {
      "width": 2.72,
      "color": "rgba(100, 100, 100, 0.49589041095890407)",
      "label": "36 publikacji"
    }
  },
  {
    "source": 55,
    "target": 80,
    "attributes": {
      "width": 2.66,
      "color": "rgba(100, 100, 100, 0.4876712328767123)",
      "label": "35 publikacji"
    }
  },
  {
    "source": 6,
    "target": 9,
    "attributes": {
      "width": 2.6,
      "color": "rgba(100, 100, 100, 0.4794520547945205)",
      "label": "34 publikacji"
    }
  },
  {
    "source": 1,
    "target": 7,
    "attributes": {
      "width": 2.6,
      "color": "rgba(100, 100, 100, 0.4794520547945205)",
      "label": "34 publikacji"
    }
  },
  {
    "source": 10,
    "target": 97,
    "attributes": {
      "width": 2.47,
      "color": "rgba(100, 100, 100, 0.46301369863013697)",
      "label": "32 publikacji"
    }
  },
  {
    "source": 1,
    "target": 80,
    "attributes": {
      "width": 2.41,
      "color": "rgba(100, 100, 100, 0.45479452054794517)",
      "label": "31 publikacji"
    }
  },
  {
    "source": 78,
    "target": 108,
    "attributes": {
      "width": 2.41,
      "color": "rgba(100, 100, 100, 0.45479452054794517)",
      "label": "31 publikacji"
    }
  },
  {
    "source": 46,
    "target": 78,
    "attributes": {
      "width": 2.41,
      "color": "rgba(100, 100, 100, 0.45479452054794517)",
      "label": "31 publikacji"
    }
  },
  {
    "source": 17,
    "target": 86,
    "attributes": {
      "width": 2.35,
      "color": "rgba(100, 100, 100, 0.4465753424657534)",
      "label": "30 publikacji"
    }
  },
  {
    "source": 59,
    "target": 64,
    "attributes": {
      "width": 2.35,
      "color": "rgba(100, 100, 100, 0.4465753424657534)",
      "label": "30 publikacji"
    }
  },
  {
    "source": 47,
    "target": 82,
    "attributes": {
      "width": 2.29,
      "color": "rgba(100, 100, 100, 0.4383561643835616)",
      "label": "29 publikacji"
    }
  },
  {
    "source": 13,
    "target": 96,
    "attributes": {
      "width": 2.29,
      "color": "rgba(100, 100, 100, 0.4383561643835616)",
      "label": "29 publikacji"
    }
  },
  {
    "source": 24,
    "target": 80,
    "attributes": {
      "width": 2.23,
      "color": "rgba(100, 100, 100, 0.4301369863013699)",
      "label": "28 publikacji"
    }
  },
  {
    "source": 55,
    "target": 57,
    "attributes": {
      "width": 2.16,
      "color": "rgba(100, 100, 100, 0.42191780821917807)",
      "label": "27 publikacji"
    }
  },
  {
    "source": 1,
    "target": 57,
    "attributes": {
      "width": 2.16,
      "color": "rgba(100, 100, 100, 0.42191780821917807)",
      "label": "27 publikacji"
    }
  },
  {
    "source": 59,
    "target": 88,
    "attributes": {
      "width": 2.16,
      "color": "rgba(100, 100, 100, 0.42191780821917807)",
      "label": "27 publikacji"
    }
  },
  {
    "source": 46,
    "target": 108,
    "attributes": {
      "width": 2.16,
      "color": "rgba(100, 100, 100, 0.42191780821917807)",
      "label": "27 publikacji"
    }
  },
  {
    "source": 64,
    "target": 88,
    "attributes": {
      "width": 2.1,
      "color": "rgba(100, 100, 100, 0.41369863013698627)",
      "label": "26 publikacji"
    }
  },
  {
    "source": 7,
    "target": 24,
    "attributes": {
      "width": 2.1,
      "color": "rgba(100, 100, 100, 0.41369863013698627)",
      "label": "26 publikacji"
    }
  },
  {
    "source": 34,
    "target": 95,
    "attributes": {
      "width": 2.1,
      "color": "rgba(100, 100, 100, 0.41369863013698627)",
      "label": "26 publikacji"
    }
  },
  {
    "source": 55,
    "target": 76,
    "attributes": {
      "width": 2.04,
      "color": "rgba(100, 100, 100, 0.4054794520547945)",
      "label": "25 publikacji"
    }
  },
  {
    "source": 45,
    "target": 80,
    "attributes": {
      "width": 2.04,
      "color": "rgba(100, 100, 100, 0.4054794520547945)",
      "label": "25 publikacji"
    }
  },
  {
    "source": 1,
    "target": 76,
    "attributes": {
      "width": 1.98,
      "color": "rgba(100, 100, 100, 0.3972602739726028)",
      "label": "24 publikacji"
    }
  },
  {
    "source": 52,
    "target": 118,
    "attributes": {
      "width": 1.98,
      "color": "rgba(100, 100, 100, 0.3972602739726028)",
      "label": "24 publikacji"
    }
  },
  {
    "source": 24,
    "target": 117,
    "attributes": {
      "width": 1.92,
      "color": "rgba(100, 100, 100, 0.3890410958904109)",
      "label": "23 publikacji"
    }
  },
  {
    "source": 55,
    "target": 91,
    "attributes": {
      "width": 1.92,
      "color": "rgba(100, 100, 100, 0.3890410958904109)",
      "label": "23 publikacji"
    }
  },
  {
    "source": 12,
    "target": 20,
    "attributes": {
      "width": 1.86,
      "color": "rgba(100, 100, 100, 0.38082191780821917)",
      "label": "22 publikacji"
    }
  },
  {
    "source": 35,
    "target": 101,
    "attributes": {
      "width": 1.86,
      "color": "rgba(100, 100, 100, 0.38082191780821917)",
      "label": "22 publikacji"
    }
  },
  {
    "source": 26,
    "target": 68,
    "attributes": {
      "width": 1.86,
      "color": "rgba(100, 100, 100, 0.38082191780821917)",
      "label": "22 publikacji"
    }
  },
  {
    "source": 5,
    "target": 34,
    "attributes": {
      "width": 1.86,
      "color": "rgba(100, 100, 100, 0.38082191780821917)",
      "label": "22 publikacji"
    }
  },
  {
    "source": 1,
    "target": 60,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 24,
    "target": 76,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 52,
    "target": 142,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 1,
    "target": 91,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 73,
    "target": 101,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 5,
    "target": 95,
    "attributes": {
      "width": 1.79,
      "color": "rgba(100, 100, 100, 0.3726027397260274)",
      "label": "21 publikacji"
    }
  },
  {
    "source": 55,
    "target": 60,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 57,
    "target": 76,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 20,
    "target": 114,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 6,
    "target": 43,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 52,
    "target": 120,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 13,
    "target": 87,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 36,
    "target": 101,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 45,
    "target": 91,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 74,
    "target": 97,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 10,
    "target": 74,
    "attributes": {
      "width": 1.73,
      "color": "rgba(100, 100, 100, 0.3643835616438356)",
      "label": "20 publikacji"
    }
  },
  {
    "source": 9,
    "target": 43,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 20,
    "target": 53,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 19,
    "target": 54,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 87,
    "target": 96,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 61,
    "target": 111,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 86,
    "target": 92,
    "attributes": {
      "width": 1.67,
      "color": "rgba(100, 100, 100, 0.3561643835616438)",
      "label": "19 publikacji"
    }
  },
  {
    "source": 45,
    "target": 60,
    "attributes": {
      "width": 1.61,
      "color": "rgba(100, 100, 100, 0.34794520547945207)",
      "label": "18 publikacji"
    }
  },
  {
    "source": 21,
    "target": 53,
    "attributes": {
      "width": 1.61,
      "color": "rgba(100, 100, 100, 0.34794520547945207)",
      "label": "18 publikacji"
    }
  },
  {
    "source": 32,
    "target": 52,
    "attributes": {
      "width": 1.61,
      "color": "rgba(100, 100, 100, 0.34794520547945207)",
      "label": "18 publikacji"
    }
  },
  {
    "source": 7,
    "target": 57,
    "attributes": {
      "width": 1.61,
      "color": "rgba(100, 100, 100, 0.34794520547945207)",
      "label": "18 publikacji"
    }
  },
  {
    "source": 24,
    "target": 57,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 118,
    "target": 120,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 52,
    "target": 119,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 19,
    "target": 97,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 81,
    "target": 101,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 7,
    "target": 80,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 34,
    "target": 110,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 4,
    "target": 34,
    "attributes": {
      "width": 1.55,
      "color": "rgba(100, 100, 100, 0.33972602739726027)",
      "label": "17 publikacji"
    }
  },
  {
    "source": 0,
    "target": 113,
    "attributes": {
      "width": 1.49,
      "color": "rgba(100, 100, 100, 0.33150684931506846)",
      "label": "16 publikacji"
    }
  },
  {
    "source": 24,
    "target": 91,
    "attributes": {
      "width": 1.49,
      "color": "rgba(100, 100, 100, 0.33150684931506846)",
      "label": "16 publikacji"
    }
  },
  {
    "source": 5,
    "target": 110,
    "attributes": {
      "width": 1.49,
      "color": "rgba(100, 100, 100, 0.33150684931506846)",
      "label": "16 publikacji"
    }
  },
  {
    "source": 60,
    "target": 91,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 23,
    "target": 47,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 19,
    "target": 98,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 58,
    "target": 79,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 14,
    "target": 55,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 95,
    "target": 110,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 4,
    "target": 5,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 4,
    "target": 110,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 4,
    "target": 95,
    "attributes": {
      "width": 1.42,
      "color": "rgba(100, 100, 100, 0.3232876712328767)",
      "label": "15 publikacji"
    }
  },
  {
    "source": 24,
    "target": 60,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 37,
    "target": 59,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 86,
    "target": 102,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 118,
    "target": 119,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 20,
    "target": 21,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 10,
    "target": 19,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 55,
    "target": 117,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 45,
    "target": 57,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 1,
    "target": 14,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 8,
    "target": 79,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 42,
    "target": 71,
    "attributes": {
      "width": 1.36,
      "color": "rgba(100, 100, 100, 0.3150684931506849)",
      "label": "14 publikacji"
    }
  },
  {
    "source": 7,
    "target": 76,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 119,
    "target": 120,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 32,
    "target": 142,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 52,
    "target": 66,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 117,
    "target": 121,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 117,
    "target": 122,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 24,
    "target": 121,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 24,
    "target": 122,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 14,
    "target": 45,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 14,
    "target": 91,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 75,
    "target": 78,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 46,
    "target": 75,
    "attributes": {
      "width": 1.3,
      "color": "rgba(100, 100, 100, 0.30684931506849317)",
      "label": "13 publikacji"
    }
  },
  {
    "source": 37,
    "target": 64,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 20,
    "target": 103,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 40,
    "target": 86,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 42,
    "target": 96,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 26,
    "target": 79,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 32,
    "target": 66,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 20,
    "target": 22,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 1,
    "target": 117,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 77,
    "target": 78,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 77,
    "target": 108,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 75,
    "target": 108,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 46,
    "target": 77,
    "attributes": {
      "width": 1.24,
      "color": "rgba(100, 100, 100, 0.29863013698630136)",
      "label": "12 publikacji"
    }
  },
  {
    "source": 67,
    "target": 81,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 29,
    "target": 34,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 121,
    "target": 122,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 36,
    "target": 81,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 90,
    "target": 115,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 78,
    "target": 115,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 66,
    "target": 142,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 30,
    "target": 101,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 48,
    "target": 101,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 42,
    "target": 113,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 17,
    "target": 92,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 92,
    "target": 102,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 40,
    "target": 102,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 45,
    "target": 76,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 76,
    "target": 80,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 18,
    "target": 20,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 23,
    "target": 94,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 60,
    "target": 80,
    "attributes": {
      "width": 1.18,
      "color": "rgba(100, 100, 100, 0.2904109589041096)",
      "label": "11 publikacji"
    }
  },
  {
    "source": 78,
    "target": 90,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 75,
    "target": 77,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 7,
    "target": 91,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 45,
    "target": 117,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 67,
    "target": 101,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 19,
    "target": 74,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 52,
    "target": 99,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 118,
    "target": 142,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 65,
    "target": 101,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 0,
    "target": 42,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 40,
    "target": 92,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 17,
    "target": 40,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 14,
    "target": 24,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 49,
    "target": 79,
    "attributes": {
      "width": 1.12,
      "color": "rgba(100, 100, 100, 0.2821917808219178)",
      "label": "10 publikacji"
    }
  },
  {
    "source": 26,
    "target": 44,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 2,
    "target": 86,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 98,
    "target": 123,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 30,
    "target": 84,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 21,
    "target": 22,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 54,
    "target": 98,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 51,
    "target": 68,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 71,
    "target": 96,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 56,
    "target": 96,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 42,
    "target": 94,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 56,
    "target": 71,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 17,
    "target": 102,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 52,
    "target": 125,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 118,
    "target": 125,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 49,
    "target": 58,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 37,
    "target": 88,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 88,
    "target": 106,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 23,
    "target": 82,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 14,
    "target": 60,
    "attributes": {
      "width": 1.05,
      "color": "rgba(100, 100, 100, 0.273972602739726)",
      "label": "9 publikacji"
    }
  },
  {
    "source": 80,
    "target": 91,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 38,
    "target": 79,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 38,
    "target": 58,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 30,
    "target": 65,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 22,
    "target": 53,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 48,
    "target": 84,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 26,
    "target": 51,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 120,
    "target": 142,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 42,
    "target": 56,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 57,
    "target": 80,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 119,
    "target": 125,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 37,
    "target": 41,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 41,
    "target": 59,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 55,
    "target": 93,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 41,
    "target": 64,
    "attributes": {
      "width": 0.99,
      "color": "rgba(100, 100, 100, 0.26575342465753427)",
      "label": "8 publikacji"
    }
  },
  {
    "source": 2,
    "target": 20,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 7,
    "target": 14,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 41,
    "target": 106,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 3,
    "target": 101,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 128,
    "target": 134,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 24,
    "target": 28,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 26,
    "target": 96,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 27,
    "target": 71,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 120,
    "target": 125,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 82,
    "target": 94,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 7,
    "target": 93,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 45,
    "target": 93,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 1,
    "target": 93,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 8,
    "target": 58,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 69,
    "target": 75,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 46,
    "target": 69,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 46,
    "target": 83,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 46,
    "target": 100,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 69,
    "target": 108,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 83,
    "target": 108,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 100,
    "target": 108,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 69,
    "target": 77,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 69,
    "target": 78,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 83,
    "target": 100,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 78,
    "target": 83,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 78,
    "target": 100,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 80,
    "target": 117,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 47,
    "target": 94,
    "attributes": {
      "width": 0.93,
      "color": "rgba(100, 100, 100, 0.25753424657534246)",
      "label": "7 publikacji"
    }
  },
  {
    "source": 46,
    "target": 63,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 63,
    "target": 108,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 63,
    "target": 75,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 63,
    "target": 77,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 63,
    "target": 78,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 1,
    "target": 122,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 1,
    "target": 121,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 55,
    "target": 122,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 45,
    "target": 121,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 55,
    "target": 121,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 36,
    "target": 143,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 36,
    "target": 134,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 101,
    "target": 134,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 66,
    "target": 99,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 30,
    "target": 104,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 101,
    "target": 104,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 65,
    "target": 84,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 39,
    "target": 98,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 68,
    "target": 112,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 25,
    "target": 113,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 46,
    "target": 115,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 108,
    "target": 115,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 27,
    "target": 113,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 27,
    "target": 42,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 52,
    "target": 149,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 142,
    "target": 149,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 37,
    "target": 106,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 59,
    "target": 106,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 7,
    "target": 72,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 45,
    "target": 72,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 1,
    "target": 72,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 24,
    "target": 93,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 55,
    "target": 72,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 75,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 75,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 75,
    "target": 83,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 75,
    "target": 100,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 46,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 46,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 85,
    "target": 108,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 108,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 77,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 77,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 77,
    "target": 83,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 77,
    "target": 100,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 69,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 69,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 69,
    "target": 83,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 69,
    "target": 100,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 83,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 85,
    "target": 100,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 78,
    "target": 85,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 83,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 100,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 31,
    "target": 78,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 24,
    "target": 138,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 122,
    "target": 138,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 117,
    "target": 138,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 7,
    "target": 60,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 64,
    "target": 106,
    "attributes": {
      "width": 0.87,
      "color": "rgba(100, 100, 100, 0.2493150684931507)",
      "label": "6 publikacji"
    }
  },
  {
    "source": 60,
    "target": 76,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 123,
    "target": 125,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 1,
    "target": 116,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 80,
    "target": 116,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 55,
    "target": 116,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 57,
    "target": 91,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 45,
    "target": 122,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 67,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 52,
    "target": 123,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 79,
    "target": 97,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 79,
    "target": 96,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 79,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 96,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 134,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 132,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 128,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 129,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 132,
    "target": 134,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 134,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 132,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 132,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 129,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 32,
    "target": 118,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 32,
    "target": 99,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 3,
    "target": 30,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 65,
    "target": 104,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 3,
    "target": 104,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 76,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 1,
    "target": 28,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 55,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 32,
    "target": 120,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 26,
    "target": 112,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 118,
    "target": 144,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 52,
    "target": 144,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 26,
    "target": 56,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 26,
    "target": 49,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 71,
    "target": 89,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 56,
    "target": 89,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 89,
    "target": 96,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 119,
    "target": 142,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 119,
    "target": 149,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 125,
    "target": 142,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 118,
    "target": 149,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 118,
    "target": 124,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 118,
    "target": 123,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 12,
    "target": 22,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 71,
    "target": 113,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 72,
    "target": 93,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 44,
    "target": 79,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 57,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 63,
    "target": 69,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 63,
    "target": 85,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 31,
    "target": 63,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 63,
    "target": 83,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 63,
    "target": 100,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 121,
    "target": 138,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 121,
    "target": 136,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 136,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 136,
    "target": 138,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 122,
    "target": 136,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 117,
    "target": 136,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 23,
    "target": 25,
    "attributes": {
      "width": 0.81,
      "color": "rgba(100, 100, 100, 0.2410958904109589)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 45,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 146,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 145,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 145,
    "target": 146,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 147,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 146,
    "target": 147,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 145,
    "target": 147,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 143,
    "target": 146,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 143,
    "target": 145,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 143,
    "target": 147,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 148,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 146,
    "target": 148,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 145,
    "target": 148,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 147,
    "target": 148,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 143,
    "target": 148,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 70,
    "target": 86,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 57,
    "target": 60,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 125,
    "target": 144,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 119,
    "target": 144,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 35,
    "target": 48,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 14,
    "target": 57,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 79,
    "target": 115,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 79,
    "target": 90,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 96,
    "target": 97,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 97,
    "target": 115,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 97,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 115,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 90,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 74,
    "target": 115,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 115,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 90,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 36,
    "target": 84,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 127,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 130,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 134,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 134,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 130,
    "target": 134,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 132,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 128,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 129,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 130,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 132,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 128,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 129,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 130,
    "target": 132,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 130,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 130,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 3,
    "target": 65,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 84,
    "target": 104,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 68,
    "target": 96,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 51,
    "target": 112,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 120,
    "target": 144,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 142,
    "target": 144,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 94,
    "target": 96,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 56,
    "target": 94,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 0,
    "target": 25,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 9,
    "target": 34,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 111,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 56,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 96,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 14,
    "target": 80,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 44,
    "target": 68,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 76,
    "target": 91,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 0,
    "target": 27,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 119,
    "target": 124,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 52,
    "target": 124,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 125,
    "target": 149,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 120,
    "target": 149,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 124,
    "target": 125,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 120,
    "target": 124,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 41,
    "target": 88,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 12,
    "target": 39,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 23,
    "target": 98,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 42,
    "target": 50,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 51,
    "target": 79,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 68,
    "target": 79,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 75,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 46,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 108,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 77,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 69,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 109,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 25,
    "target": 47,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 64,
    "target": 105,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 105,
    "target": 106,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 41,
    "target": 105,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 29,
    "target": 111,
    "attributes": {
      "width": 0.75,
      "color": "rgba(100, 100, 100, 0.23287671232876714)",
      "label": null
    }
  },
  {
    "source": 70,
    "target": 102,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 40,
    "target": 70,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 76,
    "target": 117,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 60,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 91,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 80,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 28,
    "target": 117,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 71,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 8,
    "target": 49,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 16,
    "target": 58,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 16,
    "target": 49,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 70,
    "target": 92,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 17,
    "target": 70,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 131,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 131,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 130,
    "target": 131,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 131,
    "target": 132,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 127,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 131,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 130,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 132,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 131,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 131,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 131,
    "target": 134,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 134,
    "target": 135,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 20,
    "target": 39,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 129,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 126,
    "target": 129,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 126,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 126,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 132,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 126,
    "target": 132,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 128,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 126,
    "target": 128,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 133,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 126,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 133,
    "target": 134,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 126,
    "target": 134,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 119,
    "target": 123,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 120,
    "target": 123,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 144,
    "target": 149,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 50,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 97,
    "target": 98,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 98,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 140,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 116,
    "target": 117,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 117,
    "target": 139,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 117,
    "target": 140,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 117,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 139,
    "target": 140,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 139,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 55,
    "target": 139,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 80,
    "target": 139,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 140,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 55,
    "target": 140,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 80,
    "target": 140,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 55,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 80,
    "target": 141,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 57,
    "target": 72,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 57,
    "target": 93,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 56,
    "target": 107,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 56,
    "target": 62,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 33,
    "target": 78,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 25,
    "target": 71,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 46,
    "target": 90,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 90,
    "target": 108,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 50,
    "target": 82,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 2,
    "target": 22,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 13,
    "target": 48,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 48,
    "target": 96,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 79,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 74,
    "target": 79,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 54,
    "target": 79,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 54,
    "target": 97,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 38,
    "target": 97,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 58,
    "target": 97,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 38,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 58,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 38,
    "target": 74,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 58,
    "target": 74,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 74,
    "target": 90,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 54,
    "target": 96,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 96,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 38,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 38,
    "target": 90,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 38,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 58,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 58,
    "target": 90,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 19,
    "target": 58,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 115,
    "target": 134,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 115,
    "target": 132,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 115,
    "target": 128,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 115,
    "target": 129,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 127,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 78,
    "target": 130,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 66,
    "target": 118,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 99,
    "target": 142,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 3,
    "target": 84,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 26,
    "target": 40,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 40,
    "target": 68,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 40,
    "target": 112,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 40,
    "target": 51,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 71,
    "target": 94,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 26,
    "target": 42,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 25,
    "target": 42,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 25,
    "target": 94,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 6,
    "target": 34,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 27,
    "target": 89,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 9,
    "target": 54,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 9,
    "target": 98,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 9,
    "target": 19,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 0,
    "target": 71,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 98,
    "target": 125,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 16,
    "target": 29,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 29,
    "target": 61,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 42,
    "target": 89,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 72,
    "target": 80,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 80,
    "target": 93,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 72,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 50,
    "target": 113,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 0,
    "target": 50,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 45,
    "target": 116,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 8,
    "target": 51,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 46,
    "target": 66,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 66,
    "target": 78,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 66,
    "target": 108,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 66,
    "target": 75,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 96,
    "target": 113,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 34,
    "target": 97,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 29,
    "target": 97,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 34,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 10,
    "target": 29,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 79,
    "target": 112,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 75,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 63,
    "target": 109,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 83,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 100,
    "target": 115,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 85,
    "target": 109,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 31,
    "target": 109,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 83,
    "target": 109,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 100,
    "target": 109,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 121,
    "target": 137,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 137,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 137,
    "target": 138,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 136,
    "target": 137,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 122,
    "target": 137,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 117,
    "target": 137,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 25,
    "target": 82,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 91,
    "target": 117,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 60,
    "target": 117,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 37,
    "target": 105,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 59,
    "target": 105,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 88,
    "target": 105,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 6,
    "target": 29,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 39,
    "target": 50,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 50,
    "target": 94,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 116,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  },
  {
    "source": 24,
    "target": 139,
    "attributes": {
      "width": 0.68,
      "color": "rgba(100, 100, 100, 0.22465753424657536)",
      "label": null
    }
  }
]
  };

  // Set the graph
  await ogma.setGraph(graphData);

  // Apply force-directed layout for better positioning
  if (ogma.layouts && ogma.layouts.force) {
    await ogma.layouts.force({
      duration: 2000,
      gpu: true,  // Use GPU acceleration if available
      settings: {
        gravity: 0.05,
        charge: -1000,
        springLength: 100,
        springCoefficient: 0.01,
        theta: 0.8
      }
    });
  }

  // Style the nodes and edges
  ogma.styles.setNodeStyle({
    color: '#4A90E2',
    radius: 12,
    strokeColor: '#2E5C8A',
    strokeWidth: 2,
    text: {
      font: '12px Arial, sans-serif',
      color: '#333333',
      backgroundColor: 'rgba(255, 255, 255, 0.8)',
      padding: 2,
      minVisibleSize: 10
    }
  });

  ogma.styles.setEdgeStyle({
    color: 'rgba(150, 150, 150, 0.5)',
    shape: 'line'
  });

  // Enable interactions
  ogma.events.on('click', function(evt) {
    if (evt.target && evt.target.isNode) {
      const node = evt.target;
      const connectedEdges = node.getAdjacentEdges();
      const connectedNodes = node.getAdjacentNodes();

      // Highlight selected node and its connections
      ogma.styles.setSelectedNodeStyle({
        color: '#FF6B6B',
        radius: 15
      });

      node.setSelected(true);
      connectedEdges.setSelected(true);
      connectedNodes.setSelected(true);

      console.log('Selected author:', node.getData('text'));
      console.log('Connections:', connectedNodes.size);
    }
  });

  // Add zoom controls
  ogma.view.setZoom(0.8);

  // Center the graph
  await ogma.view.locateGraph({
    duration: 1000,
    padding: 50
  });

  // Add basic controls info
  const info = document.createElement('div');
  info.style.position = 'absolute';
  info.style.top = '10px';
  info.style.left = '10px';
  info.style.padding = '10px';
  info.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
  info.style.border = '1px solid #ddd';
  info.style.borderRadius = '4px';
  info.style.fontSize = '12px';
  info.innerHTML = `
    <strong>Wizualizacja powiązań autorów</strong><br>
    Liczba autorów: 150<br>
    Liczba połączeń: 588<br>
    Min. wspólnych publikacji: 3<br>
    <br>
    <em>Kliknij na autora aby podświetlić połączenia</em>
  `;
  container.appendChild(info);

  console.log('Author connections visualization loaded successfully');
})();
