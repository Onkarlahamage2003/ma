"""
Mandi Price — Live App
=======================
One process that serves the dashboard AND the live data API, so you can run it
on your laptop and open it from your laptop's browser or your phone.

SETUP (one time)
-----------------
1. Install Python 3.9+ if you don't have it.
2. In this folder, run:
       pip install -r requirements.txt
3. Get a free API key from https://data.gov.in/ (Sign up -> My Account -> API Key)
   and set it:
       export DATA_GOV_IN_API_KEY="your_key_here"      (Mac/Linux)
       set DATA_GOV_IN_API_KEY=your_key_here            (Windows cmd)
   Without a key it falls back to the public sample key (slow / rate-limited —
   fine to test, get your own key for real use).

RUN
---
    python app.py

Then:
- On your laptop:  http://localhost:5000
- On your phone (same WiFi as your laptop): find your laptop's local IP
  (Mac: System Settings > WiFi > Details;  Windows: `ipconfig`, look for IPv4)
  then open http://<that-ip>:5000 on your phone's browser.

TO USE IT FROM ANYWHERE (not just home WiFi)
---------------------------------------------
Deploy this same folder to a free host so it gets a permanent public URL:
- Render.com (free web service): connect this folder as a repo, build command
  `pip install -r requirements.txt`, start command `python app.py`.
- Or Railway.app / PythonAnywhere — same idea.
Once deployed, that URL works on any phone or laptop, anywhere, no WiFi sharing needed.
"""

import os
from datetime import timedelta

import pandas as pd
import requests
from flask import Flask, jsonify, Response, request

import cache

API_KEY = os.environ.get(
    "DATA_GOV_IN_API_KEY",
    "579b464db66ec23bdd000001cdd3946e44ce4988839e6d2f76b81d6",  # public sample key, rate-limited
)
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

app = Flask(__name__)

# The entire frontend lives right here as a string — no separate templates/
# folder to accidentally leave out of a git push. One file, one deploy, done.
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Mandi Price Forecast — Live</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#F7F5EF; --ink:#20281F; --panel:#FFFFFF; --line:#DEDACB;
    --green:#33513A; --green-soft:#E4EAE1; --amber:#C98A1F; --amber-soft:#F6E9D2;
    --muted:#726E60; --danger:#A8452F;
    box-sizing:border-box;
    padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#181A15; --ink:#EDE9DC; --panel:#21241D; --line:#34372C;
      --green:#8FBF9B; --green-soft:#26301F; --amber:#E3A93B; --amber-soft:#332816;
      --muted:#9A9686; --danger:#E08066;
    }
  }
  html{scroll-padding-top:env(safe-area-inset-top,0px);}
  *{box-sizing:border-box;}
  body{margin:0; background:var(--bg); color:var(--ink); font-family:'Inter',system-ui,sans-serif; -webkit-font-smoothing:antialiased;}
  h1,.num{font-family:'Fraunces',Georgia,serif;}
  .wrap{max-width:980px; margin:0 auto; padding:24px 18px 50px;}
  header{display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:18px; flex-wrap:wrap;}
  header h1{font-size:1.4rem; font-weight:600; margin:0; letter-spacing:-0.01em;}
  .badge{font-size:0.76rem; padding:4px 10px; border-radius:99px; font-weight:600; white-space:nowrap;}
  .badge.live{background:var(--green-soft); color:var(--green);}
  .badge.demo{background:var(--amber-soft); color:var(--amber);}
  .controls{display:flex; gap:8px; margin-bottom:8px; flex-wrap:wrap;}
  select, input[type=text]{font:inherit; padding:10px 12px; border-radius:10px; border:1px solid var(--line); background:var(--panel); color:var(--ink); font-size:0.92rem;}
  select{min-width:170px;}
  input[type=text]{width:150px;}
  .hint{font-size:0.78rem; color:var(--muted); margin:0 0 18px;}
  .grid{display:grid; grid-template-columns:1.1fr 1.4fr; gap:14px;}
  @media (max-width:720px){ .grid{grid-template-columns:1fr;} }
  .card{background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px;}
  .label{font-size:0.78rem; color:var(--muted);}
  .hero-price{display:flex; align-items:flex-end; gap:8px; margin:6px 0 2px;}
  .hero-price .num{font-size:2.4rem; font-weight:500; line-height:1;}
  .hero-price .unit{color:var(--muted); font-size:0.88rem; padding-bottom:5px;}
  .stat-row{display:flex; gap:20px; margin-top:16px; padding-top:14px; border-top:1px solid var(--line); flex-wrap:wrap;}
  .stat .num{font-size:1.05rem; font-weight:600;}
  canvas{max-width:100%;}
  .forecast-band{margin-top:16px; padding:14px; border-radius:12px; background:var(--amber-soft); border:1px solid var(--line);}
  .forecast-range{display:flex; align-items:baseline; gap:8px;}
  .forecast-range .num{font-size:1.5rem; font-weight:600; color:var(--amber);}
  .confidence-bar{height:6px; border-radius:4px; background:var(--line); margin-top:10px; overflow:hidden;}
  .confidence-fill{height:100%; background:var(--amber); border-radius:4px;}
  .note{font-size:0.8rem; color:var(--muted); margin-top:8px; line-height:1.5;}
  .error{padding:14px; border-radius:10px; background:var(--danger); color:#fff; font-size:0.88rem; display:none; margin-bottom:14px;}
  .loading{font-size:0.85rem; color:var(--muted);}
  button{font:inherit; padding:10px 16px; border-radius:10px; border:none; background:var(--green); color:#fff; font-weight:600; cursor:pointer; font-size:0.9rem;}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Mandi Price Forecast</h1>
    <span class="badge" id="statusBadge">⏳ checking…</span>
  </header>

  <div class="controls">
    <select id="commoditySelect">
      <option>Onion</option><option>Tomato</option><option>Potato</option>
      <option>Wheat</option><option>Soyabean</option><option>Cotton</option>
      <option>Banana</option><option>Mango</option>
    </select>
    <input type="text" id="stateInput" placeholder="State (optional)">
    <input type="text" id="marketInput" placeholder="Market (optional)">
    <select id="horizonSelect">
      <option value="30">+1 month</option>
      <option value="60" selected>+2 months</option>
      <option value="90">+3 months</option>
    </select>
    <button id="goBtn">Update</button>
  </div>
  <p class="hint">Leave state/market blank to average across all reporting mandis for that commodity.</p>

  <div class="error" id="errorBox"></div>

  <div class="grid">
    <div class="card">
      <div class="label">Current modal price</div>
      <div class="hero-price"><span class="num" id="curPrice">—</span><span class="unit">₹ / quintal</span></div>
      <div class="label" id="asOf"></div>
      <div class="stat-row">
        <div class="stat"><div class="label">52-wk high</div><div class="num" id="hiPrice">—</div></div>
        <div class="stat"><div class="label">52-wk low</div><div class="num" id="loPrice">—</div></div>
        <div class="stat"><div class="label">Markets seen</div><div class="num" id="marketCount">—</div></div>
      </div>
      <div class="forecast-band">
        <div class="label" id="forecastLabel">Expected range</div>
        <div class="forecast-range"><span class="num" id="fcLow">—</span><span>–</span><span class="num" id="fcHigh">—</span><span class="unit">₹/quintal</span></div>
        <div class="confidence-bar"><div class="confidence-fill" id="confFill" style="width:0%"></div></div>
        <div class="note" id="fcNote"></div>
      </div>
    </div>
    <div class="card">
      <div class="label" style="margin-bottom:10px;">Recent price history</div>
      <canvas id="priceChart" height="230"></canvas>
    </div>
  </div>
</div>

<script>
const fmt = n => n==null ? '—' : '₹' + Math.round(n).toLocaleString('en-IN');
let chart;

async function loadData(){
  const commodity = document.getElementById('commoditySelect').value;
  const state = document.getElementById('stateInput').value.trim();
  const market = document.getElementById('marketInput').value.trim();
  const horizon = document.getElementById('horizonSelect').value;
  const badge = document.getElementById('statusBadge');
  const errorBox = document.getElementById('errorBox');
  errorBox.style.display = 'none';
  badge.textContent = '⏳ loading…'; badge.className='badge demo';

  const params = new URLSearchParams({commodity, horizon});
  if(state) params.set('state', state);
  if(market) params.set('market', market);

  try{
    const res = await fetch('/api/price?' + params.toString());
    const data = await res.json();
    if(!res.ok){ throw new Error(data.error || 'Request failed'); }
    render(data);
    badge.textContent = '🟢 Live from data.gov.in';
    badge.className = 'badge live';
  }catch(err){
    errorBox.textContent = 'Could not load live data: ' + err.message;
    errorBox.style.display = 'block';
    badge.textContent = '⚪ No data';
    badge.className = 'badge demo';
  }
}

function render(data){
  document.getElementById('curPrice').textContent = fmt(data.current_price);
  document.getElementById('asOf').textContent = 'as of ' + (data.as_of || '—');
  const prices = data.history.map(h=>h.price);
  document.getElementById('hiPrice').textContent = fmt(Math.max(...prices));
  document.getElementById('loPrice').textContent = fmt(Math.min(...prices));
  document.getElementById('marketCount').textContent = (data.markets_included||[]).length || '—';

  const fc = data.forecast;
  if(fc){
    document.getElementById('forecastLabel').textContent = 'Expected range around ' + fc.target_date;
    document.getElementById('fcLow').textContent = fmt(fc.forecast_low);
    document.getElementById('fcHigh').textContent = fmt(fc.forecast_high);
    document.getElementById('confFill').style.width = '60%';
    document.getElementById('fcNote').textContent = 'Blend of last-90-day trend and same calendar window one year ago.';
  }

  const ctx = document.getElementById('priceChart').getContext('2d');
  const styles = getComputedStyle(document.documentElement);
  const green = styles.getPropertyValue('--green').trim();
  const ink = styles.getPropertyValue('--ink').trim();
  const line = styles.getPropertyValue('--line').trim();
  const labels = data.history.map(h=>h.date.slice(5));
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type:'line',
    data:{ labels, datasets:[{label:data.commodity, data:prices, borderColor:green, backgroundColor:green+'22', fill:true, tension:0.25, pointRadius:0, borderWidth:2.5}]},
    options:{ responsive:true,
      plugins:{ legend:{position:'bottom', labels:{color:ink, font:{size:11}}} },
      scales:{ x:{ticks:{color:ink, maxTicksLimit:8, font:{size:10}}, grid:{color:line}},
               y:{ticks:{color:ink, font:{size:10}}, grid:{color:line}} } }
  });
}

document.getElementById('goBtn').addEventListener('click', loadData);
document.getElementById('commoditySelect').addEventListener('change', loadData);
loadData();
</script>
</body>
</html>
"""


def fetch_prices(commodity, state=None, market=None, limit=1000):
    params = {
        "api-key": API_KEY,
        "format": "json",
        "limit": limit,
        "filters[commodity]": commodity,
    }
    if state:
        params["filters[state]"] = state
    if market:
        params["filters[market]"] = market

    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    records = resp.json().get("records", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], format="%d/%m/%Y", errors="coerce")
    for col in ["min_price", "max_price", "modal_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["arrival_date", "modal_price"]).sort_values("arrival_date")
    return df


def forecast_price(daily_series, horizon_days):
    """daily_series: pandas Series indexed by date, modal price. Seasonal+trend blend."""
    if daily_series.empty or len(daily_series) < 10:
        return None

    last_date = daily_series.index[-1]
    last_price = float(daily_series.iloc[-1])

    recent = daily_series.tail(90)
    slope = float(recent.diff().mean()) if len(recent) >= 5 else 0.0
    trend_projection = last_price + slope * horizon_days

    target_date = last_date + timedelta(days=horizon_days)
    window = daily_series[
        (daily_series.index >= target_date - pd.Timedelta(days=372))
        & (daily_series.index <= target_date - pd.Timedelta(days=358))
    ]
    seasonal_projection = float(window.mean()) if not window.empty else last_price

    blended = 0.45 * trend_projection + 0.55 * seasonal_projection
    spread = float(daily_series.tail(180).std() or 0) * 0.6 + max(50.0, last_price * 0.04)

    return {
        "target_date": target_date.strftime("%Y-%m-%d"),
        "forecast_mid": round(blended, 2),
        "forecast_low": round(max(0, blended - spread), 2),
        "forecast_high": round(blended + spread, 2),
        "last_price": round(last_price, 2),
        "as_of": last_date.strftime("%Y-%m-%d"),
    }


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/price")
def api_price():
    commodity = request.args.get("commodity", "Onion")
    state = request.args.get("state") or None
    market = request.args.get("market") or None
    horizon = int(request.args.get("horizon", 60))

    try:
        df = fetch_prices(commodity, state, market)
    except requests.RequestException as e:
        return jsonify({"error": f"Could not reach data.gov.in: {e}"}), 502

    if df.empty and cache.load_history(commodity).empty:
        return jsonify({"error": f"No records found for '{commodity}'"
                                  f"{' in ' + state if state else ''}"
                                  f"{' at ' + market if market else ''}."}), 404

    # Save today's pull, then merge with everything cached from past runs —
    # the more this app gets used over time, the deeper this history gets.
    if not df.empty:
        cache.save_records(commodity, df)

    cached = cache.load_history(commodity)
    fresh_daily = df.groupby("arrival_date")["modal_price"].mean().rename("modal_price").reset_index() \
        if not df.empty else pd.DataFrame(columns=["arrival_date", "modal_price"])
    fresh_daily = fresh_daily.rename(columns={"arrival_date": "date"})

    merged = pd.concat([cached, fresh_daily]).groupby("date")["modal_price"].mean().sort_index()
    daily = merged.resample("D").mean().interpolate()

    history = [{"date": d.strftime("%Y-%m-%d"), "price": round(float(p), 2)}
               for d, p in daily.tail(365).items()]

    fc = forecast_price(daily, horizon)

    return jsonify({
        "commodity": commodity,
        "current_price": history[-1]["price"] if history else None,
        "as_of": history[-1]["date"] if history else None,
        "history": history,
        "forecast": fc,
        "markets_included": sorted(df["market"].dropna().unique().tolist())[:10],
    })


cache.init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render/hosts set PORT themselves
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("Starting Mandi Price live app...")
    print(f"  Laptop:  http://localhost:{port}")
    print(f"  Phone (same WiFi): http://<your-laptop-local-ip>:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
