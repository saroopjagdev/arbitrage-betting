def find_arb(odds1, odds2):
    # Only allow positive decimal odds
    if odds1 <= 1 or odds2 <= 1:
        return False
    return (1/odds1 + 1/odds2) < 1


def get_bet_info(team1, team2, odds1, odds2, bookie1, bookie2, link1="", link2=""):
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

    return (
        f"Arbitrage found!\n"
        f"→ Bet {t_stake1:.4f} units on {team1} at {b1_display} (odds {odds1})\n"
        f"→ Bet {t_stake2:.4f} units on {team2} at {b2_display} (odds {odds2})\n"
        f"**Guaranteed Minimum Profit: {actual_profit*100:.2f}%** (after rounding stakes){warning}\n"
    )


def find_arb_three_way(odds_home, odds_draw, odds_away):
    """Return True if 3-way arbitrage exists"""
    total_inverse = (1 / odds_home) + (1 / odds_draw) + (1 / odds_away)
    return total_inverse < 1


def get_arb_details_three_way(home_team, away_team, home_odds, draw_odds, away_odds, bookie_home, bookie_draw, bookie_away, link_home="", link_draw="", link_away=""):
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

    return (
        f"3-Way Arbitrage found!\n"
        f"→ Bet {t_stake_home:.4f} units on {home_team} at {bh_display} (odds {home_odds})\n"
        f"→ Bet {t_stake_draw:.4f} units on Draw at {bd_display} (odds {draw_odds})\n"
        f"→ Bet {t_stake_away:.4f} units on {away_team} at {ba_display} (odds {away_odds})\n"
        f"**Guaranteed Minimum Profit: {actual_profit*100:.2f}%** (after rounding stakes){warning}\n"
    )