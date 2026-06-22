import { RecentMatch } from "@/lib/api";

interface Props {
  matches: RecentMatch[];
}

const SURFACE_DOT: Record<string, string> = {
  Hard: "bg-blue-500",
  Clay: "bg-orange-500",
  Grass: "bg-green-500",
};

export default function RecentForm({ matches }: Props) {
  if (!matches.length) return <p className="text-gray-600 text-sm">No recent matches</p>;

  return (
    <div className="space-y-2">
      {matches.map((m, i) => (
        <div
          key={i}
          className="flex items-center gap-3 text-sm py-1.5 border-b border-gray-800 last:border-0"
        >
          {/* W/L chip */}
          <span
            className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold shrink-0 ${
              m.result === "W"
                ? "bg-emerald-900/60 text-emerald-400"
                : "bg-red-900/60 text-red-400"
            }`}
          >
            {m.result}
          </span>

          {/* Opponent */}
          <span className="flex-1 text-gray-300 truncate">{m.opponent}</span>

          {/* Surface dot */}
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${SURFACE_DOT[m.surface] ?? "bg-gray-600"}`}
            title={m.surface}
          />

          {/* Date */}
          <span className="text-gray-600 text-xs shrink-0">{m.date.slice(0, 7)}</span>
        </div>
      ))}
    </div>
  );
}
