import { create } from "zustand";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const WS_URL = `${process.env.REACT_APP_BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")}/ws`;

const useStore = create((set, get) => ({
  user: undefined,
  setUser: (user) => set({ user }),

  positions: [],
  setPositions: (positions) => set({ positions }),

  recentSignals: [],
  setRecentSignals: (recentSignals) => set({ recentSignals }),

  signalLog: [],
  addLogEntry: (entry) =>
    set((s) => ({ signalLog: [entry, ...s.signalLog].slice(0, 100) })),

  botStatus: { paused: false, active_mode: "demo", open_positions: 0 },
  setBotStatus: (botStatus) => set({ botStatus }),

  stats: { today_signals: 0, win_rate: 0, today_pnl: 0, open_positions: 0 },
  setStats: (stats) => set({ stats }),

  wsConnected: false,
  ws: null,

  connectWs: () => {
    const existing = get().ws;
    if (existing) return;
    try {
      const ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        set({ wsConnected: true, ws });
        ws.send("ping");
      };
      ws.onclose = () => {
        set({ wsConnected: false, ws: null });
        setTimeout(() => get().connectWs(), 5000);
      };
      ws.onerror = () => {
        set({ wsConnected: false, ws: null });
      };
      ws.onmessage = (ev) => {
        try {
          const { event, data } = JSON.parse(ev.data);
          if (event === "position:update") {
            set({ positions: data });
          } else if (event === "position:closed") {
            const prev = get().positions.filter((p) => p.id !== data.id);
            set({ positions: prev });
            const pnl = data.pnl_usd || 0;
            get().addLogEntry({
              time: new Date().toLocaleTimeString("en-GB"),
              text: `CLOSED ${data.pair || ""} ${data.reason} PNL ${pnl > 0 ? "+" : ""}${pnl.toFixed(2)} USDT`,
              type: pnl >= 0 ? "profit" : "loss",
            });
          } else if (event === "signal:new") {
            get().addLogEntry({
              time: new Date().toLocaleTimeString("en-GB"),
              text: `${data.side === "LONG" ? "▲" : "▼"} ${data.pair} ${data.side} @ ${data.entry_price?.toFixed?.(4) || data.entry_price} | ${data.exchange?.toUpperCase() || "DEMO"} | score:${data.confidence}`,
              type: data.side === "LONG" ? "long" : "short",
            });
          } else if (event === "bep:activated") {
            get().addLogEntry({
              time: new Date().toLocaleTimeString("en-GB"),
              text: `BEP ${data.pair || data.id} SL -> entry (risk-free)`,
              type: "info",
            });
          } else if (event === "bot:status") {
            set({ botStatus: { ...get().botStatus, ...data } });
          }
        } catch (_) {}
      };
    } catch (e) {
      console.error("WS connect failed", e);
    }
  },

  fetchStats: async () => {
    try {
      const r = await fetch(`${API}/dashboard`, { credentials: "include" });
      if (r.ok) {
        const data = await r.json();
        set({
          stats: {
            today_signals: data.today_signals,
            win_rate: data.win_rate,
            today_pnl: data.today_pnl,
            open_positions: data.open_positions,
          },
          recentSignals: data.recent_signals || [],
        });
      }
    } catch (_) {}
  },

  logout: async () => {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    set({ user: null, ws: null });
    const ws = get().ws;
    if (ws) ws.close();
  },
}));

export default useStore;
