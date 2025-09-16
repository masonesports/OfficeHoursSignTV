# OfficeHoursSignTV

A simple Flask app to display and manage an office hours schedule (Monday–Friday).

## Setup

1. Create a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the app

```bash
python app.py
```

- The site will be available at `http://127.0.0.1:5000/`.
- The schedule persists to `schedule.json` in the project root.

## Update the schedule

Two ways to update times:

1) Single day via JSON body fields `day` and `time`:

```bash
curl -X POST http://127.0.0.1:5000/api/schedule \
  -H 'Content-Type: application/json' \
  -d '{"day": "Monday", "time": "2–4 PM"}'
```

2) Bulk update with a JSON object of `day: time` pairs (partial or full):

```bash
curl -X POST http://127.0.0.1:5000/api/schedule \
  -H 'Content-Type: application/json' \
  -d '{
    "Monday": "2–4 PM",
    "Tuesday": "",
    "Wednesday": "10–12 PM",
    "Thursday": "",
    "Friday": "1–3 PM"
  }'
```

## Using in Python code

You can import and call the function that sets the time:

```python
from app import set_time

set_time("Monday", "2–4 PM")
```

## GitHub Pages (static hosting)

This repo also includes a static site for GitHub Pages:

- Root `index.html` loads `schedule.json` and renders the Monday–Friday table using JavaScript.
- Styling is shared via `static/style.css`.

To update the public schedule on GitHub Pages:

- Edit `schedule.json` directly in the repo and commit to the Pages branch (usually `main` or `gh-pages`).
- GitHub Pages will serve the updated JSON; the page fetches it on load.

Local preview of the static site:

```bash
python3 -m http.server 8080
# Then open http://127.0.0.1:8080/
```

Notes:
- If you use both Flask and static Pages, treat `schedule.json` as the source of truth. The Flask app writes to the same `schedule.json`, so you can update locally via the API, commit the new JSON, and push to Pages.
- GitHub Pages may cache assets; hard refresh if updates don’t appear immediately.

## Notes

- Supported days: Monday–Friday.
- Empty string means no hours set; the page shows an em dash (—).
- This app is for local or small internal use. For production, consider a real database and proper auth.