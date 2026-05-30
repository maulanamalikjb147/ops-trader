import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import useStore from "@/store/useStore";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function Register() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser, connectWs } = useStore();
  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match"); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters"); return; }
    setError("");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/auth/register`, { username, password }, { withCredentials: true });
      setUser(data);
      connectWs();
      navigate("/");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail.map((d) => d.msg).join(" ") : (detail || "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center" style={{ background: "#0a0e1a" }}>
      <div className="w-full max-w-sm" style={{ border: "1px solid #1a2040", background: "#0f1423", padding: "2rem" }}>
        <div className="mb-6 text-center">
          <div className="text-[#00d4ff] text-xl font-bold tracking-widest mb-1">SIGNAL BOT</div>
          <div className="text-[#8a9bc2] text-xs tracking-[0.2em] uppercase">Create Account</div>
          <div className="mt-3 h-px" style={{ background: "#1a2040" }} />
        </div>

        {error && (
          <div className="mb-4 p-2 text-xs text-[#ff3366]" style={{ border: "1px solid #ff3366", background: "rgba(255,51,102,0.05)" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-[#8a9bc2] mb-1">Username</label>
            <input
              data-testid="register-username"
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
              data-testid="register-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm text-[#e0e8ff] outline-none"
              style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
              placeholder="••••••••"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-[#8a9bc2] mb-1">Confirm Password</label>
            <input
              data-testid="register-confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-3 py-2 text-sm text-[#e0e8ff] outline-none"
              style={{ background: "#0a0e1a", border: "1px solid #1a2040" }}
              placeholder="••••••••"
              required
            />
          </div>
          <button
            data-testid="register-submit"
            type="submit"
            disabled={loading}
            className="w-full py-2 text-sm font-semibold transition-all"
            style={{ background: "#00d4ff", color: "#0a0e1a" }}
          >
            {loading ? "CREATING..." : "CREATE ACCOUNT"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <span className="text-[#8a9bc2] text-xs">Have account? </span>
          <Link to="/login" className="text-xs text-[#00d4ff]" data-testid="goto-login">Login</Link>
        </div>
      </div>
    </div>
  );
}
