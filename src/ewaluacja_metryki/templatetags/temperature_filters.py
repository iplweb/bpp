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

    # Temperature thresholds in descending order (threshold, class_name)
    thresholds = [
        (200, "temp-200"),
        (180, "temp-180"),
        (160, "temp-160"),
        (140, "temp-140"),
        (120, "temp-120"),
        (100, "temp-100"),
        (80, "temp-80"),
        (60, "temp-60"),
        (40, "temp-40"),
        (20, "temp-20"),
    ]

    for threshold, class_name in thresholds:
        if val >= threshold:
            return class_name

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
    Return a complete temperature display with gradient progress bar.
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0

    # Calculate percentage (0-200 scale)
    percentage = min((val / 200) * 100, 100)

    temp_class = temperature_class(val)
    label = temperature_label(val)

    # Format the value to 2 decimal places
    formatted_value = f"{val:.2f}"

    html = f"""
    <div class="pkd-metric-container" title="{label}: {formatted_value} PKDaut/slot">
        <div class="pkd-value-label">
            <strong>{formatted_value}</strong>
            <small>PKDaut/slot</small>
        </div>
        <div class="pkd-progress-bar">
            <div class="pkd-progress-track">
                <div class="pkd-progress-fill {temp_class}" style="width: {percentage}%">
                    <span class="pkd-marker"></span>
                </div>
            </div>
            <div class="pkd-scale-labels">
                <span>0</span>
                <span>50</span>
                <span>100</span>
                <span>150</span>
                <span>200</span>
            </div>
        </div>
    </div>
    """

    return mark_safe(html)
