"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, Overview, Player, Prediction } from "@/lib/api";
import { buildPredictUrl, parsePredictUrl } from "@/lib/predictUrl";
import { PredictorHintBar } from "@/components/PredictorHintBar";
import { RoleChip, Skeleton } from "@/components/ui";
import { PredictionResult } from "@/components/PredictionResult";
import { WinnerProbabilityChart } from "@/components/WinnerProbabilityChart";

const FORMATIONS: Record<string, { GK: number; DEF: number; MID: number; FWD: number }> = {
  "4-3-3": { GK: 1, DEF: 4, MID: 3, FWD: 3 },
  "4-4-2": { GK: 1, DEF: 4, MID: 4, FWD: 2 },
  "3-5-2": { GK: 1, DEF: 3, MID: 5, FWD: 2 },
  "4-2-3-1": { GK: 1, DEF: 4, MID: 5, FWD: 1 },
};
type Role = "GK" | "DEF" | "MID" | "FWD";
type Slot = { role: Role; player_id: number | null };

const PREDICT_MODELS = [
  { value: "all", label: "Compare all models" },
  { value: "poisson", label: "Poisson" },
  { value: "elo", label: "Elo" },
  { value: "dixon_coles", label: "Dixon-Coles" },
  { value: "xgboost", label: "XGBoost" },
] as const;
type PredictModel = (typeof PREDICT_MODELS)[number]["value"];

function slotsFor(formation: string): Slot[] {
  const f = FORMATIONS[formation];
  if (!f) return [];
  const out: Slot[] = [];
  (["GK", "DEF", "MID", "FWD"] as Role[]).forEach((r) =>
    Array.from({ length: f[r] }).forEach(() => out.push({ role: r, player_id: null }))
  );
  return out;
}

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

function autoFill(players: Player[], slots: Slot[]): Slot[] {
  const used = new Set<number>();
  const byRole = (r: Role) =>
    players
      .filter((p) => p.role === r && !used.has(p.player_id))
      .sort((a, b) => b.minutes - a.minutes);
  const anyLeft = () =>
    players.filter((p) => !used.has(p.player_id)).sort((a, b) => b.minutes - a.minutes);
  return slots.map((s) => {
    const pick = byRole(s.role)[0] || anyLeft()[0];
    if (pick) used.add(pick.player_id);
    return { ...s, player_id: pick ? pick.player_id : null };
  });
}

function FadeIn({ show, children }: { show: boolean; children: React.ReactNode }) {
  if (!show) return null;
  return <div className="animate-fade-in">{children}</div>;
}

function TeamColumn({
  side,
  teams,
  team,
  setTeam,
  formation,
  setFormation,
  players,
  slots,
  setSlots,
  loading,
}: {
  side: "a" | "b";
  teams: string[];
  team: string;
  setTeam: (t: string) => void;
  formation: string;
  setFormation: (f: string) => void;
  players: Player[];
  slots: Slot[];
  setSlots: (s: Slot[]) => void;
  loading: boolean;
}) {
  const chosen = new Set(slots.map((s) => s.player_id).filter(Boolean) as number[]);
  const step = !team ? 1 : !formation ? 2 : 3;

  function handleTeamChange(value: string) {
    setTeam(value);
    if (!value) {
      setFormation("");
      setSlots([]);
    }
  }

  function handleFormationChange(value: string) {
    setFormation(value);
    if (value) {
      setSlots(remap(slots.length ? slots : slotsFor(value), value));
    } else {
      setSlots([]);
    }
  }

  return (
    <div className="card p-4" data-testid={`team-col-${side}`}>
      <select
        value={team}
        onChange={(e) => handleTeamChange(e.target.value)}
        className="select w-full font-bold"
        data-testid={`team-select-${side}`}
      >
        <option value="">Select team…</option>
        {teams.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <FadeIn show={step >= 2}>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-faint">Formation</span>
          <select
            value={formation}
            onChange={(e) => handleFormationChange(e.target.value)}
            className="select flex-1"
            data-testid={`formation-select-${side}`}
          >
            <option value="">Choose formation…</option>
            {Object.keys(FORMATIONS).map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
      </FadeIn>

      <FadeIn show={step >= 3}>
        <div className="mt-3 flex justify-end">
          <button
            className="btn-ghost"
            data-testid={`autopick-${side}`}
            disabled={!players.length || loading}
            onClick={() => setSlots(autoFill(players, slots))}
          >
            Auto-pick XI
          </button>
        </div>

        {loading ? (
          <div className="mt-4 space-y-1.5">
            {Array.from({ length: 11 }).map((_, idx) => (
              <Skeleton key={idx} className="h-9" />
            ))}
          </div>
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
                    <option value="">— select —</option>
                    {opts.map((p) => (
                      <option
                        key={p.player_id}
                        value={p.player_id}
                        disabled={chosen.has(p.player_id) && p.player_id !== s.player_id}
                      >
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
      </FadeIn>
    </div>
  );
}

function PredictContent() {
  const searchParams = useSearchParams();
  const urlLoaded = useRef(false);
  const autoRan = useRef(false);

  const [teams, setTeams] = useState<string[]>([]);
  const [formationA, setFormationA] = useState("");
  const [formationB, setFormationB] = useState("");
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [playersA, setPlayersA] = useState<Player[]>([]);
  const [playersB, setPlayersB] = useState<Player[]>([]);
  const [loadA, setLoadA] = useState(false);
  const [loadB, setLoadB] = useState(false);
  const [slotsA, setSlotsA] = useState<Slot[]>([]);
  const [slotsB, setSlotsB] = useState<Slot[]>([]);
  const [homeSide, setHomeSide] = useState<"a" | "b" | "none">("none");
  const [predictModel, setPredictModel] = useState<PredictModel>("all");
  const [mobileTab, setMobileTab] = useState<"a" | "b">("a");
  const [result, setResult] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeams(o.teams.map((t) => t.team_name).sort((a, b) => a.localeCompare(b)))
    );
  }, []);

  useEffect(() => {
    if (urlLoaded.current) return;
    const parsed = parsePredictUrl(searchParams);
    if (parsed.teamA) setTeamA(parsed.teamA);
    if (parsed.teamB) setTeamB(parsed.teamB);
    if (parsed.formationA) setFormationA(parsed.formationA);
    if (parsed.formationB) setFormationB(parsed.formationB);
    if (parsed.homeAdvantage) setHomeSide(parsed.homeAdvantage);
    urlLoaded.current = true;
  }, [searchParams]);

  useEffect(() => {
    if (!teamA) {
      setPlayersA([]);
      return;
    }
    setLoadA(true);
    api.teamPlayers(teamA).then((r) => {
      setPlayersA(r.players);
      setLoadA(false);
      const parsed = parsePredictUrl(searchParams);
      if (parsed.playersA?.length && parsed.formationA) {
        const slots = slotsFor(parsed.formationA);
        parsed.playersA.forEach((id, i) => {
          if (i < slots.length) slots[i].player_id = id;
        });
        setSlotsA(slots);
      }
    });
  }, [teamA]); // eslint-disable-line

  useEffect(() => {
    if (!teamB) {
      setPlayersB([]);
      return;
    }
    setLoadB(true);
    api.teamPlayers(teamB).then((r) => {
      setPlayersB(r.players);
      setLoadB(false);
      const parsed = parsePredictUrl(searchParams);
      if (parsed.playersB?.length && parsed.formationB) {
        const slots = slotsFor(parsed.formationB);
        parsed.playersB.forEach((id, i) => {
          if (i < slots.length) slots[i].player_id = id;
        });
        setSlotsB(slots);
      }
    });
  }, [teamB]); // eslint-disable-line

  useEffect(() => {
    if (formationA) setSlotsA((prev) => remap(prev.length ? prev : slotsFor(formationA), formationA));
  }, [formationA]);

  useEffect(() => {
    if (formationB) setSlotsB((prev) => remap(prev.length ? prev : slotsFor(formationB), formationB));
  }, [formationB]);

  const ready =
    teamA &&
    teamB &&
    teamA !== teamB &&
    formationA &&
    formationB &&
    slotsA.every((s) => s.player_id) &&
    slotsB.every((s) => s.player_id);

  const shareUrl = useCallback(() => {
    if (typeof window === "undefined") return "";
    const path = buildPredictUrl({
      teamA,
      teamB,
      formationA,
      formationB,
      playersA: slotsA.map((s) => s.player_id).filter(Boolean) as number[],
      playersB: slotsB.map((s) => s.player_id).filter(Boolean) as number[],
      homeAdvantage: homeSide,
    });
    return `${window.location.origin}${path}`;
  }, [teamA, teamB, formationA, formationB, slotsA, slotsB, homeSide]);

  const runPredict = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: {
        team_a: { team_name: string; home: boolean; players: { player_id: number | null; role: Role }[] };
        team_b: { team_name: string; home: boolean; players: { player_id: number | null; role: Role }[] };
        model?: string;
      } = {
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
      if (predictModel !== "all") {
        body.model = predictModel;
      }
      setResult(await api.predict(body));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }, [teamA, teamB, homeSide, slotsA, slotsB, predictModel]);

  useEffect(() => {
    if (autoRan.current || !ready) return;
    const parsed = parsePredictUrl(searchParams);
    if (parsed.playersA?.length && parsed.playersB?.length) {
      autoRan.current = true;
      runPredict();
    }
  }, [ready, searchParams, runPredict]);

  const slotsAFull = slotsA.length > 0 && slotsA.every((s) => s.player_id);
  const slotsBFull = slotsB.length > 0 && slotsB.every((s) => s.player_id);

  const colA = (
    <TeamColumn
      side="a"
      teams={teams}
      team={teamA}
      setTeam={setTeamA}
      formation={formationA}
      setFormation={setFormationA}
      players={playersA}
      slots={slotsA}
      setSlots={setSlotsA}
      loading={loadA}
    />
  );
  const colB = (
    <TeamColumn
      side="b"
      teams={teams}
      team={teamB}
      setTeam={setTeamB}
      formation={formationB}
      setFormation={setFormationB}
      players={playersB}
      slots={slotsB}
      setSlots={setSlotsB}
      loading={loadB}
    />
  );

  return (
    <div className="space-y-6">
      <WinnerProbabilityChart />

      <div>
        <h1 className="text-2xl font-black text-fg">Match Predictor</h1>
        <p className="text-sm text-muted">
          Pick two teams, choose a formation for each, build your XI, and the engine predicts the
          result from tournament form.
        </p>
      </div>

      <PredictorHintBar
        teamA={teamA}
        teamB={teamB}
        formationA={formationA}
        formationB={formationB}
        slotsAFull={slotsAFull}
        slotsBFull={slotsBFull}
      />

      <div className="md:hidden">
        <div className="mb-3 flex gap-2">
          {(["a", "b"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setMobileTab(tab)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                mobileTab === tab ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-fg-soft"
              }`}
            >
              {tab === "a" ? teamA || "Team A" : teamB || "Team B"}
            </button>
          ))}
        </div>
        {mobileTab === "a" ? colA : colB}
      </div>

      <div className="hidden gap-4 md:grid md:grid-cols-2">
        {colA}
        {colB}
      </div>

      <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex flex-wrap items-center gap-4">
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
          <div className="flex items-center gap-2 text-sm">
            <label htmlFor="predict-model" className="text-faint">
              Model
            </label>
            <select
              id="predict-model"
              value={predictModel}
              onChange={(e) => setPredictModel(e.target.value as PredictModel)}
              className="select min-w-[11rem]"
              data-testid="predict-model-select"
            >
              {PREDICT_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
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
      {result && <PredictionResult p={result} shareUrl={shareUrl()} />}
    </div>
  );
}

export default function Predict() {
  return (
    <Suspense fallback={<div className="card p-8 text-faint">Loading predictor…</div>}>
      <PredictContent />
    </Suspense>
  );
}
