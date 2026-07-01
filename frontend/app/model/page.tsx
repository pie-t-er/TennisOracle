"use client";

import { useState, useEffect, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, ReferenceLine, Legend,
  ComposedChart, Scatter,
} from "recharts";
import { getModelInfo, getStoredPredictions, FeatureImportance, StoredPrediction } from "@/lib/api";
import PageHelp from "@/components/PageHelp";

const TOUR_STEPS = [
  {
    target: "#model-header",
    title: "Model Analytics",
    content: "Everything about how the model was built and how it's performing — feature weights, calibration quality, accuracy trends, and surface-level breakdowns.",
    disableBeacon: true,
  },
  {
    target: "#feature-importance",
    title: "Feature Importance",
    content: "What XGBoost learned to weigh most heavily. Rank and rank points dominate — but recent form and surface win rate matter more than raw career stats.",
  },
  {
    target: "#calibration-curve",
    title: "Calibration Curve",
    content: "A well-calibrated model's dots track the dashed diagonal: a 70% prediction should win ~70% of the time. Dots above the line mean the model is being conservative; below means overconfident.",
  },
  {
    target: "#rolling-accuracy",
    title: "Rolling Accuracy",
    content: "Accuracy over the last 30 settled predictions at each point in time. Tracks whether the model stays consistent or drifts as the season progresses.",
  },
  {
    target: "#surface-breakdown",
    title: "Surface Breakdown",
    content: "Model accuracy split by court surface. Grass has fewer data points so its estimate is noisier.",
  },
  {
    target: "#page-help",
    title: "Need help?",
    content: "Use these buttons to relaunch this walkthrough or send feedback — reports go straight to the project backlog as GitHub issues.",
    placement: "top" as const,
  },
];

// ── Feature name formatting ───────────────────────────────────────────────────

const FEATURE_LABEL: Record<string, string> = {
  p1_hand:             "Handedness (P1)",
  p1_bmi:              "BMI (P1)",
  p1_rank:             "ATP Rank (P1)",
  p1_rank_points:      "Rank Points (P1)",
  p1_career_win_pct:   "Career Win % (P1)",
  p1_career_matches:   "Career Matches (P1)",
  p1_minutes_per_match:"Match Duration (P1)",
  p1_ace_rate:         "Ace Rate (P1)",
  p1_recent_win_pct:   "Recent Form (P1)",
  p1_surface_win_pct:  "Surface Win % (P1)",
  p1_h2h_win_pct:      "H2H Win % (P1)",
  p2_hand:             "Handedness (P2)",
  p2_bmi:              "BMI (P2)",
  p2_rank:             "ATP Rank (P2)",
  p2_rank_points:      "Rank Points (P2)",
  p2_career_win_pct:   "Career Win % (P2)",
  p2_career_matches:   "Career Matches (P2)",
  p2_minutes_per_match:"Match Duration (P2)",
  p2_ace_rate:         "Ace Rate (P2)",
  p2_recent_win_pct:   "Recent Form (P2)",
  p2_surface_win_pct:  "Surface Win % (P2)",
  p2_h2h_win_pct:      "H2H Win % (P2)",
  rank_diff:           "Rank Difference",
  rank_points_diff:    "Rank Points Diff",
};

// ── Chart helpers ─────────────────────────────────────────────────────────────

const CHART_THEME = {
  text:    "#9ca3af",  // gray-400
  grid:    "#1f2937",  // gray-800
  emerald: "#10b981",
  blue:    "#60a5fa",
  amber:   "#f59e0b",
};

function ChartCard({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card space-y-4">
      <div>
        <h2 className="text-base font-semibold text-gray-100">{title}</h2>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ── Feature importance chart ──────────────────────────────────────────────────

function FeatureImportanceChart({ data }: { data: FeatureImportance[] }) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-gray-600 text-center py-8">
        No data yet — run <code className="bg-gray-800 px-1 rounded">ml/train.py</code> to generate.
      </p>
    );
  }

  const top12 = data.slice(0, 12).map((d) => ({
    label: FEATURE_LABEL[d.feature] ?? d.feature,
    value: d.importance,
    pct:   `${(d.importance * 100).toFixed(1)}%`,
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={top12} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
        <XAxis
          type="number"
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          tick={{ fill: CHART_THEME.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          width={148}
          tick={{ fill: CHART_THEME.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
          labelStyle={{ color: "#e5e7eb", fontSize: 12 }}
          formatter={(v) => [`${(Number(v) * 100).toFixed(2)}%`, "Importance"]}
          cursor={{ fill: "#1f2937" }}
        />
        <Bar dataKey="value" fill={CHART_THEME.emerald} fillOpacity={0.75} radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Calibration curve ─────────────────────────────────────────────────────────

function buildCalibration(settled: StoredPrediction[]) {
  const N_BINS = 5;
  const bins = Array.from({ length: N_BINS }, (_, i) => {
    const lo = 0.5 + i * 0.1;
    const hi = lo + 0.1;
    return { lo, hi, mid: lo + 0.05, wins: 0, total: 0 };
  });

  for (const p of settled) {
    const pred = p.prediction;
    const winnerIsP1 = pred.predicted_winner.toLowerCase() === pred.p1_name.toLowerCase();
    const prob = winnerIsP1 ? pred.p1_prob : pred.p2_prob;
    const bin = bins.find((b) => prob >= b.lo && prob < b.hi + 0.0001);
    if (!bin) continue;
    bin.total += 1;
    if (p.result!.correct) bin.wins += 1;
  }

  return bins
    .filter((b) => b.total >= 5)
    .map((b) => ({
      pred:   Math.round(b.mid * 100),
      actual: Math.round((b.wins / b.total) * 100),
      ideal:  Math.round(b.mid * 100),
      n:      b.total,
    }));
}

function CalibrationChart({ settled }: { settled: StoredPrediction[] }) {
  const data = useMemo(() => buildCalibration(settled), [settled]);

  if (data.length < 2) {
    return (
      <p className="text-sm text-gray-600 text-center py-8">
        Need at least 10 settled predictions per bucket — check back as more results land.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
        <XAxis
          dataKey="pred"
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: CHART_THEME.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          label={{ value: "Predicted win %", position: "insideBottom", offset: -2, fill: CHART_THEME.text, fontSize: 11 }}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: CHART_THEME.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          domain={[40, 100]}
          label={{ value: "Actual win %", angle: -90, position: "insideLeft", offset: 12, fill: CHART_THEME.text, fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
          labelFormatter={(v) => `Predicted: ${v}%`}
          formatter={(v, name) =>
            name === "ideal"
              ? [`${v}%`, "Perfect calibration"]
              : [`${v}%`, `Actual (n=${data.find((d) => d.actual === Number(v))?.n ?? "?"})`]
          }
          cursor={{ stroke: "#374151" }}
        />
        <Legend
          formatter={(v) => v === "ideal" ? "Perfect calibration" : "Model (actual)"}
          wrapperStyle={{ fontSize: 11, color: CHART_THEME.text }}
        />
        <Line dataKey="ideal" stroke="#374151" strokeDasharray="5 3" dot={false} strokeWidth={1.5} />
        <Line
          dataKey="actual"
          stroke={CHART_THEME.emerald}
          strokeWidth={2}
          dot={{ fill: CHART_THEME.emerald, r: 5 }}
          activeDot={{ r: 7 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── Rolling accuracy chart ────────────────────────────────────────────────────

function buildRollingAccuracy(settled: StoredPrediction[], window = 30) {
  const sorted = [...settled].sort(
    (a, b) =>
      new Date(a.result!.settled_at).getTime() -
      new Date(b.result!.settled_at).getTime(),
  );

  return sorted.slice(window - 1).map((_, idx) => {
    const slice = sorted.slice(idx, idx + window);
    const correct = slice.filter((p) => p.result!.correct).length;
    const date = new Date(slice[slice.length - 1].result!.settled_at);
    return {
      date:     date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      accuracy: Math.round((correct / window) * 100),
    };
  });
}

function RollingAccuracyChart({ settled }: { settled: StoredPrediction[] }) {
  const data = useMemo(() => buildRollingAccuracy(settled), [settled]);

  if (data.length < 5) {
    return (
      <p className="text-sm text-gray-600 text-center py-8">
        Need at least 30 settled predictions for rolling accuracy — check back soon.
      </p>
    );
  }

  const step = Math.max(1, Math.floor(data.length / 10));
  const ticks = data.filter((_, i) => i % step === 0).map((d) => d.date);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} />
        <XAxis
          dataKey="date"
          ticks={ticks}
          tick={{ fill: CHART_THEME.text, fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: CHART_THEME.text, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          domain={[40, 90]}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
          labelStyle={{ color: "#e5e7eb", fontSize: 12 }}
          formatter={(v) => [`${v}%`, "Rolling accuracy (30 matches)"]}
          cursor={{ stroke: "#374151" }}
        />
        <ReferenceLine y={65} stroke={CHART_THEME.amber} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "65%", position: "right", fill: CHART_THEME.amber, fontSize: 10 }} />
        <Line
          dataKey="accuracy"
          stroke={CHART_THEME.blue}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: CHART_THEME.blue }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Surface breakdown ─────────────────────────────────────────────────────────

function SurfaceBreakdown({ settled }: { settled: StoredPrediction[] }) {
  const surfaces = ["Hard", "Clay", "Grass"] as const;

  const stats = surfaces.map((surface) => {
    const matches = settled.filter((p) => p.surface === surface);
    const correct = matches.filter((p) => p.result!.correct).length;
    return {
      surface,
      total:    matches.length,
      correct,
      accuracy: matches.length > 0 ? (correct / matches.length) * 100 : null,
    };
  });

  const SURFACE_COLOR: Record<string, string> = {
    Hard:  "text-blue-400",
    Clay:  "text-orange-400",
    Grass: "text-emerald-400",
  };

  const SURFACE_BADGE: Record<string, string> = {
    Hard:  "surface-badge surface-hard",
    Clay:  "surface-badge surface-clay",
    Grass: "surface-badge surface-grass",
  };

  return (
    <div className="grid grid-cols-3 gap-4">
      {stats.map(({ surface, total, correct, accuracy }) => (
        <div key={surface} className="rounded-lg bg-gray-800/40 border border-gray-800 p-4 text-center space-y-2">
          <span className={SURFACE_BADGE[surface]}>{surface}</span>
          <p className={`text-3xl font-bold tabular-nums ${accuracy != null ? SURFACE_COLOR[surface] : "text-gray-600"}`}>
            {accuracy != null ? `${accuracy.toFixed(1)}%` : "—"}
          </p>
          <p className="text-xs text-gray-600 tabular-nums">
            {total > 0 ? `${correct} / ${total} correct` : "no data"}
          </p>
        </div>
      ))}
    </div>
  );
}

// ── Summary stat cards ────────────────────────────────────────────────────────

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card text-center py-5">
      <p className="text-2xl font-bold tabular-nums text-white">{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
      <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider">{label}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ModelPage() {
  const [featureImportance, setFeatureImportance] = useState<FeatureImportance[]>([]);
  const [predictions,       setPredictions]        = useState<StoredPrediction[]>([]);
  const [loading,           setLoading]            = useState(true);
  const [error,             setError]              = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getModelInfo(), getStoredPredictions()])
      .then(([info, preds]) => {
        setFeatureImportance(info.feature_importance);
        setPredictions(preds);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not reach the backend."))
      .finally(() => setLoading(false));
  }, []);

  const settled = useMemo(
    () => predictions.filter((p) => p.result != null),
    [predictions],
  );

  const overallAccuracy =
    settled.length > 0
      ? (settled.filter((p) => p.result!.correct).length / settled.length) * 100
      : null;

  return (
    <div className="space-y-8">

      {/* ── Header ── */}
      <div id="model-header">
        <h1 className="text-3xl font-bold tracking-tight">Model Analytics</h1>
        <p className="text-gray-400 mt-1 text-sm max-w-2xl">
          XGBoost classifier trained on ATP matches from 2016–2024, tested on 2025.
          Isotonic calibration ensures predicted probabilities reflect real-world win rates.
          Feature importances are averaged across five calibration folds.
        </p>
      </div>

      {error && (
        <div className="card border-red-800/60 bg-red-950/30 text-red-400 text-sm">{error}</div>
      )}

      {/* ── Top stats ── */}
      {!loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat
            label="Overall accuracy"
            value={overallAccuracy != null ? `${overallAccuracy.toFixed(1)}%` : "—"}
            sub={settled.length > 0 ? `${settled.filter((p) => p.result!.correct).length} / ${settled.length} correct` : undefined}
          />
          <Stat
            label="Settled predictions"
            value={settled.length.toString()}
          />
          <Stat
            label="Training window"
            value="2016–2024"
            sub="test on 2025"
          />
          <Stat
            label="Features"
            value="24"
            sub="rank, form, surface, H2H…"
          />
        </div>
      )}

      {/* ── Feature importance + calibration ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div id="feature-importance">
          <ChartCard
            title="Feature Importance"
            subtitle="Top 12 features by XGBoost gain — what the model weighs most heavily"
          >
            {loading ? (
              <div className="h-64 flex items-center justify-center text-gray-600 text-sm">Loading…</div>
            ) : (
              <FeatureImportanceChart data={featureImportance} />
            )}
          </ChartCard>
        </div>

        <div id="calibration-curve">
          <ChartCard
            title="Calibration Curve"
            subtitle="Predicted win probability vs actual win rate — dots near the dashed line mean honest predictions"
          >
            {loading ? (
              <div className="h-64 flex items-center justify-center text-gray-600 text-sm">Loading…</div>
            ) : (
              <CalibrationChart settled={settled} />
            )}
          </ChartCard>
        </div>
      </div>

      {/* ── Rolling accuracy ── */}
      <div id="rolling-accuracy">
        <ChartCard
          title="Rolling Accuracy (30-match window)"
          subtitle="Model accuracy over time — each point is the last 30 settled matches at that date"
        >
          {loading ? (
            <div className="h-48 flex items-center justify-center text-gray-600 text-sm">Loading…</div>
          ) : (
            <RollingAccuracyChart settled={settled} />
          )}
        </ChartCard>
      </div>

      {/* ── Surface breakdown ── */}
      <div id="surface-breakdown">
        <ChartCard
          title="Accuracy by Surface"
          subtitle="How the model performs across different court types"
        >
          {loading ? (
            <div className="h-24 flex items-center justify-center text-gray-600 text-sm">Loading…</div>
          ) : (
            <SurfaceBreakdown settled={settled} />
          )}
        </ChartCard>
      </div>

      <PageHelp steps={TOUR_STEPS} />
    </div>
  );
}
