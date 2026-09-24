"""Deploy generated demo sites to Vercel."""

import re
import shutil
import subprocess


def deploy_vercel(folder):
    """Deploy a folder to Vercel and return the live URL, or None on failure."""
    if not shutil.which("vercel"):
        print("  [deploy] Vercel CLI not found. Install: npm i -g vercel")
        return None

    try:
        result = subprocess.run(
            ["vercel", "deploy", "--prod", "--yes", str(folder)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("  [deploy] Vercel deploy timed out")
        return None

    output = result.stdout + result.stderr

    # Look for a clean alias URL first
    for line in output.splitlines():
        line = line.strip()
        if re.match(r'https://[a-z0-9\-]+\.vercel\.app$', line):
            return line

    # Fallback: any vercel.app URL (prefer shortest = alias)
    urls = re.findall(r'https://[a-zA-Z0-9\-]+\.vercel\.app', output)
    if urls:
        urls.sort(key=len)
        return urls[0]

    return None


def deploy_netlify(folder):
    """Deploy a folder to Netlify and return the live URL, or None on failure."""
    if not shutil.which("netlify"):
        print("  [deploy] Netlify CLI not found. Install: npm i -g netlify-cli")
        return None

    try:
        result = subprocess.run(
            ["netlify", "deploy", "--dir", str(folder), "--prod"],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("  [deploy] Netlify deploy timed out")
        return None

    for line in result.stdout.splitlines():
        if "netlify.app" in line or "Website URL" in line:
            for part in line.split():
                if "netlify.app" in part or part.startswith("http"):
                    return part.strip()

    return None
