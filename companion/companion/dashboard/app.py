"""Read-only browsing with one explicitly scoped risk acknowledgement mutation."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

parser = argparse.ArgumentParser()
parser.add_argument("--db", type=Path, default=Path("data/companion.db"))
args, _ = parser.parse_known_args()
db_path = args.db.resolve()
st.set_page_config(page_title="Companion · 后端观察台", page_icon="◌", layout="wide")


def read(sql: str, params: tuple = ()) -> list[dict]:
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, params)]


def acknowledge(event_id: int) -> None:
    with closing(sqlite3.connect(db_path, timeout=5)) as db, db:
        db.execute(
            "UPDATE risk_events SET handled=1,handled_at=? WHERE id=? AND handled=0",
            (datetime.now(timezone.utc).isoformat(), event_id),
        )


st.title("Companion · 后端观察台")
st.caption("对话、后台分析与风险事件 · 本地 SQLite · 每 2 秒刷新")
st.sidebar.caption("数据库")
st.sidebar.code(str(db_path))
st.sidebar.info("开发内容包含测试行动卡和待审核危机占位话术。模型与真机验收结果以验证报告为准。")
if not db_path.is_file():
    st.info("数据库尚未创建。先启动文字对话或运行剧本，再刷新此页。")
    st.stop()


@st.fragment(run_every="2s")
def dashboard() -> None:
    sessions = read(
        "SELECT session_id,user_key,started_at,lifecycle,summary,state FROM sessions ORDER BY started_at DESC LIMIT 100"
    )
    open_risks = read("SELECT COUNT(*) AS n FROM risk_events WHERE handled=0")[0]["n"]
    turns = read("SELECT COUNT(*) AS n FROM turns WHERE role='user'")[0]["n"]
    cols = st.columns(3)
    cols[0].metric("会话", len(sessions))
    cols[1].metric("用户轮次", turns)
    cols[2].metric("待处理风险", open_risks)
    conversation, risks, analysis, stats = st.tabs(["当前会话", "风险提醒", "后台分析", "运行统计"])
    with conversation:
        if not sessions:
            st.info("等待第一段对话。")
        else:
            chosen = st.selectbox(
                "会话",
                [s["session_id"] for s in sessions],
                format_func=lambda sid: next(
                    f"{s['user_key']} · {s['started_at'][:19]} · {s['lifecycle']}"
                    for s in sessions
                    if s["session_id"] == sid
                ),
            )
            selected = next(s for s in sessions if s["session_id"] == chosen)
            state = json.loads(selected["state"])
            left, right = st.columns([2, 1])
            with right:
                st.subheader("当前状态")
                st.json(
                    {
                        key: state.get(key)
                        for key in (
                            "stage",
                            "mode",
                            "generation",
                            "pending_offer",
                            "card_in_use",
                            "cards_used",
                        )
                    }
                )
                snapshots = read(
                    "SELECT data FROM snapshots WHERE session_id=? ORDER BY version DESC LIMIT 1",
                    (chosen,),
                )
                if snapshots:
                    with st.expander("最新快照"):
                        st.json(json.loads(snapshots[0]["data"]))
                if selected["summary"]:
                    st.caption(selected["summary"])
            with left:
                for row in read("SELECT * FROM turns WHERE session_id=? ORDER BY id", (chosen,)):
                    if row["role"] == "user":
                        with st.chat_message("user"):
                            st.write(row["text"])
                            st.caption(
                                f"#{row['id']} · {row['stage']} · {row['mode']} · snapshot {row['snapshot_version']}"
                            )
                            with st.expander("信号、延迟与违规"):
                                st.json(
                                    {
                                        key: json.loads(row[key])
                                        for key in ("signals", "latency", "violations")
                                    }
                                )
                    for output in read(
                        "SELECT data,status FROM outputs WHERE turn_id=? ORDER BY created_at",
                        (row["id"],),
                    ):
                        event = json.loads(output["data"])
                        with st.chat_message("assistant"):
                            st.write(event["text"] or f"练习计划：{event['plan']['script_id']}")
                            st.caption(
                                f"{output['status']} · {event['type']} · generation {event['generation']}"
                            )
    with risks:
        records = read("SELECT * FROM risk_events ORDER BY handled ASC,id DESC LIMIT 100")
        if not records:
            st.success("尚无风险事件。")
        for row in records:
            with st.container(border=True):
                label = (
                    f"#{row['id']} · {row['level']} · {row['category']} · {row['detection_status']}"
                )
                if row["handled"]:
                    st.caption(label + " · 已处理")
                else:
                    if row["level"] == "high":
                        st.error(label)
                    else:
                        st.warning(label)
                st.write(row["reason"])
                st.caption(f"会话 {row['session_id']} / 轮次 {row['turn_id']}")
                if not row["handled"] and st.button("标记为已处理", key=f"risk-{row['id']}"):
                    try:
                        acknowledge(row["id"])
                    except sqlite3.Error as error:
                        st.error(f"保存失败：{error}")
                    else:
                        st.rerun(scope="fragment")
    with analysis:
        records = read("SELECT * FROM reasoner_runs ORDER BY id DESC LIMIT 100")
        if records:
            st.dataframe(
                pd.DataFrame(records)[
                    [
                        "id",
                        "session_id",
                        "kind",
                        "triggers",
                        "source_turn_id",
                        "duration_ms",
                        "status",
                        "published_version",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )
            chosen_run = st.selectbox("查看运行详情", [r["id"] for r in records])
            row = next(r for r in records if r["id"] == chosen_run)
            st.json(
                {
                    "result": json.loads(row["result"] or "null"),
                    "rejected": json.loads(row["rejected"]),
                    "error": row["error"],
                }
            )
        else:
            st.info("尚无后台分析记录。")
    with stats:
        rows = read("SELECT latency,violations,mode,output_status FROM turns WHERE role='user'")
        if rows:
            frame = pd.DataFrame(
                [
                    {
                        **json.loads(r["latency"]),
                        "mode": r["mode"],
                        "violations": len(json.loads(r["violations"])),
                        "status": r["output_status"],
                    }
                    for r in rows
                ]
            )
            numbers = frame.select_dtypes(include="number").filter(regex="_ms$")
            if not numbers.empty:
                st.dataframe(
                    pd.DataFrame(
                        {
                            "样本数": numbers.count(),
                            "中位数 ms": numbers.median(),
                            "P90 ms": numbers.quantile(0.9),
                        }
                    ),
                    width="stretch",
                )
                if "gate_release_ms" in numbers:
                    st.line_chart(numbers[["gate_release_ms"]])
            st.metric("有违规记录的轮次比例", f"{frame['violations'].gt(0).mean():.1%}")
            usage = read(
                "SELECT card_id,COUNT(*) AS count FROM card_usage WHERE outcome='used' GROUP BY card_id"
            )
            if usage:
                st.bar_chart(pd.DataFrame(usage).set_index("card_id"))
        else:
            st.info("对话后会显示延迟分布和卡片统计。")


dashboard()
