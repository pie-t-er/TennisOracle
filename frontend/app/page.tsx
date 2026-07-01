"use client";

import { useState } from "react";
import PlayerSearch from "@/components/PlayerSearch";
import MatchupCard from "@/components/MatchupCard";
import PageHelp from "@/components/PageHelp";
import { predict, PredictResult } from "@/lib/api";

const TOUR_STEPS = [
  {
    target: "#main-nav",
    title: "Navigate the app",
    content: "Predict runs one-off match predictions. Players is the full ATP database. Live tracks the model's predictions against real bookmaker odds in real time. Model shows how the model was built and how it's performing.",
    disableBeacon: true,
    placement: "bottom" as const,
  },
  {
    target: "#predict-form",
    title: "Match Predictor",
    content: "Pick any two ATP players and a surface. The model looks up their current stats from the 2010–present database.",
  },
  {
    target: "#surface-selector",
    title: "Surface matters",
    content: "Hard, clay, and grass win rates are tracked separately — the model knows Nadal on clay is a different beast than Nadal on hard.",
  },
  {
    target: "#predict-btn",
    title: "Run the prediction",
    content: "Calibrated win probabilities: a 70% prediction means the model expects that player to win roughly 7 times in 10 — not just a ranking comparison.",
  },
  {
    target: "#page-help",
    title: "Need help?",
    content: "Use these buttons to relaunch this walkthrough or send feedback — reports go straight to the project backlog as GitHub issues.",
    placement: "top" as const,
  },
];

const SURFACES = ["Hard", "Clay", "Grass"];

export default function HomePage() {
  const [player1, setPlayer1] = useState("");
  const [player2, setPlayer2] = useState("");
  const [surface, setSurface] = useState("Hard");
  const [result, setResult] = useState<PredictResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePredict() {
    if (!player1 || !player2) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await predict(player1, player2, surface);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      setLoading(false);
    }
  }

  const canPredict = player1 && player2 && player1 !== player2;

  return (
    <div className="space-y-10">
      {/* Hero */}
      <div className="text-center pt-4 pb-2">
        <h1 className="text-4xl font-bold tracking-tight mb-2">
          ATP Match Predictor
        </h1>
        <p className="text-gray-400 text-lg">
          ML model trained on 14 years of ATP data · calibrated win probabilities
        </p>
      </div>

      {/* Prediction form */}
      <div id="predict-form" className="card max-w-2xl mx-auto space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <PlayerSearch
            label="Player 1"
            value={player1}
            onChange={setPlayer1}
            exclude={player2}
          />
          <PlayerSearch
            label="Player 2"
            value={player2}
            onChange={setPlayer2}
            exclude={player1}
          />
        </div>

        {/* Surface selector */}
        <div id="surface-selector">
          <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
            Surface
          </p>
          <div className="flex gap-2">
            {SURFACES.map((s) => (
              <button
                key={s}
                onClick={() => setSurface(s)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  surface === s
                    ? s === "Hard"
                      ? "bg-blue-600 text-white"
                      : s === "Clay"
                      ? "bg-orange-600 text-white"
                      : "bg-green-700 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <button
          id="predict-btn"
          onClick={handlePredict}
          disabled={!canPredict || loading}
          className="btn-primary w-full"
        >
          {loading ? "Predicting…" : "Predict Match"}
        </button>

        {error && (
          <p className="text-red-400 text-sm text-center">{error}</p>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="max-w-2xl mx-auto">
          <MatchupCard result={result} />
        </div>
      )}

      {/* Feature callouts */}
      {!result && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl mx-auto pt-2">
          {[
            { icon: "📈", title: "Recent Form", body: "Weights last 20 matches heavily — not just career stats" },
            { icon: "🎾", title: "Surface Splits", body: "Hard / clay / grass win rates tracked separately" },
            { icon: "🤜", title: "Head-to-Head", body: "Full H2H history baked into every prediction" },
          ].map(({ icon, title, body }) => (
            <div key={title} className="card text-center space-y-2">
              <div className="text-3xl">{icon}</div>
              <p className="font-semibold text-sm">{title}</p>
              <p className="text-gray-500 text-xs">{body}</p>
            </div>
          ))}
        </div>
      )}

      <PageHelp steps={TOUR_STEPS} />
    </div>
  );
}
