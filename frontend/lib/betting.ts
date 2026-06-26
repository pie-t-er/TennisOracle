import { StoredPrediction } from "./api";

export const STAKE = 10;

/**
 * Best decimal odds across all bookmakers for the given player name.
 * Case-insensitive: our model's name casing and the Odds API's own name
 * string for the same player can differ (e.g. "Mcdonald" vs "McDonald").
 */
export function bestOdds(bookmakers: StoredPrediction["bookmakers"], playerName: string): number | null {
  const target = playerName.toLowerCase();
  let best: number | null = null;
  for (const book of Object.values(bookmakers)) {
    for (const [name, odds] of Object.entries(book)) {
      if (name.toLowerCase() === target && (best === null || odds > best)) {
        best = odds;
      }
    }
  }
  return best;
}

export interface BetOutcome {
  /** Decimal odds the bet would've been placed at, or null if no bookmaker offered a price on the model's pick. */
  odds: number | null;
  /**
   * Actual profit/loss for a settled match, or the *potential* profit if a
   * still-pending pick wins (a loss always forfeits the flat `STAKE`, win or
   * lose isn't known yet). Null if no odds were available to simulate either way.
   */
  profit: number | null;
  /** True if `profit` reflects a real settled result; false if it's a pending potential payout. */
  settled: boolean;
}

/**
 * Simulate a flat $STAKE bet on the model's predicted winner, at the best
 * available decimal odds for that player. Decimal odds payout: a win returns
 * stake * odds total, i.e. profit = stake * (odds - 1); a loss forfeits the stake.
 */
export function simulateBet(pred: StoredPrediction): BetOutcome {
  const odds = bestOdds(pred.bookmakers, pred.prediction.predicted_winner);
  if (odds == null) {
    return { odds: null, profit: null, settled: false };
  }
  if (!pred.result) {
    // Still pending — show the potential payout if the pick wins.
    return { odds, profit: Math.round(STAKE * (odds - 1) * 100) / 100, settled: false };
  }
  const profit = pred.result.correct ? STAKE * (odds - 1) : -STAKE;
  return { odds, profit: Math.round(profit * 100) / 100, settled: true };
}

export interface BetTotals {
  /** Settled predictions where odds were available to simulate a bet. */
  betsPlaced: number;
  betsWon: number;
  totalProfit: number;
  totalStaked: number;
}

/** Aggregate simulated $STAKE-per-game betting results across a set of predictions. */
export function aggregateBets(preds: StoredPrediction[]): BetTotals {
  let betsPlaced = 0;
  let betsWon = 0;
  let totalProfit = 0;

  for (const pred of preds) {
    const { profit, settled } = simulateBet(pred);
    if (!settled || profit == null) continue;
    betsPlaced += 1;
    totalProfit += profit;
    if (profit > 0) betsWon += 1;
  }

  return {
    betsPlaced,
    betsWon,
    totalProfit: Math.round(totalProfit * 100) / 100,
    totalStaked: betsPlaced * STAKE,
  };
}
