import requests
import os




webhoook = os.getenv("WEBHOOK")

def send_alert (msg):
    data = {
        "content": msg
    }
    requests.post(webhoook, json=data)

