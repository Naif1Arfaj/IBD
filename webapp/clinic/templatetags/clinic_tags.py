import re

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def clinical_group(group):
    """Presentation labels; keep stored feature groups and calculations unchanged."""
    return {
        "Demographic data": "Patient profile",
        "Birth mode and early life": "Birth & early life",
        "Metabolism related biomarkers": "Metabolic biomarkers",
        "Red flags": "Red flags & surgical history",
    }.get(group, group)


@register.filter
def readable_text(value):
    """Repair reversible UTF-8/Windows text artifacts at display time only."""
    text = str(value or "")
    for _ in range(2):
        if not any(marker in text for marker in ("\u00c3", "\u00c2", "\u00e2\u20ac", "\u00e2\u2020")):
            break
        try:
            text = text.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
    return text

# Minimal stroke icons (24x24, Lucide-style), inlined so the app needs no CDN.
ICONS = {
    "bell": '<path d="M6 9a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18 14.8c2 .7 3.2 2.4 3.6 5.2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.2-6 8-6s7 2 8 6"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z"/><path d="M4 19a2 2 0 0 1 2-2h13"/><path d="M9 7h6"/>',
    "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "back": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "arrow": '<path d="M5 12h14M13 5l7 7-7 7"/>',
    "brain": '<path d="M9 4a3 3 0 0 0-3 3v.2A3 3 0 0 0 4 10a3 3 0 0 0 1 2.2A3 3 0 0 0 6 17a3 3 0 0 0 3 3V4z"/><path d="M15 4a3 3 0 0 1 3 3v.2A3 3 0 0 1 20 10a3 3 0 0 1-1 2.2 3 3 0 0 1-1 4.8 3 3 0 0 1-3 3V4z"/><path d="M9 9H7.5M15 9h1.5M9 14H7M15 14h2"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "clipboard": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 12h6M9 16h4"/>',
    "flask": '<path d="M9 3h6M10 3v6L4.5 18.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3"/><path d="M7 15h10"/>',
    "microbe": '<circle cx="12" cy="12" r="5"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.9 2.9M15.5 15.5l2.9 2.9M5.6 18.4l2.9-2.9M15.5 8.5l2.9-2.9"/>',
    "pill": '<path d="m10.5 20.5 10-10a4.9 4.9 0 0 0-7-7l-10 10a4.9 4.9 0 0 0 7 7z"/><path d="m8.5 8.5 7 7"/>',
    "utensils": '<path d="M4 3v7a3 3 0 0 0 3 3v8M10 3v7a3 3 0 0 1-3 3M7 3v6"/><path d="M17 21V3a4 4 0 0 1 3 4v6h-3"/>',
    "family": '<circle cx="7" cy="7" r="3"/><circle cx="17" cy="7" r="3"/><circle cx="12" cy="14" r="2.5"/><path d="M2 20c.4-3 2.4-5 5-5M22 20c-.4-3-2.4-5-5-5M8.5 21c.4-2 1.8-3.5 3.5-3.5s3.1 1.5 3.5 3.5"/>',
    "baby": '<circle cx="12" cy="8" r="5"/><path d="M10 8h.01M14 8h.01M10.5 10.5a2 2 0 0 0 3 0"/><path d="M7 21c.5-3 2.5-5 5-5s4.5 2 5 5"/>',
    "heart": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21.2l8.8-8.8a5.5 5.5 0 0 0 0-7.8z"/>',
    "flag": '<path d="M4 22V4M4 4h12l-2 4 2 4H4"/>',
    "drop": '<path d="M12 2.7 6.3 9.5a7 7 0 1 0 11.4 0z"/>',
    "printer": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 4 13c0-5 4-9 16-10-1 12-5 16-9 17z"/><path d="M4 21c3-5 6-8 10-10"/>',
    "shield": '<path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z"/><path d="m9 12 2 2 4-4"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
}

GROUP_ICONS = {
    "Demographic data": "user", "Family history": "family", "Diet": "utensils", "Lifestyle": "activity",
    "Medication and antibiotics": "pill", "Birth mode and early life": "baby", "Microbiome diversity": "microbe",
    "Inflammatory biomarkers": "flask", "Metabolism related biomarkers": "drop", "Red flags": "flag",
}


@register.simple_tag
def icon(name, size=20, cls=""):
    body = ICONS.get(name, ICONS["file"])
    return mark_safe(
        f'<svg class="ic {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>')


@register.filter
def group_icon(group):
    return GROUP_ICONS.get(group, "file")


@register.filter
def cite(text, prefix):
    """Escape text, keep paragraphs, and turn [n] markers into links to the reference list."""
    html = escape(text)
    html = re.sub(r"\[(\d+)\]", lambda m: f'<sup class="cite"><a href="#{prefix}-{m.group(1)}">{m.group(1)}</a></sup>', html)
    paras = [p.strip() for p in html.split("\n\n") if p.strip()]
    return mark_safe("".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paras))


@register.simple_tag
def paper_url(ref):
    return f'{reverse("paper", args=[ref["file"]])}#page={ref["page"]}'


@register.filter
def pct(value, digits=0):
    try:
        return f"{float(value) * 100:.{int(digits)}f}%"
    except (TypeError, ValueError):
        return ""


@register.filter
def tier_class(tier):
    return {"High": "high", "Moderate": "moderate", "Low": "low"}.get(tier, "")
