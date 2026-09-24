"""Google Places API (New) wrapper for local business discovery."""

import json
import re
import urllib.request
import urllib.parse

from .config import get_places_api_key

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
])

# National chains that won't respond to cold outreach
CHAIN_BLOCKLIST = {
    "crunch fitness", "planet fitness", "anytime fitness", "la fitness",
    "orangetheory", "ymca", "ywca", "snap fitness", "equinox",
    "gold's gym", "golds gym", "lifetime fitness", "f45", "solidcore",
    "mcdonalds", "mcdonald's", "subway", "domino's", "dominos",
    "pizza hut", "dunkin", "starbucks", "chipotle", "panera",
    "great clips", "sport clips", "supercuts", "fantastic sams",
    "jiffy lube", "valvoline", "midas", "meineke", "pep boys",
    "mr. rooter", "roto-rooter", "home depot", "lowe's", "lowes",
    "chick-fil-a", "papa john's", "jersey mike's",
}


def search(query, location, limit=20):
    """Search Google Places for businesses matching a query in a location.

    Returns a list of place dicts with keys: name, address, phone,
    website, rating, reviews, raw (original API response).
    """
    api_key = get_places_api_key()
    payload = json.dumps({
        "textQuery": f"{query} in {location}",
        "maxResultCount": min(limit, 20),
        "languageCode": "en",
    }).encode()

    req = urllib.request.Request(
        PLACES_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise SystemExit(f"Places API error {e.code}: {body}")

    results = []
    for place in data.get("places", []):
        name = place.get("displayName", {}).get("text", "").strip()
        if not name:
            continue

        # Skip chains
        if any(chain in name.lower() for chain in CHAIN_BLOCKLIST):
            continue

        results.append(_normalize_place(place))

    return results


def _normalize_place(place):
    """Flatten a Places API response into a clean dict.

    Only exports business name, address, phone, website, rating, and
    review count. Review text, photos, and hours are NOT exported to
    comply with Google Maps Platform Terms of Service.
    """
    return {
        "name": place.get("displayName", {}).get("text", "").strip(),
        "address": place.get("formattedAddress", ""),
        "phone": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "rating": place.get("rating", 0),
        "reviews": place.get("userRatingCount", 0),
    }


def parse_address(full_address):
    """Parse '123 Main St, Quincy, MA 02169, USA' into components.

    Returns (street, city, state, zip_code).
    """
    parts = [p.strip() for p in full_address.split(",")]
    if parts and parts[-1].strip().upper() == "USA":
        parts = parts[:-1]
    state_zip = parts[-1].strip().split() if parts else []
    state = state_zip[0] if len(state_zip) >= 1 else ""
    zip_code = state_zip[1] if len(state_zip) >= 2 else ""
    city = parts[-2].strip() if len(parts) >= 2 else ""
    street = parts[0].strip() if parts else ""
    return street, city, state, zip_code


def score_lead(place):
    """Score how promising a lead is (0-100). Higher = better target."""
    score = 0
    website = place.get("website", "")

    if not website:
        score += 50  # No website at all
    elif any(x in website.lower() for x in [
        "facebook.com", "yelp.com", "wixsite.com", "squarespace.com"
    ]):
        score += 30  # Weak web presence
    else:
        score += 5   # Has a real website

    review_count = place.get("reviews", 0)
    if review_count > 10:
        score += 10
    if review_count > 50:
        score += 10

    return score
