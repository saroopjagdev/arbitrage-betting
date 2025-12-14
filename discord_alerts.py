import requests
import os
from dotenv import load_dotenv

load_dotenv()

webhoook = os.getenv("webhook")

def send_alert (msg):
    data = {
        "content": msg
    }
    requests.post(webhoook, json=data)

send_alert("Arbitrage Bot Started!")