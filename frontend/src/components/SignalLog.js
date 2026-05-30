import useStore from "@/store/useStore";

const LOG_COLORS = {
  long: "#00ff88",
  short: "#ff3366",
  profit: "#00ff88",
  loss: "#ff3366",
  info: "#00d4ff",
  default: "#8a9bc2",
};

export default function SignalLog() {
  const { signalLog } = useStore();

  return (
    <div
      data-testid="signal-log"
      className="h-full overflow-y-auto p-2"
      style={{ background: "#0a0e1a", borderTop: "1px solid #1a2040", fontFamily: "JetBrains Mono, monospace" }}
    >
      <div className="text-[10px] text-[#8a9bc2] uppercase tracking-widest mb-1.5 px-1">
        SIGNAL LOG
      </div>
      {signalLog.length === 0 ? (
        <div className="text-[10px] text-[#1a2040] px-1 py-2">No signals yet. Scanner running...</div>
      ) : (
        signalLog.map((entry, i) => (
          <div
            key={i}
            className="terminal-line flex gap-2 text-[11px] leading-relaxed"
          >
            <span className="text-[#8a9bc2] tabular-nums shrink-0">{entry.time}</span>
            <span className="text-[#8a9bc2]">›</span>
            <span style={{ color: LOG_COLORS[entry.type] || LOG_COLORS.default }}>
              {entry.text}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
