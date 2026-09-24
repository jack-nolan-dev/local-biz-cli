"""CLI entry point using Click."""

import csv
import json
import sys

import click

from . import __version__


@click.group()
@click.version_option(__version__)
def main():
    """Local business lead generation and demo site pipeline.

    Find leads, enrich them with contact info, generate demo websites,
    and deploy them -- all from the command line.
    """


@main.command()
@click.option("--query", "-q", required=True, help="Business type (e.g. 'plumbers', 'nail salons')")
@click.option("--location", "-l", required=True, help="City and state (e.g. 'Portland, ME')")
@click.option("--limit", "-n", default=20, help="Max results (default 20)")
@click.option("--output", "-o", help="Save results to JSON file")
@click.option("--no-website-only", is_flag=True, help="Only show businesses without a website")
def find(query, location, limit, output, no_website_only):
    """Find local business leads via Google Places API."""
    from . import places

    click.echo(f"\nSearching for '{query}' in '{location}'...")
    results = places.search(query, location, limit)

    if not results:
        click.echo("No results found.")
        return

    # Score and sort
    for r in results:
        r["score"] = places.score_lead(r)
    results.sort(key=lambda x: -x["score"])

    if no_website_only:
        results = [r for r in results if not r["website"]]

    # Display
    click.echo(f"\n{'='*60}")
    click.echo(f"  Found {len(results)} leads (sorted by opportunity score)")
    click.echo(f"{'='*60}\n")

    for i, r in enumerate(results, 1):
        flag = " *** NO WEBSITE ***" if not r["website"] else ""
        click.echo(f"#{i}  {r['name']}{flag}")
        click.echo(f"    Address : {r['address']}")
        click.echo(f"    Phone   : {r['phone'] or 'N/A'}")
        click.echo(f"    Website : {r['website'] or 'NONE'}")
        click.echo(f"    Rating  : {r['rating']} ({r['reviews']} reviews)")
        click.echo(f"    Score   : {r['score']}/100")
        click.echo()

    no_site = sum(1 for r in results if not r["website"])
    click.echo(f"Summary: {no_site}/{len(results)} have NO website")

    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        click.echo(f"Saved to {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output CSV (default: {input}_enriched.csv)")
@click.option("--limit", "-n", type=int, help="Only process first N rows")
def enrich(input_file, output, limit):
    """Enrich a leads CSV/JSON with emails and owner lookup URLs."""
    from . import emails as email_mod
    from .enrichment import make_lookup_urls
    from .places import parse_address

    # Load input (JSON or CSV)
    if input_file.endswith(".json"):
        with open(input_file) as f:
            rows = json.load(f)
    else:
        with open(input_file, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

    if limit:
        rows = rows[:limit]

    if not output:
        base = input_file.rsplit(".", 1)[0]
        output = base + "_enriched.csv"

    click.echo(f"Enriching {len(rows)} leads from {input_file}\n")

    results = []
    for i, row in enumerate(rows, 1):
        name = row.get("name", "").strip()
        address = row.get("address", "").strip()
        phone = row.get("phone", "").strip()
        website = row.get("website", "").strip()

        click.echo(f"[{i}/{len(rows)}] {name}", nl=False)

        # Hunt email if not already present
        email = row.get("email", "").strip()
        if not email:
            _, city, _, _ = parse_address(address)
            email, source = email_mod.hunt(name, city, website if website != "NONE" else None)
            if email:
                click.echo(f" -- email: {email}", nl=False)

        click.echo()

        urls = make_lookup_urls(name, address)
        results.append({
            "name": name,
            "phone": phone,
            "address": address,
            "email": email or "",
            "website": website,
            "rating": row.get("rating", ""),
            "reviews": row.get("reviews", ""),
            **urls,
            "called": "",
            "result": "",
        })

    fields = ["name", "phone", "address", "email",
              "website", "rating", "reviews",
              "yelp_url", "google_owner_url", "linkedin_url",
              "called", "result"]

    with open(output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    email_count = sum(1 for r in results if r["email"])
    click.echo(f"\nDone. {len(results)} leads -> {output} ({email_count} with email)")


@main.command()
@click.option("--lead", "-l", type=click.Path(exists=True), required=True,
              help="Lead data as JSON file")
@click.option("--template", "-t", required=True, help="Template directory name")
@click.option("--deploy/--no-deploy", default=False, help="Deploy to Vercel after generation")
def generate(lead, template, deploy):
    """Generate a demo website for a single lead."""
    from .generator import generate as gen
    from .deployer import deploy_vercel

    with open(lead) as f:
        lead_data = json.load(f)

    # Handle both single lead dict and array of leads
    if isinstance(lead_data, list):
        lead_data = lead_data[0]

    click.echo(f"Generating demo for {lead_data['name']} using '{template}' template...")
    folder = gen(lead_data, template)

    if not folder:
        click.echo("Generation failed.", err=True)
        sys.exit(1)

    click.echo(f"Generated: {folder}")

    if deploy:
        click.echo("Deploying to Vercel...")
        url = deploy_vercel(folder)
        if url:
            click.echo(f"Live: {url}")
        else:
            click.echo("Deploy failed.", err=True)
            sys.exit(1)


@main.command()
@click.option("--types", "-t", multiple=True, help="Business types to search")
@click.option("--towns", multiple=True, required=True, help="Towns to search (e.g. 'Portland, ME')")
@click.option("--limit", "-n", default=8, help="Results per search (default 8)")
@click.option("--prospect-only", is_flag=True, help="Find leads only, skip demo generation")
@click.option("--no-deploy", is_flag=True, help="Generate demos but don't deploy")
@click.option("--workers", "-w", default=6, help="Parallel email hunting threads (default 6)")
def pipeline(types, towns, limit, prospect_only, no_deploy, workers):
    """Run the full pipeline: find -> enrich -> generate -> deploy."""
    from .pipeline import run

    run(
        types=list(types) if types else None,
        towns=list(towns),
        limit=limit,
        prospect_only=prospect_only,
        deploy=not no_deploy,
        workers=workers,
    )


if __name__ == "__main__":
    main()
