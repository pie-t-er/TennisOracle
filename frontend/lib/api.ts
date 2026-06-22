const API_BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    : "";  // empty = use Next.js rewrites in browser

export interface SurfaceStat {
  wins: number;
  losses: number;
  win_pct: number;
}

export interface RecentMatch {
  date: string;
  opponent: string;
  surface: string;
  result: "W" | "L";
  score: string;
}

export interface Player {
  name: string;
  hand: string;
  height: number;
  country: string;
  age: number;
  rank: number | null;
  rank_points: number | null;
  career_wins: number;
  career_losses: number;
  career_matches: number;
  career_win_pct: number;
  minutes_per_match: number;
  ace_rate: number;
  surface_stats: Record<string, SurfaceStat>;
  recent_win_pct: number;
  recent_matches: RecentMatch[];
}

export interface H2HRecord {
  p1_wins: number;
  p2_wins: number;
  total: number;
}

export interface PredictResult {
  player1: string;
  player2: string;
  surface: string;
  p1_prob: number;
  p2_prob: number;
  predicted_winner: string;
  confidence: "high" | "medium" | "low";
  h2h: H2HRecord;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export function getPlayers(search = "", limit = 300): Promise<Player[]> {
  const p = new URLSearchParams({ limit: String(limit) });
  if (search) p.set("search", search);
  return apiFetch<Player[]>(`/api/players?${p}`);
}

export function getPlayer(name: string): Promise<Player> {
  return apiFetch<Player>(`/api/players/${encodeURIComponent(name)}`);
}

export function predict(
  player1: string,
  player2: string,
  surface: string
): Promise<PredictResult> {
  return apiFetch<PredictResult>("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player1, player2, surface }),
  });
}

// ── Live odds / predictions ───────────────────────────────────────────────────

/** Per-bookmaker H2H odds: { bookKey: { playerName: decimalOdds } } */
export type BookmakerOdds = Record<string, Record<string, number>>;

export interface MatchPrediction {
  p1_name: string;
  p2_name: string;
  p1_prob: number;
  p2_prob: number;
  predicted_winner: string;
  confidence: "high" | "medium" | "low";
  /** Model prob minus book implied prob for player 1. Positive = value on P1. */
  p1_edge?: number;
  /** Model prob minus book implied prob for player 2. Positive = value on P2. */
  p2_edge?: number;
}

/** A live upcoming match returned by /api/odds/upcoming */
export interface UpcomingMatch {
  match_id: string;
  commence_time: string;
  tournament: string;
  surface: string;
  player1: string;
  player2: string;
  /** Best decimal odds across all bookmakers: { playerName: odds } */
  best_odds: Record<string, number>;
  bookmakers: BookmakerOdds;
  prediction: MatchPrediction | null;
}

/** A stored prediction from /api/odds/predictions (may or may not be settled) */
export interface StoredPrediction {
  match_id: string;
  commence_time: string;
  tournament: string;
  surface: string;
  player1: string;
  player2: string;
  bookmakers: BookmakerOdds;
  prediction: MatchPrediction;
  collected_at: string;
  result: {
    winner: string;
    correct: boolean;
    settled_at: string;
  } | null;
}

export interface OddsSummary {
  total: number;
  settled: number;
  pending: number;
  correct: number;
  accuracy: number | null;
}

export function getUpcomingOdds(): Promise<UpcomingMatch[]> {
  return apiFetch<UpcomingMatch[]>("/api/odds/upcoming");
}

export function getStoredPredictions(settledOnly = false): Promise<StoredPrediction[]> {
  const p = new URLSearchParams();
  if (settledOnly) p.set("settled_only", "true");
  return apiFetch<StoredPrediction[]>(`/api/odds/predictions?${p}`);
}

export function getOddsSummary(): Promise<OddsSummary> {
  return apiFetch<OddsSummary>("/api/odds/summary");
}
