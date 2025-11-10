def find_arb(odds1, odds2):
    # Only allow positive decimal odds
    if odds1 <= 1 or odds2 <= 1:
        return False
    return (1/odds1 + 1/odds2) < 1


def get_bet_info(team1, team2, odds1, odds2, bookie1, bookie2):
    # Normalized stakes
    total_inverse = (1/odds1 + 1/odds2)
    stake1 = (1/odds1) / total_inverse
    stake2 = (1/odds2) / total_inverse
    
    # Profit per unit of total stake
    profit = (1 / total_inverse) - 1

    return (
        f"Arbitrage found!\n"
        f"→ Bet {stake1:.2f} units on {team1} at {bookie1} (odds {odds1})\n"
        f"→ Bet {stake2:.2f} units on {team2} at {bookie2} (odds {odds2})\n"
        f"Guaranteed profit: {profit*100:.2f}% per total stake\n"
    )

def find_arb_three_way(odds_home, odds_draw, odds_away):
    """Return True if 3-way arbitrage exists"""
    total_inverse = (1 / odds_home) + (1 / odds_draw) + (1 / odds_away)
    return total_inverse < 1


def get_arb_details_three_way(home_team, away_team, home_odds, draw_odds, away_odds, bookie_home, bookie_draw, bookie_away):
    total_inverse = (1 / home_odds) + (1 / draw_odds) + (1 / away_odds)
    profit = (1 / total_inverse) - 1

    # Stake proportions (normalize to 1 unit total)
    stake_home = (1 / home_odds) / total_inverse
    stake_draw = (1 / draw_odds) / total_inverse
    stake_away = (1 / away_odds) / total_inverse

    return (
        f"3-Way Arbitrage found!\n"
        f"→ Bet {stake_home:.2f} units on {home_team} at {bookie_home} (odds {home_odds})\n"
        f"→ Bet {stake_draw:.2f} units on Draw at {bookie_draw} (odds {draw_odds})\n"
        f"→ Bet {stake_away:.2f} units on {away_team} at {bookie_away} (odds {away_odds})\n"
        f"Guaranteed profit: {profit*100:.2f}% per total stake\n"
    )