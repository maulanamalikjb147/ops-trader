import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const EXCHANGE_OPTIONS = [
  { name: "demo", tag: "DEMO", mode: "demo", description: "Paper trading (no real API)" },
  { name: "bybit_testnet", tag: "BYBIT TESTNET", mode: "demo", description: "Bybit testnet" },
  { name: "binance", tag: "BINANCE", mode: "live", description: "Binance live" },
  { name: "bybit", tag: "BYBIT", mode: "live", description: "Bybit live" },
  { name: "okx", tag: "OKX", mode: "live", description: "OKX live" },
  { name: "bitget", tag: "BITGET", mode: "live", description: "Bitget live" },
];

const TABS = ["BOT CONFIG", "EXCHANGES", "INTEGRATIONS", "CONTROLS"];

export default function Settings() {
  const [tab, setTab] = useState("BOT CONFIG");
  const [config, setConfig] = useState(null);
  const [exchanges, setExchanges] = useState([]);
  const [botStatus, setBotStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [addExch, setAddExch] = useState(null);
  const [loadError, setLoadError] = useState(false);

  const fetchAll = async () => {
    setLoadError(false);
    try {
      const [cfg, exch, status] = await Promise.all([
        axios.get(`${API}/config`, { withCredentials: true }),
        axios.get(`${API}/exchanges`, { withCredentials: true }),
        axios.get(`${API}/bot/status`, { withCredentials: true }),
      ]);
      setConfig(cfg.data);
      setExchanges(exch.data);
      setBotStatus(status.data);
    } catch (e) {
      console.error("Settings fetch failed:", e);
      setLoadError(true);
      // Set defaults so page doesn't stay stuck
      if (!config) setConfig({
        swing_enabled: true, scalp_enabled: false, hybrid_enabled: true,
        auto_bep: true, partial_close: true, partial_percent: 50,
        default_leverage: 5, risk_percent: 1.0, max_open_positions: 3,
        max_margin: 500, swing_min_score: 4, scalp_min_score: 3,
        hybrid_min_score: 4, coins_to_scan: [], active_mode: "demo",
        active_exchange: "demo", auto_trade_demo: true, auto_trade_live: false,
      });
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const saveConfig = async (updates) => {
    setSaving(true);
    try {
      await axios.put(`${API}/config`, { ...config, ...updates }, { withCredentials: true });
      setConfig((c) => ({ ...c, ...updates }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (_) {}
    setSaving(false);
  };

  const togglePause = async () => {
    const endpoint = botStatus?.paused ? "resume" : "pause";
    await axios.post(`${API}/bot/${endpoint}`, {}, { withCredentials: true });
    setBotStatus((s) => ({ ...s, paused: !s?.paused }));
  };

  const scanNow = async () => {
    await axios.post(`${API}/bot/scan-now`, {}, { withCredentials: true });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const toggleExchange = async (id, is_active) => {
    await axios.put(`${API}/exchanges/${id}`, { is_active }, { withCredentials: true });
    setExchanges((prev) => prev.map((e) => e.id === id ? { ...e, is_active } : e));
  };

  const addExchange = async (data) => {
    await axios.post(`${API}/exchanges`, data, { withCredentials: true });
    fetchAll();
    setAddExch(null);
  };

  const deleteExchange = async (id) => {
    await axios.delete(`${API}/exchanges/${id}`, { withCredentials: true });
    setExchanges((prev) => prev.filter((e) => e.id !== id));
  };

  if (!config) return <Layout><div className="flex items-center justify-center h-full">
    <div className="text-center">
      <div className="w-6 h-6 border-2 border-[#00d4ff] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
      <p className="text-[#8a9bc2] text-xs">Loading settings...</p>
      {loadError && <button onClick={fetchAll} className="mt-3 btn-primary text-[10px] px-3 py-1">RETRY</button>}
    </div>
  </div></Layout>;

  return (
    <Layout>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center px-3 flex-shrink-0" style={{ borderBottom: "1px solid #1a2040" }}>
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              data-testid={`settings-tab-${t.replace(" ", "-").toLowerCase()}`}
              className={`px-4 py-2 text-xs tracking-wider transition-all ${tab === t ? "tab-active" : "tab-inactive"}`}
            >
              {t}
            </button>
          ))}
          <div className="flex-1" />
          {saved && <span className="text-[10px] text-[#00ff88] mr-3">SAVED</span>}
        </div>

        <div className="flex-1 overflow-y-auto p-3">

          {/* ── BOT CONFIG ── */}
          {tab === "BOT CONFIG" && (
            <div className="space-y-4 max-w-2xl">
              <Section title="TRADING MODES">
                <Toggle label="Swing (4H/1D)" checked={config.swing_enabled} onChange={(v) => saveConfig({ swing_enabled: v })} testId="toggle-swing" />
                <Toggle label="Scalp (1m/5m)" checked={config.scalp_enabled} onChange={(v) => saveConfig({ scalp_enabled: v })} testId="toggle-scalp" />
                <Toggle label="Hybrid (15m/1H/4H)" checked={config.hybrid_enabled} onChange={(v) => saveConfig({ hybrid_enabled: v })} testId="toggle-hybrid" />
              </Section>

              <Section title="RISK MANAGEMENT">
                <NumberField label="Max Open Positions" value={config.max_open_positions} onChange={(v) => saveConfig({ max_open_positions: parseInt(v) })} min={1} max={20} testId="max-open-positions" />
                <NumberField label="Max Total Margin (USDT)" value={config.max_margin} onChange={(v) => saveConfig({ max_margin: parseFloat(v) })} min={10} step={10} testId="max-margin" />
                <NumberField label="Default Leverage" value={config.default_leverage} onChange={(v) => saveConfig({ default_leverage: parseInt(v) })} min={1} max={125} testId="default-leverage" />
                <NumberField label="Risk Per Trade (%)" value={config.risk_percent} onChange={(v) => saveConfig({ risk_percent: parseFloat(v) })} min={0.1} max={10} step={0.1} testId="risk-percent" />
              </Section>

              <Section title="MIN CONFIDENCE SCORES">
                <NumberField label="Swing Min Score" value={config.swing_min_score} onChange={(v) => saveConfig({ swing_min_score: parseInt(v) })} min={1} max={5} testId="swing-min-score" />
                <NumberField label="Scalp Min Score" value={config.scalp_min_score} onChange={(v) => saveConfig({ scalp_min_score: parseInt(v) })} min={1} max={5} testId="scalp-min-score" />
                <NumberField label="Hybrid Min Score" value={config.hybrid_min_score} onChange={(v) => saveConfig({ hybrid_min_score: parseInt(v) })} min={1} max={5} testId="hybrid-min-score" />
              </Section>

              <Section title="AUTO FEATURES">
                <Toggle label="Auto BEP (move SL to entry after TP1)" checked={config.auto_bep} onChange={(v) => saveConfig({ auto_bep: v })} testId="toggle-auto-bep" />
                <Toggle label="Partial Close at TP1" checked={config.partial_close} onChange={(v) => saveConfig({ partial_close: v })} testId="toggle-partial-close" />
                {config.partial_close && <NumberField label="Partial Close %" value={config.partial_percent} onChange={(v) => saveConfig({ partial_percent: parseInt(v) })} min={10} max={90} testId="partial-percent" />}
              </Section>

              <Section title="COINS TO SCAN">
                <CoinsList
                  coins={config.coins_to_scan}
                  onChange={(v) => saveConfig({ coins_to_scan: v })}
                  activeExchange={config.active_exchange}
                />
              </Section>

              <Section title="ACTIVE EXCHANGE">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="text-[10px] text-[#8a9bc2] uppercase tracking-widest">Mode</label>
                    <select
                      value={config.active_mode}
                      onChange={(e) => saveConfig({ active_mode: e.target.value })}
                      data-testid="active-mode"
                      className="w-full px-2 py-1.5 text-xs outline-none mt-1"
                      style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }}
                    >
                      <option value="demo">Demo (Simulation)</option>
                      <option value="live">Live</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="text-[10px] text-[#8a9bc2] uppercase tracking-widest">Exchange</label>
                    <select
                      value={config.active_exchange}
                      onChange={(e) => saveConfig({ active_exchange: e.target.value })}
                      data-testid="active-exchange"
                      className="w-full px-2 py-1.5 text-xs outline-none mt-1"
                      style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }}
                    >
                      {exchanges.map((e) => <option key={e.id} value={e.name}>{e.tag}</option>)}
                    </select>
                  </div>
                </div>
              </Section>
            </div>
          )}

          {/* ── EXCHANGES ── */}
          {tab === "EXCHANGES" && (
            <div className="space-y-2 max-w-2xl">
              {exchanges.map((ex) => (
                <ExchangeRow key={ex.id} exchange={ex} onToggle={toggleExchange} onDelete={deleteExchange} />
              ))}
              <div className="mt-3">
                {!addExch ? (
                  <button
                    onClick={() => setAddExch({})}
                    data-testid="add-exchange-btn"
                    className="btn-primary text-xs px-3 py-1.5 transition-all"
                  >
                    + ADD EXCHANGE
                  </button>
                ) : (
                  <AddExchangeForm
                    options={EXCHANGE_OPTIONS.filter((o) => !exchanges.find((e) => e.name === o.name))}
                    onSave={addExchange}
                    onCancel={() => setAddExch(null)}
                  />
                )}
              </div>
            </div>
          )}

          {/* ── INTEGRATIONS ── */}
          {tab === "INTEGRATIONS" && (
            <div className="space-y-4 max-w-lg">
              <Section title="TELEGRAM BOT">
                <ApiKeyField label="Bot Token" value={config.telegram_token || ""} onChange={(v) => setConfig({ ...config, telegram_token: v })} placeholder="123456789:ABCdef..." testId="telegram-token" />
                <ApiKeyField label="Chat ID" value={config.telegram_chat_id || ""} onChange={(v) => setConfig({ ...config, telegram_chat_id: v })} placeholder="-100123456789" testId="telegram-chat-id" />
                <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-[10px] text-[#00d4ff]">Get token from @BotFather on Telegram</a>
              </Section>
              <Section title="NOTION DATABASE">
                <ApiKeyField label="API Key" value={config.notion_api_key || ""} onChange={(v) => setConfig({ ...config, notion_api_key: v })} placeholder="secret_xxx..." testId="notion-api-key" />
                <ApiKeyField label="Database ID" value={config.notion_database_id || ""} onChange={(v) => setConfig({ ...config, notion_database_id: v })} placeholder="notion page id" testId="notion-db-id" />
                <a href="https://notion.so/my-integrations" target="_blank" rel="noreferrer" className="text-[10px] text-[#00d4ff]">Get key from notion.so/my-integrations</a>
              </Section>
              <Section title="COINGECKO API">
                <ApiKeyField label="API Key (optional)" value={config.coingecko_api_key || ""} onChange={(v) => setConfig({ ...config, coingecko_api_key: v })} placeholder="CG-xxx... (optional)" testId="coingecko-key" />
                <a href="https://coingecko.com/api" target="_blank" rel="noreferrer" className="text-[10px] text-[#00d4ff]">Get free key at coingecko.com/api</a>
              </Section>
              <button
                onClick={() => saveConfig(config)}
                data-testid="save-integrations-btn"
                disabled={saving}
                className="w-full py-2 text-sm font-semibold"
                style={{ background: "#00d4ff", color: "#0a0e1a" }}
              >
                {saving ? "SAVING..." : "SAVE ALL SETTINGS"}
              </button>
            </div>
          )}

          {/* ── CONTROLS ── */}
          {tab === "CONTROLS" && (
            <div className="space-y-3 max-w-sm">
              <Section title="BOT STATUS">
                <div className="flex items-center gap-3 mb-3">
                  <span className={`text-sm font-bold ${botStatus?.paused ? "text-[#ff3366]" : "text-[#00ff88]"}`}>
                    {botStatus?.paused ? "PAUSED" : "RUNNING"}
                  </span>
                  <span className="text-[10px] text-[#8a9bc2]">|</span>
                  <span className="text-[10px] text-[#8a9bc2]">{botStatus?.open_positions || 0} positions open</span>
                  <span className="text-[10px] text-[#8a9bc2]">|</span>
                  <span className="text-[10px] text-[#8a9bc2]">${(botStatus?.total_margin_used || 0).toFixed(2)} margin</span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={togglePause}
                    data-testid="toggle-pause-btn"
                    className={`px-4 py-2 text-xs font-bold transition-all ${botStatus?.paused ? "btn-success" : "btn-warning"}`}
                  >
                    {botStatus?.paused ? "RESUME" : "PAUSE"}
                  </button>
                  <button
                    onClick={scanNow}
                    data-testid="scan-now-btn"
                    className="btn-primary px-4 py-2 text-xs transition-all"
                  >
                    SCAN NOW
                  </button>
                </div>
              </Section>

              <Section title="AUTO TRADE">
                <div className="text-[10px] text-[#8a9bc2] mb-3 leading-relaxed">
                  When <span className="text-[#00ff88]">ON</span>: signal detected → order placed automatically.<br />
                  When <span className="text-[#ff3366]">OFF</span>: signal shown & notified, but no order placed.
                </div>
                <div className="space-y-3">
                  {/* Demo Auto Trade */}
                  <div className="p-3" style={{ border: "1px solid #1a2040", background: "#0a0e1a" }}>
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <div className="text-xs font-bold text-[#e0e8ff]">Demo Mode Auto Trade</div>
                        <div className="text-[10px] text-[#8a9bc2]">Paper trading orders placed automatically</div>
                      </div>
                      <button
                        data-testid="toggle-auto-trade-demo"
                        onClick={() => saveConfig({ auto_trade_demo: !config.auto_trade_demo })}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold transition-all"
                        style={{
                          border: `1px solid ${config.auto_trade_demo ? "#00ff88" : "#ff3366"}`,
                          background: config.auto_trade_demo ? "rgba(0,255,136,0.1)" : "rgba(255,51,102,0.1)",
                          color: config.auto_trade_demo ? "#00ff88" : "#ff3366",
                          minWidth: "80px"
                        }}
                      >
                        <span className={`w-2 h-2 rounded-full ${config.auto_trade_demo ? "bg-[#00ff88]" : "bg-[#ff3366]"}`} />
                        {config.auto_trade_demo ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>

                  {/* Live Auto Trade */}
                  <div className="p-3" style={{ border: `1px solid ${config.auto_trade_live ? "#ff3366" : "#1a2040"}`, background: "#0a0e1a" }}>
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <div className="text-xs font-bold text-[#e0e8ff]">Live Mode Auto Trade</div>
                        <div className="text-[10px] text-[#8a9bc2]">
                          Real money orders placed automatically
                          {config.auto_trade_live && <span className="text-[#ff3366] ml-1 font-bold">— USE WITH CAUTION!</span>}
                        </div>
                      </div>
                      <button
                        data-testid="toggle-auto-trade-live"
                        onClick={() => saveConfig({ auto_trade_live: !config.auto_trade_live })}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold transition-all"
                        style={{
                          border: `1px solid ${config.auto_trade_live ? "#ff3366" : "#8a9bc2"}`,
                          background: config.auto_trade_live ? "rgba(255,51,102,0.15)" : "rgba(138,155,194,0.1)",
                          color: config.auto_trade_live ? "#ff3366" : "#8a9bc2",
                          minWidth: "80px"
                        }}
                      >
                        <span className={`w-2 h-2 rounded-full ${config.auto_trade_live ? "bg-[#ff3366] pulse" : "bg-[#8a9bc2]"}`} />
                        {config.auto_trade_live ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Mode summary */}
                <div className="mt-3 p-2 text-[10px]" style={{ border: "1px solid #1a2040", background: "#0f1423" }}>
                  <div className="text-[#8a9bc2] mb-1 uppercase tracking-widest text-[9px]">Current Behavior</div>
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${config.auto_trade_demo ? "bg-[#00ff88]" : "bg-[#8a9bc2]"}`} />
                    <span className={config.auto_trade_demo ? "text-[#00ff88]" : "text-[#8a9bc2]"}>
                      Demo: {config.auto_trade_demo ? "Auto execute orders" : "Signal only (no order)"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${config.auto_trade_live ? "bg-[#ff3366] pulse" : "bg-[#8a9bc2]"}`} />
                    <span className={config.auto_trade_live ? "text-[#ff3366]" : "text-[#8a9bc2]"}>
                      Live: {config.auto_trade_live ? "Auto execute REAL orders" : "Signal only (no order)"}
                    </span>
                  </div>
                </div>
              </Section>

              <Section title="INTEGRATIONS STATUS">
                <div className="space-y-1.5 text-xs">
                  <StatusRow label="Telegram" active={botStatus?.telegram_enabled} />
                  <StatusRow label="Notion" active={botStatus?.notion_enabled} />
                  <StatusRow label="WebSocket" active={botStatus?.ws_clients > 0} extra={`${botStatus?.ws_clients || 0} clients`} />
                </div>
              </Section>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function Section({ title, children }) {
  return (
    <div style={{ border: "1px solid #1a2040", background: "#0f1423" }}>
      <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#8a9bc2]" style={{ borderBottom: "1px solid #1a2040" }}>{title}</div>
      <div className="p-3 space-y-3">{children}</div>
    </div>
  );
}

function Toggle({ label, checked, onChange, testId }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-[#e0e8ff]">{label}</span>
      <button
        data-testid={testId}
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 relative transition-all`}
        style={{ border: `1px solid ${checked ? "#00ff88" : "#1a2040"}`, background: checked ? "rgba(0,255,136,0.15)" : "#0a0e1a" }}
      >
        <span className={`absolute top-0.5 w-3.5 h-3.5 transition-all ${checked ? "right-0.5 bg-[#00ff88]" : "left-0.5 bg-[#8a9bc2]"}`} />
      </button>
    </div>
  );
}

function NumberField({ label, value, onChange, min, max, step = 1, testId }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-[#e0e8ff] flex-1">{label}</span>
      <input
        data-testid={testId}
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={(e) => onChange(e.target.value)}
        min={min} max={max} step={step}
        className="w-24 px-2 py-1 text-xs text-[#e0e8ff] text-right outline-none"
        style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
      />
    </div>
  );
}

function ApiKeyField({ label, value, onChange, placeholder, testId }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-widest text-[#8a9bc2] mb-1">{label}</label>
      <div className="flex gap-1">
        <input
          data-testid={testId}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1 px-2 py-1.5 text-xs text-[#e0e8ff] outline-none"
          style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
        />
        <button onClick={() => setShow(!show)} className="text-[10px] px-2 text-[#8a9bc2]" style={{ border: "1px solid #1a2040" }}>
          {show ? "HIDE" : "SHOW"}
        </button>
      </div>
    </div>
  );
}

function CoinsList({ coins, onChange, activeExchange }) {
  const [newCoin, setNewCoin] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  const [topInfo, setTopInfo] = useState(null);

  // Map active_exchange → public exchange source for fetching top pairs.
  // OKX is the primary source (works without API key, true SWAP futures).
  // Binance/Bybit available for users on those exchanges.
  const sourceExchange = (() => {
    const ex = (activeExchange || "").toLowerCase();
    if (ex.startsWith("bybit")) return "bybit";
    if (ex === "binance") return "binance";
    return "okx"; // okx / demo / bitget / unknown → OKX (default, public, futures-native)
  })();

  const loadTop = async (limit) => {
    setLoading(true);
    setLoadErr("");
    try {
      const res = await axios.get(
        `${API}/market/top-pairs?exchange=${sourceExchange}&limit=${limit}`,
        { withCredentials: true }
      );
      const pairs = (res.data || []).map((p) => p.pair);
      if (pairs.length === 0) {
        setLoadErr("No pairs returned");
      } else {
        onChange(pairs);
        setTopInfo({ count: pairs.length, source: sourceExchange.toUpperCase() });
        setTimeout(() => setTopInfo(null), 3000);
      }
    } catch (e) {
      setLoadErr(e?.response?.data?.detail || "Failed to load");
    }
    setLoading(false);
  };

  return (
    <div>
      {/* Auto-load controls */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-[10px] text-[#8a9bc2] uppercase tracking-widest">
          Auto-fetch futures top pairs from <span className="text-[#00d4ff]">{sourceExchange.toUpperCase()}</span>
        </span>
        <button
          onClick={() => loadTop(20)}
          disabled={loading}
          data-testid="load-top-20-btn"
          className="btn-primary text-[10px] px-2 py-1 disabled:opacity-50"
        >
          {loading ? "..." : "LOAD TOP 20"}
        </button>
        <button
          onClick={() => loadTop(50)}
          disabled={loading}
          data-testid="load-top-50-btn"
          className="btn-primary text-[10px] px-2 py-1 disabled:opacity-50"
        >
          {loading ? "..." : "LOAD TOP 50"}
        </button>
        <button
          onClick={() => loadTop(100)}
          disabled={loading}
          data-testid="load-top-100-btn"
          className="text-[10px] px-2 py-1 text-[#8a9bc2]"
          style={{ border: "1px solid #1a2040" }}
        >
          {loading ? "..." : "TOP 100"}
        </button>
        {topInfo && (
          <span className="text-[10px] text-[#00ff88]" data-testid="top-loaded-msg">
            ✓ Loaded {topInfo.count} pairs from {topInfo.source} (sorted by 24h volume)
          </span>
        )}
        {loadErr && (
          <span className="text-[10px] text-[#ff3366]" data-testid="top-load-error">
            ✗ {loadErr}
          </span>
        )}
      </div>

      {coins.length > 0 && (
        <div className="text-[10px] text-[#8a9bc2] mb-1">
          {coins.length} pairs configured
        </div>
      )}
      <div className="flex flex-wrap gap-1 mb-2 max-h-48 overflow-y-auto">
        {coins.map((c) => (
          <div key={c} className="flex items-center gap-1 px-2 py-0.5 text-[11px]" style={{ border: "1px solid #1a2040", background: "#0a0e1a" }}>
            <span>{c}</span>
            <button onClick={() => onChange(coins.filter((x) => x !== c))} className="text-[#ff3366] ml-1 text-[10px]">X</button>
          </div>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          value={newCoin}
          onChange={(e) => setNewCoin(e.target.value.toUpperCase())}
          placeholder="BTC/USDT"
          className="flex-1 px-2 py-1 text-xs text-[#e0e8ff] outline-none"
          style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
          data-testid="add-coin-input"
        />
        <button
          onClick={() => { if (newCoin && !coins.includes(newCoin)) { onChange([...coins, newCoin]); setNewCoin(""); } }}
          className="btn-primary text-[10px] px-3 py-1"
          data-testid="add-coin-btn"
        >ADD</button>
        {coins.length > 0 && (
          <button
            onClick={() => onChange([])}
            className="btn-danger text-[10px] px-3 py-1"
            data-testid="clear-coins-btn"
          >CLEAR</button>
        )}
      </div>
    </div>
  );
}

function ExchangeRow({ exchange, onToggle, onDelete }) {
  return (
    <div className="flex items-center gap-3 p-3" style={{ border: "1px solid #1a2040", background: "#0f1423" }}>
      <div className="flex-1">
        <div className="text-xs font-bold">{exchange.tag}</div>
        <div className="text-[10px] text-[#8a9bc2]">{exchange.mode.toUpperCase()} | {exchange.api_key ? `${exchange.api_key}` : "No API key"}</div>
      </div>
      <button
        onClick={() => onToggle(exchange.id, !exchange.is_active)}
        data-testid={`toggle-exchange-${exchange.name}`}
        className={`text-[10px] px-3 py-1 transition-all ${exchange.is_active ? "btn-success" : "text-[#8a9bc2]"}`}
        style={{ border: `1px solid ${exchange.is_active ? "#00ff88" : "#1a2040"}` }}
      >
        {exchange.is_active ? "ACTIVE" : "INACTIVE"}
      </button>
      {exchange.name !== "demo" && (
        <button
          onClick={() => onDelete(exchange.id)}
          data-testid={`delete-exchange-${exchange.name}`}
          className="btn-danger text-[10px] px-2 py-1 transition-all"
        >
          DEL
        </button>
      )}
    </div>
  );
}

function AddExchangeForm({ options, onSave, onCancel }) {
  const [form, setForm] = useState({ name: options[0]?.name || "", api_key: "", api_secret: "", passphrase: "", demo_balance: 10000 });
  const selected = EXCHANGE_OPTIONS.find((o) => o.name === form.name);
  return (
    <div className="p-3 space-y-2" style={{ border: "1px solid #00d4ff", background: "#0f1423" }}>
      <div className="text-[10px] text-[#00d4ff] mb-2">ADD EXCHANGE</div>
      <div>
        <label className="block text-[10px] text-[#8a9bc2] mb-1">Exchange</label>
        <select value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-2 py-1.5 text-xs outline-none" style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }}>
          {options.map((o) => <option key={o.name} value={o.name}>{o.tag}</option>)}
        </select>
      </div>
      {selected?.mode === "live" && (
        <>
          <input value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="API Key" className="w-full px-2 py-1.5 text-xs outline-none" style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }} />
          <input value={form.api_secret} onChange={(e) => setForm({ ...form, api_secret: e.target.value })} placeholder="API Secret" type="password" className="w-full px-2 py-1.5 text-xs outline-none" style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }} />
          {form.name === "okx" && <input value={form.passphrase} onChange={(e) => setForm({ ...form, passphrase: e.target.value })} placeholder="Passphrase (OKX)" className="w-full px-2 py-1.5 text-xs outline-none" style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }} />}
        </>
      )}
      {selected?.mode === "demo" && (
        <input value={form.demo_balance} onChange={(e) => setForm({ ...form, demo_balance: parseFloat(e.target.value) })} placeholder="Demo Balance (USDT)" type="number" className="w-full px-2 py-1.5 text-xs outline-none" style={{ background: "#0a0e1a", border: "1px solid #1a2040", color: "#e0e8ff" }} />
      )}
      <div className="flex gap-2 pt-1">
        <button onClick={() => onSave({ ...form, tag: selected?.tag || form.name.toUpperCase(), mode: selected?.mode || "live" })} className="btn-primary text-[10px] px-3 py-1 flex-1">SAVE</button>
        <button onClick={onCancel} className="btn-danger text-[10px] px-3 py-1">CANCEL</button>
      </div>
    </div>
  );
}

function StatusRow({ label, active, extra }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[#8a9bc2]">{label}</span>
      <div className="flex items-center gap-2">
        {extra && <span className="text-[10px] text-[#8a9bc2]">{extra}</span>}
        <span className={`text-[10px] font-bold ${active ? "text-[#00ff88]" : "text-[#ff3366]"}`}>{active ? "CONNECTED" : "DISCONNECTED"}</span>
      </div>
    </div>
  );
}
