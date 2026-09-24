"""Demo site generation: fill HTML templates with business data."""

import json
import re
import shutil
import urllib.parse

from .config import DEMOS_DIR, TEMPLATES_DIR, get_anthropic_api_key
from .places import parse_address


def generate(lead, template_name):
    """Generate a demo website for a lead using the named template.

    Reads templates/{template_name}/index.html, fills placeholders,
    writes output to output/demos/{slug}/.

    Returns the output directory path, or None on failure.
    """
    template_dir = TEMPLATES_DIR / template_name

    # Find HTML files in the template
    html_files = list(template_dir.glob("*.html"))
    if not html_files:
        print(f"  [error] No HTML files in template: {template_dir}")
        return None

    street, city, state, zip_code = parse_address(lead["address"])
    phone_raw = re.sub(r'\D', '', lead.get("phone", ""))
    biz_name = lead["name"]
    biz_short = _short_name(biz_name)

    # Build replacement map -- uses only public business facts (name, address,
    # phone) and user-supplied or AI-generated copy. No Google review text,
    # reviewer names, or API-key-bearing image URLs are embedded.
    replacements = {
        "{{BUSINESS_NAME}}":       biz_name,
        "{{BUSINESS_NAME_SHORT}}": biz_short,
        "{{CITY}}":                city,
        "{{STATE}}":               state,
        "{{ZIP}}":                 zip_code,
        "{{ADDRESS}}":             street,
        "{{PHONE_DISPLAY}}":       lead.get("phone", ""),
        "{{PHONE_RAW}}":           phone_raw,
        "{{EMAIL}}":               lead.get("email", ""),
        "{{RATING}}":              str(lead.get("rating", "")),
        "{{REVIEW_COUNT}}":        str(lead.get("reviews", "")),
        "{{MAPS_IFRAME}}":         _maps_iframe(street, city, state),
        "{{BOOKING_URL}}":         lead.get("booking_url", "#contact"),
        "{{SERVICE_AREA}}":        lead.get("service_area", f"{city} and surrounding area"),
        "{{FOUNDED}}":             lead.get("founded", ""),
        "{{YEARS}}":               lead.get("years", ""),
        "{{OWNER_NAME}}":          "",
        "{{OWNER_FIRST}}":         "",
        "{{LICENSE}}":             lead.get("license", ""),
        "{{LOCATION_TAG}}":        f"{city}, {state}",
        "{{STREETVIEW_IMG_TAG}}":  "",
        "{{MAP_IMG_TAG}}":         "",
    }

    # Generate AI copy if API key is available, otherwise use defaults
    ai_copy = _generate_copy(lead, template_name)
    replacements.update({
        "{{HERO_H1_LINE1}}":  ai_copy.get("hero_h1_line1", "Quality Service."),
        "{{HERO_H1_LINE2}}":  ai_copy.get("hero_h1_line2", "Every Time."),
        "{{HERO_SUBTEXT}}":   ai_copy.get("hero_subtext", f"Proudly serving {city} and the surrounding area."),
        "{{ABOUT_COPY}}":     ai_copy.get("about_copy", "Built on hard work, honest pricing, and results that speak for themselves."),
    })

    # Copy template dir to output
    out_dir = DEMOS_DIR / _slug(biz_name)
    if out_dir.exists():
        shutil.rmtree(out_dir)

    has_assets = any(template_dir.iterdir()) and len(html_files) > 1
    if has_assets:
        shutil.copytree(template_dir, out_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Fill placeholders in every HTML file
    for html_file in (out_dir.glob("*.html") if has_assets else html_files):
        src = html_file if has_assets else html_file
        dest = out_dir / html_file.name if not has_assets else html_file

        with open(src) as f:
            html = f.read()

        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        with open(dest, "w") as f:
            f.write(html)

    return str(out_dir)


# --- AI Copy Generation ---

_FALLBACK_COPY = {
    "hero_h1_line1": "Quality Service.",
    "hero_h1_line2": "Every Time.",
    "hero_subtext":  "Proudly serving our community with honest work and fair prices.",
    "about_copy":    "Built on hard work, honest pricing, and results that speak for themselves.",
}


def _generate_copy(lead, template_name):
    """Call Claude API to generate unique website copy, or return fallbacks."""
    api_key = get_anthropic_api_key()
    if not api_key:
        return _FALLBACK_COPY

    _, city, state, _ = parse_address(lead["address"])
    rating = lead.get("rating", 4.8)

    prompt = (
        f'You are writing website copy for a local business called "{lead["name"]}" '
        f'in {city}, {state}. It has a {rating} star rating.\n\n'
        f'Write 4 short pieces of copy. Return ONLY valid JSON:\n'
        f'{{"hero_h1_line1": "4-6 word punchy opening line",\n'
        f' "hero_h1_line2": "3-5 word completing line",\n'
        f' "hero_subtext": "One sentence, max 20 words, about what makes them the local go-to",\n'
        f' "about_copy": "One sentence, max 25 words, about their philosophy"}}\n\n'
        f'Rules: No cliches. Sound local and real. Don\'t repeat the business name.'
    )

    try:
        req_body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        import urllib.request
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=req_body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        raw = data["content"][0]["text"].strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        copy = json.loads(raw)
        required = ("hero_h1_line1", "hero_h1_line2", "hero_subtext", "about_copy")
        if all(copy.get(k) for k in required):
            return copy
    except Exception as e:
        print(f"  [AI copy] falling back to defaults: {e}")

    return _FALLBACK_COPY


# --- Helpers ---

def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _short_name(full_name):
    """'Rocco & Sons BarberShop' -> 'Rocco'"""
    cleaned = re.sub(
        r'\b(barbershop|barber shop|salon|spa|nails?|plumbing|heating|'
        r'services?|contractors?|inc\.?|llc\.?|co\.?)\b',
        '', full_name, flags=re.IGNORECASE
    ).strip()
    words = [w for w in re.split(r'[\s&,]+', cleaned) if len(w) > 1]
    return words[0].rstrip("'s") if words else full_name.split()[0]


def _maps_iframe(street, city, state):
    """Google Maps embed iframe (no API key required)."""
    query = urllib.parse.quote(f"{street}, {city}, {state}")
    return (
        f'<iframe src="https://maps.google.com/maps?q={query}&output=embed" '
        f'width="100%" height="200" style="border:0;border-radius:10px;margin-top:20px;" '
        f'allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
    )
