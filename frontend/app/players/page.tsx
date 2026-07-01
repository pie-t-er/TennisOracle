"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { getPlayers, Player } from "@/lib/api";
import PageHelp from "@/components/PageHelp";

const TOUR_STEPS = [
  {
    target: "#players-header",
    title: "Player Database",
    content: "Over 300 ATP players from 2010 to present, built from the same match data the model trains on.",
    disableBeacon: true,
  },
  {
    target: "#player-search",
    title: "Search",
    content: "Type a name to filter instantly — or use the handedness dropdown to compare left vs right-handed players.",
  },
  {
    target: "#players-grid-heading",
    title: "Player cards",
    content: "Career win rate, recent form (last 20 matches), and surface splits at a glance. Click any card for the full profile.",
    placement: "bottom" as const,
  },
  {
    target: "#page-help",
    title: "Need help?",
    content: "Use these buttons to relaunch this walkthrough or send feedback — reports go straight to the project backlog as GitHub issues.",
    placement: "top" as const,
  },
];

const HANDS = [
  { value: "", label: "Any hand" },
  { value: "R", label: "Right-handed" },
  { value: "L", label: "Left-handed" },
];

const PAGE_SIZE = 20;

function SurfaceBar({ pct, surface }: { pct: number; surface: string }) {
  const color =
    surface === "Hard" ? "bg-blue-500" : surface === "Clay" ? "bg-orange-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="w-8 text-gray-500">{surface[0]}</span>
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.round(pct * 100)}%` }} />
      </div>
      <span className="w-8 text-right text-gray-400">{Math.round(pct * 100)}%</span>
    </div>
  );
}

function PlayerCard({ player }: { player: Player }) {
  const rankDisplay = player.rank ? `#${player.rank}` : "—";
  return (
    <Link
      href={`/players/${encodeURIComponent(player.name)}`}
      className="card hover:border-gray-600 transition-colors block space-y-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold leading-tight">{player.name}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {player.country} · {player.hand === "R" ? "Right" : player.hand === "L" ? "Left" : "?"}-handed
          </p>
        </div>
        <span className="text-lg font-bold text-gray-400 shrink-0">{rankDisplay}</span>
      </div>

      <div className="flex gap-4 text-sm">
        <div>
          <p className="text-gray-500 text-xs">Win%</p>
          <p className="font-semibold">{Math.round(player.career_win_pct * 100)}%</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Matches</p>
          <p className="font-semibold">{player.career_matches.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Recent</p>
          <p className="font-semibold">{Math.round(player.recent_win_pct * 100)}%</p>
        </div>
      </div>

      <div className="space-y-1">
        {["Hard", "Clay", "Grass"].map((s) => (
          <SurfaceBar key={s} surface={s} pct={player.surface_stats[s]?.win_pct ?? 0} />
        ))}
      </div>
    </Link>
  );
}

export default function PlayersPage() {
  const [query, setQuery] = useState("");
  const [hand, setHand] = useState("");
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const fetchPlayers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await getPlayers(query, 300);
      const filtered = hand ? results.filter((p) => p.hand === hand) : results;
      setPlayers(filtered);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load players");
    } finally {
      setLoading(false);
    }
  }, [query, hand]);

  useEffect(() => {
    const t = setTimeout(fetchPlayers, query ? 250 : 0);
    return () => clearTimeout(t);
  }, [fetchPlayers, query]);

  // Reset to the first page whenever the underlying result set changes.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [players]);

  // Reveal another page once the sentinel below the grid scrolls into view.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || visibleCount >= players.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisibleCount((c) => Math.min(c + PAGE_SIZE, players.length));
        }
      },
      { rootMargin: "300px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [players, visibleCount]);

  const visiblePlayers = players.slice(0, visibleCount);

  return (
    <div className="space-y-6">
      <div id="players-header">
        <h1 className="text-3xl font-bold">Player Database</h1>
        <p className="text-gray-400 mt-1">
          {players.length.toLocaleString()} players · ATP 2010–present
        </p>
      </div>

      {/* Filters */}
      <div id="player-search" className="flex flex-wrap gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name…"
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm
                     placeholder-gray-500 focus:outline-none focus:border-blue-500 w-64"
        />
        <select
          value={hand}
          onChange={(e) => setHand(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm
                     focus:outline-none focus:border-blue-500"
        >
          {HANDS.map((h) => (
            <option key={h.value} value={h.value}>
              {h.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-red-400">{error}</p>}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="card h-44 animate-pulse bg-gray-900" />
          ))}
        </div>
      ) : (
        <>
          <p id="players-grid-heading" className="text-xs text-gray-600">
            {players.length.toLocaleString()} result{players.length !== 1 ? "s" : ""}
          </p>
          <div id="players-grid" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {visiblePlayers.map((p) => (
              <PlayerCard key={p.name} player={p} />
            ))}
            {players.length === 0 && (
              <p className="col-span-3 text-gray-500 text-center py-12">No players found.</p>
            )}
          </div>

          {visibleCount < players.length && (
            <div ref={sentinelRef} className="py-6 text-center text-gray-500 text-sm">
              Showing {visibleCount} of {players.length} — scroll for more…
            </div>
          )}
        </>
      )}

      <PageHelp steps={TOUR_STEPS} />
    </div>
  );
}
