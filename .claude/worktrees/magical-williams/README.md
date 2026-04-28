# SOTA Calendar Builder

A web tool for generating customizable ICS calendars from the [SOTA Alerts API](https://api2.sota.org.uk/api/alerts).

Built by [OpsRelay](https://ops-relay.co).

---

## What it does

[SOTA (Summits on the Air)](https://www.sota.org.uk) is an amateur radio program where operators activate mountain summits worldwide. Activators post advance alerts so other operators know when and where to listen.

**SOTA Calendar Builder** lets you:

- Select one or more SOTA associations (countries/regions) from 400+ worldwide
- Optionally narrow down to specific regions within an association
- Add a watchlist of activator callsigns to track across any association
- Set an alert window from 1 week up to 12 months out
- Preview matching alerts before exporting
- Download an `.ics` file for one-time import, or subscribe via a live `webcal://` URL for automatic updates

The resulting calendar events appear in Google Calendar, Outlook, Apple Calendar, or any ICS-compatible app — with the summit name, activator callsign, planned frequencies, and a direct link to the summit on [SOTLAS](https://sotl.as).

---

## Quickstart (local)

```bash
git clone https://github.com/YOUR_USERNAME/sota-calendar.git
cd sota-calendar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Deploying to Render

1. Fork or clone this repo to your GitHub account
2. Create a new **Web Service** on [Render](https://render.com) and connect the repo
3. Render auto-detects `render.yaml` — confirm settings and deploy
4. Optionally add a custom domain in **Settings → Custom Domains**

**Environment variables** (all optional — see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `CACHE_TTL` | `1800` | Seconds to cache the SOTA alerts list in memory |

No API keys are required. The app uses only the public SOTA Alerts API.

---

## Calendar subscription (live auto-updating)

After building your calendar in the UI, click **Copy Subscribe URL** to get a `webcal://` URL. Paste it into your calendar app as a subscription — it will automatically refresh every 30 minutes.

This requires the server to be publicly accessible (e.g. hosted on Render or behind a Cloudflare Tunnel).

---

## Pi-based Google Calendar sync (`sota_calendar.py`)

This repo also contains `sota_calendar.py`, a separate script for syncing SOTA alerts directly to a shared Google Calendar via a service account. It is designed to run on a Raspberry Pi via a systemd timer. See [SETUP.md](SETUP.md) for setup instructions.

The Pi sync script and the web calendar builder are independent — you can run either or both.

---

## Stack

- **Backend:** Python / Flask
- **ICS generation:** [icalendar](https://pypi.org/project/icalendar/)
- **Frontend:** Vanilla JS + Tailwind CSS
- **Data:** [SOTA Alerts API](https://api2.sota.org.uk/api/alerts) (public, no auth required)

---

## Disclaimer

This project is not affiliated with or endorsed by the SOTA Management Team.
SOTA data is used in accordance with the public SOTA API.
