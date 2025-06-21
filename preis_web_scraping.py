import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime
import plotly.graph_objects as go
from threading import Thread
import csv
import os

# Global variables to store price data
price_data = []
timestamps = []

# File to store the data
DATA_FILE = "price_data.csv"

# Function to load data from the file
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as file:
            reader = csv.reader(file)
            for row in reader:
                timestamps.append(datetime.fromisoformat(row[0]))
                price_data.append(float(row[1]))
        print(f"Loaded {len(price_data)} data points from {DATA_FILE}.")

# Function to save data to the file
def save_data():
    with open(DATA_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        for timestamp, price in zip(timestamps, price_data):
            writer.writerow([timestamp.isoformat(), price])
    print(f"Saved {len(price_data)} data points to {DATA_FILE}.")

# Function to scrape the price
def scrape_price():
    url = "https://www.mediamarkt.de/de/product/_sony-sel90m28g-vollformat-1984585.html?gQT=2"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    whole_price_element = soup.find("span", {"data-test": "branded-price-whole-value"})
    decimal_price_element = soup.find("span", {"data-test": "branded-price-decimal-value"})
    
    if whole_price_element and decimal_price_element:
        price = f"{whole_price_element.text.strip()}{decimal_price_element.text.strip()}"
        price = price.replace("–", "").replace(",", ".")
        price = float(price)
        price_data.append(price)
        timestamps.append(datetime.now())
        print(f"Price scraped: {price} at {timestamps[-1]}")
        save_data()  # Save data after each scrape
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

# Load existing data on startup
load_data()

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

# #%%
# import requests
# from bs4 import BeautifulSoup
# import schedule
# import time
# from datetime import datetime
# import plotly.graph_objects as go
# from threading import Thread
# from telegram import Update
# from telegram.ext import Updater, CommandHandler, CallbackContext

# # Global variables to store price data
# price_data = []
# timestamps = []

# # Function to scrape the price
# def scrape_price():
#     url = "https://www.mediamarkt.de/de/product/_sony-sel90m28g-vollformat-1984585.html?gQT=2"
#     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
#     response = requests.get(url, headers=headers)
#     soup = BeautifulSoup(response.content, "html.parser")
    
#     whole_price_element = soup.find("span", {"data-test": "branded-price-whole-value"})
#     decimal_price_element = soup.find("span", {"data-test": "branded-price-decimal-value"})
    
#     if whole_price_element and decimal_price_element:
#         price = f"{whole_price_element.text.strip()}{decimal_price_element.text.strip()}"
#         price = price.replace("–", "").replace(",", ".")
#         price = float(price)
#         price_data.append(price)
#         timestamps.append(datetime.now())
#         print(f"Price scraped: {price} at {timestamps[-1]}")
#     else:
#         print("Failed to scrape the price.")

# # Function to create the plot and save it as an image
# def create_plot(save_as_image=False):
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(x=timestamps, y=price_data, mode='lines+markers', name='Price'))
#     fig.update_layout(
#         title="Price Development",
#         xaxis_title="Timestamp",
#         yaxis_title="Price (€)",
#         xaxis=dict(
#             rangeslider=dict(visible=True),
#             type="date",
#             rangeselector=dict(
#                 buttons=[
#                     dict(count=5, label="5h", step="hour", stepmode="backward"),
#                     dict(count=24, label="24h", step="hour", stepmode="backward"),
#                     dict(count=7, label="Week", step="day", stepmode="backward"),
#                     dict(count=30, label="Month", step="day", stepmode="backward"),
#                     dict(step="all", label="Max")
#                 ]
#             )
#         ),
#     )
#     if save_as_image:
#         fig.write_image("price_plot.png")  # Save the plot as an image
#     else:
#         fig.show()

# # Telegram bot command to send the plot
# def send_plot(update: Update, context: CallbackContext):
#     if not price_data or not timestamps:
#         update.message.reply_text("No price data available yet.")
#         return
    
#     create_plot(save_as_image=True)  # Save the plot as an image
#     with open("price_plot.png", "rb") as image:
#         update.message.reply_photo(photo=image)

# # Start the Telegram bot
# def start_bot():
#     TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
#     updater = Updater(TOKEN)
#     dispatcher = updater.dispatcher

#     # Command to get the latest plot
#     dispatcher.add_handler(CommandHandler("update", send_plot))

#     # Start the bot
#     updater.start_polling()
#     print("Telegram bot started. Send /update to get the latest price plot.")
#     updater.idle()

# # Start the program by scraping the first price
# scrape_price()

# # Schedule the scraping every 10 minutes
# schedule.every(10).minutes.do(scrape_price)

# # Start the Telegram bot in a separate thread
# Thread(target=start_bot, daemon=True).start()

# print("Starting price monitoring... Press Ctrl+C to stop.")
# try:
#     while True:
#         schedule.run_pending()
#         time.sleep(1)
# except KeyboardInterrupt:
#     print("Stopped monitoring.")