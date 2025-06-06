# Whale Trap Screener & Telegram Alert Bot
# Features:
# - Tracks coins that pumped over 24 hours up to 7 days
# - Detects potential reversal traps (e.g., RSI drop, CCI cooldown)
# - Scores and ranks top 10 trap candidates
# - Monitors BTC correlation
# - Sends Telegram alert + CSV
# - Accepts Telegram command: /trap

import pandas as pd
import requests
import os
from io import BytesIO
from flask import Flask, request

app = Flask(__name__)

# ------------------------------
# TRAP DETECTION LOGIC
# ------------------------------
def detect_whale_traps(data):
    df = pd.DataFrame(data)

    def trap_score(row):
        score = 0
        score += 1 if 5 < row['Price Change % 7 days'] < 40 else 0
        score += 1 if row['Price Change % 24 hours'] < 0 else 0
        score += 1 if row['Relative Strength Index (14) 1 day'] < 50 else 0
        score += 1 if row['Commodity Channel Index (20) 1 day'] < 0 else 0
        score += 1 if abs(row.get('BTC Correlation', 0)) < 0.3 else 0  # weak BTC tie
        return score

    df['trap_score'] = df.apply(trap_score, axis=1)
    top_traps = df.sort_values(by='trap_score', ascending=False).head(10)
    return df, top_traps

# ------------------------------
# TELEGRAM SENDER
# ------------------------------
def send_telegram_report(bot_token, chat_id, top_traps, full_df):
    message = u"\U0001f575 Whale Trap Detector Report\n\n"
    message += u"\U0001f4a3 Top 10 Trap Candidates:\n"

    for i, row in top_traps.iterrows():
        message += "%s | 7D: %.1f%% | 24H: %.1f%% | RSI: %.1f | CCI: %.1f | Score: %d\n" % (
            row['Symbol'],
            row['Price Change % 7 days'],
            row['Price Change % 24 hours'],
            row['Relative Strength Index (14) 1 day'],
            row['Commodity Channel Index (20) 1 day'],
            row['trap_score']
        )

    url = "https://api.telegram.org/bot%s/sendMessage" % bot_token
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, json=payload)

    file_buffer = BytesIO()
    full_df.to_csv(file_buffer, index=False)
    file_buffer.seek(0)

    url_file = "https://api.telegram.org/bot%s/sendDocument" % bot_token
    files = {"document": ("trap_report.csv", file_buffer)}
    data = {"chat_id": chat_id}
    requests.post(url_file, files=files, data=data)

# ------------------------------
# FLASK WEBHOOK ENDPOINT
# ------------------------------
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if text.strip().lower() == "/trap":
        coins = [
            {"Symbol": "ADAUSDT.P", "Price Change % 7 days": 15.0, "Price Change % 24 hours": -2.0, "Relative Strength Index (14) 1 day": 47, "Commodity Channel Index (20) 1 day": -30, "BTC Correlation": 0.15},
            {"Symbol": "CRVUSDT.P", "Price Change % 7 days": 10.0, "Price Change % 24 hours": -3.2, "Relative Strength Index (14) 1 day": 44, "Commodity Channel Index (20) 1 day": -52, "BTC Correlation": 0.08},
            {"Symbol": "SOLUSDT.P", "Price Change % 7 days": 28.0, "Price Change % 24 hours": -1.5, "Relative Strength Index (14) 1 day": 48, "Commodity Channel Index (20) 1 day": -20, "BTC Correlation": 0.10},
            {"Symbol": "APEUSDT.P", "Price Change % 7 days": 6.0, "Price Change % 24 hours": -1.0, "Relative Strength Index (14) 1 day": 45, "Commodity Channel Index (20) 1 day": -10, "BTC Correlation": 0.22},
            {"Symbol": "XRPUSDT.P", "Price Change % 7 days": 8.0, "Price Change % 24 hours": -0.5, "Relative Strength Index (14) 1 day": 49, "Commodity Channel Index (20) 1 day": -5, "BTC Correlation": 0.30}
        ]

        df, top_traps = detect_whale_traps(coins)
        send_telegram_report(os.getenv("TELEGRAM_BOT_TOKEN"), chat_id, top_traps, df)

    return "OK"

# ------------------------------
# START FLASK SERVER
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
