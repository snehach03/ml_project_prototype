import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty } from "./ui.jsx";

const AXIS = { stroke: "#64748b", fontSize: 11 };
const TOOLTIP = {
  contentStyle: { background: "#0b1120", border: "1px solid #1b2740", borderRadius: 12, fontSize: 12 },
  labelStyle: { color: "#94a3b8" },
};

/** kind: 'line' | 'area' | 'bar'. series: [{key, name, color}] */
export function TimeSeries({ data, series, kind = "line", xKey = "minute", height = 220, yDomain, band }) {
  if (!data || data.length === 0) return <Empty>No data yet. Start a monitoring session on the Live tab.</Empty>;
  const common = { data, margin: { top: 8, right: 12, left: -8, bottom: 0 } };
  const grid = <CartesianGrid stroke="#1b2740" strokeDasharray="3 3" />;
  const axes = (
    <>
      <XAxis dataKey={xKey} {...AXIS} tickLine={false} />
      <YAxis {...AXIS} tickLine={false} axisLine={false} domain={yDomain} width={52} />
      <Tooltip {...TOOLTIP} />
      {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />}
    </>
  );
  let chart;
  if (kind === "bar") {
    chart = (
      <BarChart {...common}>
        {grid}{axes}
        {series.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} />)}
      </BarChart>
    );
  } else if (kind === "area") {
    chart = (
      <AreaChart {...common}>
        {grid}{axes}
        {series.map((s) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} fill={s.color} fillOpacity={0.15} strokeWidth={2} />)}
      </AreaChart>
    );
  } else {
    chart = (
      <LineChart {...common}>
        {grid}{axes}
        {band && <ReferenceArea y1={band[0]} y2={band[1]} fill="#64748b" fillOpacity={0.12} />}
        {series.map((s) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={false} connectNulls />)}
      </LineChart>
    );
  }
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>{chart}</ResponsiveContainer>
    </div>
  );
}
