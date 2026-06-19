"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Overview, Player, Prediction } from "@/lib/api";
import { RoleChip, Spinner } from "@/components/ui";
import { PredictionResult } from "@/components/PredictionResult";

const FORMATIONS: Record<string, { GK: number; DEF: number; MID: number; FWD: number }> = {
  "4-3-3": { GK: 1, DEF: 4, MID: 3, FWD: 3 },
  "4-4-2": { GK: 1, DEF: 4, MID: 4, FWD: 2 },
  "3-5-2": { GK: 1, DEF: 3, MID: 5, FWD: 2 },
  "4-2-3-1": { GK: 1, DEF: 4, MID: 5, FWD: 1 },
};
type Role = "GK" | "DEF" | "MID" | "FWD";
type Slot = { role: Role; player_id: number | null };

function slotsFor(formation: string): Slot[] {
  const f = FORMATIONS[formation];
  const out: Slot[] = [];
  (["GK", "DEF", "MID", "FWD"] as Role[]).forEach((r) =>
    Array.from({ length: f[r] }).forEach(() => out.push({ role: r, player_id: null }))
  );
  return out;
}

// Greedy auto-fill: best players (by minutes) per role, falling back across roles.
function autoFill(players: Player[], slots: Slot[]): Slot[] {
  const used = new Set<number>();
  const byRole = (r: Role) =>
    players
      .filter((p) => p.role === r && !used.has(p.player_id))
      .sort((a, b) => b.minutes - a.minutes);
  const anyLeft = () =>
    players.filter((p) => !used.has(p.player_id)).sort((a, b) => b.minutes - a.minutes);
  return slots.map((s) => {
    let pick = byRole(s.role)[0] || anyLeft()[0];
    if (pick) used.add(pick.player_id);
    return { ...s, player_id: pick ? pick.player_id : null };
  });
}

function TeamColumn({
  side,
  teams,
  team,
  setTeam,
  players,
  slots,
  setSlots,
  loading,
}: {
  side: "a" | "b";
  teams: string[];
  team: string;
  setTeam: (t: string) => void;
  players: Player[];
  slots: Slot[];
  setSlots: (s: Slot[]) => void;
  loading: boolean;
}) {
  const accent = side === "a" ? "text-pitch-accent" : "text-pitch-accent2";
  const nameById = useMemo(
    () => Object.fromEntries(players.map((p) => [p.player_id, p])),
    [players]
  );
  const chosen = new Set(slots.map((s) => s.player_id).filter(Boolean) as number[]);

  return (
    <div className="card p-4" data-testid={`team-col-${side}`}>
      <div className="flex items-center justify-between">
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          className="select font-bold"
          data-testid={`team-select-${side}`}
        >
          <option value="">Select team…</option>
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <button
          className="btn-ghost"
          data-testid={`autopick-${side}`}
          disabled={!players.length}
          onClick={() => setSlots(autoFill(players, slots))}
        >
          Auto-pick XI
        </button>
      </div>

      {loading ? (
        <Spinner />
      ) : (
        <div className="mt-4 space-y-1.5">
          {slots.map((s, idx) => {
            const opts = players
              .filter((p) => p.role === s.role || s.player_id === p.player_id)
              .sort((a, b) => b.minutes - a.minutes);
            return (
              <div key={idx} className="flex items-center gap-2">
                <RoleChip role={s.role} />
                <select
                  className="select flex-1"
                  value={s.player_id ?? ""}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : null;
                    setSlots(slots.map((x, i) => (i === idx ? { ...x, player_id: v } : x)));
                  }}
                >
                  <option value="">— empty —</option>
                  {opts.map((p) => (
                    <option key={p.player_id} value={p.player_id} disabled={chosen.has(p.player_id) && p.player_id !== s.player_id}>
                      {p.player_name} · {p.minutes > 0 ? `${p.minutes}m` : "DNP"}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-3 text-right text-xs text-faint">
        {chosen.size}/{slots.length} selected
      </div>
    </div>
  );
}

export default function Predict() {
  const [teams, setTeams] = useState<string[]>([]);
  const [formation, setFormation] = useState("4-3-3");
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [playersA, setPlayersA] = useState<Player[]>([]);
  const [playersB, setPlayersB] = useState<Player[]>([]);
  const [loadA, setLoadA] = useState(false);
  const [loadB, setLoadB] = useState(false);
  const [slotsA, setSlotsA] = useState<Slot[]>(slotsFor("4-3-3"));
  const [slotsB, setSlotsB] = useState<Slot[]>(slotsFor("4-3-3"));
  const [homeSide, setHomeSide] = useState<"a" | "b" | "none">("none");
  const [result, setResult] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeams(o.teams.map((t) => t.team_name).sort((a, b) => a.localeCompare(b)))
    );
  }, []);

  // re-shape slots when formation changes (keeps any still-valid picks by role order)
  useEffect(() => {
    setSlotsA((prev) => remap(prev, formation));
    setSlotsB((prev) => remap(prev, formation));
  }, [formation]);

  function remap(prev: Slot[], f: string): Slot[] {
    const fresh = slotsFor(f);
    (["GK", "DEF", "MID", "FWD"] as Role[]).forEach((r) => {
      const old = prev.filter((s) => s.role === r && s.player_id);
      let k = 0;
      fresh.forEach((s) => {
        if (s.role === r && k < old.length) s.player_id = old[k++].player_id;
      });
    });
    return fresh;
  }

  useEffect(() => {
    if (!teamA) return;
    setLoadA(true);
    api.teamPlayers(teamA).then((r) => {
      setPlayersA(r.players);
      setSlotsA((s) => autoFill(r.players, slotsFor(formation)));
      setLoadA(false);
    });
  }, [teamA]); // eslint-disable-line

  useEffect(() => {
    if (!teamB) return;
    setLoadB(true);
    api.teamPlayers(teamB).then((r) => {
      setPlayersB(r.players);
      setSlotsB((s) => autoFill(r.players, slotsFor(formation)));
      setLoadB(false);
    });
  }, [teamB]); // eslint-disable-line

  const ready =
    teamA && teamB && teamA !== teamB &&
    slotsA.some((s) => s.player_id) && slotsB.some((s) => s.player_id);

  async function runPredict() {
    setBusy(true);
    setErr(null);
    try {
      const body = {
        team_a: {
          team_name: teamA,
          home: homeSide === "a",
          players: slotsA.filter((s) => s.player_id).map((s) => ({ player_id: s.player_id, role: s.role })),
        },
        team_b: {
          team_name: teamB,
          home: homeSide === "b",
          players: slotsB.filter((s) => s.player_id).map((s) => ({ player_id: s.player_id, role: s.role })),
        },
      };
      setResult(await api.predict(body));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black text-fg">Match Predictor</h1>
          <p className="text-sm text-muted">
            Pick two teams, build an XI for each, and the engine predicts the result from
            tournament form.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-faint">Formation</span>
          <select value={formation} onChange={(e) => setFormation(e.target.value)} className="select">
            {Object.keys(FORMATIONS).map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <TeamColumn side="a" teams={teams} team={teamA} setTeam={setTeamA} players={playersA} slots={slotsA} setSlots={setSlotsA} loading={loadA} />
        <TeamColumn side="b" teams={teams} team={teamB} setTeam={setTeamB} players={playersB} slots={slotsB} setSlots={setSlotsB} loading={loadB} />
      </div>

      <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-faint">Home advantage</span>
          {(["none", "a", "b"] as const).map((h) => (
            <button
              key={h}
              onClick={() => setHomeSide(h)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                homeSide === h ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-fg-soft"
              }`}
            >
              {h === "none" ? "Neutral" : h === "a" ? teamA || "Team A" : teamB || "Team B"}
            </button>
          ))}
        </div>
        <button
          className="btn-primary"
          data-testid="predict-button"
          disabled={!ready || busy}
          onClick={runPredict}
        >
          {busy ? "Simulating…" : "Predict result →"}
        </button>
      </div>

      {err && (
        <div className="card p-4 text-rose-300" data-testid="predict-error">
          Prediction failed: {err}
        </div>
      )}
      {result && <PredictionResult p={result} />}
    </div>
  );
}
