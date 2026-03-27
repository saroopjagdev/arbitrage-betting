import requests
import os




webhook = os.getenv("WEBHOOK")

def send_alert(msg, embed=None):
    data = {
        "content": msg
    }
    if embed:
        data["embeds"] = [embed]
        
    requests.post(webhook, json=data)

