import sys
from pathlib import Path

from companion.core.models import RiskResult, SessionState, TurnSignals
from streamlit.testing.v1 import AppTest


def test_dashboard_fresh_runtime_renders_risks_and_history(store, monkeypatch):
    state = SessionState(session_id="dashboard", user_key="synthetic-dashboard")
    store.create_session(state)
    identifier = store.add_input(state, "1", "synthetic test input", "user", TurnSignals())
    store.update_turn(identifier, stage="explore", mode="normal", latency={"gate_release_ms": 500})
    store.record_risk("dashboard", identifier, RiskResult(level="high", reason="synthetic test"))
    monkeypatch.setattr(sys, "argv", ["dashboard", "--db", str(store.path)])
    script = Path(__file__).parents[1] / "companion/dashboard/app.py"
    app = AppTest.from_file(str(script)).run(timeout=15)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["当前会话", "风险提醒", "后台分析", "运行统计"]
    assert any(error.value.startswith("#1 · high") for error in app.error)
    assert len(app.chat_message) == 1
    assert any(button.label == "标记为已处理" for button in app.button)
