import http from 'k6/http';
import { check, sleep } from 'k6';

import { baseUrl, defaultHeaders } from './config.js';

const FORMATION = { GK: 1, DEF: 4, MID: 3, FWD: 3 };
const PAUSE_SEC = Number(__ENV.ATWC26_K6_PAUSE_SEC || 0.15);

export function getJson(path, endpoint) {
  const res = http.get(`${baseUrl}${path}`, {
    headers: defaultHeaders,
    tags: { endpoint },
  });
  check(res, {
    [`${endpoint} status 200`]: (r) => r.status === 200,
  });
  sleep(PAUSE_SEC);
  if (res.status !== 200) {
    return null;
  }
  try {
    return res.json();
  } catch (_) {
    return null;
  }
}

export function postJson(path, body, endpoint) {
  const res = http.post(`${baseUrl}${path}`, JSON.stringify(body), {
    headers: defaultHeaders,
    tags: { endpoint },
  });
  check(res, {
    [`${endpoint} status 200`]: (r) => r.status === 200,
  });
  sleep(PAUSE_SEC);
  if (res.status !== 200) {
    return null;
  }
  try {
    return res.json();
  } catch (_) {
    return null;
  }
}

function roleCounts(players) {
  const counts = {};
  for (const player of players) {
    counts[player.role] = (counts[player.role] || 0) + 1;
  }
  return counts;
}

export function canBuildXi(players) {
  const counts = roleCounts(players);
  return Object.entries(FORMATION).every(([role, needed]) => (counts[role] || 0) >= needed);
}

export function buildXi(teamName, players, home = false) {
  const picks = [];
  for (const [role, needed] of Object.entries(FORMATION)) {
    const rolePlayers = players.filter((p) => p.role === role).slice(0, needed);
    if (rolePlayers.length < needed) {
      return null;
    }
    for (const player of rolePlayers) {
      picks.push({ player_id: player.player_id, role });
    }
  }
  return { team_name: teamName, players: picks, home };
}

export function pickPredictTeams(teams) {
  const names = teams.map((t) => t.team_name);
  for (let i = 0; i < names.length; i += 1) {
    const teamA = names[i];
    const playersA = getJson(`/api/teams/${encodeURIComponent(teamA)}/players`, 'team_players');
    if (!playersA || !canBuildXi(playersA.players)) {
      continue;
    }
    for (let j = i + 1; j < names.length; j += 1) {
      const teamB = names[j];
      const playersB = getJson(`/api/teams/${encodeURIComponent(teamB)}/players`, 'team_players');
      if (!playersB || !canBuildXi(playersB.players)) {
        continue;
      }
      return {
        teamA,
        teamB,
        playersA: playersA.players,
        playersB: playersB.players,
      };
    }
  }
  return null;
}

export function runUserJourney() {
  const health = getJson('/api/health', 'health');
  if (!health) {
    return;
  }

  const overview = getJson('/api/overview', 'overview');
  if (!overview) {
    return;
  }

  const teams = getJson('/api/teams', 'teams');
  if (!teams) {
    return;
  }

  getJson('/api/players?sort=minutes&limit=10', 'players');
  getJson('/api/leaderboard?metric=expectedGoals_p90&limit=10', 'leaderboard');

  const matches = getJson('/api/matches', 'matches');
  if (matches && matches.matches && matches.matches.length > 0) {
    const gameId = matches.matches[0].game_id;
    getJson(`/api/matches/${encodeURIComponent(gameId)}`, 'match_detail');
  }

  const picked = pickPredictTeams(teams.teams);
  if (!picked) {
    check(null, { 'predict teams available': () => false });
    return;
  }

  const body = {
    team_a: buildXi(picked.teamA, picked.playersA, true),
    team_b: buildXi(picked.teamB, picked.playersB, false),
  };
  const prediction = postJson('/api/predict', body, 'predict');
  if (prediction) {
    const total =
      prediction.team_a.win_probability +
      prediction.team_b.win_probability +
      prediction.draw_prob;
    check(prediction, {
      'predict probabilities sum to 1': () => Math.abs(total - 1.0) < 0.01,
    });
  }
}
