import { useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fmt(n, decimals = 4) {
  if (n == null) return "--";
  const v = typeof n === "string" ? parseFloat(n) : n;
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function PnlDisplay({ pnl, pct }) {
  const isProfit = pnl >= 0;
  return (
    <div className={`text-sm font-bold tabular-nums ${isProfit ? "text-[#00ff88]" : "text-[#ff3366]"}`}>
      {isProfit ? "+" : ""}{fmt(pnl, 2)} USDT
      <span className="text-xs ml-1 font-normal">({pct >= 0 ? "+" : ""}{fmt(pct, 2)}%)</span>
    </div>
  );
}

export default function PositionCard({ position, onAction }) {
  const [showModify, setShowModify] = useState(false);
  const [tpPrice, setTpPrice] = useState("");
  const [slPrice, setSlPrice] = useState("");
  const [loading, setLoading] = useState(null);

  const id = position.id;
  const pnl = position.pnl_usd || 0;
  const pct = position.pnl_pct || 0;
  const isLong = position.side === "LONG";
  const exchangeTag = (position.exchange || "demo").toUpperCase();

  const action = async (type, body = {}) => {
    setLoading(type);
    try {
      await axios.post(`${API}/signals/${id}/${type}`, body, { withCredentials: true });
      onAction?.();
    } catch (err) {
      console.error(type, err);
    } finally {
      setLoading(null);
      setShowModify(false);
    }
  };

  return (
    <div
      data-testid={`position-card-${position.pair?.replace("/", "-")}`}
      className="fade-in"
      style={{ border: "1px solid #1a2040", background: "#0f1423", marginBottom: "1px" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold ${isLong ? "text-[#00ff88]" : "text-[#ff3366]"}`}>
            {isLong ? "▲" : "▼"} {position.pair}
          </span>
          <span className="text-[10px] px-1 text-[#8a9bc2]" style={{ border: "1px solid #1a2040" }}>{exchangeTag}</span>
          <span className={`text-[10px] px-1 ${isLong ? "text-[#00ff88]" : "text-[#ff3366]"}`} style={{ border: `1px solid ${isLong ? "#00ff88" : "#ff3366"}` }}>
            {position.side}
          </span>
        </div>
        <PnlDisplay pnl={pnl} pct={pct} />
      </div>

      {/* Price info */}
      <div className="px-3 pb-2 grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-[#8a9bc2] text-[10px]">ENTRY</div>
          <div className="tabular-nums">${fmt(position.entry_price)}</div>
        </div>
        <div>
          <div className="text-[#8a9bc2] text-[10px]">CURRENT</div>
          <div className="tabular-nums text-[#00d4ff]">${fmt(position.current_price)}</div>
        </div>
        <div>
          <div className="text-[#8a9bc2] text-[10px]">TP2 / SL</div>
          <div className="tabular-nums text-[10px]">
            <span className="text-[#00ff88]">{fmt(position.tp2, 2)}</span>
            {" / "}
            <span className="text-[#ff3366]">{fmt(position.sl, 2)}</span>
          </div>
        </div>
      </div>

      {/* Margin/Leverage info */}
      <div className="px-3 pb-2 flex gap-3 text-[10px] text-[#8a9bc2]">
        <span>Margin: <span className="text-[#e0e8ff]">${fmt(position.margin, 2)}</span></span>
        <span>Lev: <span className="text-[#00d4ff]">{position.leverage}x</span></span>
      </div>

      {/* Action buttons */}
      <div className="flex gap-1 px-3 pb-2 flex-wrap">
        <button
          data-testid={`close-position-btn-${position.pair?.replace("/", "-")}`}
          onClick={() => action("close")}
          disabled={loading === "close"}
          className="btn-danger text-[10px] px-2 py-1 transition-all"
        >
          {loading === "close" ? "..." : "CLOSE"}
        </button>
        <button
          data-testid={`set-tp-btn-${position.pair?.replace("/", "-")}`}
          onClick={() => setShowModify(showModify === "tp" ? null : "tp")}
          className="btn-primary text-[10px] px-2 py-1 transition-all"
        >
          INST TP
        </button>
        <button
          data-testid={`set-sl-btn-${position.pair?.replace("/", "-")}`}
          onClick={() => setShowModify(showModify === "sl" ? null : "sl")}
          className="btn-warning text-[10px] px-2 py-1 transition-all"
        >
          INST SL
        </button>
        <button
          data-testid={`set-bep-btn-${position.pair?.replace("/", "-")}`}
          onClick={() => action("set-bep")}
          disabled={loading === "set-bep" || position.bep_activated}
          className={`text-[10px] px-2 py-1 transition-all ${position.bep_activated ? "opacity-50" : "btn-success"}`}
        >
          {position.bep_activated ? "BEP ON" : (loading === "set-bep" ? "..." : "SL->BEP")}
        </button>
      </div>

      {/* Modify TP panel */}
      {showModify === "tp" && (
        <div className="px-3 pb-2 flex gap-2 fade-in" style={{ borderTop: "1px solid #1a2040" }}>
          <input
            type="number"
            value={tpPrice}
            onChange={(e) => setTpPrice(e.target.value)}
            placeholder={`TP Price (curr: ${fmt(position.tp2, 2)})`}
            className="flex-1 px-2 py-1 text-xs text-[#e0e8ff] outline-none"
            style={{ background: "#0a0e1a", border: "1px solid #00d4ff" }}
          />
          <button
            onClick={() => action("set-tp", { price: parseFloat(tpPrice) })}
            disabled={!tpPrice}
            className="btn-primary text-[10px] px-3 py-1"
          >
            SET
          </button>
        </div>
      )}

      {/* Modify SL panel */}
      {showModify === "sl" && (
        <div className="px-3 pb-2 flex gap-2 fade-in" style={{ borderTop: "1px solid #1a2040" }}>
          <input
            type="number"
            value={slPrice}
            onChange={(e) => setSlPrice(e.target.value)}
            placeholder={`SL Price (curr: ${fmt(position.sl, 2)})`}
            className="flex-1 px-2 py-1 text-xs text-[#e0e8ff] outline-none"
            style={{ background: "#0a0e1a", border: "1px solid #ffaa00" }}
          />
          <button
            onClick={() => action("set-sl", { price: parseFloat(slPrice) })}
            disabled={!slPrice}
            className="btn-warning text-[10px] px-3 py-1"
          >
            SET
          </button>
        </div>
      )}
    </div>
  );
}
