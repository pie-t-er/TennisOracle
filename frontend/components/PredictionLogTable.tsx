"use client";

import { StoredPrediction, MatchPrediction } from "@/lib/api";
import { simulateBet, bestOdds, STAKE } from "@/lib/betting";

const SURFACE_CLASS: Record<string, string> = {
  Hard:  "surface-badge surface-hard",
  Clay:  "surface-badge surface-clay",
  Grass: "surface-badge surface-grass",
};

const CONFIDENCE_CLASS: Record<string, string> = {
  high:   "text-emerald-400",
  medium: "text-yellow-400",
  low:    "text-gray-500",
};

const EDGE_THRESHOLD = 0.03;

/** Pick the side with the largest model-vs-market divergence. Returns null if none clears the threshold. */
function modelEdge(pred: MatchPrediction): {
  name: string;
  edge: number;
  odds: number | null;
  disagreesWithModel: boolean;
} | null {
  const candidates: { name: string; edge: number; isP1: boolean }[] = [];
  if (pred.p1_edge != null)
    candidates.push({ name: pred.p1_name, edge: pred.p1_edge, isP1: true });
  if (pred.p2_edge != null)
    candidates.push({ name: pred.p2_name, edge: pred.p2_edge, isP1: false });

  const best = candidates.sort((a, b) => b.edge - a.edge)[0] ?? null;
  if (!best || best.edge < EDGE_THRESHOLD) return null;

  const modelPickedP1    = pred.p1_prob >= pred.p2_prob;
  const disagreesWithModel = best.isP1 !== modelPickedP1;

  return { name: best.name, edge: best.edge, odds: null, disagreesWithModel };
}

function ResultBadge({ result }: { result: StoredPrediction["result"] }) {
  if (!result) {
    return (
      <span className="inline-flex items-center gap-1 text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-pulse" />
        Pending
      </span>
    );
  }
  return result.correct ? (
    <span className="text-xs bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-2 py-0.5 rounded-full">
      ✓ Correct
    </span>
  ) : (
    <span className="text-xs bg-red-900/50 text-red-300 border border-red-800/60 px-2 py-0.5 rounded-full">
      ✗ Wrong
    </span>
  );
}

export default function PredictionLogTable({
  predictions,
}: {
  predictions: StoredPrediction[];
}) {
  const lastName = (name: string) => name.split(" ").slice(-1)[0];

  return (
    <div className="card overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900/60">
              {[
                { label: "Match",       align: "left"  },
                { label: "Model pick",  align: "left"  },
                { label: "Model edge",  align: "left"  },
                { label: `$${STAKE} bet`, align: "left"  },
                { label: "Result",      align: "right" },
              ].map(({ label, align }) => (
                <th
                  key={label}
                  className={`px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-${align}`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-800/40">
            {predictions.map((pred) => {
              const p    = pred.prediction;
              const edge = modelEdge(p);
              const bet  = simulateBet(pred);

              // Attach best-available odds to the edge object
              const edgeOdds = edge
                ? bestOdds(
                    pred.bookmakers,
                    edge.name === p.p1_name ? pred.player1 : pred.player2
                  )
                : null;

              const date    = new Date(pred.commence_time);
              const dateStr = date.toLocaleDateString("en-US", {
                month: "short", day: "numeric",
              });

              return (
                <tr
                  key={pred.match_id}
                  className="hover:bg-gray-800/30 transition-colors"
                >
                  {/* ── Match ── */}
                  <td className="px-4 py-3 min-w-[180px]">
                    <p className="font-medium text-gray-100">
                      {lastName(pred.player1)}{" "}
                      <span className="text-gray-600 font-normal">vs</span>{" "}
                      {lastName(pred.player2)}
                    </p>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      <span className="text-xs text-gray-500 truncate max-w-[110px]">
                        {pred.tournament}
                      </span>
                      <span className="text-gray-700">·</span>
                      <span className="text-xs text-gray-500">{dateStr}</span>
                      <span
                        className={
                          (SURFACE_CLASS[pred.surface] ??
                            "surface-badge bg-gray-800 text-gray-400") +
                          " text-[10px] px-1.5 py-0"
                        }
                      >
                        {pred.surface}
                      </span>
                    </div>
                  </td>

                  {/* ── Model pick ── */}
                  <td className="px-4 py-3 min-w-[130px]">
                    <p className="font-medium text-gray-100">
                      {lastName(p.predicted_winner)}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5 tabular-nums">
                      {(p.p1_prob * 100).toFixed(0)}%
                      <span className="text-gray-700"> / </span>
                      {(p.p2_prob * 100).toFixed(0)}%
                      <span className="text-gray-700"> · </span>
                      <span className={CONFIDENCE_CLASS[p.confidence]}>
                        {p.confidence}
                      </span>
                    </p>
                  </td>

                  {/* ── Model edge ── */}
                  <td className="px-4 py-3 min-w-[160px]">
                    {edge ? (
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`font-medium ${
                              edge.disagreesWithModel
                                ? "text-amber-300"
                                : "text-emerald-300"
                            }`}
                          >
                            {lastName(edge.name)}
                          </span>
                          {edgeOdds && (
                            <span className="font-mono text-gray-400 text-xs">
                              @{edgeOdds.toFixed(2)}
                            </span>
                          )}
                          <span
                            className={`text-xs tabular-nums ${
                              edge.edge > 0.05
                                ? "text-emerald-400 font-semibold"
                                : "text-yellow-400"
                            }`}
                          >
                            +{(edge.edge * 100).toFixed(1)}%
                          </span>
                        </div>
                        {edge.disagreesWithModel && (
                          <p className="text-xs text-amber-500/70 mt-0.5">
                            ⚠ vs model pick
                          </p>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-600">No edge</span>
                    )}
                  </td>

                  {/* ── $10 bet ── */}
                  <td className="px-4 py-3 min-w-[100px]">
                    {bet.profit == null ? (
                      <span className="text-xs text-gray-600">no odds</span>
                    ) : bet.settled ? (
                      <div>
                        <p
                          className={`font-mono font-medium tabular-nums ${
                            bet.profit > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {bet.profit > 0 ? "+" : ""}${bet.profit.toFixed(2)}
                        </p>
                        {bet.odds != null && (
                          <p className="text-[10px] text-gray-600 font-mono">
                            @{bet.odds.toFixed(2)}
                          </p>
                        )}
                      </div>
                    ) : (
                      <div>
                        <p className="font-mono text-xs text-gray-400 tabular-nums">
                          +${bet.profit.toFixed(2)}{" "}
                          <span className="text-gray-600">if right</span>
                        </p>
                        {bet.odds != null && (
                          <p className="text-[10px] text-gray-600 font-mono">
                            @{bet.odds.toFixed(2)}
                          </p>
                        )}
                      </div>
                    )}
                  </td>

                  {/* ── Result ── */}
                  <td className="px-4 py-3 text-right">
                    <ResultBadge result={pred.result} />
                    {pred.result && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {lastName(pred.result.winner)} won
                      </p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
