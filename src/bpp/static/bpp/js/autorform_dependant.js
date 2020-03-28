(function($){
var autorform_dependant = function () {
    var prefix = $(this).getFormPrefix();
    var value = $(this).val();

    if (!value) {
        $(':input[name=' + prefix + 'jednostka]').val(null).trigger('change');
        $(':input[name=' + prefix + 'typ_odpowiedzialnosci]').val(null).trigger('change');
        $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');
        $(':input[name=' + prefix + 'dyscyplina_naukowa]').val(null).trigger('change');
    } else {
        $.ajax({
            url: "/bpp/api/ostatnia-jednostka-i-dyscyplina/",
            context: document.body,
            method: "POST",
            data: {'autor_id': $(this).val(), 'rok': $("#id_rok").val()}
        }).done(function (data) {
            if (data.status == 'error')
                return;

            if (data.jednostka_id && data.nazwa) {
                $(':input[name=' + prefix + 'jednostka]').append(
                    '<option selected="selected" value=' + data['jednostka_id'] + '>'
                    + data['nazwa'] + '</option>');

                $(':input[name=' + prefix + 'jednostka]').trigger("change");
            }

            if (data['dyscyplina_id']) {
                $(':input[name=' + prefix + 'dyscyplina_naukowa]').append(
                    '<option selected="selected" value=' + data['dyscyplina_id'] + '>'
                    + data['dyscyplina_nazwa'] + '</option>');

                $(':input[name=' + prefix + 'dyscyplina_naukowa]').trigger("change");
            }

            $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');

        });

    }
};

$(document).on('autocompleteLightInitialize', '[data-autocomplete-light-function=select2]', function () {
    $(':input[name$=autor]').off('change', autorform_dependant);
    $(':input[name$=autor]').on('change', autorform_dependant);
})
}(django.jQuery));