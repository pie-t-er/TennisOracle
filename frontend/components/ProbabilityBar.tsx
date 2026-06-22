"use client";

interface Props {
  p1Name: string;
  p2Name: string;
  p1Prob: number;
  p2Prob: number;
  confidence: "high" | "medium" | "low";
}

const CONFIDENCE_STYLE = {
  high: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
  medium: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  low: "bg-gray-800 text-gray-400 border-gray-700",
};

export default function ProbabilityBar({
  p1Name,
  p2Name,
  p1Prob,
  p2Prob,
  confidence,
}: Props) {
  const p1Pct = Math.round(p1Prob * 100);
  const p2Pct = Math.round(p2Prob * 100);
  const winner = p1Prob >= p2Prob ? p1Name : p2Name;

  return (
    <div className="space-y-4">
      {/* Winner banner */}
      <div className="text-center">
        <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Predicted winner</p>
        <p className="text-2xl font-bold text-white">{winner}</p>
        <span
          className={`mt-1.5 inline-block text-xs font-medium px-2.5 py-0.5 rounded-full border ${CONFIDENCE_STYLE[confidence]}`}
        >
          {confidence} confidence
        </span>
      </div>

      {/* Bar */}
      <div>
        <div className="flex justify-between text-sm font-semibold mb-1.5">
          <span className={p1Prob >= p2Prob ? "text-blue-400" : "text-gray-400"}>
            {p1Pct}%
          </span>
          <span className={p2Prob > p1Prob ? "text-red-400" : "text-gray-400"}>
            {p2Pct}%
          </span>
        </div>
        <div className="h-4 rounded-full overflow-hidden flex bg-gray-800">
          <div
            className="bg-blue-500 transition-all duration-700 ease-out"
            style={{ width: `${p1Pct}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-700 ease-out flex-1"
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span className="truncate max-w-[45%]">{p1Name}</span>
          <span className="truncate max-w-[45%] text-right">{p2Name}</span>
        </div>
      </div>
    </div>
  );
}
