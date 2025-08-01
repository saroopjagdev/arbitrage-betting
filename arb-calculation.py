def find_arb (odds1, odds2):
  if (1/odds1 + 1/odds2) < 1:
    return True
  else:
    return False

def get_bet_info (team1, team2, odds1, odds2):
  units1 = 1 / 1 + (odds1/odds2)
  units2 = 1 - units1
  units_profit = odd1 * units1 - 1
  return f"Bet {units1} units on {team1} at {odds1} and {units2} units on {team2} at {odds2} to guarantee {units_profit} profit"
