# Crosby VW used-vehicle descriptions

Finds used vehicles on crosbyvw.com with no description (or only the generic
"family-owned business for over 50 years" blurb) and builds a review page where
each vehicle gets an inventory type and a ready-to-paste description.

- `prompts/` - the Safety Certified and CPO prompts, and the fixed AS-IS text.
- `scan.py` - pulls the used inventory through the website and writes
  `data/inventory.json` and `review.html`. Run: `python3 scan.py`
- `review_template.html` - the review page; `scan.py` fills in the vehicles and prompts.

## Hosting

GitHub Pages serves the page at https://izzo2thepoint.github.io/Paragon/.
`.github/workflows/pages.yml` rescans the inventory and republishes it every day
at 09:00 UTC (5 a.m. Toronto in summer, 4 a.m. in winter), on every push to
`main`, and on demand from the Actions tab ("Run workflow"). If a scan fails,
the previous page stays up.

## Writing descriptions

Outside Claude (GitHub Pages and the desktop app) the page writes descriptions
through the Anthropic API. Paste an API key from console.anthropic.com into the
box at the top of the page; it is saved only in that browser. API usage is
billed to that Anthropic account, separately from any Claude subscription.
Requests use Claude Opus 5, with Anthropic's default fallback model if a
request is declined. "Copy prompt" still works without a key.

The page embeds the official Anthropic JS SDK from
`vendor/anthropic-sdk.min.js`, so it doesn't depend on a CDN. Rebuild it with
`vendor/build-sdk.sh [version]`.

Type suggestions: certified units default to CPO, units under $5,000 default to
AS-IS, everything else to Safety Certified. Change any of them on the page.

## Desktop app (Windows)

Download `CrosbyDescriptions.exe` from
https://github.com/Izzo2thePoint/Paragon/releases/tag/desktop-app and put it on
your desktop. Double-click it: it scans the live inventory (about a minute),
saves "Crosby Descriptions.html" next to the .exe, and opens it in your browser.

The first time, Windows may show "Windows protected your PC" because the app
isn't signed. Click "More info", then "Run anyway".

`.github/workflows/desktop-app.yml` rebuilds the .exe whenever `scan.py`, the
prompts or the page template change on `main`, so edited prompts reach the app
automatically. Re-download it after a change.
