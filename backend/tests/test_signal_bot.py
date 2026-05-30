"""
Signal Bot API Tests - Auth, Signals, Config, Bot Status, Performance
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture(scope="module")
def auth_session(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"username": "opsculun", "password": "@Traderculun147"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return session


# ── Auth Tests ────────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_success(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login", json={"username": "opsculun", "password": "@Traderculun147"})
        assert r.status_code == 200
        data = r.json()
        assert "username" in data
        assert data["username"] == "opsculun"

    def test_login_invalid(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login", json={"username": "opsculun", "password": "wrongpass"})
        assert r.status_code == 401

    def test_me_authenticated(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "opsculun"

    def test_me_unauthenticated(self, session):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code in [401, 403]

    def test_register_duplicate(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/auth/register", json={"username": "opsculun", "password": "test123"})
        assert r.status_code == 400

    def test_register_new_user(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/auth/register", json={"username": "TEST_user_001", "password": "test123"})
        assert r.status_code == 200
        data = r.json()
        assert "username" in data
        assert data["username"] == "TEST_user_001"


# ── Signals Tests ─────────────────────────────────────────────────────────────
class TestSignals:
    def test_list_signals(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/signals")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_signals_filter_by_status(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/signals?status=open")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for sig in data:
            assert sig.get("status") == "open"

    def test_signals_unauthenticated(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/signals")
        assert r.status_code in [401, 403]


# ── Bot Status ────────────────────────────────────────────────────────────────
class TestBotStatus:
    def test_bot_status(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/bot/status")
        assert r.status_code == 200
        data = r.json()
        assert "paused" in data
        assert "active_mode" in data
        assert "open_positions" in data
        assert isinstance(data["open_positions"], int)

    def test_bot_pause_resume(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/bot/pause")
        assert r.status_code == 200
        assert r.json()["paused"] == True
        # Resume
        r = auth_session.post(f"{BASE_URL}/api/bot/resume")
        assert r.status_code == 200
        assert r.json()["paused"] == False


# ── Config Tests ──────────────────────────────────────────────────────────────
class TestConfig:
    def test_get_config(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/config")
        assert r.status_code == 200
        data = r.json()
        assert "max_open_positions" in data
        assert "max_margin" in data
        assert "default_leverage" in data

    def test_update_config(self, auth_session):
        r = auth_session.put(f"{BASE_URL}/api/config", json={"max_open_positions": 3})
        assert r.status_code == 200
        assert r.json()["ok"] == True


# ── Performance ───────────────────────────────────────────────────────────────
class TestPerformance:
    def test_get_performance(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/performance")
        assert r.status_code == 200
        data = r.json()
        assert "total_trades" in data
        assert "win_rate" in data
        assert "net_pnl" in data

    def test_equity_curve(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/performance/equity")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Exchanges ─────────────────────────────────────────────────────────────────
class TestExchanges:
    def test_list_exchanges(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/exchanges")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        names = [e["name"] for e in data]
        assert "demo" in names


# ── Dashboard ─────────────────────────────────────────────────────────────────
class TestDashboard:
    def test_dashboard_stats(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "today_signals" in data
        assert "open_positions" in data
        assert "win_rate" in data
