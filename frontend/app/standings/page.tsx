"use client";
import { useEffect, useState } from "react";
import { api, GroupStandings } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { GroupTable } from "@/components/GroupTable";

export default function Standings() {
  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);

  useEffect(() => {
    api.standings().then((r) => setGroups(r.groups));
  }, []);

  if (!groups) return <Spinner label="Loading standings…" />;

  const names = Object.keys(groups).sort();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Group Standings</h1>
        <p className="text-sm text-muted">
          Real group tables from every played match. Try a score for the remaining
          fixture(s) below any group to see how the table would change — predictions
          aren't saved, reload to reset.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {names.map((name) => (
          <GroupTable key={name} name={name} group={groups[name]} />
        ))}
      </div>
    </div>
  );
}
