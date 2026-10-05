/**
 * Klawiatura znaków specjalnych (kbw-keypad) dla pól ``.charmap``.
 *
 * Ładowane przez ``Media`` widgetów CharmapTextInput / CharmapTextarea
 * (src/bpp/admin/helpers/widgets.py) — tylko na stronach, które mają
 * takie pola. Wcześniej ten kod siedział w bloku footer base_site.html
 * i wykonywał się na każdej stronie admina.
 */
(function ($) {
    'use strict';

    $(document).ready(function () {
        if (typeof $.fn.keypad !== 'function') {
            if (window.console) {
                console.error(
                    'charmap-keypad: wtyczka jquery.keypad nie jest ' +
                    'podpięta pod grp.jQuery — klawiatura niedostępna.'
                );
            }
            return;
        }

        $('.charmap').keypad({
            keypadOnly: false,
            layout: [
                'αβγδεζ ©® àáâãäåæçß ъяшертыу',
                'ηθικλμ ™℠ èéêëìííî  иопющэас',
                'νξοπρσ €£ ïñòóôõöø  дфгчйкль',
                'τυφχψω ¥¢ ùúûüýÿðþ  жзхцвбнм',
                $.keypad.SHIFT + $.keypad.CLOSE
            ],
            showAnim: 'fadeIn',
            duration: 'fast',
            showOn: 'button',
            buttonText: '🌐'
        });

        // Przyciski jquery.keypad
        $('button.keypad-trigger').each(function (no, tag) {
            var $tag = $(tag);
            var first = $tag.siblings().first();
            if (first.is('textarea')) {
                $tag.css('margin-left', '12px').css('margin-top', '15px');
            }
            $tag.css('color', 'black').attr('tabindex', '-1');
        });
    });
})(grp.jQuery);
