"""Lead enrichment: generate research URLs for manual owner lookup."""

import urllib.parse


def make_lookup_urls(business_name, address, owner_name=None):
    """Generate research URLs for manual enrichment.

    Returns dict with yelp_url, google_owner_url, linkedin_url.
    These are clickable links for the user to manually research
    owner names -- no automated scraping.
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
