import sys
import os
import json

# Add local directory to path to import our modules
sys.path.append(os.getcwd())

from arb_calculation import get_bet_info, get_arb_details_three_way

def test_embeds():
    print("--- Testing 2-Way Arbitrage Embed ---")
    msg, embed = get_bet_info(
        "Novak Djokovic", "Carlos Alcaraz", 2.05, 2.05, 
        "Bet365", "Pinnacle", 
        "https://bet365.com/tennis", "https://pinnacle.com/tennis",
        commence_time="2026-03-28T14:00:00Z"
    )
    print(f"Message: {msg}")
    print(f"Embed: {json.dumps(embed, indent=2)}")

    print("\n--- Testing 3-Way Arbitrage Embed ---")
    msg_3, embed_3 = get_arb_details_three_way(
        "Arsenal", "Man City", 3.4, 3.6, 3.4, 
        "Ladbrokes", "Betfair", "William Hill",
        "https://l.com", "https://bf.com", "https://wh.com",
        commence_time="2026-03-29T16:30:00Z"
    )
    print(f"Message: {msg_3}")
    print(f"Embed: {json.dumps(embed_3, indent=2)}")

if __name__ == "__main__":
    test_embeds()
