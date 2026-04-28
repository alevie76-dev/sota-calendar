# SOTA Calendar Integration — Pi Setup

## Files

| File | Purpose |
|------|---------|
| `sota_calendar.py` | Main script |
| `activators.json` | Callsigns to watch outside W7M |
| `service_account.json` | Google service account key (you provide) |
| `processed_alerts.json` | Auto-created; tracks synced alerts |
| `sota_calendar.log` | Auto-created; rolling log |

---

## 1. Copy files to the Pi

From your Mac:
```bash
scp -r ~/Documents/sota-calendar kh7al@192.168.51.2:/home/kh7al/
```

SSH in:
```bash
ssh kh7al@192.168.51.2
```

---

## 2. Install Python dependencies

```bash
cd ~/sota-calendar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Add your service account key

Copy your Google service account JSON file to the Pi as:
```
/home/kh7al/sota-calendar/service_account.json
```

Make sure the service account email has been granted **Editor** access
on the shared Google Calendar.

---

## 4. Test it manually

```bash
cd ~/sota-calendar
source venv/bin/activate
python sota_calendar.py
```

Check the log:
```bash
tail -f sota_calendar.log
```

---

## 5. Install the systemd timer (runs every 15 min)

```bash
sudo cp ~/sota-calendar/sota-calendar.service /etc/systemd/system/
sudo cp ~/sota-calendar/sota-calendar.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sota-calendar.timer
```

Check status:
```bash
systemctl status sota-calendar.timer
systemctl list-timers sota-calendar.timer
journalctl -u sota-calendar.service -f
```

---

## 6. Managing the watched activators list

Edit `activators.json` and add/remove callsigns:

```json
{
  "callsigns": [
    "KK7SDH",
    "K4MEW",
    "W7XYZ"
  ]
}
```

No restart needed — the script reads this file on every run.

---

## How it works

- **W7M alerts** within the next 9 months → creates a normal calendar event
  Title: `LM-175 (K4MEW) - Mount Jumbo`

- **Watched callsigns** activating outside W7M → creates a `[WATCH]` event
  Title: `[WATCH] W7W/WE-006 (KK7SDH) - Mount Spokane`

- **Watched callsigns inside W7M** → treated as a normal W7M event (no `[WATCH]`)

- If SOTA edits an alert, the script detects the change and updates the existing calendar event instead of duplicating it.

- Alerts that disappear from the SOTA API are pruned from tracking (the calendar event is left in place).
