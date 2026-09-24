# Crosby VW used-vehicle descriptions

Finds used vehicles on crosbyvw.com with no description (or only the generic
"family-owned business for over 50 years" blurb) and builds a review page where
each vehicle gets an inventory type and a ready-to-paste description.

- `prompts/` - the Safety Certified and CPO prompts, and the fixed AS-IS text.
- `scan.py` - pulls the used inventory through the website and writes
  `data/inventory.json` and `review.html`. Run: `python3 scan.py`
- `review_template.html` - the review page; `scan.py` fills in the vehicles and prompts.

Type suggestions: certified units default to CPO, units under $5,000 default to
AS-IS, everything else to Safety Certified. Change any of them on the page.
