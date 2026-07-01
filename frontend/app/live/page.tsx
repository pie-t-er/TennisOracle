"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getUpcomingOdds,
  getStoredPredictions,
  getOddsSummary,
  UpcomingMatch,
  StoredPrediction,
  OddsSummary,
} from "@/lib/api";
import LivePredictionCard from "@/components/LivePredictionCard";
import CompactPredictionCard from "@/components/CompactPredictionCard";
import PredictionLogTable from "@/components/PredictionLogTable";
import PageHelp from "@/components/PageHelp";
import { aggregateBets, STAKE } from "@/lib/betting";

const TOUR_STEPS = [
  {
    target: "#live-stats",
    title: "Model scorecard",
    content: "Running accuracy and simulated P&L across every settled prediction. Updates automatically as matches finish.",
    disableBeacon: true,
  },
  {
    target: "#upcoming-heading",
    title: "Upcoming predictions",
    content: "Click any card for the full odds breakdown — model probability vs bookmaker implied probability, and where the model diverges from the market.",
    placement: "bottom" as const,
  },
  {
    target: "#log-filter-bar",
    title: "Filter & sort",
    content: "Narrow by surface or result, or sort by P&L to see which picks returned the most value.",
  },
  {
    target: "#log-heading",
    title: "Prediction history",
    content: "Every prediction the model has made — from big tournaments with full bookmaker odds to smaller events predicted from TML results alone.",
    placement: "bottom" as const,
  },
  {
    target: "#page-help",
    title: "Need help?",
    content: "Use these buttons to relaunch this walkthrough or send feedback — reports go straight to the project backlog as GitHub issues.",
    placement: "top" as const,
  },
];

const UPCOMING_PAGE_SIZE = 20;

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "green" | "red" | "neutral";
}) {
  const color =
    accent === "green" ? "text-emerald-400" :
    accent === "red"   ? "text-red-400"     : "text-white";

  return (
    <div className="card text-center py-5">
      <p className={`text-3xl font-bold tracking-tight tabular-nums ${color}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-600 mt-0.5 tabular-nums">{sub}</p>}
      <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider">{label}</p>
    </div>
  );
}


// ── Upcoming match modal ───────────────────────────────────────────────────────

function UpcomingModal({ match, onClose }: { match: UpcomingMatch; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-end mb-2">
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-gray-500 hover:text-gray-200 text-xl leading-none transition-colors w-8 h-8 flex items-center justify-center rounded hover:bg-gray-800"
          >
            ✕
          </button>
        </div>
        <LivePredictionCard match={match} />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LivePage() {
  const [upcoming,      setUpcoming]      = useState<UpcomingMatch[]>([]);
  const [log,           setLog]           = useState<StoredPrediction[]>([]);
  const [summary,       setSummary]       = useState<OddsSummary | null>(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState<string | null>(null);
  const [upcomingPage,  setUpcomingPage]  = useState(0);
  const [selectedMatch, setSelectedMatch] = useState<UpcomingMatch | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, l, s] = await Promise.all([
        getUpcomingOdds(),
        getStoredPredictions(),
        getOddsSummary(),
      ]);
      setUpcoming(u);
      setLog(l);
      setSummary(s);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reach the backend."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const upcomingWithPrediction = upcoming.filter((m) => m.prediction !== null);
  const upcomingTotalPages     = Math.ceil(upcomingWithPrediction.length / UPCOMING_PAGE_SIZE);
  const upcomingSlice          = upcomingWithPrediction.slice(
    upcomingPage * UPCOMING_PAGE_SIZE,
    (upcomingPage + 1) * UPCOMING_PAGE_SIZE,
  );

  const accuracyAccent =
    summary?.accuracy == null    ? "neutral" :
    summary.accuracy >= 0.65     ? "green"   : "red";

  const betTotals = aggregateBets(log);
  const plAccent =
    betTotals.betsPlaced === 0 ? "neutral" :
    betTotals.totalProfit >= 0 ? "green"   : "red";

  return (
    <div className="space-y-10">

      {/* ── Header ── */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Live Predictions</h1>
        <p className="text-gray-400 mt-1 text-sm">
          Model predictions across the ATP tour, refreshed automatically throughout the day.
          Matches at majors and bigger events are tracked against real bookmaker odds; smaller
          tournaments are predicted as soon as results land, without odds.
        </p>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="card border-red-800/60 bg-red-950/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* ── Stats bar ── */}
      {summary && (
        <div id="live-stats" className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <StatCard label="Predictions" value={summary.total} />
          <StatCard label="Pending"     value={summary.pending} />
          <StatCard
            label="Settled"
            value={summary.settled}
            sub={
              summary.settled > 0
                ? `${summary.correct} correct`
                : undefined
            }
          />
          <StatCard
            label="Accuracy"
            value={
              summary.accuracy != null
                ? `${(summary.accuracy * 100).toFixed(1)}%`
                : "—"
            }
            sub={
              summary.settled > 0
                ? `${summary.correct} / ${summary.settled}`
                : undefined
            }
            accent={accuracyAccent}
          />
          <StatCard
            label={`Sim. $${STAKE}/bet P&L`}
            value={
              betTotals.betsPlaced > 0
                ? `${betTotals.totalProfit >= 0 ? "+" : ""}$${betTotals.totalProfit.toFixed(2)}`
                : "—"
            }
            sub={
              betTotals.betsPlaced > 0
                ? `${betTotals.betsWon}/${betTotals.betsPlaced} won  ·  $${betTotals.totalStaked} staked`
                : undefined
            }
            accent={plAccent}
          />
        </div>
      )}

      {/* ── Upcoming ── */}
      <section id="upcoming-section" className="space-y-4">
        <div id="upcoming-heading" className="flex items-baseline gap-2">
          <h2 className="text-lg font-semibold">Upcoming</h2>
          {!loading && (
            <span className="text-sm text-gray-500">
              {upcomingWithPrediction.length === 0
                ? "no matches with predictions right now"
                : `${upcomingWithPrediction.length} match${upcomingWithPrediction.length !== 1 ? "es" : ""}`}
            </span>
          )}
        </div>

        {loading && upcomingWithPrediction.length === 0 ? (
          <div className="card text-gray-600 text-sm text-center py-12">
            Loading…
          </div>
        ) : upcomingWithPrediction.length === 0 ? (
          <div className="card text-center py-12 space-y-2">
            <p className="text-gray-500 text-sm">
              No upcoming matches with predictions right now.
            </p>
            <p className="text-gray-600 text-xs">
              New predictions are collected automatically once a day — check back soon.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {upcomingSlice.map((match) => (
                <CompactPredictionCard
                  key={match.match_id}
                  match={match}
                  onClick={() => setSelectedMatch(match)}
                />
              ))}
            </div>

            {upcomingTotalPages > 1 && (
              <div className="flex items-center justify-between text-xs text-gray-500 px-1">
                <span className="tabular-nums">
                  {upcomingPage * UPCOMING_PAGE_SIZE + 1}–{Math.min(
                    (upcomingPage + 1) * UPCOMING_PAGE_SIZE,
                    upcomingWithPrediction.length,
                  )}{" "}
                  of {upcomingWithPrediction.length}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setUpcomingPage((p) => p - 1)}
                    disabled={upcomingPage === 0}
                    className="px-3 py-1.5 rounded bg-gray-800 text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    ← Prev
                  </button>
                  <button
                    onClick={() => setUpcomingPage((p) => p + 1)}
                    disabled={upcomingPage >= upcomingTotalPages - 1}
                    className="px-3 py-1.5 rounded bg-gray-800 text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── Prediction log ── */}
      <section id="prediction-log" className="space-y-4">
        <div id="log-heading" className="flex items-baseline gap-2">
          <h2 className="text-lg font-semibold">Prediction Log</h2>
          {log.length > 0 && (
            <span className="text-sm text-gray-500">
              {log.length} stored
            </span>
          )}
        </div>

        {log.length === 0 ? (
          <div className="card text-gray-600 text-sm text-center py-12">
            No stored predictions yet.
          </div>
        ) : (
          <PredictionLogTable predictions={log} />
        )}
      </section>

      {/* ── Match detail modal ── */}
      {selectedMatch && (
        <UpcomingModal
          match={selectedMatch}
          onClose={() => setSelectedMatch(null)}
        />
      )}

      <PageHelp steps={TOUR_STEPS} />
    </div>
  );
}
