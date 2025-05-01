import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
from threading import Thread

# Global variables to store price data
price_data = []
timestamps = []

# Function to scrape the price
def scrape_price():
    url = "https://www.mediamarkt.de/de/product/_sony-sel90m28g-vollformat-1984585.html?gQT=2"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Extract the price (adjust the selector based on the website's structure)
    whole_price_element = soup.find("span", {"data-test": "branded-price-whole-value"})
    decimal_price_element = soup.find("span", {"data-test": "branded-price-decimal-value"})
    
    if whole_price_element and decimal_price_element:
        # Combine the whole and decimal parts of the price
        price = f"{whole_price_element.text.strip()}{decimal_price_element.text.strip()}"
        price = price.replace("–", "").replace(",", ".")  # Remove invalid characters and replace comma with dot
        price = float(price)
        price_data.append(price)
        timestamps.append(datetime.now())
        print(f"Price scraped: {price} at {timestamps[-1]}")
    else:
        print("Failed to scrape the price.")

# Function to create and update the dynamic plot
def create_plot():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=timestamps, y=price_data, mode='lines+markers', name='Price'))
    fig.update_layout(
        title="Price Development",
        xaxis_title="Timestamp",
        yaxis_title="Price (€)",
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="date",
            rangeselector=dict(
                buttons=[
                    dict(count=5, label="5h", step="hour", stepmode="backward"),
                    dict(count=24, label="24h", step="hour", stepmode="backward"),
                    dict(count=7, label="Week", step="day", stepmode="backward"),
                    dict(count=30, label="Month", step="day", stepmode="backward"),
                    dict(step="all", label="Max")
                ]
            )
        ),
    )
    fig.show()

# Function to continuously update the plot
def update_plot():
    while True:
        time.sleep(600)  # Update every 10 minutes
        create_plot()

# Start the program by scraping the first price
scrape_price()

# Open the initial plot
Thread(target=update_plot, daemon=True).start()
create_plot()

# Schedule the scraping every 10 minutes
schedule.every(10).minutes.do(scrape_price)

print("Starting price monitoring... Press Ctrl+C to stop.")
try:
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped monitoring.")