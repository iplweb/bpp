var autorform_dependant = function () {
    var prefix = $(this).getFormPrefix();
    var value = $(this).val();

    if (!value) {
        $(':input[name=' + prefix + 'jednostka]').val(null).trigger('change');
        $(':input[name=' + prefix + 'typ_odpowiedzialnosci]').val(null).trigger('change');
        $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');
    } else {
        $.ajax({
            url: "/bpp/api/ostatnia-jednostka/",
            context: document.body,
            method: "POST",
            data: {'autor_id': $(this).val()}
        }).done(function (data) {
            console.log(data['jednostka_id']);

            $(':input[name=' + prefix + 'jednostka]').append(
                '<option selected="selected" value=' + data['jednostka_id'] + '>'
                + data['nazwa'] + '</option>');

            $(':input[name=' + prefix + 'jednostka]').trigger("change");

            $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');

        });

    }
};

$(document).on('autocompleteLightInitialize', '[data-autocomplete-light-function=select2]', function () {
    $(':input[name$=autor]').off('change', autorform_dependant);
    $(':input[name$=autor]').on('change', autorform_dependant);
})