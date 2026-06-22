import { UpcomingMatch, MatchPrediction } from "@/lib/api";
import ProbabilityBar from "./ProbabilityBar";

const SURFACE_CLASS: Record<string, string> = {
  Hard:  "surface-badge surface-hard",
  Clay:  "surface-badge surface-clay",
  Grass: "surface-badge surface-grass",
};

const EDGE_THRESHOLD = 0.03; // surface a model-vs-market callout above +3% divergence

/** Returns the player with the largest model-vs-market divergence, or null if none clears the threshold. */
function modelEdge(pred: MatchPrediction): {
  name: string;
  edge: number;
  disagreesWithModel: boolean;
} | null {
  const p1Edge = pred.p1_edge ?? null;
  const p2Edge = pred.p2_edge ?? null;

  const best =
    p1Edge !== null && p2Edge !== null
      ? p1Edge >= p2Edge
        ? { name: pred.p1_name, edge: p1Edge, isP1: true }
        : { name: pred.p2_name, edge: p2Edge, isP1: false }
      : p1Edge !== null
      ? { name: pred.p1_name, edge: p1Edge, isP1: true }
      : p2Edge !== null
      ? { name: pred.p2_name, edge: p2Edge, isP1: false }
      : null;

  if (!best || best.edge < EDGE_THRESHOLD) return null;

  const modelPickedP1 = pred.p1_prob >= pred.p2_prob;
  const disagreesWithModel = best.isP1 !== modelPickedP1;

  return { name: best.name, edge: best.edge, disagreesWithModel };
}

function OddsSide({
  playerName,
  decimalOdds,
  modelProb,
  edge,
  isHighlighted,
  align,
}: {
  playerName: string;
  decimalOdds: number | undefined;
  modelProb: number;
  edge: number | undefined;
  isHighlighted: boolean;
  align: "left" | "right";
}) {
  const impliedProb = decimalOdds ? 1 / decimalOdds : null;
  const edgeColor =
    edge == null        ? "text-gray-600" :
    edge >  EDGE_THRESHOLD ? "text-emerald-400 font-semibold" :
    edge < -EDGE_THRESHOLD ? "text-red-400" :
                            "text-yellow-400";

  const isRight = align === "right";

  return (
    <div className={`space-y-2 ${isRight ? "text-right" : ""}`}>
      <p className="text-xs text-gray-500 uppercase tracking-wide truncate">
        {playerName}
      </p>

      {/* Decimal odds */}
      <p className="font-mono text-xl font-semibold text-gray-100">
        {decimalOdds != null ? decimalOdds.toFixed(2) : "—"}
      </p>

      {/* Three-row comparison */}
      <div className="space-y-0.5 text-xs">
        <div className={`flex gap-1.5 ${isRight ? "justify-end" : ""}`}>
          <span className="text-gray-600 w-14 shrink-0">implied</span>
          <span className="text-gray-400 tabular-nums">
            {impliedProb != null ? `${(impliedProb * 100).toFixed(1)}%` : "—"}
          </span>
        </div>
        <div className={`flex gap-1.5 ${isRight ? "justify-end" : ""}`}>
          <span className="text-gray-600 w-14 shrink-0">model</span>
          <span className="text-gray-200 tabular-nums font-medium">
            {(modelProb * 100).toFixed(1)}%
          </span>
        </div>
        <div className={`flex gap-1.5 ${isRight ? "justify-end" : ""}`}>
          <span className="text-gray-600 w-14 shrink-0">edge</span>
          <span className={`tabular-nums ${edgeColor}`}>
            {edge != null
              ? `${edge > 0 ? "+" : ""}${(edge * 100).toFixed(1)}%`
              : "—"}
          </span>
        </div>
      </div>

      {/* Edge badge */}
      {isHighlighted && (
        <span className="inline-block text-[10px] font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700/60 px-2 py-0.5 rounded-full uppercase tracking-wide">
          Model edge
        </span>
      )}
    </div>
  );
}

export default function LivePredictionCard({ match }: { match: UpcomingMatch }) {
  const { player1, player2, surface, tournament, commence_time, prediction, best_odds } =
    match;
  if (!prediction) return null;

  const date    = new Date(commence_time);
  const dateStr = date.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
  const timeStr = date.toLocaleTimeString("en-US", {
    hour: "2-digit", minute: "2-digit",
  });

  const p1Odds = best_odds[player1];
  const p2Odds = best_odds[player2];
  const edge   = modelEdge(prediction);

  const edgeIsP1 = edge?.name === prediction.p1_name;
  const edgeIsP2 = edge?.name === prediction.p2_name;

  return (
    <div className="card space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-gray-100">{tournament}</p>
          <p className="text-xs text-gray-500 mt-0.5">{dateStr} · {timeStr}</p>
        </div>
        <span className={SURFACE_CLASS[surface] ?? "surface-badge bg-gray-800 text-gray-300"}>
          {surface}
        </span>
      </div>

      {/* Win probability */}
      <ProbabilityBar
        p1Name={prediction.p1_name}
        p2Name={prediction.p2_name}
        p1Prob={prediction.p1_prob}
        p2Prob={prediction.p2_prob}
        confidence={prediction.confidence}
      />

      {/* Odds comparison */}
      <div className="border-t border-gray-800 pt-4 grid grid-cols-2 gap-6">
        <OddsSide
          playerName={prediction.p1_name}
          decimalOdds={p1Odds}
          modelProb={prediction.p1_prob}
          edge={prediction.p1_edge}
          isHighlighted={edgeIsP1}
          align="left"
        />
        <OddsSide
          playerName={prediction.p2_name}
          decimalOdds={p2Odds}
          modelProb={prediction.p2_prob}
          edge={prediction.p2_edge}
          isHighlighted={edgeIsP2}
          align="right"
        />
      </div>

      {/* Model-vs-market divergence callout */}
      <div className="border-t border-gray-800 pt-3">
        {edge ? (
          <div
            className={`rounded-lg px-3 py-2.5 text-sm flex items-start gap-2 ${
              edge.disagreesWithModel
                ? "bg-amber-950/40 border border-amber-800/50"
                : "bg-emerald-950/40 border border-emerald-800/50"
            }`}
          >
            <span className="text-lg leading-none mt-0.5">
              {edge.disagreesWithModel ? "⚠️" : "📊"}
            </span>
            <div>
              <p
                className={`font-semibold ${
                  edge.disagreesWithModel ? "text-amber-300" : "text-emerald-300"
                }`}
              >
                {edge.name} favored by model{" "}
                <span className="font-normal text-xs opacity-80">
                  ({edge.edge > 0 ? "+" : ""}{(edge.edge * 100).toFixed(1)}% vs market)
                </span>
              </p>
              {edge.disagreesWithModel && (
                <p className="text-amber-400/70 text-xs mt-0.5">
                  Model predicts {prediction.predicted_winner} — market has them priced differently
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-xs text-gray-600 text-center">
            No divergence above {EDGE_THRESHOLD * 100}% — market appears efficient here
          </p>
        )}
      </div>

      <p className="text-[10px] text-gray-700 -mt-1">
        Best available odds across {Object.keys(match.bookmakers).length} bookmakers
      </p>
    </div>
  );
}
