#!/usr/bin/env python3
"""Plot cloud disk/writeback bottleneck proof charts."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "perf" / "figures"
CJK_AVAILABLE = False


def read_csv(path_text: str | Path) -> list[dict[str, str]]:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str] | None, field: str) -> float:
    if not row:
        return 0.0
    try:
        value = float(row.get(field, "") or "0")
        return 0.0 if math.isnan(value) or math.isinf(value) else value
    except ValueError:
        return 0.0


def configure_style() -> None:
    global CJK_AVAILABLE
    preferred = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Zen Hei",
        "SimHei",
        "Microsoft YaHei",
        "Arial Unicode MS",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    selected = next((name for name in preferred if name in available), "")
    CJK_AVAILABLE = bool(selected)
    plt.rcParams.update(
        {
            "font.family": [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.figsize": (10.5, 6.0),
            "axes.facecolor": "#f8f8f6",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def label(en: str, zh: str) -> str:
    return f"{en} / {zh}" if CJK_AVAILABLE else en


def metrics(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("metric", ""): row for row in rows}


def metric_value(by_metric: dict[str, dict[str, str]], name: str) -> float:
    return number(by_metric.get(name), "value")


def scope_caption(by_metric: dict[str, dict[str, str]]) -> str:
    scope = by_metric.get("run_size_scope", {}).get("value", "")
    if scope == "focused_long_file":
        return label(
            "Formal attribution: focused 1GiB/4GiB repeat=3; 64MiB smoke is excluded from proof.",
            "正式归因：1GiB/4GiB repeat=3 focused；64MiB smoke 不作为瓶颈结论。",
        )
    return label(
        "Smoke only: short-file/page-cache effects; do not use as formal disk/writeback proof.",
        "仅 smoke：短文件/page cache 影响明显，不作为正式硬盘/writeback 证明。",
    )


def add_scope_caption(fig: plt.Figure, by_metric: dict[str, dict[str, str]]) -> None:
    fig.text(0.5, -0.02, scope_caption(by_metric), ha="center", fontsize=10)


def save(fig: plt.Figure, output_dir: Path, stem: str, fmt: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = ["png", "svg"] if fmt == "both" else [fmt]
    paths: list[Path] = []
    for extension in formats:
        path = output_dir / f"{stem}.{extension}"
        fig.savefig(path, dpi=160 if extension == "png" else None, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def add_bar_labels(ax: plt.Axes, values: list[float], *, suffix: str = "G", digits: int = 2) -> None:
    ymax = max(values or [0.0])
    offset = max(ymax * 0.025, 0.04)
    for index, value in enumerate(values):
        if value <= 0.0:
            continue
        ax.text(index, value + offset, f"{value:.{digits}f}{suffix}", ha="center", va="bottom", fontsize=9)


def network_vs_stor(by_metric: dict[str, dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    labels = ["TCP c->s best", "TCP s->c best", "STOR median", "STOR best"]
    values = [
        metric_value(by_metric, "network_client_to_server_best_gbps"),
        metric_value(by_metric, "network_server_to_client_best_gbps"),
        metric_value(by_metric, "stor_e2e_median_gbps"),
        metric_value(by_metric, "stor_e2e_best_gbps"),
    ]
    fig, ax = plt.subplots()
    ax.bar(range(len(values)), values, color=["#4575b4", "#74add1", "#dd7f27", "#fdae61"])
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Gbps")
    ax.set_title(label("Network baseline vs GridFlux STOR", "网络上限 vs GridFlux STOR"))
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.set_ylim(0, max(values or [1.0]) * 1.25 if max(values or [0.0]) > 0 else 1.0)
    add_bar_labels(ax, values)
    add_scope_caption(fig, by_metric)
    return save(fig, output_dir, "cloud_disk_network_vs_stor", fmt)


def storage_vs_stor(by_metric: dict[str, dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    labels = ["storage write", "storage read", "STOR e2e", "STOR temp-write"]
    values = [
        metric_value(by_metric, "storage_write_median_gbps"),
        metric_value(by_metric, "storage_read_median_gbps"),
        metric_value(by_metric, "stor_e2e_median_gbps"),
        metric_value(by_metric, "stor_temp_write_median_gbps"),
    ]
    fig, ax = plt.subplots()
    ax.bar(range(len(values)), values, color=["#7f9f35", "#a6d96a", "#dd7f27", "#2f9e68"])
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Gbps")
    ax.set_title(label("Storage write/read vs STOR", "存储读写 vs STOR"))
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.set_ylim(0, max(values or [1.0]) * 1.25 if max(values or [0.0]) > 0 else 1.0)
    add_bar_labels(ax, values)
    add_scope_caption(fig, by_metric)
    return save(fig, output_dir, "cloud_disk_storage_vs_stor", fmt)


def stor_stage_breakdown(by_metric: dict[str, dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    shares = [
        metric_value(by_metric, "stor_temp_write_share_median") * 100.0,
        metric_value(by_metric, "stor_data_receive_share_median") * 100.0,
    ]
    other = max(0.0, 100.0 - sum(shares))
    values = [shares[0], shares[1], other]
    labels = ["temp_write", "data_receive", "other"]
    fig, ax = plt.subplots()
    ax.bar(range(len(values)), values, color=["#dd7f27", "#4575b4", "#bdbdbd"])
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Wall share %")
    ax.set_title(label("STOR stage wall-share median", "STOR 阶段耗时占比 median"))
    ax.set_ylim(0, 100)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    add_bar_labels(ax, values, suffix="%", digits=1)
    add_scope_caption(fig, by_metric)
    return save(fig, output_dir, "cloud_disk_stage_breakdown", fmt)


def checksum_context(by_metric: dict[str, dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    labels = ["CRC32C hardware", "CRC32C software", "STOR median"]
    values = [
        metric_value(by_metric, "checksum_hardware_best_gbps"),
        metric_value(by_metric, "checksum_software_median_gbps"),
        metric_value(by_metric, "stor_e2e_median_gbps"),
    ]
    fig, ax = plt.subplots()
    ax.bar(range(len(values)), values, color=["#2f9e68", "#74c476", "#dd7f27"])
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Gbps")
    ax.set_title(label("CRC32C benchmark context", "CRC32C benchmark 对照"))
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.set_ylim(0, max(values or [1.0]) * 1.25 if max(values or [0.0]) > 0 else 1.0)
    add_bar_labels(ax, values)
    add_scope_caption(fig, by_metric)
    return save(fig, output_dir, "cloud_disk_checksum_context", fmt)


def retr_stage_breakdown(by_metric: dict[str, dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    shares = [
        metric_value(by_metric, "retr_download_temp_write_share_median") * 100.0,
        metric_value(by_metric, "retr_network_send_share_median") * 100.0,
    ]
    other = max(0.0, 100.0 - sum(shares))
    values = [shares[0], shares[1], other]
    labels = ["download_temp_write", "network_send", "other"]
    fig, ax = plt.subplots()
    ax.bar(range(len(values)), values, color=["#dd7f27", "#4575b4", "#bdbdbd"])
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Wall share %")
    ax.set_title(label("RETR stage wall-share median", "RETR 阶段耗时占比 median"))
    ax.set_ylim(0, 100)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    add_bar_labels(ax, values, suffix="%", digits=1)
    add_scope_caption(fig, by_metric)
    return save(fig, output_dir, "cloud_disk_retr_stage_breakdown", fmt)


def plot_all(summary_csv: str | Path, output_dir: str | Path = DEFAULT_OUTPUT_DIR, fmt: str = "both") -> list[Path]:
    configure_style()
    by_metric = metrics(read_csv(summary_csv))
    output = Path(output_dir)
    if not output.is_absolute():
        output = ROOT / output
    paths: list[Path] = []
    paths.extend(network_vs_stor(by_metric, output, fmt))
    paths.extend(storage_vs_stor(by_metric, output, fmt))
    paths.extend(stor_stage_breakdown(by_metric, output, fmt))
    paths.extend(checksum_context(by_metric, output, fmt))
    paths.extend(retr_stage_breakdown(by_metric, output, fmt))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-csv", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["png", "svg", "both"], default="both")
    args = parser.parse_args()
    for path in plot_all(args.summary_csv, args.output_dir, args.format):
        try:
            rendered = path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            rendered = str(path.resolve())
        print(f"figure={rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
