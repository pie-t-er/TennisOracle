import { notFound } from "next/navigation";
import Link from "next/link";
import { getPlayer } from "@/lib/api";
import SurfaceStats from "@/components/SurfaceStats";
import RecentForm from "@/components/RecentForm";

interface Props {
  params: Promise<{ slug: string }>;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}

export default async function PlayerDetailPage({ params }: Props) {
  const { slug } = await params;
  const name = decodeURIComponent(slug);

  let player;
  try {
    player = await getPlayer(name);
  } catch {
    notFound();
  }

  const winPct = Math.round(player.career_win_pct * 100);
  const recentPct = Math.round(player.recent_win_pct * 100);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back */}
      <Link href="/players" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
        ← Players
      </Link>

      {/* Header */}
      <div className="card flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{player.name}</h1>
          <p className="text-gray-400 mt-1">
            {player.country}
            {player.height ? ` · ${player.height} cm` : ""}
            {player.age ? ` · age ${player.age}` : ""}
            {player.hand
              ? ` · ${player.hand === "R" ? "Right" : player.hand === "L" ? "Left" : "?"}-handed`
              : ""}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-4xl font-black text-gray-200">
            {player.rank ? `#${player.rank}` : "—"}
          </p>
          <p className="text-xs text-gray-600">ATP Ranking</p>
          {player.rank_points != null && (
            <p className="text-sm text-gray-500">{player.rank_points.toLocaleString()} pts</p>
          )}
        </div>
      </div>

      {/* Career stats grid */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-5">
          Career Statistics
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-6 gap-x-4">
          <Stat label="Win %" value={`${winPct}%`} />
          <Stat label="Wins" value={player.career_wins.toLocaleString()} />
          <Stat label="Losses" value={player.career_losses.toLocaleString()} />
          <Stat label="Matches" value={player.career_matches.toLocaleString()} />
          <Stat label="Recent form" value={`${recentPct}%`} />
          <Stat label="Avg min/match" value={Math.round(player.minutes_per_match)} />
          <Stat
            label="Ace rate"
            value={player.ace_rate ? `${(player.ace_rate * 100).toFixed(1)}%` : "—"}
          />
        </div>
      </div>

      {/* Surface breakdown */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-5">
          Surface Win %
        </h2>
        <SurfaceStats surfaceStats={player.surface_stats} />
      </div>

      {/* Recent form */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-5">
          Recent Matches
        </h2>
        <RecentForm matches={player.recent_matches} />
      </div>

      {/* Predict with this player */}
      <div className="text-center">
        <Link
          href={`/?player1=${encodeURIComponent(player.name)}`}
          className="btn-secondary inline-block"
        >
          Predict a match with {player.name.split(" ").pop()} →
        </Link>
      </div>
    </div>
  );
}
