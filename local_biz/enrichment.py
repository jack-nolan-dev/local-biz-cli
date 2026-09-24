"""Lead enrichment: owner name lookup via web scraping."""

import re
import urllib.request
import urllib.parse
from html.parser import HTMLParser

from .config import SCRAPE_HEADERS

# Patterns that match owner names in search result snippets
OWNER_PATTERNS = [
    re.compile(r'owner[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})', re.I),
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})[,\s]+(?:owner|founder|proprietor)', re.I),
    re.compile(r'(?:hi|hello)[,\s]+(?:i\'?m|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.I),
    re.compile(r'(?:my name is|i\'?m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.I),
    re.compile(r'[-\u2013]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*(?:owner|founder)', re.I),
]

FALSE_POSITIVES = {
    'the', 'our', 'your', 'this', 'that', 'we', 'they', 'he', 'she',
    'thank', 'thanks', 'google', 'yelp', 'facebook', 'instagram',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'january', 'february', 'march', 'april', 'june', 'july', 'august',
    'september', 'october', 'november', 'december', 'please', 'feel', 'free',
    'hello', 'great', 'service', 'best', 'highly', 'recommend',
}


class _DDGParser(HTMLParser):
    """Extract result snippets from DuckDuckGo's HTML results."""

    def __init__(self):
        super().__init__()
        self.snippets = []
        self._in_snippet = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get('class', '')
        if 'result__snippet' in cls or 'result__body' in cls:
            self._in_snippet = True
            self._depth = 0
            self.snippets.append('')
        elif self._in_snippet:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._in_snippet:
            if self._depth == 0:
                self._in_snippet = False
            else:
                self._depth -= 1

    def handle_data(self, data):
        if self._in_snippet and self.snippets:
            self.snippets[-1] += data


def _extract_owner_name(text):
    """Try to extract an owner name from text. Returns (name, confidence) or (None, None)."""
    for pattern in OWNER_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            if not name[0].isupper():
                continue
            first = name.split()[0].lower()
            if first not in FALSE_POSITIVES and len(name) > 3:
                return name, "high"
    return None, None


def search_owner(business_name, address):
    """Search DuckDuckGo for a business owner's name.

    Returns (owner_name, confidence, google_search_url).
    """
    city_state = _extract_city_state(address)
    query = f'"{business_name}" {city_state} owner'.strip()
    google_url = f'https://www.google.com/search?q={urllib.parse.quote(query)}'

    try:
        encoded = urllib.parse.urlencode({'q': query})
        url = f'https://html.duckduckgo.com/html/?{encoded}'
        req = urllib.request.Request(url, headers=SCRAPE_HEADERS)

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        parser = _DDGParser()
        parser.feed(html)

        for snippet in parser.snippets:
            name, confidence = _extract_owner_name(snippet)
            if name:
                return name, confidence, google_url
    except Exception:
        pass

    return None, None, google_url


def make_lookup_urls(business_name, address, owner_name=None):
    """Generate research URLs for manual enrichment.

    Returns dict with yelp_url, google_owner_url, linkedin_url.
    """
    city_state = _extract_city_state(address)

    yelp_url = (
        f'https://www.yelp.com/search?find_desc={urllib.parse.quote(business_name)}'
        f'&find_loc={urllib.parse.quote(city_state)}'
    )
    google_url = (
        f'https://www.google.com/search?q='
        f'{urllib.parse.quote(f"{business_name} {city_state} owner")}'
    )
    keywords = f'{owner_name} {business_name}' if owner_name else business_name
    linkedin_url = (
        f'https://www.linkedin.com/search/results/people/'
        f'?keywords={urllib.parse.quote(keywords)}'
    )

    return {
        "yelp_url": yelp_url,
        "google_owner_url": google_url,
        "linkedin_url": linkedin_url,
    }


def _extract_city_state(address):
    """Pull 'City, STATE' from a full address string."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(',')]
    if len(parts) >= 3:
        return f'{parts[-3]}, {parts[-2]}'
    if len(parts) >= 2:
        return parts[-2]
    return ""
