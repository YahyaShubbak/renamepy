import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from scipy.optimize import curve_fit

# --- SCRAPE ELECTRICITY PRICES FROM BDEW ---
import requests
from bs4 import BeautifulSoup
import pandas as pd

def get_electricity_prices():
    url = "https://charts.bdew-data.de/ojEOF/30/dataset.csv"
    try:
        print(f"Requesting {url} ...")
        df = pd.read_csv(url, sep=",", encoding="utf-8")
        # Sum all columns except the year to get total ct/kWh
        year_col = [c for c in df.columns if "Berechnungsstichtag" in c or "Jahr" in c][0]
        value_cols = [c for c in df.columns if c != year_col]
        years = df[year_col].astype(int).values
        prices = df[value_cols].astype(float).sum(axis=1).values
        print(f"Scraped years: {years}")
        print(f"Scraped prices: {prices}")
        return years, prices
    except Exception as e:
        print(f"Webscraping failed, trying local CSV. Error: {e}")
        try:
            df = pd.read_csv("C:/Users/yshub/Documents/GitHub/Other/Bread_price/dataset_electricity.csv", sep=",", encoding="utf-8")
            year_col = [c for c in df.columns if "Berechnungsstichtag" in c or "Jahr" in c][0]
            value_cols = [c for c in df.columns if c != year_col]
            years = df[year_col].astype(int).values
            prices = df[value_cols].astype(float).sum(axis=1).values
            print(f"Loaded years from local CSV: {years}")
            print(f"Loaded prices from local CSV: {prices}")
            return years, prices
        except Exception as e2:
            print(f"Local CSV loading failed, using hardcoded electricity prices. Error: {e2}")
            return None
# --- HARDCODED DATA FROM USER ---
years = np.arange(2015, 2026)

# Try to get scraped electricity prices
scraped = get_electricity_prices()
if scraped:
    elec_years, elec_prices = scraped
    # Only use years in our range
    mask = (elec_years >= years[0]) & (elec_years <= years[-1])
    if mask.sum() > 2:
        elec_years = elec_years[mask]
        elec_prices = elec_prices[mask]
        print("Using electricity prices scraped from BDEW.")
    else:
        # Not enough data, fallback
        elec_years = np.array([2015, 2023, 2025])
        elec_prices = np.array([27.5, 34, 35.86])
        print("Not enough scraped data, using hardcoded electricity prices.")
else:
    elec_years = np.array([2015, 2023, 2025])
    elec_prices = np.array([27.5, 34, 35.86])
    print("Using hardcoded electricity prices.")

all_elec = np.interp(years, elec_years, elec_prices)


# Actual bread prices per kg (2015–2025)
bread_price_years = np.arange(2015, 2026)
bread_prices_per_kg = np.array([
    2.50,  # 2015
    2.50,  # 2016
    2.50,  # 2017
    2.50,  # 2018
    2.50,  # 2019
    2.60,  # 2020
    2.70,  # 2021
    3.10,  # 2022
    3.35,  # 2023
    3.45,  # 2024
    3.50   # 2025
])
all_bread = np.interp(years, bread_price_years, bread_prices_per_kg)

# flour prices per kg (2015–2025)
flour_price_years = np.arange(2015, 2026)
flour_price_markenmehl = np.array([
    0.79,  # 2015
    0.79,  # 2016
    0.79,  # 2017
    0.79,  # 2018
    0.79,  # 2019
    0.79,  # 2020
    0.85,  # 2021
    1.29,  # 2022
    1.29,  # 2023
    1.38,  # 2024
    1.38   # 2025
])
all_flour_markenmehl = np.interp(years, flour_price_years, flour_price_markenmehl)

# --- PREDICT NEXT 5 YEARS (simple linear fit) ---
def linear(x, a, b):
    return a * x + b

future_years = np.arange(years[-1]+1, years[-1]+15)

# Electricity prediction
popt_elec, _ = curve_fit(linear, years, all_elec)
future_elec = linear(future_years, *popt_elec)

# Bread prediction (now using updated prices)
popt_bread, _ = curve_fit(linear, years, all_bread)
future_bread = linear(future_years, *popt_bread)
all_bread_full = np.concatenate([all_bread, future_bread])

#Flour price prediction
popt_flour, _ = curve_fit(linear, years, all_flour_markenmehl)
future_flour = linear(future_years, *popt_flour)
all_flour_markenmehl = np.concatenate([all_flour_markenmehl, future_flour])

# Combine all years and prices
all_years = np.concatenate([years, future_years])
all_elec_full = np.concatenate([all_elec, future_elec])
all_bread_full = np.concatenate([all_bread, future_bread])
all_flour_markenmehl = np.concatenate([all_flour_markenmehl, future_flour])

kneader_price = 1000  # EUR
kneader_power = 0.5  # kW
knead_time = 0.25  # hours (15 min)
oven_power = 0.93  # kW
bake_time = 0.75  # hours
preheat_time = 0.75  # hours
weeks_per_year = 52
flour_per_bread_kg = 0.6  # 800g

# ...existing code...

# --- USER PARAMETERS ---
possible_breads_per_week = [1, 2, 3, 4]
possible_loaves_per_batch = [1, 2, 3, 4]
oven_capacity = 2  # how many loaves fit in the oven at once

# --- PRECOMPUTE ALL SCENARIOS ---
scenario_results = {}
for breads_per_week in possible_breads_per_week:
    for loaves_per_batch in possible_loaves_per_batch:
        weeks_per_year = 52
        breads_per_year = breads_per_week * weeks_per_year
        baking_sessions_per_year = int(np.ceil(breads_per_year / loaves_per_batch))
        batches_per_session = int(np.ceil(loaves_per_batch / oven_capacity))
        total_bake_time_per_year = baking_sessions_per_year * batches_per_session * bake_time
        total_preheat_time_per_year = baking_sessions_per_year * preheat_time
        total_knead_time_per_year = baking_sessions_per_year * knead_time * kneader_power
        total_kWh_per_year = (
            total_knead_time_per_year +
            oven_power * (total_bake_time_per_year + total_preheat_time_per_year)
        )
        kWh_per_bread = total_kWh_per_year / breads_per_year
        elec_costs_per_bread = all_elec_full / 100 * kWh_per_bread  # ct to EUR
        flour_costs_per_bread = flour_per_bread_kg * all_flour_markenmehl
        buy_costs = all_bread_full * breads_per_year

        # Calculate cumulative costs with reset at kneader purchase
        buy_costs_1 = []
        bake_costs_1 = []
        buy_costs_2 = []
        bake_costs_2 = []

        kneader_added_year = 2025  # Year when kneader is bought
        kneader_added_idx = np.where(all_years == kneader_added_year)[0][0]

        # First phase: before kneader is bought (up to 2024)
        for i in range(kneader_added_idx):
            annual_bake_cost = (elec_costs_per_bread[i] + flour_costs_per_bread[i]) * breads_per_year
            if i == 0:
                buy_costs_1.append(all_bread_full[i] * breads_per_year)
                bake_costs_1.append(annual_bake_cost)
            else:
                buy_costs_1.append(buy_costs_1[-1] + all_bread_full[i] * breads_per_year)
                bake_costs_1.append(bake_costs_1[-1] + annual_bake_cost)

        # Second phase: after kneader is bought (from 2025)
        for i in range(kneader_added_idx, len(all_years)):
            annual_bake_cost = (elec_costs_per_bread[i] + flour_costs_per_bread[i]) * breads_per_year
            if i == kneader_added_idx:
                buy_costs_2.append(all_bread_full[i] * breads_per_year)
                bake_costs_2.append(kneader_price + annual_bake_cost)
            else:
                buy_costs_2.append(buy_costs_2[-1] + all_bread_full[i] * breads_per_year)
                bake_costs_2.append(bake_costs_2[-1] + annual_bake_cost)

        scenario_results[(breads_per_week, loaves_per_batch)] = {
            "buy_costs_1": buy_costs_1,
            "bake_costs_1": bake_costs_1,
            "buy_costs_2": buy_costs_2,
            "bake_costs_2": bake_costs_2,
            "kneader_added_idx": kneader_added_idx
        }

# --- PLOT WITH DROPDOWN ---
import plotly.io as pio

# Default selection
default_breads_per_week = 2
default_loaves_per_batch = 2

def make_traces(breads_per_week, loaves_per_batch):
    res = scenario_results[(breads_per_week, loaves_per_batch)]
    kneader_added_idx = res["kneader_added_idx"]
    traces = [
        go.Scatter(
            x=all_years[:kneader_added_idx], y=res["buy_costs_1"],
            name="Brot beim Bäcker (bis 2024)", mode='lines+markers', line=dict(color='blue')
        ),
        go.Scatter(
            x=all_years[:kneader_added_idx], y=res["bake_costs_1"],
            name="Brot zu Hause (bis 2024)", mode='lines+markers', line=dict(color='orange')
        ),
        go.Scatter(
            x=all_years[kneader_added_idx:], y=res["buy_costs_2"],
            name="Brot beim Bäcker (ab 2025)", mode='lines+markers', line=dict(color='blue', dash='dash')
        ),
        go.Scatter(
            x=all_years[kneader_added_idx:], y=res["bake_costs_2"],
            name="Brot zu Hause (ab 2025, mit Kneter)", mode='lines+markers', line=dict(color='orange', dash='dash')
        ),
    ]
    return traces

# Create figure
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.15,
    subplot_titles=(
        "Brot- und Strompreisentwicklung (EUR/Leib, ct/kWh)",
        "Kosten Brot Kaufen vs Backen"
    ),
    specs=[[{"secondary_y": True}], [{}]]
)

# Top plot: Bread and electricity price
fig.add_trace(go.Scatter(
    x=all_years, y=all_bread_full, name="Brotpreis (EUR/Leib)", mode='lines+markers'
), row=1, col=1, secondary_y=False)
fig.add_trace(go.Scatter(
    x=all_years, y=all_elec_full, name="Stromkosten (ct/kWh)", mode='lines+markers'
), row=1, col=1, secondary_y=True)
fig.add_trace(go.Scatter(
    x=all_years, y=all_flour_markenmehl, name="Weizenmehl (EUR/kg)", mode='lines+markers'
), row=1, col=1, secondary_y=False)

# Add default traces for bottom plot
for trace in make_traces(default_breads_per_week, default_loaves_per_batch):
    fig.add_trace(trace, row=2, col=1)

# Dropdown menus
dropdown_buttons = []
for breads_per_week in possible_breads_per_week:
    for loaves_per_batch in possible_loaves_per_batch:
        visible = [True]*3  # top plot always visible
        # For each scenario, only show the corresponding traces in the bottom plot
        for b in possible_breads_per_week:
            for l in possible_loaves_per_batch:
                if (b, l) == (breads_per_week, loaves_per_batch):
                    visible += [True]*4
                else:
                    visible += [False]*4
        label = f"{breads_per_week} Brote/Woche, {loaves_per_batch} Brote/Backvorgang"
        dropdown_buttons.append(dict(
            label=label,
            method="update",
            args=[
                {"visible": visible},
                {"annotations": []}  # Optionally update annotation text
            ]
        ))

# Add all scenario traces (hidden except default)
for b in possible_breads_per_week:
    for l in possible_loaves_per_batch:
        if (b, l) == (default_breads_per_week, default_loaves_per_batch):
            continue  # already added
        for trace in make_traces(b, l):
            fig.add_trace(trace, row=2, col=1)

# Add dropdown
fig.update_layout(
    updatemenus=[
        dict(
            buttons=dropdown_buttons,
            direction="down",
            showactive=True,
            x=0.5,
            y=1.15,
            xanchor="center",
            yanchor="top"
        )
    ]
)

# --- Add parameter annotation to bottom plot (for default) ---
param_text = (
    f"<b>Parameter:</b><br>"
    f"Brote/Woche: {default_breads_per_week}<br>"
    f"Brote/Backvorgang: {default_loaves_per_batch}<br>"
    f"Kneter: {kneader_price} €<br>"
    f"Kneten: {kneader_power} kW × {knead_time} h<br>"
    f"Vorheizen: {oven_power} kW × {preheat_time} h<br>"
    f"Backen: {oven_power} kW × {bake_time} h<br>"
)
fig.add_annotation(
    text=param_text,
    xref="paper", yref="paper",
    x=0.01, y=0.52,  # top left of bottom plot (relative coordinates)
    showarrow=False,
    align="left",
    font=dict(size=13),
    bordercolor="black",
    borderwidth=1,
    bgcolor="white",
    row=2, col=1
)

# Layout
fig.update_yaxes(title_text="Brotpreis (EUR/loaf)", row=1, col=1, secondary_y=False)
fig.update_yaxes(title_text="Strompreis (ct/kWh)", row=1, col=1, secondary_y=True)
fig.update_yaxes(title_text="EUR (kumuliert)", row=2, col=1)
fig.update_xaxes(title_text="Jahr", row=2, col=1)
fig.update_layout(
    height=1400,
    legend=dict(x=0.01, y=0.99),
    showlegend=True
)

# Highlight prediction area (from 2026 onwards)
prediction_start = 2026
fig.add_vrect(
    x0=prediction_start - 0.5, x1=all_years[-1] + 0.5,
    fillcolor="lightgray", opacity=0.3, layer="below", line_width=0,
    row="all", col=1
)
fig.write_html("bread_cost_comparison.html")
fig.show()