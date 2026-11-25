(function ($) {
    // FD#640: w formularzu zgłaszania prac pole „Dyscyplina naukowa” jest
    // oznaczone ``data-tylko-autor-uczelni`` — dla autora spoza uczelni
    // chowamy je (i czyścimy wartość). W pozostałych formularzach (admin)
    // pola nie mają tego atrybutu, więc nic się tam nie zmienia.
    var poleDyscypliny = function (prefix) {
        return $(':input[name=' + prefix + 'dyscyplina_naukowa]');
    };

    var tylkoDlaAutorowUczelni = function (prefix) {
        return poleDyscypliny(prefix).is('[data-tylko-autor-uczelni]');
    };

    var pokazDyscypline = function (prefix, pokaz) {
        var pole = poleDyscypliny(prefix);
        var holder = pole.closest('.holder');
        if (pokaz) {
            holder.show();
        } else {
            pole.val(null).trigger('change');
            holder.hide();
        }
    };

    // FD#640: pole „Jednostka” w formularzu zgłaszania prac jest oznaczone
    // ``data-obcy-tylko-obca-jednostka`` — autorowi spoza uczelni ustawiamy
    // jednostkę obcą uczelni (API zwraca ją w ``obca_jednostka_*``, gdy jest
    // skonfigurowana). Autocomplete tego pola i tak podpowiada takiemu
    // autorowi tylko ją, a serwer odrzuca jednostkę uczelni.
    var poleJednostki = function (prefix) {
        return $(':input[name=' + prefix + 'jednostka]');
    };

    var obcyTylkoObcaJednostka = function (prefix) {
        return poleJednostki(prefix).is('[data-obcy-tylko-obca-jednostka]');
    };

    var ustawJednostke = function (prefix, id, nazwa) {
        var pole = poleJednostki(prefix);
        pole.find('option').filter(function () {
            return this.value === String(id);
        }).remove();
        pole.append($('<option>', {value: id, text: nazwa, selected: true}));
        pole.trigger('change');
    };

    var obcaJednostkaDlaObcego = function (prefix, data) {
        if (!obcyTylkoObcaJednostka(prefix) || data.autor_uczelni !== false)
            return null;
        if (!data.obca_jednostka_id)
            return null;
        return {id: data.obca_jednostka_id, nazwa: data.obca_jednostka_nazwa};
    };

    var zapytajOAutora = function (element) {
        // CSRF token z najbliższego formularza — nie polegamy na
        // globalnym $.ajaxSetup, bo public-facing zglos_publikacje
        // nie ma go w base.html (tylko admin/base.html).
        var csrfToken = $(element).closest('form').find(
            '[name=csrfmiddlewaretoken]'
        ).val();
        return $.ajax({
            url: "/bpp/api/ostatnia-jednostka-i-dyscyplina/",
            context: document.body,
            method: "POST",
            data: {
                'autor_id': $(element).val(),
                'rok': $("#id_rok").val(),
                'csrfmiddlewaretoken': csrfToken
            }
        });
    };

    var autorform_dependant = function () {
        var prefix = $(this).getFormPrefix();
        var value = $(this).val();

        if (!value) {
            $(':input[name=' + prefix + 'jednostka]').val(null).trigger('change');
            $(':input[name=' + prefix + 'typ_odpowiedzialnosci]').val(null).trigger('change');
            $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');
            $(':input[name=' + prefix + 'dyscyplina_naukowa]').val(null).trigger('change');
            if (tylkoDlaAutorowUczelni(prefix))
                pokazDyscypline(prefix, true);
        } else {
            var pole = this;
            zapytajOAutora(this).done(function (data) {
                if (data.status == 'error')
                    return;
                // Odpowiedź dla autora, którego w międzyczasie zmieniono.
                if ($(pole).val() !== value)
                    return;

                var obca = obcaJednostkaDlaObcego(prefix, data);
                if (obca) {
                    ustawJednostke(prefix, obca.id, obca.nazwa);
                } else if (data.jednostka_id && data.nazwa) {
                    $(':input[name=' + prefix + 'jednostka]').append(
                        '<option selected="selected" value=' + data['jednostka_id'] + '>'
                        + data['nazwa'] + '</option>');

                    $(':input[name=' + prefix + 'jednostka]').trigger("change");
                }

                var spozaUczelni = (
                    tylkoDlaAutorowUczelni(prefix) && data.autor_uczelni === false
                );
                if (tylkoDlaAutorowUczelni(prefix))
                    pokazDyscypline(prefix, !spozaUczelni);

                if (data['dyscyplina_id'] && !spozaUczelni) {
                    $(':input[name=' + prefix + 'dyscyplina_naukowa]').append(
                        '<option selected="selected" value=' + data['dyscyplina_id'] + '>'
                        + data['dyscyplina_nazwa'] + '</option>');

                    $(':input[name=' + prefix + 'dyscyplina_naukowa]').trigger("change");
                }

                $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');

            });

        }
    };

    // FD#640: formularz wyrenderowany z już wybranym autorem (powrót do kroku,
    // błąd walidacji, edycja zwróconego zgłoszenia) — ustawiamy widoczność
    // pola dyscypliny, a jednostkę zmieniamy tylko autorowi spoza uczelni
    // (na obcą); autorowi uczelni wybranej jednostki nie nadpisujemy.
    var sprawdzWybranegoAutora = function (element) {
        var prefix = $(element).getFormPrefix();
        if (!$(element).val())
            return;
        if (!tylkoDlaAutorowUczelni(prefix) && !obcyTylkoObcaJednostka(prefix))
            return;
        var wyslany = $(element).val();
        zapytajOAutora(element).done(function (data) {
            if (data.status == 'error' || $(element).val() !== wyslany)
                return;
            if (tylkoDlaAutorowUczelni(prefix))
                pokazDyscypline(prefix, data.autor_uczelni !== false);
            var obca = obcaJednostkaDlaObcego(prefix, data);
            if (obca && poleJednostki(prefix).val() !== String(obca.id))
                ustawJednostke(prefix, obca.id, obca.nazwa);
        });
    };

    $(document).on('autocompleteLightInitialize', '[data-autocomplete-light-function=select2]', function () {
        $(':input[name$=autor]').off('change', autorform_dependant);
        $(':input[name$=autor]').on('change', autorform_dependant);
        if (/(^|-)autor$/.test($(this).attr('name') || ''))
            sprawdzWybranegoAutora(this);
    })
}(django.jQuery || jQuery));
