import sys
import os

# Add local directory to path to import our modules
sys.path.append(os.getcwd())

from arb_calculation import get_bet_info, get_arb_details_three_way

def test_links():
    print("--- Testing 2-Way Arbitrage with Links ---")
    print(get_bet_info(
        "Team A", "Team B", 2.02, 2.02, 
        "Bookie 1", "Bookie 2", 
        "https://bookie1.com/event1", "https://bookie2.com/event1"
    ))

    print("--- Testing 3-Way Arbitrage with Links ---")
    print(get_arb_details_three_way(
        "Home", "Away", 2.5, 3.5, 4.5, 
        "B1", "BDraw", "B2",
        "https://b1.com", "https://bdraw.com", "https://b2.com"
    ))

if __name__ == "__main__":
    test_links()
