import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import useStore from "@/store/useStore";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Signals from "@/pages/Signals";
import Performance from "@/pages/Performance";
import Settings from "@/pages/Settings";
import "@/App.css";
import "@/index.css";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

function ProtectedRoute({ children }) {
  const { user } = useStore();
  if (user === undefined) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: "#0a0e1a" }}>
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[#00d4ff] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[#8a9bc2] text-xs">Loading...</p>
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { setUser, connectWs } = useStore();

  useEffect(() => {
    fetch(`${API}/auth/me`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        setUser(data || null);
        if (data) connectWs();
      })
      .catch(() => setUser(null));
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/signals" element={<ProtectedRoute><Signals /></ProtectedRoute>} />
        <Route path="/performance" element={<ProtectedRoute><Performance /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
