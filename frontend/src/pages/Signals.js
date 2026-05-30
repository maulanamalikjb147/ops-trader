import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import SignalCard from "@/components/SignalCard";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const STATUS_OPTIONS = ["ALL", "open", "closed", "cancelled"];
const MODE_OPTIONS = ["ALL", "swing", "scalp", "hybrid"];
const EXCH_OPTIONS = ["ALL", "demo", "binance", "bybit", "okx", "bitget"];

export default function Signals() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("ALL");
  const [mode, setMode] = useState("ALL");
  const [exchange, setExchange] = useState("ALL");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const fetch = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: PAGE_SIZE, skip: page * PAGE_SIZE });
      if (status !== "ALL") params.set("status", status);
      if (mode !== "ALL") params.set("trading_mode", mode);
      if (exchange !== "ALL") params.set("exchange", exchange);
      const { data } = await axios.get(`${API}/signals?${params}`, { withCredentials: true });
      setSignals(data);
    } catch (_) {}
    setLoading(false);
  };

  useEffect(() => { fetch(); }, [status, mode, exchange, page]);

  return (
    <Layout>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Filter bar */}
        <div className="flex items-center gap-4 px-3 py-2 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040" }}>
          <FilterGroup label="STATUS" options={STATUS_OPTIONS} value={status} onChange={setStatus} testPrefix="status" />
          <FilterGroup label="MODE" options={MODE_OPTIONS} value={mode} onChange={setMode} testPrefix="mode" />
          <FilterGroup label="EXCHANGE" options={EXCH_OPTIONS} value={exchange} onChange={setExchange} testPrefix="exch" />
          <div className="flex-1" />
          <span className="text-[10px] text-[#8a9bc2]">{signals.length} results</span>
          <button onClick={fetch} className="text-[10px] btn-primary px-2 py-1 transition-all">REFRESH</button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-[#8a9bc2] text-xs">Loading...</div>
          ) : signals.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-[#1a2040] text-xs">No signals found</div>
          ) : (
            <div className="space-y-0.5">
              {signals.map((s) => <SignalCard key={s.id} signal={s} />)}
            </div>
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0" style={{ borderTop: "1px solid #1a2040" }}>
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="text-[10px] btn-primary px-3 py-1 disabled:opacity-30"
          >
            PREV
          </button>
          <span className="text-[10px] text-[#8a9bc2]">Page {page + 1}</span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={signals.length < PAGE_SIZE}
            className="text-[10px] btn-primary px-3 py-1 disabled:opacity-30"
          >
            NEXT
          </button>
        </div>
      </div>
    </Layout>
  );
}

function FilterGroup({ label, options, value, onChange, testPrefix }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-[#8a9bc2] uppercase tracking-widest mr-1">{label}:</span>
      {options.map((opt) => (
        <button
          key={opt}
          data-testid={`filter-${testPrefix}-${opt.toLowerCase()}`}
          onClick={() => onChange(opt)}
          className={`px-2 py-0.5 text-[10px] transition-all ${value === opt ? "text-[#00d4ff] border-b border-[#00d4ff]" : "text-[#8a9bc2] hover:text-[#e0e8ff]"}`}
        >
          {opt.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
