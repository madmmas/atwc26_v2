import { api, Player } from "@/lib/api";
import { FixturePrediction } from "@/lib/fixtures";

type Role = "GK" | "DEF" | "MID" | "FWD";
type Slot = { role: Role; player_id: number | null };

const FORMATION: Record<string, Record<Role, number>> = {
  "4-3-3": { GK: 1, DEF: 4, MID: 3, FWD: 3 },
};

function slotsFor(formation: string): Slot[] {
  const f = FORMATION[formation];
  if (!f) return [];
  const out: Slot[] = [];
  (["GK", "DEF", "MID", "FWD"] as Role[]).forEach((role) => {
    for (let i = 0; i < f[role]; i += 1) {
      out.push({ role, player_id: null });
    }
  });
  return out;
}

function autoFill(players: Player[], slots: Slot[]): Slot[] {
  const used = new Set<number>();
  const byRole = (role: Role) =>
    players
      .filter((p) => p.role === role && !used.has(p.player_id))
      .sort((a, b) => b.minutes - a.minutes);
  const anyLeft = () =>
    players.filter((p) => !used.has(p.player_id)).sort((a, b) => b.minutes - a.minutes);
  return slots.map((slot) => {
    const pick = byRole(slot.role)[0] || anyLeft()[0];
    if (pick) used.add(pick.player_id);
    return { ...slot, player_id: pick ? pick.player_id : null };
  });
}

const teamPlayersCache = new Map<string, Player[]>();

async function teamPlayers(team: string): Promise<Player[]> {
  const cached = teamPlayersCache.get(team);
  if (cached) return cached;
  const res = await api.teamPlayers(team);
  teamPlayersCache.set(team, res.players);
  return res.players;
}

export function predictionFromApi(
  home: string,
  away: string,
  prediction: {
    team_a: { team_name: string; win_probability: number };
    team_b: { team_name: string; win_probability: number };
    draw_prob: number;
  }
): FixturePrediction {
  const homeIsA = prediction.team_a.team_name === home;
  const homeWin = homeIsA ? prediction.team_a.win_probability : prediction.team_b.win_probability;
  const awayWin = homeIsA ? prediction.team_b.win_probability : prediction.team_a.win_probability;
  const predictedWinner =
    homeWin >= awayWin && homeWin >= prediction.draw_prob
      ? home
      : awayWin >= prediction.draw_prob
        ? away
        : null;
  return {
    home_win_prob: homeWin,
    draw_prob: prediction.draw_prob,
    away_win_prob: awayWin,
    predicted_winner: predictedWinner,
  };
}

export async function quickPredict(home: string, away: string): Promise<FixturePrediction> {
  const [playersA, playersB] = await Promise.all([teamPlayers(home), teamPlayers(away)]);
  const slotsA = autoFill(playersA, slotsFor("4-3-3"));
  const slotsB = autoFill(playersB, slotsFor("4-3-3"));
  if (!slotsA.every((s) => s.player_id) || !slotsB.every((s) => s.player_id)) {
    throw new Error(`Could not auto-pick XI for ${home} vs ${away}`);
  }
  const result = await api.predict({
    team_a: {
      team_name: home,
      home: true,
      players: slotsA.map((s) => ({ player_id: s.player_id, role: s.role })),
    },
    team_b: {
      team_name: away,
      home: false,
      players: slotsB.map((s) => ({ player_id: s.player_id, role: s.role })),
    },
    model: "poisson",
  });
  return predictionFromApi(home, away, result);
}
