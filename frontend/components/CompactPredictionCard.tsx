import { UpcomingMatch } from "@/lib/api";
import { STAKE, upcomingPayout, bestUpcomingOdds } from "@/lib/betting";

const SURFACE_CLASS: Record<string, string> = {
  Hard:  "surface-badge surface-hard",
  Clay:  "surface-badge surface-clay",
  Grass: "surface-badge surface-grass",
};

const CONFIDENCE_COLOR: Record<string, string> = {
  high:   "text-emerald-400",
  medium: "text-yellow-400",
  low:    "text-gray-500",
};

export default function CompactPredictionCard({
  match,
  onClick,
}: {
  match: UpcomingMatch;
  onClick: () => void;
}) {
  const { prediction, best_odds, surface, player1, player2, tournament, commence_time } = match;
  if (!prediction) return null;

  const lastName    = (name: string) => name.split(" ").slice(-1)[0];
  const payout      = upcomingPayout(best_odds, prediction.predicted_winner);
  const winnerOdds  = bestUpcomingOdds(best_odds, prediction.predicted_winner);

  const winnerIsP1  = prediction.predicted_winner.toLowerCase() === prediction.p1_name.toLowerCase();
  const winProb     = winnerIsP1 ? prediction.p1_prob : prediction.p2_prob;

  const date    = new Date(commence_time);
  const dateStr = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <button
      onClick={onClick}
      className="card text-left w-full hover:ring-1 hover:ring-gray-600 active:bg-gray-800/60 transition-all cursor-pointer flex flex-col gap-3 p-4"
    >
      {/* Tournament + surface */}
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0">
          <p className="text-[10px] text-gray-500 truncate leading-tight">{tournament}</p>
          <p className="text-[10px] text-gray-600 mt-0.5">{dateStr}</p>
        </div>
        <span
          className={`${SURFACE_CLASS[surface] ?? "surface-badge bg-gray-800 text-gray-400"} shrink-0 text-[10px] px-1.5 py-0`}
        >
          {surface}
        </span>
      </div>

      {/* Matchup */}
      <p className="text-sm font-semibold text-gray-100 truncate">
        {lastName(player1)}{" "}
        <span className="text-gray-600 font-normal">vs</span>{" "}
        {lastName(player2)}
      </p>

      {/* Pick / odds / payout */}
      <div className="border-t border-gray-800 pt-3 space-y-2 mt-auto">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] text-gray-600 uppercase tracking-wide shrink-0">Pick</span>
          <span className="text-xs font-semibold text-gray-100 truncate text-right">
            {lastName(prediction.predicted_winner)}{" "}
            <span className={`font-normal tabular-nums ${CONFIDENCE_COLOR[prediction.confidence]}`}>
              {(winProb * 100).toFixed(0)}%
            </span>
          </span>
        </div>

        {winnerOdds != null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-gray-600 uppercase tracking-wide shrink-0">Odds</span>
            <span className="text-xs font-mono text-gray-300 tabular-nums">
              @{winnerOdds.toFixed(2)}
            </span>
          </div>
        )}

        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] text-gray-600 uppercase tracking-wide shrink-0">
            ${STAKE} bet
          </span>
          {payout != null ? (
            <span className="text-base font-mono font-bold text-emerald-400 tabular-nums">
              +${payout.toFixed(2)}
            </span>
          ) : (
            <span className="text-xs text-gray-600">no odds</span>
          )}
        </div>
      </div>
    </button>
  );
}
