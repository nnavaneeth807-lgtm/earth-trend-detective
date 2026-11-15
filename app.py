import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from scipy.stats import linregress, kendalltau, theilslopes
from datetime import datetime, timezone

st.set_page_config(
    page_title="Earth System Trend Detective",
    page_icon="🌍",
    layout="wide"
)

CITIES = {
    "Shivamogga": (13.9299, 75.5681),
    "Bengaluru": (12.9716, 77.5946),
    "Mangaluru": (12.9141, 74.8560),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
}

PARAMETERS = {
    "T2M": ("Mean temperature", "°C", "mean"),
    "PRECTOTCORR": ("Annual precipitation", "mm/year", "sum"),
    "RH2M": ("Relative humidity", "%", "mean"),
    "WS10M": ("Wind speed", "m/s", "mean"),
}

st.title("🌍 Earth System Trend Detective")
st.caption("Explore long-term Earth-system trends using NASA POWER, with optional short-range weather context from Meteomatics.")
st.info(
    "Historical climate analysis and short-range weather forecasts are shown separately. "
    "A forecast is not a historical observation, and a detected trend does not prove causation."
)

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def fetch_nasa_daily(city: str, start: str, end: str) -> pd.DataFrame:
    lat, lon = CITIES[city]
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": ",".join(PARAMETERS.keys()),
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
        "time-standard": "UTC",
    }
    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    parameter_data = payload["properties"]["parameter"]
    frame = pd.DataFrame(parameter_data)
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame = frame.apply(pd.to_numeric, errors="coerce")
    frame = frame.replace(-999, float("nan"))
    return frame.sort_index()

def annualize(daily: pd.DataFrame) -> pd.DataFrame:
    aggregations = {key: rule for key, (_, _, rule) in PARAMETERS.items()}
    annual = daily.groupby(daily.index.year).agg(aggregations)
    annual.index.name = "Year"
    return annual

def trend_summary(series: pd.Series):
    clean = series.dropna()
    if len(clean) < 8:
        return None
    x = clean.index.astype(float).to_numpy()
    y = clean.to_numpy(dtype=float)
    regression = linregress(x, y)
    tau, p_value = kendalltau(x, y)
    slope, intercept, low, high = theilslopes(y, x)
    if p_value < 0.05 and regression.slope > 0:
        direction = "Increasing"
    elif p_value < 0.05 and regression.slope < 0:
        direction = "Decreasing"
    else:
        direction = "No statistically significant monotonic trend"
    return {
        "direction": direction,
        "slope_decade": slope * 10,
        "p_value": p_value,
        "tau": tau,
        "low_decade": low * 10,
        "high_decade": high * 10,
        "years": len(clean),
    }

def anomaly_table(annual: pd.DataFrame, parameter: str) -> pd.DataFrame:
    baseline = annual.loc[2001:2020, parameter].dropna()
    if len(baseline) < 10:
        return pd.DataFrame()
    mean = baseline.mean()
    std = baseline.std()
    if pd.isna(std) or std == 0:
        return pd.DataFrame()
    out = annual[[parameter]].dropna().copy()
    out["Baseline average"] = mean
    out["Z-score"] = (out[parameter] - mean) / std
    out["Detection"] = out["Z-score"].apply(
        lambda z: "Unusually high" if z >= 2
        else ("Unusually low" if z <= -2 else "Within baseline range")
    )
    out.index.name = "Year"
    return out.reset_index()

@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_meteomatics(username: str, password: str, lat: float, lon: float):
    url = (
        "https://api.meteomatics.com/"
        "now--now+24H:PT1H/"
        "t_2m:C,relative_humidity_2m:p,wind_speed_10m:ms,precip_1h:mm/"
        f"{lat},{lon}/json"
    )
    response = requests.get(url, auth=(username, password), timeout=60)
    response.raise_for_status()
    payload = response.json()
    rows = []
    for item in payload.get("data", []):
        for coordinate in item.get("coordinates", []):
            for obs in coordinate.get("dates", []):
                rows.append({
                    "Time": obs.get("date"),
                    "Parameter": item.get("parameter"),
                    "Value": obs.get("value"),
                })
    return pd.DataFrame(rows)

with st.sidebar:
    st.header("Study settings")
    city = st.selectbox("Study location", list(CITIES.keys()), index=0)
    start_year = st.selectbox("Start year", [2001, 2005, 2010], index=0)
    end_year = st.selectbox("End year", [2023, 2024, 2025], index=2)
    st.caption("NASA POWER data is fetched for the selected city and date range.")
    refresh = st.button("Refresh NASA data")

if start_year >= end_year:
    st.error("Choose an end year later than the start year.")
    st.stop()

start_date = f"{start_year}0101"
end_date = f"{end_year}1231"

try:
    with st.spinner(f"Loading NASA POWER data for {city}..."):
        if refresh:
            fetch_nasa_daily.clear()
        daily = fetch_nasa_daily(city, start_date, end_date)
        annual = annualize(daily)
except Exception as exc:
    st.error(f"NASA POWER request failed: {exc}")
    st.info("Check your internet connection and try Refresh NASA data.")
    st.stop()

st.success(f"NASA POWER data loaded for {city}: {len(daily):,} daily records.")
latest_year = int(annual.index.max())
first_year = int(annual.index.min())

tab_overview, tab_trends, tab_anomalies, tab_map, tab_weather = st.tabs(
    ["Overview", "Trend analysis", "Anomaly detection", "India map", "Meteomatics weather"]
)

with tab_overview:
    st.subheader(f"{city}: historical climate overview")
    cols = st.columns(4)
    for col, (key, (label, unit, _)) in zip(cols, PARAMETERS.items()):
        value = annual[key].mean() if key != "PRECTOTCORR" else annual[key].mean()
        col.metric(label, f"{value:,.2f} {unit}" if pd.notna(value) else "Unavailable")
    selected = st.selectbox(
        "Climate variable",
        list(PARAMETERS.keys()),
        format_func=lambda k: f"{PARAMETERS[k][0]} ({PARAMETERS[k][1]})",
        key="overview_parameter",
    )
    label, unit, _ = PARAMETERS[selected]
    chart = px.line(
        annual.reset_index(), x="Year", y=selected, markers=True,
        title=f"{city} — annual {label.lower()}",
        labels={selected: f"{label} ({unit})"},
        template="plotly_white",
    )
    st.plotly_chart(chart, use_container_width=True)
    st.download_button(
        "Download annual NASA data (CSV)",
        annual.to_csv().encode("utf-8"),
        file_name=f"{city.lower()}_nasa_annual_{first_year}_{latest_year}.csv",
        mime="text/csv",
    )
    st.caption("Precipitation is the sum of daily corrected precipitation values. Other listed variables are annual daily means.")

with tab_trends:
    st.subheader("Statistical trend analysis")
    trend_rows = []
    for key, (label, unit, _) in PARAMETERS.items():
        result = trend_summary(annual[key])
        if result:
            trend_rows.append({
                "Variable": label,
                "Trend": result["direction"],
                f"Theil–Sen slope ({unit}/decade)": round(result["slope_decade"], 4),
                "Kendall tau": round(result["tau"], 3),
                "p-value": round(result["p_value"], 4),
                "Years analysed": result["years"],
            })
    if trend_rows:
        st.dataframe(pd.DataFrame(trend_rows), use_container_width=True, hide_index=True)
        st.caption("Trend direction is classified using Kendall's tau test at p < 0.05. Theil–Sen slope is a robust estimate of change per decade. Serial autocorrelation is not adjusted.")
    else:
        st.warning("Not enough valid annual data to calculate trends.")

with tab_anomalies:
    st.subheader("Unusual climate years")
    st.caption("Anomalies are screened against the 2001–2020 baseline using a z-score threshold of ±2.")
    anomaly_param = st.selectbox(
        "Variable to inspect",
        list(PARAMETERS.keys()),
        format_func=lambda k: f"{PARAMETERS[k][0]} ({PARAMETERS[k][1]})",
        key="anomaly_parameter",
    )
    anomalies = anomaly_table(annual, anomaly_param)
    if anomalies.empty:
        st.warning("There is not enough baseline data to calculate anomalies.")
    else:
        flagged = anomalies[anomalies["Detection"] != "Within baseline range"]
        st.metric("Flagged years", len(flagged))
        st.dataframe(flagged, use_container_width=True, hide_index=True)
        st.download_button(
            "Download anomaly report (CSV)",
            anomalies.to_csv(index=False).encode("utf-8"),
            file_name=f"{city.lower()}_anomalies.csv",
            mime="text/csv",
        )

with tab_map:
    st.subheader("India study locations")
    map_rows = []
    for city_name, (lat, lon) in CITIES.items():
        map_rows.append({"City": city_name, "Latitude": lat, "Longitude": lon})
    map_frame = pd.DataFrame(map_rows)
    map_fig = px.scatter_geo(
        map_frame, lat="Latitude", lon="Longitude", text="City",
        scope="asia", projection="natural earth",
        title="Selected study locations in India",
    )
    map_fig.update_geos(
        showcountries=True, countrycolor="gray",
        lataxis_range=[5, 38], lonaxis_range=[67, 98],
    )
    map_fig.update_traces(marker=dict(size=11))
    map_fig.update_layout(height=550, margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(map_fig, use_container_width=True)
    st.caption("Markers show the seven selected study locations. Select a city in the sidebar to load its NASA POWER historical data.")

with tab_weather:
    st.subheader("Meteomatics: short-range weather")
    st.warning("This section displays forecast values separately from NASA POWER historical climate observations.")
    lat, lon = CITIES[city]
    try:
        username = st.secrets["METEOMATICS_USERNAME"]
        password = st.secrets["METEOMATICS_PASSWORD"]
    except Exception:
        username = None
        password = None

    if not username or not password:
        st.info(
            "Meteomatics credentials are not configured. Add METEOMATICS_USERNAME "
            "and METEOMATICS_PASSWORD in Streamlit Community Cloud → App settings → Secrets. "
            "Do not put credentials in app.py or a public GitHub repository."
        )
    else:
        if st.button("Load 24-hour Meteomatics forecast"):
            try:
                with st.spinner("Requesting Meteomatics forecast..."):
                    forecast = fetch_meteomatics(username, password, lat, lon)
                if forecast.empty:
                    st.warning("The API returned no forecast records.")
                else:
                    forecast["Time"] = pd.to_datetime(forecast["Time"], utc=True)
                    st.success(f"Received {len(forecast)} forecast records for {city}.")
                    st.dataframe(forecast, use_container_width=True, hide_index=True)
                    for parameter in forecast["Parameter"].unique():
                        subset = forecast[forecast["Parameter"] == parameter]
                        fig = px.line(
                            subset, x="Time", y="Value", markers=True,
                            title=f"{parameter} — 24-hour forecast",
                            template="plotly_white",
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    st.download_button(
                        "Download Meteomatics forecast (CSV)",
                        forecast.to_csv(index=False).encode("utf-8"),
                        file_name=f"{city.lower()}_meteomatics_forecast.csv",
                        mime="text/csv",
                    )
            except Exception as exc:
                st.error(f"Meteomatics request failed: {exc}")
                st.caption("Check that the account is still active, credentials are current, and the API plan allows the requested parameters.")

st.divider()
st.caption(
    "Data: NASA POWER and, when configured, Meteomatics. "
    "This educational tool is not an official warning system or a substitute for authoritative local forecasts."
)
