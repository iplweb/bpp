//
// Żeby ten plik dzialal dynamicznie, uzywamy zmiennej {{ class }}, a
// cały ten plik przepuszczamy przez Django (jako template), a Django wstawia
// tam właśnie nazwę klasy;
// jest to związane z tym, że django będzie nazywać wiersze w inline formset w
// taki sposób:
//
// * wydanwnictwo_ciagle_autor,
// * wydawnictwo_zwarte_autor,
//
// a ponieważ ten plik ma obsługiwać wiele różnych klas z bpp.models,
// takie postępowanie jest jak najbardziej niezbędne
//

if (window.bpp == undefined) window.bpp = {};

String.prototype.endsWith = function(suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
};

window.bpp.wiersz = function (numer, nazwa) {
    return $('#id_{{ class }}_set-' + numer + '-' + nazwa);
}

window.bpp.label = function (numer) {
    return $('#{{ class }}_set-' + numer).find(".original")[0].children[0];
}

window.bpp.ustawZaleznosciDlaWiersza = function (numer, noReset) {
    // ID to numerek.
    var autorSelectElement = bpp.wiersz(numer, 'autor');
    var jednostkaSelectElement = bpp.wiersz(numer, 'jednostka');
    var zapisanyJakoElement = bpp.wiersz(numer, 'zapisany_jako');
    var typOdpowiedzialnosciSelectElement = bpp.wiersz(numer, 'typ_odpowiedzialnosci');

    var autorWidget = autorSelectElement.parents('.autocomplete-light-widget').yourlabsWidget();
    var jednostkaWidgetElement = jednostkaSelectElement.parents('.autocomplete-light-widget');
    var jednostkaWidget = jednostkaWidgetElement.yourlabsWidget();
    var zapisanyJakoWidget = zapisanyJakoElement.yourlabsTextWidget();

    var value = autorSelectElement.val();

    var selector = jednostkaWidget.autocomplete.choiceSelector;
    var choice = jednostkaWidgetElement.find(selector);

    if (!noReset) {
        /* Skasuj ustawienia, które być może były wybrane */
        jednostkaWidget.deselectChoice(choice);

        typOdpowiedzialnosciSelectElement.val("");
        zapisanyJakoElement.val("");
    }

    /* Ustaw autor_id dla widgetu jednostki, aby odpytywał on dodatkowo
     tylko o tego konkretnego autora:
     */

    if (value) {
        var data = {'autor_id': value[0]};
    } else {
        var data = {};
    }

    // Odkomentowanie poniższej linii ograniczy nam wyszukiwanie tylko
    // do jednostek, które AUTOR ma wpisane:
    // -- na ten moment jednakże pozwalamy na wybór WSZYSTKICH jednostek
    // w bazie danych, jakich tylko dusza zapraganie.

    // jednostkaWidget.autocomplete.data = data;
    zapisanyJakoWidget.autocomplete.data = data;

};

// Poniższy kod korzysta z kontekstu djangowego jQuery, bo zdarzenia będą
// generowane "po tamtej stronie", czyli przez jQuery załączone do Djangowego
// admina:
$(document).ready(function () {

    for (a = 0; a < 199; a++) {
        // 200 autorow should be enough for anyone
        if (bpp.wiersz(a, 'autor').length)
            if (bpp.wiersz(a, 'autor').val())
                bpp.ustawZaleznosciDlaWiersza(a, true);
    }


    function onAutorChanged(t) {
        var autorSelectElement = $(t);

        var id = $(t).attr('id'); // id_wydawnictwo_ciagle_autor_set-3-autor
        id = id.replace('id_{{ class }}_set-', '').replace('-autor', '');
        bpp.ustawZaleznosciDlaWiersza(id);

        jednostkaSelectElement = bpp.wiersz(id, 'jednostka');
        typOdpowiedzialnosciSelectElement = bpp.wiersz(id, 'typ_odpowiedzialnosci');

        autor_id = autorSelectElement.val();
        if (autor_id != null)
            $.ajax(
                {
                    type: "POST",
                    data: {"autor_id": autor_id},
                    url: "{% url "bpp:api_ostatnia_jednostka" %}",
                }).success(
                function (res) {
                    $(jednostkaSelectElement).append(
                        '<option value="' + res.jednostka_id + '" selected="selected">' +
                        res.nazwa + '</option>')

                    // tu moznaby rozwinac "typ odpowiedzialnosci",
                    // gdyby nie to, ze jest to cholernie karkolomne do zrobienia
                    // w javascript
                    typOdpowiedzialnosciSelectElement.val(1);

                });
    }

    $("body").on("change", function(e) {
        var target = $(e.target);

        if (target.attr("id").endsWith("-autor"))
            onAutorChanged(target);
    });

});

