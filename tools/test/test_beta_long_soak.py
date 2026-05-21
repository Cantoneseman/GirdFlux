#!/usr/bin/env python3
"""Helper tests for the beta long-soak wrapper."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import run_beta_long_soak


def base_args(**overrides):
    values = {
        "build_dir": "build",
        "duration_seconds": 0.0,
        "iterations": 1,
        "profile": "tiny",
        "include_token": False,
        "include_tls": False,
        "include_data_tls": False,
        "json_output": "",
        "event_log_dir": "",
        "results_dir": "tools/perf/results",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_standard_profile_includes_security_cases() -> None:
    names = [case.name for case in run_beta_long_soak.cases_for_profile("standard")]
    expected = [
        "stor",
        "retr",
        "stor_resume",
        "retr_resume",
        "tree_upload",
        "tree_download",
        "token_auth",
        "control_tls",
        "data_tls",
    ]
    if names != expected:
        raise AssertionError(f"unexpected standard profile: {names}")


def test_optional_cases_extend_tiny_profile() -> None:
    names = [
        case.name
        for case in run_beta_long_soak.cases_for_profile(
            "tiny",
            include_token=True,
            include_tls=True,
            include_data_tls=True,
        )
    ]
    for expected in ["stor", "retr", "token_auth", "control_tls", "data_tls"]:
        if expected not in names:
            raise AssertionError(f"missing optional case {expected}: {names}")


def test_run_soak_summarizes_fake_cases() -> None:
    with tempfile.TemporaryDirectory(prefix="gridflux-beta-soak-test.") as temp:
        root = Path(temp)
        args = base_args(
            results_dir=str(root / "results"),
            event_log_dir=str(root / "events"),
            json_output=str(root / "summary.json"),
        )
        original_run = run_beta_long_soak.subprocess.run

        class FakeCompleted:
            returncode = 0
            stdout = "gridflux smoke passed total_bytes=4096\n"
            stderr = ""

        def fake_run(*_args, **_kwargs):
            return FakeCompleted()

        run_beta_long_soak.subprocess.run = fake_run
        try:
            code = run_beta_long_soak.run_soak(args)
        finally:
            run_beta_long_soak.subprocess.run = original_run
        if code != 0:
            raise AssertionError("fake beta soak should pass")
        payload = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        if payload.get("result") != "pass" or payload.get("pass_count") != 2:
            raise AssertionError(f"unexpected summary: {payload}")
        if payload.get("total_bytes") != 8192:
            raise AssertionError(f"total_bytes was not aggregated: {payload}")
        if not payload.get("event_log_paths"):
            raise AssertionError(f"missing runner event logs: {payload}")


def main() -> int:
    test_standard_profile_includes_security_cases()
    test_optional_cases_extend_tiny_profile()
    test_run_soak_summarizes_fake_cases()
    print("beta long soak helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
