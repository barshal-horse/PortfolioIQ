"""End-to-end API smoke test against a running backend (localhost:8000).

Covers the full user journey: register -> login -> portfolio -> holdings ->
risk -> benchmark -> health -> stress -> news -> report -> copilot session.
"""
import json
import sys
import time
import uuid

import requests

BASE = "http://localhost:8000/api/v1"
EMAIL = f"smoke_{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "SmokeTest123!"


def section(name):
    print(f"\n=== {name} ===")


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def main():
    ok = True
    s = requests.Session()

    # ── Auth ────────────────────────────────────────────────
    section("AUTH")
    r = s.post(f"{BASE}/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "full_name": "Smoke Tester", "base_currency": "USD"})
    ok &= check("register", r.status_code == 201, f"{r.status_code}")
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    ok &= check("login", r.status_code == 200)
    token = r.json()["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    r = s.get(f"{BASE}/auth/me", headers=H)
    ok &= check("auth/me", r.status_code == 200)
    user_id = r.json()["data"]["id"]

    # ── Portfolio + holdings ────────────────────────────────
    section("PORTFOLIO")
    r = s.post(f"{BASE}/portfolios", headers=H, json={
        "name": "Smoke Portfolio", "description": "E2E", "benchmark": "SP500", "base_currency": "USD"})
    ok &= check("create portfolio", r.status_code in (200, 201))
    pid = r.json()["data"]["id"]

    holdings = [
        {"ticker": "AAPL", "quantity": 10, "average_cost": 150, "currency": "USD"},
        {"ticker": "MSFT", "quantity": 5, "average_cost": 300, "currency": "USD"},
        {"ticker": "JPM", "quantity": 8, "average_cost": 140, "currency": "USD"},
    ]
    r = s.post(f"{BASE}/portfolios/{pid}/holdings/bulk", headers=H,
               json={"holdings": holdings, "mode": "merge"})
    ok &= check("bulk holdings", r.status_code in (200, 201), f"{r.status_code}")

    # ── Analytics (requires yfinance network) ───────────────
    section("ANALYTICS (network-dependent)")
    r = s.get(f"{BASE}/portfolios/{pid}/valuation?period=1mo", headers=H)
    val_ok = r.status_code == 200
    ok &= check("valuation", val_ok, f"{r.status_code} {r.text[:120] if not val_ok else ''}")

    r = s.get(f"{BASE}/portfolios/{pid}/risk?lookback_days=252", headers=H)
    ok &= check("risk metrics", r.status_code == 200, f"{r.status_code}")

    r = s.get(f"{BASE}/portfolios/{pid}/risk/contributions", headers=H)
    ok &= check("risk contributions", r.status_code == 200, f"{r.status_code}")

    r = s.get(f"{BASE}/portfolios/{pid}/benchmark?lookback_days=252", headers=H)
    ok &= check("benchmark comparison", r.status_code == 200, f"{r.status_code}")

    r = s.get(f"{BASE}/portfolios/{pid}/health", headers=H)
    ok &= check("health score", r.status_code == 200, f"{r.status_code}")

    # ── Stress testing ──────────────────────────────────────
    section("STRESS TESTING")
    r = s.get(f"{BASE}/portfolios/stress-test/scenarios", headers=H)
    ok &= check("scenarios list", r.status_code == 200)
    r = s.post(f"{BASE}/portfolios/{pid}/stress-test", headers=H,
               json={"scenarios": ["covid_2020"]})
    ok &= check("run stress test", r.status_code == 200, f"{r.status_code}")
    r = s.get(f"{BASE}/portfolios/{pid}/stress-test/history", headers=H)
    ok &= check("stress history", r.status_code == 200)

    # ── News (requires news API keys for refresh) ───────────
    section("NEWS")
    r = s.get(f"{BASE}/news/portfolio/{pid}?days=7", headers=H)
    ok &= check("portfolio news query", r.status_code == 200, f"{r.status_code}")
    r = s.post(f"{BASE}/news/portfolio/{pid}/refresh?days=7", headers=H)
    # 200 with keys; may be empty counts without — but must NOT 500
    ok &= check("news refresh (no 500)", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    r = s.get(f"{BASE}/news/sentiment/portfolio/{pid}?days=7", headers=H)
    ok &= check("portfolio sentiment", r.status_code == 200)

    # ── Reports (previously 100% broken) ────────────────────
    section("REPORTS")
    r = s.post(f"{BASE}/reports/generate?portfolio_id={pid}", headers=H,
               json={"report_type": "executive_summary", "parameters": {}})
    rep_ok = r.status_code in (200, 201)
    ok &= check("generate report", rep_ok, f"{r.status_code} {r.text[:200] if not rep_ok else ''}")
    if rep_ok:
        rid = r.json()["data"]["report_id"]
        # Poll for completion
        final_status = "generating"
        for _ in range(30):
            time.sleep(1)
            sr = s.get(f"{BASE}/reports/{rid}/status", headers=H)
            final_status = sr.json()["data"]["status"]
            if final_status != "generating":
                break
        ok &= check("report completes", final_status == "completed", final_status)
        if final_status == "completed":
            dr = s.get(f"{BASE}/reports/{rid}/download", headers=H)
            pdf_ok = dr.status_code == 200 and dr.content[:5] == b"%PDF-"
            ok &= check("download PDF (valid header)", pdf_ok,
                        f"{dr.status_code}, {len(dr.content)} bytes")
        lr = s.get(f"{BASE}/reports", headers=H)
        ok &= check("list reports", lr.status_code == 200)

    # ── Copilot (works without Gemini key: graceful fallback) ──
    section("COPILOT")
    r = s.post(f"{BASE}/copilot/sessions", headers=H, json={"portfolio_id": pid, "title": "Smoke"})
    cop_ok = r.status_code in (200, 201)
    ok &= check("create session", cop_ok, f"{r.status_code} {r.text[:150] if not cop_ok else ''}")
    if cop_ok:
        sid = r.json()["data"]["id"]
        mr = s.post(f"{BASE}/copilot/sessions/{sid}/messages", headers=H,
                    json={"content": "What is my portfolio health score?"})
        ok &= check("send message (no 500)", mr.status_code == 200,
                    f"{mr.status_code} {mr.text[:200] if mr.status_code != 200 else ''}")
        sr = s.get(f"{BASE}/copilot/sessions/{sid}/messages", headers=H)
        ok &= check("get messages", sr.status_code == 200)
        # SSE stream endpoint
        strm = s.post(f"{BASE}/copilot/sessions/{sid}/messages/stream", headers=H,
                      json={"content": "hello"}, stream=True, timeout=60)
        ok &= check("stream endpoint (no 500)", strm.status_code == 200,
                    f"{strm.status_code}")
        strm.close()

    print("\n" + "=" * 50)
    print("SMOKE RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
