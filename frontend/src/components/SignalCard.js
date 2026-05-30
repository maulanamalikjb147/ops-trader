function fmt(n, d = 4) {
  if (n == null) return "--";
  return (typeof n === "string" ? parseFloat(n) : n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

const EXCHANGE_COLORS = {
  demo: "#8a9bc2",
  binance: "#f0b90b",
  bybit: "#00d4ff",
  okx: "#ff6b00",
  bitget: "#9b59b6",
  bybit_testnet: "#8a9bc2",
};

const MODE_LABELS = { swing: "SWING", scalp: "SCALP", hybrid: "HYBRID" };

export default function SignalCard({ signal, compact = false }) {
  const isLong = signal.side === "LONG";
  const isClosed = signal.status === "closed";
  const isWin = isClosed && signal.close_reason && !signal.close_reason.includes("SL");
  const exColor = EXCHANGE_COLORS[signal.exchange] || "#8a9bc2";

  return (
    <div
      data-testid={`signal-card-${signal.id}`}
      className="fade-in"
      style={{
        border: `1px solid ${isClosed ? (isWin ? "rgba(0,255,136,0.2)" : "rgba(255,51,102,0.2)") : "#1a2040"}`,
        background: "#0f1423",
        padding: "0.625rem 0.75rem",
      }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold ${isLong ? "text-[#00ff88]" : "text-[#ff3366]"}`}>
            {isLong ? "▲" : "▼"} {signal.pair}
          </span>
          <span className="text-[10px] px-1" style={{ border: `1px solid ${exColor}`, color: exColor }}>
            {(signal.exchange || "demo").toUpperCase()}
          </span>
          <span className="text-[10px] px-1 text-[#8a9bc2]" style={{ border: "1px solid #1a2040" }}>
            {MODE_LABELS[signal.trading_mode] || signal.trading_mode?.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isClosed ? (
            <span className={`text-[10px] font-bold ${isWin ? "text-[#00ff88]" : "text-[#ff3366]"}`}>
              {signal.close_reason}
            </span>
          ) : (
            <span className="text-[10px] text-[#00d4ff]">OPEN</span>
          )}
          <span className="text-[10px] text-[#8a9bc2]">{signal.confidence}</span>
        </div>
      </div>

      {/* Price row */}
      <div className="grid grid-cols-4 gap-1.5 text-[11px]">
        <div>
          <div className="text-[#8a9bc2] text-[9px]">ENTRY</div>
          <div className="tabular-nums">${fmt(signal.entry_price)}</div>
        </div>
        <div>
          <div className="text-[#8a9bc2] text-[9px]">TP1</div>
          <div className="tabular-nums text-[#00ff88]">${fmt(signal.tp1)}</div>
        </div>
        <div>
          <div className="text-[#8a9bc2] text-[9px]">TP2</div>
          <div className="tabular-nums text-[#00ff88]">${fmt(signal.tp2)}</div>
        </div>
        <div>
          <div className="text-[#8a9bc2] text-[9px]">SL</div>
          <div className="tabular-nums text-[#ff3366]">${fmt(signal.sl)}</div>
        </div>
      </div>

      {/* Margin/Leverage */}
      <div className="flex gap-3 mt-1.5 text-[10px] text-[#8a9bc2]">
        <span>RR: <span className="text-[#e0e8ff]">{signal.rr_ratio}</span></span>
        <span>Margin: <span className="text-[#e0e8ff]">${fmt(signal.margin, 2)}</span></span>
        <span>Lev: <span className="text-[#00d4ff]">{signal.leverage}x</span></span>
        <span className="ml-auto">{new Date(signal.created_at).toLocaleString("en-GB", { hour12: false, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
      </div>
    </div>
  );
}
