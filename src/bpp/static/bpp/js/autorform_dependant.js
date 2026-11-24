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
            zapytajOAutora(this).done(function (data) {
                if (data.status == 'error')
                    return;

                if (data.jednostka_id && data.nazwa) {
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
    // błąd walidacji, edycja zwróconego zgłoszenia) — ustawiamy tylko
    // widoczność pola dyscypliny, bez nadpisywania jednostki.
    var sprawdzWybranegoAutora = function (element) {
        var prefix = $(element).getFormPrefix();
        if (!$(element).val() || !tylkoDlaAutorowUczelni(prefix))
            return;
        zapytajOAutora(element).done(function (data) {
            if (data.status == 'error')
                return;
            pokazDyscypline(prefix, data.autor_uczelni !== false);
        });
    };

    $(document).on('autocompleteLightInitialize', '[data-autocomplete-light-function=select2]', function () {
        $(':input[name$=autor]').off('change', autorform_dependant);
        $(':input[name$=autor]').on('change', autorform_dependant);
        if (/(^|-)autor$/.test($(this).attr('name') || ''))
            sprawdzWybranegoAutora(this);
    })
}(django.jQuery || jQuery));
