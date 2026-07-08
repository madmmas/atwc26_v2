export type StatDefinition = {
  label: string;
  definition: string;
  unit?: string;
};

export const STAT_DEFINITIONS: Record<string, StatDefinition> = {
  xG: {
    label: "Expected Goals",
    definition: "Quality of chances — likelihood a shot becomes a goal.",
    unit: "per 90 mins",
  },
  xA: {
    label: "Expected Assists",
    definition: "Likelihood a pass leads to an assist.",
    unit: "per 90 mins",
  },
  xGA: {
    label: "Expected Goals Against",
    definition: "Quality of chances a team conceded.",
    unit: "per game",
  },
  xGI: {
    label: "Expected Goal Involvement",
    definition: "Expected goals plus expected assists combined.",
    unit: "per 90 mins",
  },
  SOT: {
    label: "Shots on Target",
    definition: "Shots that would score without a save or block.",
    unit: "total",
  },
  "Big Ch.": {
    label: "Big Chances Created",
    definition: "Passes that set up a clear scoring opportunity.",
    unit: "total",
  },
  TCH: {
    label: "Touches",
    definition: "Total times a player touched the ball.",
    unit: "total",
  },
  "Pass%": {
    label: "Pass Completion",
    definition: "Share of attempted passes that were completed.",
    unit: "%",
  },
  DUELW: {
    label: "Duels Won",
    definition: "1v1 ground and aerial contests won.",
    unit: "total",
  },
  DINT: {
    label: "Defensive Interventions",
    definition: "Tackles, interceptions, clearances and blocks combined.",
    unit: "total",
  },
  CLR: {
    label: "Clearances",
    definition: "Defensive actions clearing the ball from danger.",
    unit: "total",
  },
  MINS: {
    label: "Minutes Played",
    definition: "Total minutes played in the tournament.",
    unit: "mins",
  },
  "xG±": {
    label: "xG Balance",
    definition: "Expected goals scored minus expected goals conceded. Positive = creating more than conceding.",
    unit: "total",
  },
  Min: {
    label: "Minutes Played",
    definition: "Total minutes played in the tournament.",
    unit: "mins",
  },
  G: {
    label: "Goals",
    definition: "Goals scored.",
    unit: "total",
  },
  A: {
    label: "Assists",
    definition: "Assists provided.",
    unit: "total",
  },
  Shots: {
    label: "Shots",
    definition: "Total shots attempted.",
    unit: "total",
  },
  Passes: {
    label: "Passes",
    definition: "Total passes attempted.",
    unit: "total",
  },
  Goals: {
    label: "Goals",
    definition: "Goals scored in the tournament.",
    unit: "total",
  },
  "xG / 90": {
    label: "Expected Goals per 90",
    definition: "Quality of chances — likelihood a shot becomes a goal.",
    unit: "per 90 mins",
  },
  "xA / 90": {
    label: "Expected Assists per 90",
    definition: "Likelihood a pass leads to an assist.",
    unit: "per 90 mins",
  },
  "Shots / 90": {
    label: "Shots per 90",
    definition: "Shot attempts scaled to a full match.",
    unit: "per 90 mins",
  },
  "Duels won / 90": {
    label: "Duels Won per 90",
    definition: "1v1 ground and aerial contests won.",
    unit: "per 90 mins",
  },
  "Def. actions / 90": {
    label: "Defensive Actions per 90",
    definition: "Tackles, interceptions, clearances and blocks combined.",
    unit: "per 90 mins",
  },
  Minutes: {
    label: "Minutes Played",
    definition: "Total minutes played in the tournament.",
    unit: "mins",
  },
};
