# local-biz-cli

A command-line pipeline that finds local businesses, enriches them with contact info, generates personalized demo websites, and deploys them -- ready for outreach.

Built for web design agencies and freelancers doing cold outreach to local businesses that need a better web presence.

## How it works

```
local-biz find         Search Google Places for businesses in a target area
     |
local-biz enrich       Hunt for emails, owner names, and research URLs
     |
local-biz generate     Fill an HTML template with real business data
     |
local-biz pipeline     Run the full flow end-to-end across multiple towns
```

## Architecture

```
local_biz/
  cli.py            Click CLI with 4 subcommands
  config.py         .env loading, paths, settings
  places.py         Google Places API (New) -- search, scoring, address parsing
  emails.py         Email extraction from websites + search engines
  enrichment.py     Owner name lookup via DuckDuckGo, research URL generation
  generator.py      Template-based demo site generation + AI copy via Claude API
  deployer.py       Vercel / Netlify deployment
  pipeline.py       Full orchestration with parallel email hunting
```

## Quick start

```bash
# Clone and install
git clone https://github.com/jack-nolan-dev/local-biz-cli.git
cd local-biz-cli
pip install -e .

# Set up API keys
cp .env.example .env
# Edit .env with your Google Places API key

# Find leads
local-biz find -q "plumbers" -l "Portland, ME" -n 10

# Enrich a leads file with emails and owner lookup URLs
local-biz enrich leads.json -o cold_calls.csv

# Generate a demo site from a template
local-biz generate -l lead.json -t plumber_v2

# Run the full pipeline across multiple towns
local-biz pipeline --towns "Portland, ME" "Manchester, NH" -t Barbershop -n 8
```

## Example output

```
$ local-biz find -q "barbershops" -l "Portland, ME" -n 5

============================================================
  Found 5 leads (sorted by opportunity score)
============================================================

#1  Classic Cuts Barbershop *** NO WEBSITE ***
    Address : 142 Congress St, Portland, ME 04101, USA
    Phone   : (207) 555-0184
    Website : NONE
    Rating  : 4.9 (63 reviews)
    Score   : 70/100

#2  Harbor Fades
    Address : 88 Exchange St, Portland, ME 04101, USA
    Phone   : (207) 555-0221
    Website : https://www.facebook.com/harborfades
    Rating  : 4.8 (89 reviews)
    Score   : 50/100

Summary: 1/5 have NO website
```

```
$ local-biz pipeline --towns "Portland, ME" -t Barbershop -n 5

============================================================
  PIPELINE  |  2026-09-24 10:30
============================================================
  Types: 1  x  Towns: 1  =  1 searches
  Limit per search: 5

[Barbershop]
  Portland, ME: 5 results
  Hunting emails for 4 unique businesses...
  + Classic Cuts Barbershop -- info@classiccuts.com
  + Harbor Fades -- mike@harborfades.com

  Total leads: 2

  Generating demos...

  Building: Classic Cuts Barbershop (barber_v2)... generated -> deploying... LIVE: https://classic-cuts-barbershop.vercel.app
  Building: Harbor Fades (barber_v2)... generated -> deploying... LIVE: https://harbor-fades.vercel.app

============================================================
  SUMMARY
============================================================
  Demos deployed:   2
  Without demo:     0
```

## Templates

Drop your HTML templates in `./templates/`. Each template is a directory with an `index.html` that uses `{{PLACEHOLDER}}` variables:

| Placeholder | Description |
|---|---|
| `{{BUSINESS_NAME}}` | Full business name |
| `{{BUSINESS_NAME_SHORT}}` | Abbreviated name for logos |
| `{{CITY}}`, `{{STATE}}`, `{{ZIP}}` | Location |
| `{{ADDRESS}}` | Street address |
| `{{PHONE_DISPLAY}}`, `{{PHONE_RAW}}` | Phone (formatted + digits only) |
| `{{EMAIL}}` | Contact email |
| `{{RATING}}`, `{{REVIEW_COUNT}}` | Google rating and review count |
| `{{HERO_H1_LINE1}}`, `{{HERO_H1_LINE2}}` | AI-generated hero headline |
| `{{HERO_SUBTEXT}}` | AI-generated subheadline |
| `{{ABOUT_COPY}}` | AI-generated about section |
| `{{MAPS_IFRAME}}` | Google Maps embed |
| `{{STREETVIEW_IMG_TAG}}` | Street View image |

If an `ANTHROPIC_API_KEY` is set, hero and about copy are generated per-business via Claude. Otherwise, sensible defaults are used.

## Tech stack

- **Python 3.10+** -- stdlib `urllib` for HTTP (zero heavy dependencies)
- **Click** -- clean CLI with subcommands and help text
- **Google Places API (New)** -- business discovery and metadata
- **Claude API** -- AI-generated website copy (optional)
- **Vercel CLI** -- one-command deployment

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Yes | Google Places API key |
| `ANTHROPIC_API_KEY` | No | Enables AI-generated website copy |
| `LOCAL_BIZ_OUTPUT` | No | Output directory (default: `./output`) |
| `LOCAL_BIZ_TEMPLATES` | No | Template directory (default: `./templates`) |

## License

MIT
