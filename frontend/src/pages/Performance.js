import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

function KPICard({ label, value, color = "#e0e8ff", sub }) {
  return (
    <div className="p-3" style={{ border: "1px solid #1a2040", background: "#0f1423" }}>
      <div className="text-[10px] uppercase tracking-widest text-[#8a9bc2] mb-1">{label}</div>
      <div className="text-lg font-bold tabular-nums" style={{ color }}>{value}</div>
      {sub && <div className="text-[10px] text-[#8a9bc2] mt-0.5">{sub}</div>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    const pnl = payload[0]?.value;
    return (
      <div style={{ background: "#0f1423", border: "1px solid #1a2040", padding: "8px 12px", fontFamily: "JetBrains Mono, monospace" }}>
        <p className="text-[10px] text-[#8a9bc2]">{label}</p>
        <p className="text-xs" style={{ color: pnl >= 0 ? "#00ff88" : "#ff3366" }}>
          PNL: {pnl >= 0 ? "+" : ""}{(pnl || 0).toFixed(2)} USDT
        </p>
      </div>
    );
  }
  return null;
};

export default function Performance() {
  const [stats, setStats] = useState(null);
  const [equity, setEquity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("all");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, equityRes] = await Promise.all([
        axios.get(`${API}/performance`, { withCredentials: true }),
        axios.get(`${API}/performance/equity`, { withCredentials: true }),
      ]);
      setStats(statsRes.data);
      setEquity(equityRes.data);
    } catch (_) {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) return <Layout><div className="flex items-center justify-center h-full text-[#8a9bc2] text-xs">Loading...</div></Layout>;

  const netPnl = stats?.net_pnl || 0;
  const winRate = stats?.win_rate || 0;
  const totalTrades = stats?.total_trades || 0;
  const wins = stats?.wins || 0;
  const losses = stats?.losses || 0;
  const avgHold = Math.round(stats?.avg_hold_minutes || 0);
  const avgHoldStr = avgHold < 60 ? `${avgHold}m` : `${Math.floor(avgHold / 60)}h ${avgHold % 60}m`;

  // Exchange breakdown for bar chart
  const summaries = stats?.summaries || [];
  const byExchange = summaries.reduce((acc, s) => {
    const k = s.exchange || "demo";
    if (!acc[k]) acc[k] = { exchange: k, wins: 0, losses: 0, net_pnl: 0 };
    acc[k].wins += s.wins || 0;
    acc[k].losses += s.losses || 0;
    acc[k].net_pnl += s.net_pnl || 0;
    return acc;
  }, {});
  const exchData = Object.values(byExchange);

  // Equity chart - sample every 5 trades if too many
  const equityData = equity.slice(-100).map((e, i) => ({
    i: i + 1,
    pnl: e.pnl,
    date: e.date ? e.date.substring(0, 10) : "",
  }));

  return (
    <Layout>
      <div className="h-full overflow-y-auto p-3">
        {/* Period selector */}
        <div className="flex items-center gap-2 mb-3">
          {["all", "month", "week"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              data-testid={`period-${p}`}
              className={`px-3 py-1 text-[11px] transition-all ${period === p ? "tab-active" : "tab-inactive"}`}
            >
              {p.toUpperCase()}
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={fetchData} className="text-[10px] btn-primary px-2 py-1">REFRESH</button>
        </div>

        {/* KPI Grid */}
        <div className="grid grid-cols-5 gap-1 mb-3">
          <KPICard label="WIN RATE" value={`${winRate}%`} color={winRate >= 50 ? "#00ff88" : "#ff3366"} sub={`${wins}W / ${losses}L`} />
          <KPICard label="NET PNL" value={`${netPnl >= 0 ? "+" : ""}${netPnl.toFixed(2)}`} color={netPnl >= 0 ? "#00ff88" : "#ff3366"} sub="USDT" />
          <KPICard label="TOTAL TRADES" value={totalTrades} color="#00d4ff" />
          <KPICard label="AVG HOLD" value={avgHoldStr} color="#e0e8ff" />
          <KPICard label="ACTIVE" value={stats?.active_positions || 0} color="#ffaa00" sub="positions" />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-2 gap-2">
          {/* Equity curve */}
          <div style={{ border: "1px solid #1a2040", background: "#0f1423", padding: "1rem" }}>
            <div className="text-[10px] uppercase tracking-widest text-[#8a9bc2] mb-3">EQUITY CURVE</div>
            {equityData.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={equityData}>
                  <CartesianGrid stroke="#1a2040" strokeDasharray="3 3" />
                  <XAxis dataKey="i" stroke="#8a9bc2" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                  <YAxis stroke="#8a9bc2" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="pnl" stroke="#00d4ff" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-48 text-[#1a2040] text-xs">No data yet</div>
            )}
          </div>

          {/* Win/Loss by exchange */}
          <div style={{ border: "1px solid #1a2040", background: "#0f1423", padding: "1rem" }}>
            <div className="text-[10px] uppercase tracking-widest text-[#8a9bc2] mb-3">BY EXCHANGE</div>
            {exchData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={exchData}>
                  <CartesianGrid stroke="#1a2040" strokeDasharray="3 3" />
                  <XAxis dataKey="exchange" stroke="#8a9bc2" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                  <YAxis stroke="#8a9bc2" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="wins" fill="#00ff88" maxBarSize={30} />
                  <Bar dataKey="losses" fill="#ff3366" maxBarSize={30} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-48 text-[#1a2040] text-xs">No data yet</div>
            )}
          </div>
        </div>

        {/* Performance table */}
        {summaries.length > 0 && (
          <div className="mt-2" style={{ border: "1px solid #1a2040", background: "#0f1423" }}>
            <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#8a9bc2]" style={{ borderBottom: "1px solid #1a2040" }}>
              BREAKDOWN
            </div>
            <table className="w-full">
              <thead>
                <tr style={{ borderBottom: "1px solid #1a2040" }}>
                  {["Period", "Exchange", "Mode", "Trades", "Wins", "WR%", "PNL"].map((h) => (
                    <th key={h} className="px-3 py-1.5 text-left text-[10px] text-[#8a9bc2] font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summaries.map((s, i) => (
                  <tr key={i} className="hover:bg-[#171d30] transition-all" style={{ borderBottom: "1px solid #1a2040" }}>
                    <td className="px-3 py-1.5 text-xs tabular-nums">{s.period}</td>
                    <td className="px-3 py-1.5 text-xs">{s.exchange}</td>
                    <td className="px-3 py-1.5 text-xs">{s.trading_mode}</td>
                    <td className="px-3 py-1.5 text-xs tabular-nums">{s.total_trades}</td>
                    <td className="px-3 py-1.5 text-xs tabular-nums text-[#00ff88]">{s.wins}</td>
                    <td className="px-3 py-1.5 text-xs tabular-nums">{s.win_rate?.toFixed(1)}%</td>
                    <td className={`px-3 py-1.5 text-xs tabular-nums font-bold ${(s.net_pnl || 0) >= 0 ? "text-[#00ff88]" : "text-[#ff3366]"}`}>
                      {(s.net_pnl || 0) >= 0 ? "+" : ""}{(s.net_pnl || 0).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}
