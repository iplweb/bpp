from django import template

from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def temperature_class(value):
    """
    Return temperature class based on PKDaut/slot value.

    Temperature scale:
    200+     : temp-200 (blazing hot)
    180-200  : temp-180 (very hot)
    160-180  : temp-160 (hot)
    140-160  : temp-140 (warm-hot)
    120-140  : temp-120 (warm)
    100-120  : temp-100 (moderate-warm)
    80-100   : temp-80  (moderate)
    60-80    : temp-60  (cool)
    40-60    : temp-40  (cold)
    20-40    : temp-20  (very cold)
    0-20     : temp-0   (freezing)
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0

    if val >= 200:
        return "temp-200"
    elif val >= 180:
        return "temp-180"
    elif val >= 160:
        return "temp-160"
    elif val >= 140:
        return "temp-140"
    elif val >= 120:
        return "temp-120"
    elif val >= 100:
        return "temp-100"
    elif val >= 80:
        return "temp-80"
    elif val >= 60:
        return "temp-60"
    elif val >= 40:
        return "temp-40"
    elif val >= 20:
        return "temp-20"
    else:
        return "temp-0"


@register.filter
def temperature_label(value):
    """
    Return temperature label description.
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0

    if val >= 200:
        return "Wyjątkowy"
    elif val >= 150:
        return "Bardzo dobry"
    elif val >= 100:
        return "Dobry"
    elif val >= 75:
        return "Przeciętny"
    elif val >= 50:
        return "Poniżej przeciętnej"
    elif val >= 25:
        return "Słaby"
    else:
        return "Bardzo słaby"


@register.simple_tag
def temperature_display(value):
    """
    Return a complete temperature display with gradient background.
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0

    temp_class = temperature_class(val)
    label = temperature_label(val)

    # Format the value to 2 decimal places
    formatted_value = f"{val:.2f}"

    html = f"""
    <div class="temperature-display {temp_class}" title="{label}: {formatted_value} PKDaut/slot">
        <span class="temperature-value">{formatted_value}</span>
        <span class="temperature-icon">🌡️</span>
    </div>
    """

    return mark_safe(html)
