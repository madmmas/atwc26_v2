// Split v2 API bases (Issue 7). Falls back to monolith NEXT_PUBLIC_API_URL for v1.
// Treat "" as unset — build scripts may export empty split URLs before fallback runs.
function envOr<T>(value: string | undefined, fallback: T): string | T {
  return value && value.trim() !== "" ? value : fallback;
}

// Static export on CloudFront: call same-origin /api/* (proxied to API Gateway).
const SAME_ORIGIN_API = process.env.NEXT_PUBLIC_SAME_ORIGIN_API === "true";

const MONOLITH_BASE = SAME_ORIGIN_API
  ? ""
  : envOr(process.env.NEXT_PUBLIC_API_URL, "http://localhost:8000");

export const ANALYTICS_BASE = SAME_ORIGIN_API
  ? ""
  : envOr(process.env.NEXT_PUBLIC_ANALYTICS_API_URL, MONOLITH_BASE);

export const PREDICT_BASE = SAME_ORIGIN_API
  ? ""
  : envOr(process.env.NEXT_PUBLIC_PREDICT_API_URL, MONOLITH_BASE);

// Kept for backwards compatibility with single-URL builds.
export const API_BASE = MONOLITH_BASE;

export type Player = {
  player_id: number;
  player_name: string;
  team_name: string;
  flag_url?: string | null;
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
  flag_url?: string | null;
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
  attack_rating?: number;
  defense_rating?: number;
  gk_rating?: number;
  expected_goals?: number;
  win_probability: number;
  elo_rating?: number;
  key_players?: KeyPlayer[];
};

export type Prediction = {
  team_a: TeamBlock;
  team_b: TeamBlock;
  draw_prob: number;
  most_likely_score?: { a: number; b: number; prob: number };
  top_scorelines?: { a: number; b: number; prob: number }[];
  radar?: { dimensions: string[]; [team: string]: any };
  narrative?: string;
  model: {
    type?: string;
    name?: string;
    version?: string;
    description?: string;
    avg_team_goals_baseline?: number;
    assumptions?: string;
  };
  comparison?: Record<
    string,
    {
      win_probability_a: number;
      draw_probability: number;
      win_probability_b: number;
      model_name: string;
    }
  >;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${ANALYTICS_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  overview: () => get<Overview>("/api/overview"),
  teamPlayers: (team: string) =>
    get<{ team_name: string; players: Player[] }>(
      `/api/teams/${encodeURIComponent(team)}/players`
    ),
  players: (q: string) =>
    get<{ count: number; page_size: number; next_cursor: string | null; players: Player[] }>(
      `/api/players?${q}`
    ),
  leaderboard: (metric: string, role?: string) =>
    get<{ metric: string; leaders: Player[] }>(
      `/api/leaderboard?metric=${metric}${role ? `&role=${role}` : ""}`
    ),
  predict: async (body: unknown): Promise<Prediction> => {
    const res = await fetch(`${PREDICT_BASE}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`predict -> ${res.status}`);
    return res.json();
  },
  matches: () => get<{ matches: MatchListItem[] }>("/api/matches"),
  matchDetail: (id: string) => get<MatchDetail>(`/api/matches/${id}`),
  playerDetail: (id: number) => get<PlayerDetail>(`/api/players/${id}`),
  standings: () => get<{ groups: Record<string, GroupStandings> }>("/api/standings"),
  bracket: () => get<BracketData>("/api/bracket"),
  winnerProbabilities: () => get<{ teams: WinnerProbability[] }>("/api/winner-probabilities"),
};

// --- Match Analysis ---
export type MatchListItem = {
  game_id: string;
  date: string;
  home_team: string;
  away_team: string;
  home_flag?: string | null;
  away_flag?: string | null;
  home_score: number | null;
  away_score: number | null;
  // Only set when the match was decided on penalties.
  home_shootout_score?: number | null;
  away_shootout_score?: number | null;
};
export type MatchIndicator = {
  key: string;
  label: string;
  better_high: boolean;
  a: number;
  b: number;
};
export type MatchEvent = {
  minute: number;
  display: string;
  type: string;
  team: string | null;
  label: string;
  scoring: boolean;
};
export type MomentumPoint = { minute: number; value: number };
export type MatchTimeline = {
  home_team: string;
  away_team: string;
  events: MatchEvent[];
  momentum: MomentumPoint[];
  duration: number;
};
export type MatchTeamBlock = {
  team_name: string;
  flag_url?: string | null;
  score: number | null;
  // Only set when the match was decided on penalties.
  shootout_score?: number | null;
};
export type MatchDetail = {
  meta: MatchListItem;
  team_a: MatchTeamBlock;
  team_b: MatchTeamBlock;
  indicators: MatchIndicator[];
  timeline: MatchTimeline | null;
};

// --- Player Analysis ---
export type PlayerMatch = {
  game_id: string;
  date: string;
  opponent: string;
  opp_flag?: string | null;
  home_away: string;
  result: "W" | "D" | "L" | null;
  score: string | null;
  minutes: number;
  stats: Record<string, number | null>;
};
// --- Group Standings ---
export type GroupTeam = {
  team_id: string;
  team_name: string;
  flag_url?: string | null;
  rank: number;
  GP: number;
  W: number;
  D: number;
  L: number;
  F: number;
  A: number;
  GD: number;
  P: number;
  advanced: boolean;
};
export type RemainingMatch = {
  game_id: string;
  kickoff_utc: string;
  home_team_id: string;
  home_team: string;
  away_team_id: string;
  away_team: string;
};
export type GroupStandings = {
  teams: GroupTeam[];
  remaining_matches: RemainingMatch[];
};

// --- Knockout Bracket ---
export type BracketSlot =
  | { type: "group_rank"; group: string; rank: number }
  | { type: "third_place"; candidate_groups: string[] }
  | { type: "team"; team_id: string; team_name: string; flag_url?: string | null }
  | { type: "match_winner" | "match_loser"; round: string; position: number };
export type BracketPrediction = {
  team_a_name: string | null;
  team_a_flag: string | null;
  team_b_name: string | null;
  team_b_flag: string | null;
  predicted_score_a: number | null;
  predicted_score_b: number | null;
  predicted_winner: string | null;
  // Advancing probability of the predicted winner, 0..1.
  win_probability?: number | null;
};
export type BracketMatch = {
  game_id: string;
  position: number;
  kickoff_utc: string;
  completed: boolean;
  slot_a: BracketSlot;
  slot_b: BracketSlot;
  score_a: string | null;
  score_b: string | null;
  // Only set when the draw was resolved on penalties.
  shootout_a?: number | null;
  shootout_b?: number | null;
  // Only present on unplayed matches.
  prediction?: BracketPrediction | null;
};
export type BracketRound = { name: string; matches: BracketMatch[] };
export type BracketData = { rounds: BracketRound[] };

// --- Winner Probability ---
export type WinnerProbability = {
  team_name: string;
  flag_url?: string | null;
  probability: number;
  eliminated: boolean;
};

export type PlayerDetail = {
  player: {
    player_id: number;
    player_name: string;
    team_name: string;
    flag_url?: string | null;
    role: string;
    position: string;
    games: number;
    minutes: number;
    rating: number | null;
  };
  indicators: { key: string; label: string; per90: boolean }[];
  matches: PlayerMatch[];
  totals: Record<string, number>;
  per90: Record<string, number>;
};
