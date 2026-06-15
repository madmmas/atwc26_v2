// Thin typed client for the AnalyseThisWC26 backend.
// `??` (not `||`) so an explicit empty string means "same-origin" — used when
// the app is served behind Nginx that routes /api to the backend.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Player = {
  player_id: number;
  player_name: string;
  team_name: string;
  role: "GK" | "DEF" | "MID" | "FWD";
  games: number;
  minutes: number;
  rating: number;
  expectedGoals_p90?: number;
  expectedAssists_p90?: number;
  totalShots_p90?: number;
  defensiveInterventions_p90?: number;
  duelsWon_p90?: number;
  saves_p90?: number;
  totalGoals_total?: number;
  expectedGoals_total?: number;
  passPct?: number;
  [k: string]: any;
};

export type Team = {
  team_name: string;
  games: number;
  goals_for: number;
  goals_against: number;
  goals_per_game: number;
  conceded_per_game: number;
  xg_per_game: number;
  xga_per_game: number;
  shots_per_game: number;
  sot_per_game: number;
  big_chances_per_game: number;
};

export type Overview = {
  league: { avg_team_goals: number; games: number; teams: number; players: number };
  teams: Team[];
  top_scorers: Player[];
  top_xg_per90: Player[];
  top_creators_per90: Player[];
};

export type KeyPlayer = {
  player_id: number;
  player_name: string;
  role: string;
  attack: number;
  defense: number;
};

export type TeamBlock = {
  team_name: string;
  attack_rating: number;
  defense_rating: number;
  gk_rating: number;
  expected_goals: number;
  win_probability: number;
  key_players: KeyPlayer[];
};

export type Prediction = {
  team_a: TeamBlock;
  team_b: TeamBlock;
  draw_prob: number;
  most_likely_score: { a: number; b: number; prob: number };
  top_scorelines: { a: number; b: number; prob: number }[];
  radar: { dimensions: string[]; [team: string]: any };
  narrative: string;
  model: { type: string; avg_team_goals_baseline: number; assumptions: string };
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  overview: () => get<Overview>("/api/overview"),
  teamPlayers: (team: string) =>
    get<{ team_name: string; players: Player[] }>(
      `/api/teams/${encodeURIComponent(team)}/players`
    ),
  players: (q: string) => get<{ count: number; players: Player[] }>(`/api/players?${q}`),
  leaderboard: (metric: string, role?: string) =>
    get<{ metric: string; leaders: Player[] }>(
      `/api/leaderboard?metric=${metric}${role ? `&role=${role}` : ""}`
    ),
  predict: async (body: unknown): Promise<Prediction> => {
    const res = await fetch(`${API_BASE}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`predict -> ${res.status}`);
    return res.json();
  },
};
