import { SurfaceStat } from "@/lib/api";

interface Props {
  surfaceStats: Record<string, SurfaceStat>;
}

const SURFACES = [
  { key: "Hard", label: "Hard", color: "bg-blue-500", bg: "bg-blue-900/20" },
  { key: "Clay", label: "Clay", color: "bg-orange-500", bg: "bg-orange-900/20" },
  { key: "Grass", label: "Grass", color: "bg-green-500", bg: "bg-green-900/20" },
];

export default function SurfaceStats({ surfaceStats }: Props) {
  return (
    <div className="space-y-3">
      {SURFACES.map(({ key, label, color, bg }) => {
        const stat = surfaceStats[key];
        if (!stat) return null;
        const pct = Math.round(stat.win_pct * 100);
        return (
          <div key={key}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-400">{label}</span>
              <span className="font-semibold">
                {pct}%
                <span className="text-gray-500 text-xs font-normal ml-1.5">
                  ({stat.wins}W–{stat.losses}L)
                </span>
              </span>
            </div>
            <div className={`h-2 rounded-full ${bg} overflow-hidden`}>
              <div
                className={`h-full ${color} rounded-full transition-all duration-500`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
