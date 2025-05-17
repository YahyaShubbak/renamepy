import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from scipy.optimize import curve_fit

# --- HARDCODED DATA FROM USER ---
years = np.arange(2015, 2026)

# Electricity: 2015 = 27.5 ct, 2023 = ~34 ct, 2025 = 35.86 ct
elec_years = np.array([2015, 2023, 2025])
elec_prices = np.array([27.5, 34, 35.86])
all_elec = np.interp(years, elec_years, elec_prices)
flour_price_per_kg = 1.0  # EUR
flour_per_bread_kg = 0.8  # 800g


# Bread: 2019 = x, 2023 = 4.00 EUR, 2024 = 4.12 EUR (2.9% more), 2025 = 4.12 EUR (assume stable)
# 2019 price: 4.00 / 1.344 ≈ 2.98 EUR
bread_years = np.array([2019, 2023, 2024, 2025])
bread_prices = np.array([2.98, 4.00, 4.12, 4.12])
all_bread = np.interp(years, bread_years, bread_prices)

# --- PREDICT NEXT 5 YEARS (simple linear fit) ---
def linear(x, a, b):
    return a * x + b

future_years = np.arange(years[-1]+1, years[-1]+6)

# Electricity prediction
popt_elec, _ = curve_fit(linear, years, all_elec)
future_elec = linear(future_years, *popt_elec)

# Bread prediction
popt_bread, _ = curve_fit(linear, years, all_bread)
future_bread = linear(future_years, *popt_bread)

# Combine all years and prices
all_years = np.concatenate([years, future_years])
all_elec_full = np.concatenate([all_elec, future_elec])
all_bread_full = np.concatenate([all_bread, future_bread])

# --- USER INPUT ---
breads_per_week = int(input("How many breads do you eat per week? (e.g. 3): "))
kneader_price = 1000  # EUR
kneader_power = 1.0  # kW
knead_time = 0.25  # hours (15 min)
oven_power = 2.0  # kW
bake_time = 1.0  # hours
preheat_time = 1.0  # hours

weeks_per_year = 52
breads_per_year = breads_per_week * weeks_per_year

# Home baking cost per bread (electricity only, EUR)
kWh_per_bread = kneader_power * knead_time + oven_power * (bake_time + preheat_time)
elec_costs_per_bread = all_elec_full / 100 * kWh_per_bread  # ct to EUR
flour_costs_per_bread = flour_per_bread_kg * flour_price_per_kg


# Total cost per year
buy_costs = all_bread_full * breads_per_year

# ...existing code up to bake_costs...

# ...existing code up to bake_costs...

# Calculate cumulative costs
buy_costs = []
bake_costs = []
for i in range(len(all_years)):
    annual_bake_cost = (elec_costs_per_bread[i] + flour_costs_per_bread) * breads_per_year
    if i == 0:
        buy_costs.append(all_bread_full[i] * breads_per_year)
        bake_costs.append(kneader_price + annual_bake_cost)
    else:
        buy_costs.append(buy_costs[-1] + all_bread_full[i] * breads_per_year)
        bake_costs.append(bake_costs[-1] + annual_bake_cost)
buy_costs = np.array(buy_costs)
bake_costs = np.array(bake_costs)

# Find amortization year
amortized_idx = np.argmax(bake_costs < buy_costs)
if bake_costs[amortized_idx] >= buy_costs[amortized_idx]:
    amortized_idx = None
else:
    # Extend years if needed
    while amortized_idx + 3 >= len(all_years):
        # Add more future years
        next_year = all_years[-1] + 1
        all_years = np.append(all_years, next_year)
        # Predict prices
        all_elec_full = np.append(all_elec_full, linear(next_year, *popt_elec))
        all_bread_full = np.append(all_bread_full, linear(next_year, *popt_bread))
        elec_costs_per_bread = np.append(elec_costs_per_bread, all_elec_full[-1] / 100 * kWh_per_bread)
        # Add new costs
        annual_bake_cost = (elec_costs_per_bread[-1] + flour_costs_per_bread) * breads_per_year
        buy_costs = np.append(buy_costs, buy_costs[-1] + all_bread_full[-1] * breads_per_year)
        bake_costs = np.append(bake_costs, bake_costs[-1] + annual_bake_cost)

# ...existing plotting code...
# --- MAKE SUBPLOTS ---
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.15,
    subplot_titles=(
        "Bread & Electricity Price Development",
        f"Cumulative Cost: Buy vs. Bake ({breads_per_week} breads/week)"
    ),
    specs=[[{"secondary_y": True}], [{}]]
)

# Top plot: Bread and electricity price
fig.add_trace(go.Scatter(
    x=all_years, y=all_bread_full, name="Bread price (EUR/loaf)", mode='lines+markers'
), row=1, col=1, secondary_y=False)
fig.add_trace(go.Scatter(
    x=all_years, y=all_elec_full, name="Electricity (ct/kWh)", mode='lines+markers'
), row=1, col=1, secondary_y=True)

# Bottom plot: Cumulative cost comparison
fig.add_trace(go.Scatter(
    x=all_years, y=buy_costs, name="Buy bread (EUR, cumulative)", mode='lines+markers'
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=all_years, y=bake_costs, name="Bake at home (EUR, cumulative)", mode='lines+markers'
), row=2, col=1)

# Mark amortization year
if amortized_idx is not None:
    fig.add_vline(
        x=all_years[amortized_idx], line_width=2, line_dash="dash", line_color="green", row=2, col=1
    )
    fig.add_annotation(
        x=all_years[amortized_idx], y=(bake_costs[amortized_idx]+buy_costs[amortized_idx])/2,
        text=f"Amortized: {int(all_years[amortized_idx])}",
        showarrow=True, arrowhead=1, row=2, col=1
    )

# Layout
fig.update_yaxes(title_text="Bread price (EUR/loaf)", row=1, col=1, secondary_y=False)
fig.update_yaxes(title_text="Electricity (ct/kWh)", row=1, col=1, secondary_y=True)
fig.update_yaxes(title_text="EUR (cumulative)", row=2, col=1)
fig.update_xaxes(title_text="Year", row=2, col=1)
fig.update_layout(
    height=800,
    legend=dict(x=0.01, y=0.99),
    showlegend=True
)
fig.show()