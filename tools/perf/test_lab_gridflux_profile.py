#!/usr/bin/env python3
"""Helper tests for the lab GridFlux profile wrapper."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_runner():
    path = ROOT / "tools" / "perf" / "run_lab_gridflux_profile.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def args(profile: str, *, repeat: int | None = None) -> argparse.Namespace:
    runner = load_runner()
    size, default_repeat = runner.profile_defaults(profile)
    return argparse.Namespace(
        profile=profile,
        size=size,
        repeat=default_repeat if repeat is None else repeat,
        output_dir="tools/perf/results",
        remote="gridflux-lab-small",
        server_host="192.168.100.2",
        local_build_dir="/home/Su/projects/GridFlux/build",
        remote_build_dir="/home/Su/projects/GridFlux/build",
        run_root_base="",
        case_timeout=1800,
        manifest_flush_intervals=runner.default_manifest_flush_intervals(profile),
        skip_cleanup=False,
    )


def flag_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_profile_case_counts() -> None:
    runner = load_runner()
    assert len(runner.profile_cases("quick")) == 4
    assert runner.expanded_row_count("quick", 1) == 4
    assert len(runner.profile_cases("focused")) == 6
    assert runner.expanded_row_count("focused", 1) == 6
    assert len(runner.profile_cases("release")) == 16
    assert runner.expanded_row_count("release", 2) == 32
    assert runner.expanded_row_count("release", 3) == 48
    assert len(runner.profile_cases("final-verify")) == 8
    assert runner.expanded_row_count("final-verify", 1) == 8
    assert len(runner.profile_cases("heavy")) == 30
    assert runner.expanded_row_count("heavy", 3) == 90
    assert len(runner.profile_cases("manifest-flush")) == 22
    assert runner.expanded_row_count("manifest-flush", 1) == 22
    assert len(runner.profile_cases("manifest-flush", [16, 64, 256, 1024])) == 44
    assert runner.expanded_row_count("manifest-flush", 1, [16, 64, 256, 1024]) == 44
    assert len(runner.profile_cases("manifest-flush-20gib")) == 8
    assert runner.expanded_row_count("manifest-flush-20gib", 1) == 8
    assert len(runner.profile_cases("manifest-flush-20gib", [16, 64, 256, 1024])) == 16
    assert runner.expanded_row_count("manifest-flush-20gib", 1, [16, 64, 256, 1024]) == 16


def test_no_none_verified_chunks_profile_cases() -> None:
    runner = load_runner()
    for profile in (
        "quick",
        "focused",
        "release",
        "final-verify",
        "heavy",
        "manifest-flush",
        "manifest-flush-20gib",
    ):
        for case in runner.profile_cases(profile):
            assert not (
                case.checksum == "none" and case.final_verify_policy == "verified_chunks"
            )


def test_quick_profile_exact_cases_and_commands() -> None:
    runner = load_runner()
    cases = runner.profile_cases("quick")
    assert [(case.direction, case.checksum, case.final_verify_policy, case.connections) for case in cases] == [
        ("stor", "none", "full", 1),
        ("stor", "crc32c", "full", 4),
        ("retr", "none", "full", 4),
        ("retr", "crc32c", "full", 4),
    ]
    specs = runner.build_step_specs(args("quick"), "DRYRUN", Path("out"))
    assert len(specs) == 4
    first = specs[0].command
    assert flag_value(first, "--directions") == "stor"
    assert flag_value(first, "--checksums") == "none"
    assert flag_value(first, "--connections") == "1"
    assert flag_value(first, "--final-verify-policies") == "full"
    for spec in specs:
        command = spec.command
        assert flag_value(command, "--file-io-backends") == "posix"
        assert flag_value(command, "--tls-modes") == "off"
        assert flag_value(command, "--data-tls-modes") == "off"
        assert flag_value(command, "--receiver-write-profiles") == "default"
        assert flag_value(command, "--receiver-write-yield-policies") == "none"
        assert flag_value(command, "--repeat") == "1"
        assert "--manifest-flush-interval-chunks-list" not in command


def test_release_and_heavy_dimensions() -> None:
    runner = load_runner()
    release = runner.profile_cases("release")
    assert sum(1 for case in release if case.checksum == "none") == 6
    assert sum(1 for case in release if case.checksum == "crc32c" and case.final_verify_policy == "full") == 6
    assert sum(1 for case in release if case.checksum == "crc32c" and case.final_verify_policy == "verified_chunks") == 4
    assert {case.connections for case in release if case.final_verify_policy == "verified_chunks"} == {4, 16}

    heavy = runner.profile_cases("heavy")
    assert {case.connections for case in heavy} == {1, 4, 8, 16, 32}
    assert sum(1 for case in heavy if case.checksum == "none") == 10
    assert sum(1 for case in heavy if case.checksum == "crc32c" and case.final_verify_policy == "full") == 10
    assert sum(1 for case in heavy if case.checksum == "crc32c" and case.final_verify_policy == "verified_chunks") == 10


def test_final_verify_profile_exact_cases_and_commands() -> None:
    runner = load_runner()
    cases = runner.profile_cases("final-verify")
    assert [(case.direction, case.checksum, case.final_verify_policy, case.connections) for case in cases] == [
        ("stor", "crc32c", "full", 1),
        ("stor", "crc32c", "verified_chunks", 1),
        ("stor", "crc32c", "full", 4),
        ("stor", "crc32c", "verified_chunks", 4),
        ("retr", "crc32c", "full", 4),
        ("retr", "crc32c", "verified_chunks", 4),
        ("retr", "crc32c", "full", 16),
        ("retr", "crc32c", "verified_chunks", 16),
    ]
    specs = runner.build_step_specs(args("final-verify"), "DRYRUN", Path("out"))
    assert len(specs) == 8
    assert {flag_value(spec.command, "--checksums") for spec in specs} == {"crc32c"}
    assert {flag_value(spec.command, "--final-verify-policies") for spec in specs} == {
        "full",
        "verified_chunks",
    }
    assert {flag_value(spec.command, "--connections") for spec in specs} == {"1", "4", "16"}
    assert all("--manifest-flush-interval-chunks-list" not in spec.command for spec in specs)


def test_manifest_flush_profile_dimensions_and_intervals() -> None:
    runner = load_runner()
    cases = runner.profile_cases("manifest-flush")
    assert len(cases) == 22
    assert {case.manifest_flush_interval_chunks for case in cases} == {16, 256}
    assert sum(1 for case in cases if case.direction == "stor") == 10
    assert sum(1 for case in cases if case.direction == "retr") == 12
    assert sum(1 for case in cases if case.checksum == "none") == 6
    assert sum(1 for case in cases if case.checksum == "crc32c" and case.final_verify_policy == "full") == 8
    assert sum(1 for case in cases if case.checksum == "crc32c" and case.final_verify_policy == "verified_chunks") == 8

    expanded = runner.profile_cases("manifest-flush", [16, 64, 256, 1024])
    assert len(expanded) == 44
    assert {case.manifest_flush_interval_chunks for case in expanded} == {16, 64, 256, 1024}

    subset = runner.profile_cases("manifest-flush-20gib")
    assert len(subset) == 8
    assert {case.manifest_flush_interval_chunks for case in subset} == {16, 256}
    assert {case.connections for case in subset} == {1, 16}
    specs = runner.build_step_specs(args("manifest-flush-20gib"), "DRYRUN", Path("out"))
    assert len(specs) == 8
    assert {flag_value(spec.command, "--manifest-flush-interval-chunks-list") for spec in specs} == {
        "16",
        "256",
    }


def test_default_manifest_flush_interval_is_256_when_unspecified() -> None:
    runner = load_runner()
    assert runner.default_manifest_flush_intervals("quick") == [256]
    assert runner.default_manifest_flush_intervals("release") == [256]
    quick_cases = runner.profile_cases("quick")
    assert all(case.manifest_flush_interval_chunks == 256 for case in quick_cases)
    specs = runner.build_step_specs(args("quick"), "DRYRUN", Path("out"))
    for spec in specs:
        assert "--manifest-flush-interval-chunks-list" not in spec.command


def main() -> int:
    test_profile_case_counts()
    test_no_none_verified_chunks_profile_cases()
    test_quick_profile_exact_cases_and_commands()
    test_release_and_heavy_dimensions()
    test_final_verify_profile_exact_cases_and_commands()
    test_manifest_flush_profile_dimensions_and_intervals()
    test_default_manifest_flush_interval_is_256_when_unspecified()
    print("lab gridflux profile helper tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
