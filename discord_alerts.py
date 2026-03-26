import requests
import os




webhook = os.getenv("WEBHOOK")

def send_alert (msg):
    data = {
        "content": msg
    }
    requests.post(webhook, json=data)

