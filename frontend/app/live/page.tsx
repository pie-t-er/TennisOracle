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
import PredictionLogTable from "@/components/PredictionLogTable";
import { aggregateBets, STAKE } from "@/lib/betting";

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

// ── Spinner icon ──────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LivePage() {
  const [upcoming,  setUpcoming]  = useState<UpcomingMatch[]>([]);
  const [log,       setLog]       = useState<StoredPrediction[]>([]);
  const [summary,   setSummary]   = useState<OddsSummary | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState<string | null>(null);

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
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Live Predictions</h1>
          <p className="text-gray-400 mt-1 text-sm">
            Model predictions across the ATP tour, refreshed automatically throughout the day.
            Matches at majors and bigger events are tracked against real bookmaker odds; smaller
            tournaments are predicted as soon as results land, without odds.
          </p>
        </div>

        <button
          onClick={load}
          disabled={loading}
          className="btn-secondary flex items-center gap-2 self-start shrink-0"
        >
          {loading ? <Spinner /> : <span>↻</span>}
          Refresh
        </button>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="card border-red-800/60 bg-red-950/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* ── Stats bar ── */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
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
      <section className="space-y-4">
        <div className="flex items-baseline gap-2">
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {upcomingWithPrediction.map((match) => (
              <LivePredictionCard key={match.match_id} match={match} />
            ))}
          </div>
        )}
      </section>

      {/* ── Prediction log ── */}
      <section className="space-y-4">
        <div className="flex items-baseline gap-2">
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

    </div>
  );
}
