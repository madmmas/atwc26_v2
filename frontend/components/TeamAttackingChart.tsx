"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Label,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const XG_COLOR = "#F5A623";
const XGA_COLOR = "#1D9E75";

type ChartRow = { name: string; xG: number; xGA: number };

export function TeamAttackingChart({ data, width }: { data: ChartRow[]; width: number }) {
  return (
    <div className="card relative overflow-x-auto p-4">
      <div
        className="absolute right-6 top-6 z-10 flex items-center gap-4 text-[11px] text-[#888]"
        aria-label="Chart legend"
      >
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: XG_COLOR }} />
          xG (attacking)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: XGA_COLOR }} />
          xGA (defensive)
        </span>
      </div>
      <div style={{ width, height: 340 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 36, right: 8, bottom: 56, left: 4 }}>
            <CartesianGrid stroke="#94a3b8" strokeOpacity={0.18} vertical={false} />
            <XAxis
              dataKey="name"
              angle={-45}
              textAnchor="end"
              interval={0}
              height={70}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
            />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }}>
              <Label
                value="per game"
                angle={-90}
                position="insideLeft"
                offset={12}
                style={{ fill: "#555", fontSize: 10, textAnchor: "middle" }}
              />
            </YAxis>
            <Tooltip
              cursor={{ fill: "#94a3b8", fillOpacity: 0.1 }}
              contentStyle={{
                background: "rgb(var(--card))",
                border: "1px solid rgb(var(--edge))",
                borderRadius: 12,
                color: "rgb(var(--fg))",
              }}
              labelStyle={{ color: "rgb(var(--fg))" }}
            />
            <Bar dataKey="xG" name="xG (attacking)" fill={XG_COLOR} radius={[4, 4, 0, 0]} />
            <Bar dataKey="xGA" name="xGA (defensive)" fill={XGA_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
