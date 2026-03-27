def find_arb(odds1, odds2):
    # Only allow positive decimal odds
    if odds1 <= 1 or odds2 <= 1:
        return False
    return (1/odds1 + 1/odds2) < 1


def get_bet_info(team1, team2, odds1, odds2, bookie1, bookie2, link1="", link2="", commence_time=""):
    # Theoretical stakes (normalized to 1 unit)
    total_inverse = (1/odds1 + 1/odds2)
    t_stake1 = (1/odds1) / total_inverse
    t_stake2 = (1/odds2) / total_inverse
    
    # Theoretical profit
    t_profit = (1 / total_inverse) - 1

    # Actual profit if rounded to 2 decimal places (worst case)
    r_stake1 = round(t_stake1, 2)
    r_stake2 = round(t_stake2, 2)
    payoff1 = r_stake1 * odds1
    payoff2 = r_stake2 * odds2
    actual_min_payout = min(payoff1, payoff2)
    actual_cost = r_stake1 + r_stake2
    actual_profit = (actual_min_payout / actual_cost) - 1

    warning = ""
    if actual_profit <= 0:
        warning = "\n[WARNING] Rounding to 0.01 units eliminates profit!"
    elif actual_profit < t_profit * 0.8:
        warning = f"\n[CAUTION] Rounding significantly reduces profit (Theoretical: {t_profit*100:.2f}%)"

    b1_display = f"[{bookie1}]({link1})" if link1 else bookie1
    b2_display = f"[{bookie2}]({link2})" if link2 else bookie2

    # Choose embed color based on profit
    # Green: >2%, Yellow: >0%, Red: <=0%
    color = 0x2ecc71 if actual_profit > 0.02 else (0xf1c40f if actual_profit > 0 else 0xe74c3c)

    embed = {
        "title": f"🎾 Arbitrage: {team1} vs {team2}",
        "description": f"**{actual_profit*100:.2f}% Guaranteed Profit** (after rounding)\nStarts: {commence_time if commence_time else 'N/A'}",
        "color": color,
        "fields": [
            {"name": f"Bet on {team1}", "value": f"**{t_stake1:.4f} Units** @ {odds1}\nBookie: {b1_display}", "inline": True},
            {"name": f"Bet on {team2}", "value": f"**{t_stake2:.4f} Units** @ {odds2}\nBookie: {b2_display}", "inline": True},
        ],
        "footer": {"text": "Arbitrage Betting Tracker | UK Regions"}
    }

    if warning:
        embed["fields"].append({"name": "Risk Analysis", "value": warning.strip(), "inline": False})

    message = f"Arbitrage Found: {team1} vs {team2} ({actual_profit*100:.2f}%)"
    return message, embed


def find_arb_three_way(odds_home, odds_draw, odds_away):
    """Return True if 3-way arbitrage exists"""
    total_inverse = (1 / odds_home) + (1 / odds_draw) + (1 / odds_away)
    return total_inverse < 1


def get_arb_details_three_way(home_team, away_team, home_odds, draw_odds, away_odds, bookie_home, bookie_draw, bookie_away, link_home="", link_draw="", link_away="", commence_time=""):
    total_inverse = (1 / home_odds) + (1 / draw_odds) + (1 / away_odds)
    t_profit = (1 / total_inverse) - 1

    # Theoretical stakes
    t_stake_home = (1 / home_odds) / total_inverse
    t_stake_draw = (1 / draw_odds) / total_inverse
    t_stake_away = (1 / away_odds) / total_inverse

    # Actual profit if rounded to 2 decimal places
    r_stake_home = round(t_stake_home, 2)
    r_stake_draw = round(t_stake_draw, 2)
    r_stake_away = round(t_stake_away, 2)
    
    payoff_home = r_stake_home * home_odds
    payoff_draw = r_stake_draw * draw_odds
    payoff_away = r_stake_away * away_odds
    
    actual_min_payout = min(payoff_home, payoff_draw, payoff_away)
    actual_cost = r_stake_home + r_stake_draw + r_stake_away
    actual_profit = (actual_min_payout / actual_cost) - 1

    warning = ""
    if actual_profit <= 0:
        warning = "\n[WARNING] Rounding to 0.01 units eliminates profit!"
    elif actual_profit < t_profit * 0.8:
        warning = f"\n[CAUTION] Rounding significantly reduces profit (Theoretical: {t_profit*100:.2f}%)"

    bh_display = f"[{bookie_home}]({link_home})" if link_home else bookie_home
    bd_display = f"[{bookie_draw}]({link_draw})" if link_draw else bookie_draw
    ba_display = f"[{bookie_away}]({link_away})" if link_away else bookie_away

    color = 0x2ecc71 if actual_profit > 0.02 else (0xf1c40f if actual_profit > 0 else 0xe74c3c)

    embed = {
        "title": f"⚽ 3-Way Arbitrage: {home_team} vs {away_team}",
        "description": f"**{actual_profit*100:.2f}% Guaranteed Profit** (after rounding)\nStarts: {commence_time if commence_time else 'N/A'}",
        "color": color,
        "fields": [
            {"name": f"Bet on {home_team}", "value": f"**{t_stake_home:.4f} Units** @ {home_odds}\nBookie: {bh_display}", "inline": True},
            {"name": "Bet on Draw", "value": f"**{t_stake_draw:.4f} Units** @ {draw_odds}\nBookie: {bd_display}", "inline": True},
            {"name": f"Bet on {away_team}", "value": f"**{t_stake_away:.4f} Units** @ {away_odds}\nBookie: {ba_display}", "inline": True},
        ],
        "footer": {"text": "Arbitrage Betting Tracker | UK Regions"}
    }

    if warning:
        embed["fields"].append({"name": "Risk Analysis", "value": warning.strip(), "inline": False})

    message = f"3-Way Arbitrage Found: {home_team} vs {away_team} ({actual_profit*100:.2f}%)"
    return message, embed