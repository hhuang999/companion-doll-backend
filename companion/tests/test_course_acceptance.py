from argparse import Namespace

from companion.tools.course_acceptance import run


def test_idle_end_replay_records_closed_session_after_registry_eviction(tmp_path):
    report = run(
        Namespace(
            config_dir=None,
            env_file=tmp_path / "unused.env",
            output=tmp_path / "replay",
            only="N08",
            final=False,
            fake=True,
        )
    )
    scenario = report["scenarios"][0]
    assert not scenario["errors"]
    assert scenario["samples"][-1]["input"]["kind"] == "idle_end"
    assert scenario["samples"][-1]["state"]["lifecycle"] == "closed"
    assert scenario["automatic_checks"]["end_done"]
