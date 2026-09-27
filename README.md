# Mandi Price Forecast — Live App

Live mandi (Agmarknet) commodity prices + a harvest-time price forecast,
as a small Flask app you can run locally or deploy for free.

## Run locally
```
pip install -r requirements.txt
export DATA_GOV_IN_API_KEY="your_key_here"   # get free at https://data.gov.in
python app.py
```
Open http://localhost:5000 on your laptop, or http://<laptop-local-ip>:5000
on your phone (same WiFi).

## Deploy to Render (free, public URL, works on any device anywhere)
1. Push this folder to a new GitHub repo.
2. Go to https://render.com → sign in with GitHub → **New +** → **Web Service**.
3. Connect the repo.
4. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
   - **Instance type:** Free
5. Under **Environment**, add a variable: `DATA_GOV_IN_API_KEY` = your key.
6. Deploy. Render gives you a URL like `https://your-app.onrender.com` —
   that works from any phone or laptop, no shared WiFi needed.

Notes:
- Free-tier Render services spin down after ~15 minutes idle and take a
  few seconds to wake back up on the next request — normal, not a bug.
- The free tier's disk is not persistent across restarts/redeploys, so
  `price_cache.db` (the growing local history) resets each time the service
  restarts. For real persistent history, either add a Render **paid** disk,
  or swap `cache.py` for a free hosted Postgres (Neon or Supabase both have
  free tiers) — same function names, different connection.

## Improving forecast accuracy further
- The forecast currently blends a 90-day trend with the same calendar
  window a year ago. This gets meaningfully better the deeper the price
  history is — which is what `cache.py` is for.
- Once you have 1+ year of real daily history (via persistent cache or a
  hosted DB), swap in Facebook Prophet for the forecast — it handles
  seasonality and trend changes properly instead of the current linear blend.
  (`pip install prophet`, then replace the `forecast_price` call with a
  Prophet fit — ask if you want this wired in.)
