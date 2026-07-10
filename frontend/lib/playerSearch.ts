import { api, Player } from "@/lib/api";

const PAGE = 200;

type FetchAllOptions = {
  fields?: "full" | "slim";
  force?: boolean;
};

let cachedFull: Promise<Player[]> | null = null;
let cachedSlim: Promise<Player[]> | null = null;

async function fetchAllPlayersUncached(fields: "full" | "slim"): Promise<Player[]> {
  const all: Player[] = [];
  let cursor: string | null = null;
  for (;;) {
    const q = new URLSearchParams({
      sort: "minutes",
      dir: "desc",
      limit: String(PAGE),
      fields,
    });
    if (cursor) q.set("cursor", cursor);
    const data = await api.players(q.toString());
    all.push(...data.players);
    if (!data.next_cursor) break;
    cursor = data.next_cursor;
  }
  return all;
}

/** Load every player once per session; subsequent calls reuse the in-flight/cached promise. */
export async function fetchAllPlayers(opts: FetchAllOptions = {}): Promise<Player[]> {
  const fields = opts.fields ?? "full";
  if (opts.force) {
    if (fields === "full") cachedFull = null;
    else cachedSlim = null;
  }
  if (fields === "full") {
    if (!cachedFull) cachedFull = fetchAllPlayersUncached("full");
    return cachedFull;
  }
  if (!cachedSlim) cachedSlim = fetchAllPlayersUncached("slim");
  return cachedSlim;
}

/** Drop the module cache (useful after a known ETL refresh). */
export function clearPlayerSearchCache(): void {
  cachedFull = null;
  cachedSlim = null;
}

export function matchPlayerName(name: string, query: string): boolean {
  return name.toLowerCase().includes(query.toLowerCase());
}
