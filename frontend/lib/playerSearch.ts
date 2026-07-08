import { api, Player } from "@/lib/api";

const PAGE = 200;

export async function fetchAllPlayers(): Promise<Player[]> {
  const all: Player[] = [];
  let cursor: string | null = null;
  for (;;) {
    const q = new URLSearchParams({
      sort: "minutes",
      dir: "desc",
      limit: String(PAGE),
      fields: "slim",
    });
    if (cursor) q.set("cursor", cursor);
    const data = await api.players(q.toString());
    all.push(...data.players);
    if (!data.next_cursor) break;
    cursor = data.next_cursor;
  }
  return all;
}

export function matchPlayerName(name: string, query: string): boolean {
  return name.toLowerCase().includes(query.toLowerCase());
}
