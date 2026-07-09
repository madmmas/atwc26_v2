type PredictUrlState = {
  teamA: string;
  teamB: string;
  formationA: string;
  formationB: string;
  playersA: number[];
  playersB: number[];
  homeAdvantage: "a" | "b" | "none";
};

export function buildPredictUrl(state: PredictUrlState): string {
  const params = new URLSearchParams();
  params.set("teamA", state.teamA);
  params.set("teamB", state.teamB);
  if (state.formationA) params.set("formationA", state.formationA);
  if (state.formationB) params.set("formationB", state.formationB);
  if (state.playersA.length) params.set("playersA", state.playersA.join(","));
  if (state.playersB.length) params.set("playersB", state.playersB.join(","));
  if (state.homeAdvantage !== "none") {
    params.set("homeAdvantage", state.homeAdvantage === "a" ? "A" : "B");
  }
  return `/predict?${params.toString()}`;
}

export function parsePredictUrl(params: URLSearchParams): Partial<PredictUrlState> {
  const home = params.get("homeAdvantage");
  return {
    teamA: params.get("teamA") ?? "",
    teamB: params.get("teamB") ?? "",
    formationA: params.get("formationA") ?? "",
    formationB: params.get("formationB") ?? "",
    playersA: (params.get("playersA") ?? "")
      .split(",")
      .map((x) => Number(x))
      .filter((n) => Number.isFinite(n) && n > 0),
    playersB: (params.get("playersB") ?? "")
      .split(",")
      .map((x) => Number(x))
      .filter((n) => Number.isFinite(n) && n > 0),
    homeAdvantage: home === "A" ? "a" : home === "B" ? "b" : "none",
  };
}

export function buildSimplePredictUrl(home: string, away: string): string {
  return buildPredictUrl({
    teamA: home,
    teamB: away,
    formationA: "",
    formationB: "",
    playersA: [],
    playersB: [],
    homeAdvantage: "none",
  });
}

export function buildPredictorMatchUrl(home: string, away: string): string {
  return `${buildSimplePredictUrl(home, away)}&tab=predictor`;
}
