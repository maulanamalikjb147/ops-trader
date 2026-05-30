import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import useStore from "@/store/useStore";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser, connectWs } = useStore();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/auth/login`, { username, password }, { withCredentials: true });
      setUser(data);
      connectWs();
      navigate("/");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail.map((d) => d.msg).join(" ") : (detail || "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center" style={{ background: "#0a0e1a" }}>
      <div className="w-full max-w-sm" style={{ border: "1px solid #1a2040", background: "#0f1423", padding: "2rem" }}>
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="text-[#00d4ff] text-xl font-bold tracking-widest mb-1">SIGNAL BOT</div>
          <div className="text-[#8a9bc2] text-xs tracking-[0.2em] uppercase">Trading System</div>
          <div className="mt-3 h-px" style={{ background: "#1a2040" }} />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-2 text-xs text-[#ff3366]" style={{ border: "1px solid #ff3366", background: "rgba(255,51,102,0.05)" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-[#8a9bc2] mb-1">Username</label>
            <input
              data-testid="login-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 text-sm text-[#e0e8ff] outline-none"
              style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
              placeholder="username"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-[#8a9bc2] mb-1">Password</label>
            <input
              data-testid="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm text-[#e0e8ff] outline-none"
              style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
              placeholder="••••••••"
              required
            />
          </div>
          <button
            data-testid="login-submit"
            type="submit"
            disabled={loading}
            className="w-full py-2 text-sm font-semibold transition-all"
            style={{ background: "#00d4ff", color: "#0a0e1a" }}
          >
            {loading ? "AUTHENTICATING..." : "LOGIN"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <span className="text-[#8a9bc2] text-xs">No account? </span>
          <Link to="/register" className="text-xs text-[#00d4ff]" data-testid="goto-register">Register</Link>
        </div>
      </div>
    </div>
  );
}
