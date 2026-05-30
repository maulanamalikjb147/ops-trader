import { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";
import PositionCard from "@/components/PositionCard";
import SignalLog from "@/components/SignalLog";
import useStore from "@/store/useStore";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"];
const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];
const MODES = ["ALL", "SWING", "SCALP", "HYBRID"];
const EXCHANGES = ["ALL", "DEMO", "BINANCE", "BYBIT", "OKX", "BITGET"];

function TradingViewChart({ pair, timeframe }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";
    const script = document.createElement("script");
    script.type = "text/javascript";
    script.async = true;
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: `BINANCE:${pair.replace("/", "")}`,
      interval: timeframe.toUpperCase(),
      timezone: "UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "#0a0e1a",
      gridColor: "#1a2040",
      hide_side_toolbar: true,
      allow_symbol_change: false,
      save_image: false,
      calendar: false,
    });
    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.style.cssText = "height:100%;width:100%;";
    const inner = document.createElement("div");
    inner.className = "tradingview-widget-container__widget";
    inner.style.cssText = "height:calc(100% - 32px);width:100%;";
    wrapper.appendChild(inner);
    wrapper.appendChild(script);
    ref.current.appendChild(wrapper);
  }, [pair, timeframe]);

  return <div ref={ref} style={{ height: "100%", width: "100%" }} />;
}

export default function Dashboard() {
  const { positions, fetchStats } = useStore();
  const [pair, setPair] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [modeFilter, setModeFilter] = useState("ALL");
  const [exchFilter, setExchFilter] = useState("ALL");
  const [openSignals, setOpenSignals] = useState([]);

  const fetchOpen = async () => {
    try {
      const { data } = await axios.get(`${API}/signals?status=open`, { withCredentials: true });
      setOpenSignals(data);
    } catch (_) {}
  };

  useEffect(() => {
    fetchOpen();
    fetchStats();
    const t = setInterval(fetchOpen, 15000);
    return () => clearInterval(t);
  }, []);

  // Merge live PNL from WebSocket into signal data
  const mergedPositions = openSignals.map((sig) => {
    const live = positions.find((p) => p.id === sig.id);
    return live ? { ...sig, ...live } : sig;
  });

  const filteredPositions = mergedPositions.filter((p) => {
    if (modeFilter !== "ALL" && p.trading_mode?.toUpperCase() !== modeFilter) return false;
    if (exchFilter !== "ALL" && p.exchange?.toUpperCase() !== exchFilter) return false;
    return true;
  });

  return (
    <Layout>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Filter Bar */}
        <div className="flex items-center gap-1 px-2 py-1.5 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040" }}>
          {/* Mode tabs */}
          <div className="flex items-center mr-4">
            {MODES.map((m) => (
              <button
                key={m}
                data-testid={`mode-filter-${m.toLowerCase()}`}
                onClick={() => setModeFilter(m)}
                className={`px-3 py-1 text-[11px] font-medium transition-all ${modeFilter === m ? "tab-active" : "tab-inactive"}`}
              >
                {m}
              </button>
            ))}
          </div>
          <span className="text-[#1a2040] text-xs">|</span>
          {/* Exchange filters */}
          <div className="flex items-center ml-2">
            {EXCHANGES.map((e) => (
              <button
                key={e}
                data-testid={`exch-filter-${e.toLowerCase()}`}
                onClick={() => setExchFilter(e)}
                className={`px-2 py-1 text-[10px] transition-all ${exchFilter === e ? "text-[#00d4ff]" : "text-[#8a9bc2] hover:text-[#e0e8ff]"}`}
              >
                {e}
              </button>
            ))}
          </div>
          <div className="flex-1" />
          {/* Pair selector */}
          <select
            value={pair}
            onChange={(e) => setPair(e.target.value)}
            data-testid="pair-selector"
            className="text-[11px] px-2 py-1 outline-none cursor-pointer"
            style={{ background: "#0f1423", border: "1px solid #1a2040", color: "#e0e8ff" }}
          >
            {PAIRS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          {/* Timeframe */}
          <div className="flex items-center ml-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                data-testid={`tf-${tf}`}
                className={`px-2 py-1 text-[10px] transition-all ${timeframe === tf ? "text-[#00d4ff]" : "text-[#8a9bc2]"}`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Main content area */}
        <div className="flex-1 min-h-0 flex">
          {/* Chart */}
          <div className="flex-1 min-w-0" style={{ borderRight: "1px solid #1a2040" }}>
            <TradingViewChart pair={pair} timeframe={timeframe} />
          </div>

          {/* Positions Panel */}
          <div
            className="flex flex-col overflow-hidden"
            style={{ width: "320px", background: "#0a0e1a" }}
            data-testid="positions-panel"
          >
            <div className="flex items-center justify-between px-3 py-2 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040" }}>
              <span className="text-[10px] uppercase tracking-widest text-[#8a9bc2]">ACTIVE POSITIONS</span>
              <span className="text-[10px] text-[#00d4ff]">{filteredPositions.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto">
              {filteredPositions.length === 0 ? (
                <div className="flex items-center justify-center h-24 text-[11px] text-[#1a2040]">
                  No open positions
                </div>
              ) : (
                filteredPositions.map((pos) => (
                  <PositionCard key={pos.id} position={pos} onAction={fetchOpen} />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Signal Log */}
        <div style={{ height: "140px", borderTop: "1px solid #1a2040", flexShrink: 0 }}>
          <SignalLog />
        </div>
      </div>
    </Layout>
  );
}
