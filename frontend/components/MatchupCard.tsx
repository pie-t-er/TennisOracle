"use client";

import Link from "next/link";
import { PredictResult } from "@/lib/api";
import ProbabilityBar from "./ProbabilityBar";

interface Props {
  result: PredictResult;
}

const SURFACE_CLASS: Record<string, string> = {
  Hard: "surface-badge surface-hard",
  Clay: "surface-badge surface-clay",
  Grass: "surface-badge surface-grass",
};

export default function MatchupCard({ result }: Props) {
  const { player1, player2, surface, p1_prob, p2_prob, confidence, h2h } = result;

  return (
    <div className="card space-y-6">
      {/* Players row */}
      <div className="grid grid-cols-3 items-center gap-4">
        <div className="text-center">
          <Link
            href={`/players/${encodeURIComponent(player1)}`}
            className="text-lg font-bold hover:text-blue-400 transition-colors line-clamp-2"
          >
            {player1}
          </Link>
        </div>

        <div className="text-center">
          <span className={SURFACE_CLASS[surface] ?? "surface-badge bg-gray-800 text-gray-300"}>
            {surface}
          </span>
          <p className="text-gray-600 text-xs mt-1">vs</p>
        </div>

        <div className="text-center">
          <Link
            href={`/players/${encodeURIComponent(player2)}`}
            className="text-lg font-bold hover:text-red-400 transition-colors line-clamp-2"
          >
            {player2}
          </Link>
        </div>
      </div>

      {/* Probability bar */}
      <ProbabilityBar
        p1Name={player1}
        p2Name={player2}
        p1Prob={p1_prob}
        p2Prob={p2_prob}
        confidence={confidence}
      />

      {/* H2H */}
      {h2h.total > 0 && (
        <div className="border-t border-gray-800 pt-4 text-center text-sm text-gray-400">
          <span className="font-medium text-gray-200">H2H</span>
          {" — "}
          <span className={h2h.p1_wins > h2h.p2_wins ? "text-blue-400 font-semibold" : ""}>
            {player1} {h2h.p1_wins}
          </span>
          {" – "}
          <span className={h2h.p2_wins > h2h.p1_wins ? "text-red-400 font-semibold" : ""}>
            {h2h.p2_wins} {player2}
          </span>
          <span className="text-gray-600"> ({h2h.total} matches)</span>
        </div>
      )}
    </div>
  );
}
