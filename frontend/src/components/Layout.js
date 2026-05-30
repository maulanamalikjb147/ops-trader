import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import useStore from "@/store/useStore";

function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="text-[#00d4ff] tabular-nums text-xs">
      {time.toLocaleTimeString("en-GB")} UTC
    </span>
  );
}

const NAV_ITEMS = [
  { path: "/", label: "DASHBOARD" },
  { path: "/signals", label: "SIGNALS" },
  { path: "/performance", label: "PERFORMANCE" },
  { path: "/settings", label: "SETTINGS" },
];

export default function Layout({ children }) {
  const location = useLocation();
  const { user, logout, botStatus, wsConnected, stats, fetchStats } = useStore();

  useEffect(() => {
    fetchStats();
    const t = setInterval(fetchStats, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "#0a0e1a", color: "#e0e8ff" }}>
      {/* Top Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040", background: "#0f1423" }}>
        <div className="flex items-center gap-4">
          <span className="text-[#00d4ff] font-bold text-sm tracking-[0.15em]">SIGNAL BOT</span>
          <span className="text-[10px] text-[#8a9bc2]">|</span>
          <span className="text-[10px] text-[#8a9bc2] uppercase tracking-widest">Trading System</span>
        </div>
        <div className="flex items-center gap-4">
          <Clock />
          {/* WS indicator */}
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-[#00ff88] pulse" : "bg-[#ff3366]"}`} />
            <span className="text-[10px] text-[#8a9bc2]">{wsConnected ? "LIVE" : "OFFLINE"}</span>
          </div>
          {/* Bot status */}
          <div className="flex items-center gap-1">
            <span className={`text-[10px] ${botStatus.is_paused ? "text-[#ff3366]" : "text-[#00ff88]"}`}>
              {botStatus.is_paused ? "PAUSED" : "SCANNING"}
            </span>
          </div>
          {user && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-[#8a9bc2]">{user.username?.toUpperCase()}</span>
              <button
                onClick={logout}
                data-testid="logout-btn"
                className="text-[10px] text-[#ff3366] px-2 py-0.5 transition-all hover:bg-[rgba(255,51,102,0.1)]"
                style={{ border: "1px solid #ff3366" }}
              >
                LOGOUT
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Nav Tabs */}
      <div className="flex items-center px-3 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040", background: "#0f1423" }}>
        {NAV_ITEMS.map((item) => {
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={`px-4 py-2 text-xs font-medium tracking-wider transition-all ${active ? "tab-active" : "tab-inactive hover:text-[#e0e8ff]"}`}
            >
              {item.label}
            </Link>
          );
        })}
        <div className="flex-1" />
        {/* Stats bar */}
        <div className="flex items-center gap-4 text-xs">
          <StatItem label="TODAY" value={`${stats.today_signals || 0} SIG`} color="#00d4ff" />
          <StatItem label="WIN RATE" value={`${stats.win_rate || 0}%`} color="#00ff88" />
          <StatItem label="PNL" value={`${(stats.today_pnl || 0) >= 0 ? "+" : ""}${(stats.today_pnl || 0).toFixed(2)} USDT`} color={(stats.today_pnl || 0) >= 0 ? "#00ff88" : "#ff3366"} />
          <StatItem label="OPEN" value={`${stats.open_positions || 0} POS`} color="#ffaa00" />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {children}
      </div>
    </div>
  );
}

function StatItem({ label, value, color }) {
  return (
    <div className="flex items-center gap-1.5 px-2">
      <span className="text-[#8a9bc2] text-[10px] uppercase tracking-widest">{label}:</span>
      <span className="text-[10px] font-semibold tabular-nums" style={{ color }}>{value}</span>
    </div>
  );
}
