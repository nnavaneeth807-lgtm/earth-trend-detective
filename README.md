# Earth System Trend Detective

A Streamlit web dashboard for exploring historical climate indicators from NASA POWER and optional short-range weather forecasts from Meteomatics.

## Features
- NASA POWER daily point data for seven Indian study locations
- Annual temperature, precipitation, humidity and wind summaries
- Trend analysis using linear regression, Kendall tau and Theil–Sen slope
- Simple anomaly screening against a 2001–2020 baseline
- India study-location map
- Optional Meteomatics 24-hour forecast integration
- CSV downloads

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Meteomatics credentials
For local use, create `.streamlit/secrets.toml`:
```toml
METEOMATICS_USERNAME = "your_username"
METEOMATICS_PASSWORD = "your_password"
```
Never commit this file. Add `.streamlit/` to `.gitignore`.

For Streamlit Community Cloud, paste the two key-value entries into App settings -> Secrets. Do not put credentials in source code or a public repository. Credentials are optional; NASA POWER features work without them.

## Deploy
1. Push `app.py`, `requirements.txt`, and `README.md` to a GitHub repository.
2. Sign in at https://share.streamlit.io/ with GitHub.
3. Create app, choose the repository, branch `main`, and main file `app.py`.
4. In Advanced settings, configure Python 3.12 if needed.
5. Add Meteomatics secrets only if the account is still active.
6. Deploy.

## Important limitations
- NASA POWER is gridded/reanalysis-derived point data, not a local weather-station observation.
- Annual summaries hide seasonal patterns.
- Trend p-values here do not adjust for serial autocorrelation.
- Statistical association does not establish causation.
- The Meteomatics panel shows a short-range forecast, not historical observations.
- This is an educational research prototype, not an official early-warning service.
