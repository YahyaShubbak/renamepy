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

# --- USER INPUT ---
breads_per_week = int(input("How many breads do you eat per week? (e.g. 3): "))
loaves_per_batch = int(input("How many loaves do you bake at once? (e.g. 4): "))
oven_capacity = 2  # how many loaves fit in the oven at once

weeks_per_year = 52
breads_per_year = breads_per_week * weeks_per_year

# Calculate how many baking sessions per year
baking_sessions_per_year = int(np.ceil(breads_per_year / loaves_per_batch))

# For each session, how many batches are needed?
batches_per_session = int(np.ceil(loaves_per_batch / oven_capacity))

# Total oven time per year
total_bake_time_per_year = baking_sessions_per_year * batches_per_session * bake_time
total_preheat_time_per_year = baking_sessions_per_year * preheat_time

# Kneading time per year (assuming you knead once per session)
total_knead_time_per_year = baking_sessions_per_year * knead_time * kneader_power

# Total kWh per year
total_kWh_per_year = (
    total_knead_time_per_year +
    oven_power * (total_bake_time_per_year + total_preheat_time_per_year)
)

# Per bread
kWh_per_bread = total_kWh_per_year / breads_per_year

# Update cost calculations
elec_costs_per_bread = all_elec_full / 100 * kWh_per_bread  # ct to EUR
flour_costs_per_bread = flour_per_bread_kg * all_flour_markenmehl


# Total cost per year
buy_costs = all_bread_full * breads_per_year

# ...existing code up to bake_costs...

# ...existing code up to bake_costs...

# Calculate cumulative costs
# ...existing code...

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
        # Start at the first value of the first phase again (not cumulative)
        buy_costs_2.append(all_bread_full[i] * breads_per_year)
        bake_costs_2.append(kneader_price + annual_bake_cost)
    else:
        buy_costs_2.append(buy_costs_2[-1] + all_bread_full[i] * breads_per_year)
        bake_costs_2.append(bake_costs_2[-1] + annual_bake_cost)

# Find amortization year (start checking only from the year the kneader was bought, after reset)
amortization_mask = np.array(bake_costs_2) < np.array(buy_costs_2)
if not np.any(amortization_mask):
    amortized_idx = None
else:
    amortized_idx = kneader_added_idx + np.argmax(amortization_mask)
    while amortized_idx + 3 >= len(all_years):
        next_year = all_years[-1] + 1
        all_years = np.append(all_years, next_year)
        all_elec_full = np.append(all_elec_full, linear(next_year, *popt_elec))
        all_bread_full = np.append(all_bread_full, linear(next_year, *popt_bread))
        new_flour_price = np.interp(next_year, flour_price_years, flour_price_markenmehl)
        all_flour_markenmehl = np.append(all_flour_markenmehl, new_flour_price)
        flour_costs_per_bread = np.append(flour_costs_per_bread, flour_per_bread_kg * new_flour_price)
        elec_costs_per_bread = np.append(elec_costs_per_bread, all_elec_full[-1] / 100 * kWh_per_bread)
        annual_bake_cost = (elec_costs_per_bread[-1] + flour_costs_per_bread[-1]) * breads_per_year
        buy_costs_2 = np.append(buy_costs_2, buy_costs_2[-1] + all_bread_full[-1] * breads_per_year)
        bake_costs_2 = np.append(bake_costs_2, bake_costs_2[-1] + annual_bake_cost)
        amortization_mask = np.array(bake_costs_2) < np.array(buy_costs_2)
        amortized_idx = kneader_added_idx + np.argmax(amortization_mask)
# ...existing code for plotting...


# --- MAKE SUBPLOTS ---
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.15,
    subplot_titles=(
        "Brot- und Strompreisentwicklung (EUR/Leib, ct/kWh)",
        f"Kosten Brot Kaufen vs Backen ({breads_per_week} Brote/Woche)"
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


# ...existing code...

# Bottom plot: Cumulative cost comparison with separate lines
# ...existing code...

# Bottom plot: Cumulative cost comparison with separate lines
# ...existing code...

fig.add_trace(go.Scatter(
    x=all_years[:kneader_added_idx],
    y=buy_costs_1,
    name="Brot beim Bäcker (bis 2024)",
    mode='lines+markers',
    line=dict(color='blue'),
    customdata=[
        (breads_per_year * (i + 1),)  # cumulative breads consumed
        for i in range(kneader_added_idx)
    ],
    hovertemplate=(
        "Jahr: %{x}<br>"
        "Kumulierte Kosten: %{y:.2f} €<br>"
        "Verzehrte Brote: %{customdata[0]:.0f}<extra></extra>"
    )
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=all_years[:kneader_added_idx],
    y=bake_costs_1,
    name="Brot zu Hause (bis 2024)",
    mode='lines+markers',
    line=dict(color='orange'),
    customdata=[
        (
            elec_costs_per_bread[i] + flour_costs_per_bread[i],
            elec_costs_per_bread[i],
            flour_costs_per_bread[i],
            breads_per_year * (i + 1)  # cumulative breads consumed
        ) for i in range(kneader_added_idx)
    ],
    hovertemplate=(
        "Jahr: %{x}<br>"
        "Kumulierte Kosten: %{y:.2f} €<br>"
        "Kosten pro Laib: %{customdata[0]:.2f} €<br>"
        "davon Stromkosten: %{customdata[1]:.2f} €<br>"
        "davon Mehlkosten: %{customdata[2]:.2f} €<br>"
        "Verzehrte Brote: %{customdata[3]:.0f}<extra></extra>"
    )
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=all_years[kneader_added_idx:],
    y=buy_costs_2,
    name="Brot beim Bäcker (ab 2025)",
    mode='lines+markers',
    line=dict(color='blue', dash='dash'),
    customdata=[
        (breads_per_year * (i + 1),)
        for i in range(len(all_years) - kneader_added_idx)
    ],
    hovertemplate=(
        "Jahr: %{x}<br>"
        "Kumulierte Kosten: %{y:.2f} €<br>"
        "Verzehrte Brote: %{customdata[0]:.0f}<extra></extra>"
    )
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=all_years[kneader_added_idx:],
    y=bake_costs_2,
    name="Brot zu Hause (ab 2025, mit Kneter)",
    mode='lines+markers',
    line=dict(color='orange', dash='dash'),
    customdata=[
        (
            elec_costs_per_bread[i] + flour_costs_per_bread[i],
            elec_costs_per_bread[i],
            flour_costs_per_bread[i],
            breads_per_year * (i + 1)
        ) for i in range(kneader_added_idx, len(all_years))
    ],
    hovertemplate=(
        "Jahr: %{x}<br>"
        "Kumulierte Kosten: %{y:.2f} €<br>"
        "Kosten pro Laib: %{customdata[0]:.2f} €<br>"
        "davon Stromkosten: %{customdata[1]:.2f} €<br>"
        "davon Mehlkosten: %{customdata[2]:.2f} €<br>"
        "Verzehrte Brote: %{customdata[3]:.0f}<extra></extra>"
    )
), row=2, col=1)

# ...existing code...

# ...existing code...
# --- Add parameter annotation to bottom plot ---
param_text = (
    f"<b>Parameter:</b><br>"
    f"Brote/Woche: {breads_per_week}<br>"
    f"Brote/Backvorgang: {loaves_per_batch}<br>"
    f"Kneter: {kneader_price} €<br>"
    f"Kneten: {kneader_power} kW × {knead_time} h<br>"
    f"Vorheizen: {oven_power} kW × {preheat_time} h<br>"
    f"Backen: {oven_power} kW × {bake_time} h<br>"
)
fig.add_annotation(
    text=param_text,
    xref="paper", yref="paper",
    x=2018, y=2000,  # top left of bottom plot
    showarrow=False,
    align="left",
    font=dict(size=13),
    bordercolor="black",
    borderwidth=1,
    bgcolor="white",
    row=2, col=1
)

# Add annotation for kneader cost at 2025
fig.add_annotation(
    x=all_years[kneader_added_idx],
    y=bake_costs_2[0],
    text=f"{kneader_price} € Initialkosten für Teigkneter",
    showarrow=True,
    arrowhead=2,
    ax=40,
    ay=-40,
    row=2,
    col=1
)


# Mark amortization year
if amortized_idx is not None:
    idx2 = amortized_idx - kneader_added_idx  # index in the second phase arrays
    fig.add_vline(
        x=all_years[amortized_idx], line_width=2, line_dash="dash", line_color="green", row=2, col=1
    )
    fig.add_annotation(
        x=all_years[amortized_idx], y=(bake_costs_2[idx2] + buy_costs_2[idx2]) / 2,
        text=f"Amortisiert: {int(all_years[amortized_idx])}",
        showarrow=True, arrowhead=1, row=2, col=1
    )

# Layout
fig.update_yaxes(title_text="Brotpreis (EUR/loaf)", row=1, col=1, secondary_y=False)
fig.update_yaxes(title_text="Strompreis (ct/kWh)", row=1, col=1, secondary_y=True)
fig.update_yaxes(title_text="EUR (kumuliert)", row=2, col=1)

# Set x-axis to show years as default, but allow monthly ticks when zoomed in
fig.update_xaxes(
    title_text="Jahr",
    row=1, col=1,
    dtick="M12",  # Default: one tick per year
    tickformat="%Y",  # Show only year by default
    ticklabelmode="period",
    ticklabelstep=1,
    rangeslider_visible=False,  # Optional: add a range slider for easier zooming
    tickformatstops=[
        dict(dtickrange=[None, "M1"], value="%b %Y"),   # If zoomed in to months, show "Jan 2025"
        dict(dtickrange=["M1", None], value="%Y")       # Otherwise, show just the year
    ]
)
fig.update_xaxes(
    title_text="Jahr",
    row=2, col=1,
    dtick="M12",  # Default: one tick per year
    tickformat="%Y",  # Show only year by default
    ticklabelmode="period",
    ticklabelstep=1,
    rangeslider_visible=False,  # Optional: add a range slider for easier zooming
    tickformatstops=[
        dict(dtickrange=[None, "M1"], value="%b %Y"),   # If zoomed in to months, show "Jan 2025"
        dict(dtickrange=["M1", None], value="%Y")       # Otherwise, show just the year
    ]
)

fig.update_layout(
    height=1400,  # Increased height for taller plots
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