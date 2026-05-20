#!/usr/bin/env python3
"""Generate comparison charts for the final FTP/GridFTP/GridFlux run."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY = ROOT / "tools" / "perf" / "results" / "20260520T120942Z_ftp-gridftp-gridflux-summary.csv"
DEFAULT_HOST_BASELINE = ROOT / "tools" / "perf" / "results" / "20260520T120942Z_three-way-host-baseline.csv"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "perf" / "figures"
TEN_GB_BYTES = 10_000_000_000

PROTOCOL_LABELS = {
    "plain_ftp": "FTP",
    "native_gridftp": "native GridFTP",
    "gridflux": "GridFlux",
}

PROTOCOL_COLORS = {
    "plain_ftp": "#7f8c8d",
    "native_gridftp": "#1f77b4",
    "gridflux": "#d35400",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: str) -> float:
    try:
        return float(value or "0")
    except ValueError:
        return 0.0


def valid_summary_rows(path: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    return [
        row
        for row in rows
        if row.get("fail_count", "0") == "0" and row.get("sha256_mismatch_count", "0") == "0"
    ]


def find_best_row(
    rows: list[dict[str, str]],
    *,
    protocol: str,
    direction: str,
    size_bytes: int,
    checksum: str | None = None,
) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row.get("protocol") == protocol
        and row.get("direction") == direction
        and row.get("size_bytes") == str(size_bytes)
        and (checksum is None or row.get("checksum", "") == checksum)
    ]
    if not matches:
        raise ValueError(f"missing summary rows for {protocol} {direction} {size_bytes} checksum={checksum}")
    return max(matches, key=lambda row: to_float(row.get("best_Gbps", "0")))


def estimate_seconds(gbps_value: float) -> float:
    if gbps_value <= 0:
        return 0.0
    return TEN_GB_BYTES * 8 / (gbps_value * 1_000_000_000)


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.figsize": (10.5, 6.2),
            "axes.titlesize": 16,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "axes.facecolor": "#f7f7f5",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def add_value_labels(ax: plt.Axes, values: list[float], *, suffix: str, decimals: int = 3) -> None:
    ymax = max(values) if values else 0.0
    offset = max(ymax * 0.02, 0.03)
    for index, value in enumerate(values):
        ax.text(index, value + offset, f"{value:.{decimals}f}{suffix}", ha="center", va="bottom", fontsize=10)


def save_figure(fig: plt.Figure, output_dir: Path, stem: str, fmt: str) -> list[Path]:
    outputs: list[Path] = []
    formats = ["png", "svg"] if fmt == "both" else [fmt]
    for extension in formats:
        path = output_dir / f"{stem}.{extension}"
        fig.savefig(path, dpi=160 if extension == "png" else None, bbox_inches="tight")
        outputs.append(path)
    plt.close(fig)
    return outputs


def plot_1g_upload(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    selected = [
        find_best_row(rows, protocol="plain_ftp", direction="upload", size_bytes=1073741824),
        find_best_row(rows, protocol="native_gridftp", direction="upload", size_bytes=1073741824),
        find_best_row(rows, protocol="gridflux", direction="stor", size_bytes=1073741824),
    ]
    values = [to_float(row["best_Gbps"]) for row in selected]
    labels = [PROTOCOL_LABELS[row["protocol"]] for row in selected]
    colors = [PROTOCOL_COLORS[row["protocol"]] for row in selected]
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=colors, width=0.62)
    ax.set_ylabel("Best throughput (Gbps)")
    ax.set_title("1GiB upload / STOR best throughput")
    ax.set_ylim(0, max(values) * 1.25)
    add_value_labels(ax, values, suffix=" Gbps")
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    fig.text(
        0.5,
        -0.02,
        "Fair headline view: 1GiB runs reduce short-file cache distortion. GridFlux is effectively tied with native GridFTP here.",
        ha="center",
        fontsize=10,
    )
    return save_figure(fig, output_dir, "three_way_1g_upload_best", fmt)


def plot_1g_download(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    selected = [
        find_best_row(rows, protocol="plain_ftp", direction="download", size_bytes=1073741824),
        find_best_row(rows, protocol="native_gridftp", direction="download", size_bytes=1073741824),
        find_best_row(rows, protocol="gridflux", direction="retr", size_bytes=1073741824),
    ]
    values = [to_float(row["best_Gbps"]) for row in selected]
    labels = [PROTOCOL_LABELS[row["protocol"]] for row in selected]
    colors = [PROTOCOL_COLORS[row["protocol"]] for row in selected]
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=colors, width=0.62)
    ax.set_ylabel("Best throughput (Gbps)")
    ax.set_title("1GiB download / RETR best throughput")
    ax.set_ylim(0, max(values) * 1.20)
    add_value_labels(ax, values, suffix=" Gbps")
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    fig.text(
        0.5,
        -0.02,
        "GridFlux's strongest fair comparison in this run is 1GiB RETR, where it clearly leads the two baselines.",
        ha="center",
        fontsize=10,
    )
    return save_figure(fig, output_dir, "three_way_1g_download_best", fmt)


def plot_10gb_estimate(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    uploads = [
        find_best_row(rows, protocol="plain_ftp", direction="upload", size_bytes=1073741824),
        find_best_row(rows, protocol="native_gridftp", direction="upload", size_bytes=1073741824),
        find_best_row(rows, protocol="gridflux", direction="stor", size_bytes=1073741824),
    ]
    downloads = [
        find_best_row(rows, protocol="plain_ftp", direction="download", size_bytes=1073741824),
        find_best_row(rows, protocol="native_gridftp", direction="download", size_bytes=1073741824),
        find_best_row(rows, protocol="gridflux", direction="retr", size_bytes=1073741824),
    ]
    upload_values = [estimate_seconds(to_float(row["best_Gbps"])) for row in uploads]
    download_values = [estimate_seconds(to_float(row["best_Gbps"])) for row in downloads]
    labels = [PROTOCOL_LABELS[row["protocol"]] for row in uploads]
    colors = [PROTOCOL_COLORS[row["protocol"]] for row in uploads]
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 6.0), sharey=False)
    for ax, title, values in [
        (axes[0], "10GB estimated upload / STOR time", upload_values),
        (axes[1], "10GB estimated download / RETR time", download_values),
    ]:
        ax.bar(labels, values, color=colors, width=0.62)
        ax.set_ylabel("Seconds")
        ax.set_title(title)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        add_value_labels(ax, values, suffix=" s", decimals=1)
    fig.text(0.5, -0.02, "Estimate uses 10 GB decimal size and the best 1GiB throughput for each protocol/direction.", ha="center", fontsize=10)
    return save_figure(fig, output_dir, "three_way_10gb_estimated_time", fmt)


def plot_baseline_context(host_rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    iperf_rows = [row for row in host_rows if row.get("kind") == "iperf3" and row.get("status") == "pass"]
    storage_rows = [row for row in host_rows if row.get("kind") == "storage" and row.get("status") == "pass"]
    iperf_rows.sort(key=lambda row: int(row.get("parallelism") or "0"))
    storage_rows.sort(key=lambda row: row.get("machine", ""))

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.0))
    iperf_labels = [f"p{row['parallelism']}" for row in iperf_rows]
    iperf_values = [to_float(row.get("Gbps", "0")) for row in iperf_rows]
    axes[0].bar(iperf_labels, iperf_values, color="#2c7fb8", width=0.62)
    axes[0].set_title("iperf3 private-network baseline")
    axes[0].set_ylabel("Gbps")
    axes[0].set_ylim(0, max(iperf_values) * 1.20)
    axes[0].grid(axis="y", linestyle="--", alpha=0.25)
    add_value_labels(axes[0], iperf_values, suffix=" Gbps")

    storage_labels = [row.get("machine", "").replace("_", " ") for row in storage_rows]
    storage_values = [to_float(row.get("MBps", "0")) for row in storage_rows]
    axes[1].bar(storage_labels, storage_values, color="#7a9e2f", width=0.62)
    axes[1].set_title("1GiB local write baseline")
    axes[1].set_ylabel("MB/s")
    axes[1].set_ylim(0, max(storage_values) * 1.25)
    axes[1].grid(axis="y", linestyle="--", alpha=0.25)
    add_value_labels(axes[1], storage_values, suffix=" MB/s", decimals=1)

    fig.text(
        0.5,
        -0.02,
        "Network headroom is about 15.5 Gbps, but local write is only about 128.6 MB/s (about 1.03 Gbps). This is key context for STOR limits.",
        ha="center",
        fontsize=10,
    )
    return save_figure(fig, output_dir, "three_way_baseline_context", fmt)


def plot_gridflux_short_vs_1g(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    selected = [
        ("256MiB STOR none", find_best_row(rows, protocol="gridflux", direction="stor", size_bytes=268435456, checksum="none"), "#f39c12"),
        ("256MiB RETR none", find_best_row(rows, protocol="gridflux", direction="retr", size_bytes=268435456, checksum="none"), "#f1c40f"),
        ("1GiB STOR best", find_best_row(rows, protocol="gridflux", direction="stor", size_bytes=1073741824), "#d35400"),
        ("1GiB RETR best", find_best_row(rows, protocol="gridflux", direction="retr", size_bytes=1073741824), "#1f77b4"),
    ]
    labels = [item[0] for item in selected]
    values = [to_float(item[1]["best_Gbps"]) for item in selected]
    colors = [item[2] for item in selected]
    fig, ax = plt.subplots(figsize=(11.8, 6.2))
    ax.bar(labels, values, color=colors, width=0.62)
    ax.set_ylabel("Best throughput (Gbps)")
    ax.set_title("GridFlux short-file peak vs 1GiB best")
    ax.set_ylim(0, max(values) * 1.18)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    add_value_labels(ax, values, suffix=" Gbps")
    ax.tick_params(axis="x", labelrotation=10)
    fig.text(
        0.5,
        -0.03,
        "256MiB peaks are short-file/page-cache observations only. They should not be presented as long-duration sustained throughput.",
        ha="center",
        fontsize=10,
    )
    return save_figure(fig, output_dir, "gridflux_short_vs_1g", fmt)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-csv", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--host-baseline-csv", default=str(DEFAULT_HOST_BASELINE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["png", "svg", "both"], default="both")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    summary_csv = Path(args.summary_csv).resolve()
    host_baseline_csv = Path(args.host_baseline_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    configure_style()
    summary_rows = valid_summary_rows(summary_csv)
    host_rows = read_csv_rows(host_baseline_csv)

    created: list[Path] = []
    created += plot_1g_upload(summary_rows, output_dir, args.format)
    created += plot_1g_download(summary_rows, output_dir, args.format)
    created += plot_10gb_estimate(summary_rows, output_dir, args.format)
    created += plot_baseline_context(host_rows, output_dir, args.format)
    created += plot_gridflux_short_vs_1g(summary_rows, output_dir, args.format)

    for path in created:
        print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
