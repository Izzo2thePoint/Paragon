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

On GitHub Pages the "Write with Claude" button is hidden; use "Copy prompt" and
paste into Claude.

Type suggestions: certified units default to CPO, units under $5,000 default to
AS-IS, everything else to Safety Certified. Change any of them on the page.
