"""Email discovery: scrape business websites and search engines for contact emails."""

import re
import time
import urllib.request
import urllib.parse

from .config import SCRAPE_HEADERS

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Domains that aren't real business emails
SKIP_DOMAINS = {
    "sentry.io", "wixpress.com", "squarespace.com", "example.com",
    "domain.com", "email.com", "yoursite.com", "site.com",
    "google.com", "facebook.com", "instagram.com", "twitter.com",
    "yelp.com", "tripadvisor.com", "apple.com", "icloud.com",
    "myshopify.com", "weebly.com", "godaddy.com", "bluehost.com",
    "zendesk.com", "mailchimp.com", "constantcontact.com",
    "getbento.com", "latofonts.com",
}

SKIP_LOCALPARTS = {
    "hi", "hello", "test", "demo", "admin", "webmaster",
    "postmaster", "noreply", "no-reply", "donotreply",
    "newsletter", "abuse", "hostmaster", "spam", "user",
}

SKIP_TLDS = {".ru", ".de", ".uk", ".cn", ".fr", ".eu", ".nl", ".pl",
             ".ua", ".br", ".mx", ".au", ".ca", ".in"}

SUSPICIOUS = [
    re.compile(r'impallari'),
    re.compile(r'@fonts\.'),
    re.compile(r'@schema\.'),
    re.compile(r'@w3\.org'),
]

_PLACEHOLDER_RE = re.compile(r'^[a-z]\.[a-z]{2,}$')


def extract(text):
    """Extract valid business emails from raw text. Returns deduplicated list."""
    found = EMAIL_RE.findall(text)
    clean, seen = [], set()

    for email in found:
        email = email.lower().strip(".")
        localpart = email.split("@")[0]
        domain = email.split("@")[-1]
        tld = "." + domain.rsplit(".", 1)[-1] if "." in domain else ""

        if domain in SKIP_DOMAINS:
            continue
        if any(domain.endswith("." + skip) for skip in SKIP_DOMAINS):
            continue
        if localpart in SKIP_LOCALPARTS:
            continue
        if _PLACEHOLDER_RE.match(localpart):
            continue
        if tld in SKIP_TLDS:
            continue
        if any(p.search(email) for p in SUSPICIOUS):
            continue
        if re.search(r'\.(png|jpg|gif|svg|webp)$', email):
            continue

        if email not in seen:
            seen.add(email)
            clean.append(email)

    return clean


def _fetch(url, timeout=8):
    """Fetch a URL and return its text content."""
    try:
        req = urllib.request.Request(url, headers=SCRAPE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(80_000)
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def hunt(name, city, website=None):
    """Hunt for a business email across multiple sources.

    Tries: (1) their website, (2) Google search.
    Returns (email, source) or (None, None).
    """
    # 1. Scrape their website
    if website and "facebook.com" not in website and "yelp.com" not in website:
        emails = extract(_fetch(website))
        if not emails:
            emails = extract(_fetch(website.rstrip("/") + "/contact"))
        if emails:
            return emails[0], "website"

    # 2. Google search fallback
    q = urllib.parse.quote(f'"{name}" "{city}" email contact')
    emails = extract(_fetch(f"https://www.google.com/search?q={q}&num=5"))
    if emails:
        return emails[0], "google"

    return None, None
