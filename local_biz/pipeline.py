"""Full pipeline: find leads -> hunt emails -> generate demos -> deploy."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from . import places, emails
from .config import RESULTS_DIR
from .deployer import deploy_vercel
from .generator import generate

# Business types with template mappings and outreach hooks
BUSINESS_TYPES = [
    {"query": "barbershops",                "label": "Barbershop",      "template": "barber_v2"},
    {"query": "nail salons",                "label": "Nail Salon",      "template": "nail_salon"},
    {"query": "pizza restaurants",          "label": "Pizza Restaurant","template": "restaurant"},
    {"query": "plumbers plumbing",          "label": "Plumber",         "template": "plumber_v2"},
    {"query": "auto repair shops",          "label": "Auto Repair",     "template": "auto_shop"},
    {"query": "gyms fitness centers",       "label": "Gym",             "template": "gym"},
    {"query": "landscaping lawn care",      "label": "Landscaper",      "template": "landscaper"},
    {"query": "roofers roofing",            "label": "Roofer",          "template": "roofer"},
    {"query": "electricians",               "label": "Electrician",     "template": "electrician"},
    {"query": "dentists dental offices",    "label": "Dentist",         "template": "dentist"},
]


def run(types=None, towns=None, limit=8, prospect_only=False,
        deploy=True, workers=6, min_rating=3.8, min_reviews=10, max_reviews=500):
    """Run the full lead generation pipeline.

    Args:
        types: List of business type labels to search (default: all).
        towns: List of "City, ST" strings to search (default: must provide).
        limit: Max Places API results per search.
        prospect_only: If True, skip demo generation and deployment.
        deploy: If True, deploy generated demos to Vercel.
        workers: Thread pool size for parallel email hunting.
        min_rating: Skip businesses below this rating.
        min_reviews: Skip businesses with fewer reviews.
        max_reviews: Skip businesses with more reviews (likely chains).

    Returns:
        List of lead dicts with results.
    """
    if not towns:
        raise SystemExit("No towns specified. Use --towns 'City, ST' or provide a list.")

    active_types = BUSINESS_TYPES
    if types:
        type_lower = [t.lower() for t in types]
        active_types = [t for t in BUSINESS_TYPES if t["label"].lower() in type_lower]

    total = len(active_types) * len(towns)
    print(f"\n{'='*60}")
    print(f"  PIPELINE  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"  Types: {len(active_types)}  x  Towns: {len(towns)}  =  {total} searches")
    print(f"  Limit per search: {limit}\n")

    # Phase 1: Find leads and hunt emails
    all_leads = []
    seen_names = set()

    for btype in active_types:
        print(f"\n[{btype['label']}]")
        all_places = []

        for town in towns:
            results = places.search(btype["query"], town, limit)
            print(f"  {town}: {len(results)} results")

            for place in results:
                name = place["name"]
                if name in seen_names:
                    continue
                if place["rating"] < min_rating:
                    continue
                if place["reviews"] < min_reviews or place["reviews"] > max_reviews:
                    continue
                seen_names.add(name)
                all_places.append(place)

        print(f"  Hunting emails for {len(all_places)} unique businesses...")
        found = 0

        def _process(place):
            _, city, _, _ = places.parse_address(place["address"])
            email, source = emails.hunt(place["name"], city, place.get("website"))
            if not email:
                return None
            place["email"] = email
            place["email_source"] = source
            place["template"] = btype["template"]
            place["biz_type"] = btype["label"]
            return place

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_process, p): p for p in all_places}
            for fut in as_completed(futures):
                lead = fut.result()
                if lead:
                    all_leads.append(lead)
                    found += 1
                    print(f"  + {lead['name']} -- {lead['email']}")

        print(f"  -> {found} leads with emails")

    print(f"\n  Total leads: {len(all_leads)}")

    if not all_leads:
        print("  No leads found.")
        return []

    if prospect_only:
        _save_results(all_leads)
        return all_leads

    # Phase 2: Generate demos and deploy
    print(f"\n  Generating demos...\n")

    for lead in all_leads:
        template = lead.get("template")
        if not template:
            continue

        print(f"  Building: {lead['name']} ({template})...", end=" ", flush=True)
        folder = generate(lead, template)

        if not folder:
            print("FAILED")
            continue

        print("generated", end="")

        if deploy:
            print(" -> deploying...", end=" ", flush=True)
            url = deploy_vercel(folder)
            if url:
                lead["demo_url"] = url
                print(f"LIVE: {url}")
            else:
                print("deploy failed")
            time.sleep(1)
        else:
            lead["demo_folder"] = folder
            print(f" -> {folder}")

    _save_results(all_leads)
    _print_summary(all_leads)
    return all_leads


def _save_results(leads):
    """Save pipeline results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"run_{ts}.json"

    # Strip non-serializable data
    clean = []
    for lead in leads:
        clean.append({k: v for k, v in lead.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))})

    with open(out_path, "w") as f:
        json.dump(clean, f, indent=2)

    latest = RESULTS_DIR / "latest.json"
    with open(latest, "w") as f:
        json.dump(clean, f, indent=2)

    print(f"\n  Results saved -> {out_path}")


def _print_summary(leads):
    with_demo = [l for l in leads if l.get("demo_url")]
    without = [l for l in leads if not l.get("demo_url")]

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Demos deployed:   {len(with_demo)}")
    print(f"  Without demo:     {len(without)}")

    if with_demo:
        print(f"\n  READY:")
        for l in with_demo:
            print(f"    {l['name']}")
            print(f"      Email: {l['email']}")
            print(f"      Demo:  {l['demo_url']}")
