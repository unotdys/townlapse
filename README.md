# Neighborhood Timeline Map

A satellite map of a neighborhood with a timeline slider from 1900 to today: drag it and see which shops,
restaurants, theaters and offices stood on each block in any year. Neighbors suggest places they remember,
an AI checks each suggestion against old newspapers and the web, and accepted ones appear on the map within minutes.

**Live example:** Downtown Palo Alto, https://ofcourseduh.com/downtownpaloalto/ (and this repo's own build: https://unotdys.github.io/neighborhood-timeline-map/)
**Part of:** HUB_NAME_PLACEHOLDER, a directory of neighborhood maps (coming soon)

Everything runs on free services: **GitHub Pages** (the map), **GitHub Actions** (builds, AI review, weekly refresh),
**GitHub Issues** (the suggestion queue), and optionally a **Cloudflare Worker** (forms without a GitHub account,
a contact form, and a connector for Meta's Muse agent). The only possible cost is the AI review (see below).

## How it works

```
 visitor ──"Suggest a place"──▶ Cloudflare Worker ──▶ GitHub issue (label: suggestion)
                                                            │
                         GitHub Action: scripts/review.py ◀─┘
                         AI checks the claim on the web (or a maintainer approves)
                            ├─ accept     → data/suggestions_applied.json → rebuild → GitHub Pages
                            ├─ needs info → label "needs-info" → (optional) Muse searches local Facebook groups
                            │                └─ findings posted on the issue → reviewed again
                            └─ reject     → issue closed with the reason
 weekly GitHub Action: scripts/fetch_osm.py → today's businesses from OpenStreetMap
```

## Make it yours (about 15 minutes)

1. **Copy this repo**: click **Use this template** (or fork it). Make the copy public (GitHub Pages is free for public repos).
2. **Edit `config.json`**:
   - `title`, `description`, `startYear`, `geocodeSuffix` (e.g. `"Ann Arbor, MI"`; appended to addresses when looking them up)
   - `area.polygon`: the corners of your neighborhood as `[lat, lng]` points (right-click a spot in Google Maps to copy its coordinates). Today's businesses are taken from OpenStreetMap inside this shape.
   - `map.bearing`: which compass direction points up on screen (0 = north; Palo Alto uses 38.2 so its main street runs straight up).
     `map.bottom` / `map.top`: two points the opening view fits between. `map.streetLabels`: optional labels.
   - `github.repo`: `"your-name/your-repo"`.
3. **Replace `data/history.json`** with your neighborhood's places (see *Data format*). Start with a handful you know; neighbors will add the rest.
4. **Clear the Palo Alto data**: set `data/osm_current.json` to `{"elements": []}` and `data/geocache.json` to `{}`, then run the **Refresh today's businesses** workflow once (Actions tab → Run workflow).
5. **Turn on Pages**: Settings → Pages → Source: **GitHub Actions**. Push any change (or run **Build and deploy the map**) and your map is live at `https://your-name.github.io/your-repo/`.
6. **Create the labels** used by the reviewer (Issues → Labels): `suggestion`, `needs-info`, `needs-review`, `muse-reported`, `approved`, `accepted`, `declined`.
7. **Pick a reviewer** (Settings → Secrets and variables → Actions):
   - **Claude** (best results): secret `ANTHROPIC_API_KEY`. Uses web search; roughly $0.05–$0.50 per suggestion.
   - **Gemini**: secret `GEMINI_API_KEY` from Google AI Studio. Has a free tier with Google Search grounding (limits change; check AI Studio).
   - **Manual** (free): add no key. Each suggestion waits for you; add the `approved` label to publish it as submitted.
   Optional variables: `REVIEW_PROVIDER` (`anthropic`/`gemini`/`manual`), `ANTHROPIC_MODEL`, `GEMINI_MODEL`.

Without the Worker, the **Suggest a place** button opens a GitHub issue form (visitors need a GitHub account) and **Contact us** is hidden.

## Optional: the Cloudflare Worker (free)

Lets anyone suggest without a GitHub account, adds **Contact us** (emails you; your address is never shown), and serves the Muse connector.

1. Create a free Cloudflare account. In `worker/wrangler.toml` set `GITHUB_REPO`, `ALLOWED_ORIGINS` (your Pages URL) and `SITE_NAME`.
2. Create a GitHub **fine-grained token** limited to this repo with **Issues: Read and write**. Then:
   `cd worker && npx wrangler secret put GITHUB_TOKEN && npx wrangler deploy`
3. Put the Worker's URL in `config.json` → `api.url`. (Set `api.contact` to `true` once email is set up in step 4.)
4. *Contact form:* needs a domain on Cloudflare with **Email Routing** on and your address verified as a destination; then fill
   `FROM_ADDRESS` / `TO_ADDRESS` and uncomment the `send_email` block.
5. *Rate limiting:* create a KV namespace and uncomment the `RATE` block.

## Optional: Facebook history groups via Muse

Much neighborhood memory lives in Facebook groups that web search can't read. If you use Meta's **Muse** agent and belong to local history groups:

1. `npx wrangler secret put MUSE_KEY` (any long random string) and redeploy the Worker.
2. In Muse, ask: *Create a custom connector named "Neighborhood map" for a remote MCP server. URL: `https://<your-worker>/mcp` (streamable HTTP). Auth header: `x-dpa-key`.* Paste the key into Muse's secure prompt (never into the chat), and approve Muse sharing data with your Worker's domain.
3. Ask Muse to run a daily task: list unconfirmed suggestions, search your Facebook groups, report findings for each, and only read (never post or message anyone).

Muse only reads the suggestions marked `needs-info`, and its findings are posted on the issue **without links or names**; the reviewer then decides again, treating Facebook posts as recollections (years marked approximate).

## Data format

`data/history.json` is a list of places:

```json
{"name": "Varsity Theatre", "address": "456 University Ave", "start": 1927, "end": 1994,
 "category": "entertainment", "approx": false, "note": "Movie palace; later a Borders bookstore."}
```

- `category`: `retail`, `food`, `entertainment`, `tech`, `hotel`, `landmark`, `services`, `fitness`
- `end: null` means still open; `start: null` means open today with the opening year unknown
- `approx: true` shows the years with `~`
- Add `"lat"` / `"lng"` if the address can't be looked up (otherwise it is geocoded with OpenStreetMap Nominatim and cached in `data/geocache.json`)

Accepted suggestions go to `data/suggestions_applied.json` (additions and corrections), so `history.json` stays yours to curate.
To build locally: `python3 scripts/build.py`, then open `site/index.html` through any local web server.

## Safety and privacy

- Suggestions are untrusted text. The AI only gets web search and returns a verdict; `scripts/review.py` validates it and is the only thing that writes data.
- The Worker never puts submitters' email addresses in public issues; they are emailed privately to the owner.
- Muse findings are posted without links or names of private people.
- Satellite imagery: check your tile provider's terms for your use and swap `imagery.url` if needed.

## Licenses

- **Code:** MIT (see `LICENSE`).
- **Data** (`data/` and the published `places.json`): includes OpenStreetMap data, so it is published under the
  **Open Database License (ODbL) 1.0**. By submitting a suggestion you agree it may be published under the same license.
  Map data © OpenStreetMap contributors.
