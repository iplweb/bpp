# Register your models here.
import json

from django.forms import widgets

from django.utils.safestring import mark_safe


class PrettyJSONWidget(widgets.Textarea):
    show_only_current = False

    def format_value(self, value):
        try:
            v = json.loads(value)
            if self.show_only_current:
                # Pokazuj tylko ostatnią wersję z PBNu
                v = [value for value in v if value.get("current", False) is True]
            value = json.dumps(v, indent=4, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 60)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception:
            # logger.warning("Error while formatting JSON: {}".format(e))
            return super().format_value(value)


class PrettyJSONWidgetReadonly(PrettyJSONWidget):
    def __init__(self, attrs=None):
        default_attrs = {"readonly": True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class PrettyJSONWidgetReadonlyOnlyCurrent(PrettyJSONWidgetReadonly):
    show_only_current = True


class JSONWithActionsWidget(PrettyJSONWidgetReadonly):
    """
    Widget that displays formatted JSON with copy and download buttons.
    """

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}

        # Add a unique ID for the container
        if "id" not in attrs:
            attrs["id"] = "id_%s" % name

        container_id = f"{attrs['id']}_container"

        # Format the JSON value
        formatted_value = self.format_value(value)

        # Create the HTML with buttons and textarea
        html = f"""
        <div id="{container_id}" class="json-with-actions-widget">
            <div class="json-actions" style="margin-bottom: 10px;">
                <button type="button" class="button json-copy-btn" data-target="{attrs['id']}">
                    📋 Kopiuj JSON
                </button>
                <button type="button" class="button json-download-btn" data-target="{attrs['id']}">
                    💾 Pobierz JSON
                </button>
            </div>
            {super().render(name, formatted_value, attrs, renderer)}
        </div>

        <script>
        (function($) {{
            $(document).ready(function() {{
                // Copy to clipboard functionality
                $('.json-copy-btn').on('click', function() {{
                    var targetId = $(this).data('target');
                    var textarea = $('#' + targetId);
                    var text = textarea.val();

                    // Try modern clipboard API first
                    if (navigator.clipboard && navigator.clipboard.writeText) {{
                        navigator.clipboard.writeText(text).then(function() {{
                            // Show success feedback
                            var btn = $('.json-copy-btn[data-target="' + targetId + '"]');
                            var originalText = btn.text();
                            btn.text('✓ Skopiowano!').addClass('success');
                            setTimeout(function() {{
                                btn.text(originalText).removeClass('success');
                            }}, 2000);
                        }}).catch(function(err) {{
                            console.error('Failed to copy: ', err);
                            fallbackCopyToClipboard(text, targetId);
                        }});
                    }} else {{
                        fallbackCopyToClipboard(text, targetId);
                    }}
                }});

                // Fallback copy method
                function fallbackCopyToClipboard(text, targetId) {{
                    var textarea = document.createElement('textarea');
                    textarea.value = text;
                    textarea.style.position = 'fixed';
                    textarea.style.opacity = '0';
                    document.body.appendChild(textarea);
                    textarea.select();

                    try {{
                        document.execCommand('copy');
                        var btn = $('.json-copy-btn[data-target="' + targetId + '"]');
                        var originalText = btn.text();
                        btn.text('✓ Skopiowano!').addClass('success');
                        setTimeout(function() {{
                            btn.text(originalText).removeClass('success');
                        }}, 2000);
                    }} catch (err) {{
                        console.error('Fallback copy failed: ', err);
                    }}

                    document.body.removeChild(textarea);
                }}

                // Download functionality
                $('.json-download-btn').on('click', function() {{
                    var targetId = $(this).data('target');
                    var textarea = $('#' + targetId);
                    var text = textarea.val();

                    // Find object ID dynamically from the admin form
                    var objectId = 'unknown';
                    $('.field-box').each(function() {{
                        var label = $(this).find('label').text().trim();
                        if (label === 'Object id') {{
                            objectId = $(this).find('.grp-readonly').text().trim();
                            return false; // break the loop
                        }}
                    }});

                    var filename = 'sent-data-' + objectId + '.json';

                    // Create blob and download link
                    var blob = new Blob([text], {{ type: 'application/json' }});
                    var url = window.URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }});
            }});
        }})(django.jQuery);
        </script>
        """

        return mark_safe(html)
