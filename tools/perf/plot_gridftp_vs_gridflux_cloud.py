#!/usr/bin/env python3
"""Plot native GridFTP vs GridFlux cloud comparison charts."""

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
TEN_GIB = 10 * 1024**3
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


def integer(row: dict[str, str] | None, field: str) -> int:
    if not row:
        return 0
    try:
        return int(float(row.get(field, "") or "0"))
    except ValueError:
        return 0


def valid(row: dict[str, str]) -> bool:
    return integer(row, "fail_count") == 0 and integer(row, "sha256_mismatch_count") == 0


def size_label(size: int) -> str:
    if size % (1024**3) == 0:
        return f"{size // (1024**3)}GiB"
    if size % (1024**2) == 0:
        return f"{size // (1024**2)}MiB"
    return str(size)


def find_best(rows: list[dict[str, str]], *, protocol: str, direction: str, size: int, checksum: str = "") -> dict[str, str] | None:
    matches = [
        row
        for row in rows
        if valid(row)
        and row.get("protocol") == protocol
        and row.get("direction") == direction
        and row.get("size_bytes") == str(size)
        and (not checksum or row.get("checksum") == checksum)
        and (protocol != "gridflux" or (row.get("file_io_backend") == "posix" and row.get("tls_mode") == "off" and row.get("data_tls_mode") == "off"))
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: number(row, "best_Gbps"))


def find_median(rows: list[dict[str, str]], *, protocol: str, direction: str, size: int, p: int, checksum: str = "") -> float:
    matches = [
        row
        for row in rows
        if valid(row)
        and row.get("protocol") == protocol
        and row.get("direction") == direction
        and row.get("size_bytes") == str(size)
        and (row.get("parallelism") == str(p) or row.get("connections") == str(p))
        and (not checksum or row.get("checksum") == checksum)
        and (protocol != "gridflux" or (row.get("file_io_backend") == "posix" and row.get("tls_mode") == "off" and row.get("data_tls_mode") == "off"))
    ]
    return max([number(row, "median_Gbps") for row in matches] or [0.0])


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
    font_family = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    plt.rcParams.update(
        {
            "font.family": font_family,
            "axes.unicode_minus": False,
            "figure.figsize": (11.5, 6.4),
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.facecolor": "#f8f8f6",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def label(en: str, zh: str) -> str:
    return f"{en} / {zh}" if CJK_AVAILABLE else en


def add_labels(ax: plt.Axes, positions: list[float], values: list[float], *, suffix: str = "", digits: int = 2) -> None:
    ymax = max(values) if values else 0.0
    offset = max(ymax * 0.025, 0.03)
    for x, value in zip(positions, values, strict=False):
        if value <= 0.0:
            continue
        ax.text(x, value + offset, f"{value:.{digits}f}{suffix}", ha="center", va="bottom", fontsize=9)


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


def grouped_best_plot(rows: list[dict[str, str]], output_dir: Path, fmt: str, *, direction: str, gridflux_direction: str, stem: str, title: str) -> list[Path]:
    sizes = [1024**3, 10 * 1024**3]
    labels = [size_label(size) for size in sizes]
    series = [
        ("native GridFTP", "#2f6fbb", [number(find_best(rows, protocol="native_gridftp", direction=direction, size=size), "best_Gbps") for size in sizes]),
        ("GridFlux none", "#dd7f27", [number(find_best(rows, protocol="gridflux", direction=gridflux_direction, size=size, checksum="none"), "best_Gbps") for size in sizes]),
        ("GridFlux crc32c", "#2f9e68", [number(find_best(rows, protocol="gridflux", direction=gridflux_direction, size=size, checksum="crc32c"), "best_Gbps") for size in sizes]),
    ]
    fig, ax = plt.subplots()
    width = 0.24
    x_base = list(range(len(sizes)))
    all_values: list[float] = []
    for offset, (name, color, values) in zip([-width, 0.0, width], series, strict=False):
        xs = [x + offset for x in x_base]
        ax.bar(xs, values, width=width, label=name, color=color)
        add_labels(ax, xs, values, suffix="G")
        all_values.extend(values)
    ax.set_xticks(x_base)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Best throughput / Gbps")
    ax.set_title(title)
    ax.set_ylim(0, max(max(all_values or [0.0]), 1.0) * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.legend()
    fig.text(
        0.5,
        -0.02,
        label(
            "256MiB short-file rows are excluded from this headline chart; 1GiB/10GiB are better for stable comparisons.",
            "256MiB 短文件不进入该 headline 图；1GiB/10GiB 更适合展示稳定对比。",
        ),
        ha="center",
        fontsize=10,
    )
    return save(fig, output_dir, stem, fmt)


def scaling_plot(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    p_values = [1, 4, 8, 16]
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.8), sharey=False)
    configs = [
        (axes[0], "upload / STOR", "upload", "stor"),
        (axes[1], "download / RETR", "download", "retr"),
    ]
    for ax, title, native_direction, gridflux_direction in configs:
        ax.plot(p_values, [find_median(rows, protocol="native_gridftp", direction=native_direction, size=1024**3, p=p) for p in p_values], marker="o", label="native GridFTP", color="#2f6fbb")
        ax.plot(p_values, [find_median(rows, protocol="gridflux", direction=gridflux_direction, size=1024**3, p=p, checksum="none") for p in p_values], marker="o", label="GridFlux none", color="#dd7f27")
        ax.plot(p_values, [find_median(rows, protocol="gridflux", direction=gridflux_direction, size=1024**3, p=p, checksum="crc32c") for p in p_values], marker="o", label="GridFlux crc32c", color="#2f9e68")
        ax.set_title(f"1GiB {title} parallel scaling")
        ax.set_xlabel("parallelism / connections")
        ax.set_ylabel("Median throughput / Gbps")
        ax.set_xticks(p_values)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        ax.legend()
    fig.text(
        0.5,
        -0.02,
        label(
            "Scaling uses 1GiB medians; p16 flattening is not a 100G ceiling claim.",
            "Scaling 使用 1GiB median；p16 无提升时不代表 100G 上限。",
        ),
        ha="center",
        fontsize=10,
    )
    return save(fig, output_dir, "gridftp_vs_gridflux_parallel_scaling", fmt)


def baseline_plot(host_rows: list[dict[str, str]], checksum_rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.6))
    iperf = [row for row in host_rows if row.get("kind") == "iperf3" and row.get("status") == "pass"]
    storage = [row for row in host_rows if row.get("kind") == "storage" and row.get("status") == "pass"]
    checksum = [row for row in checksum_rows if row.get("status") == "pass"]

    iperf_labels = [f"{row.get('machine','')} p{row.get('parallelism','')}" for row in iperf]
    iperf_values = [number(row, "Gbps") for row in iperf]
    axes[0].bar(range(len(iperf_values)), iperf_values, color="#4575b4")
    axes[0].set_title(label("TCP baseline", "裸 TCP"))
    axes[0].set_ylabel("Gbps")
    axes[0].set_xticks(range(len(iperf_labels)))
    axes[0].set_xticklabels(iperf_labels, rotation=60, ha="right")
    axes[0].grid(axis="y", linestyle="--", alpha=0.25)

    storage_labels = [f"{row.get('machine','')} {row.get('operation','')} {size_label(int(row.get('size_bytes') or '0'))}" for row in storage]
    storage_values = [number(row, "Gbps") for row in storage]
    axes[1].bar(range(len(storage_values)), storage_values, color="#7f9f35")
    axes[1].set_title(label("Storage baseline", "本地读写"))
    axes[1].set_ylabel("Gbps equivalent")
    axes[1].set_xticks(range(len(storage_labels)))
    axes[1].set_xticklabels(storage_labels, rotation=60, ha="right")
    axes[1].grid(axis="y", linestyle="--", alpha=0.25)

    checksum_labels = [f"{row.get('machine','')} {row.get('backend','')}" for row in checksum]
    checksum_values = [number(row, "throughput_Gbps") for row in checksum]
    axes[2].bar(range(len(checksum_values)), checksum_values, color="#6a51a3")
    axes[2].set_title("CRC32C baseline")
    axes[2].set_ylabel("Gbps")
    axes[2].set_xticks(range(len(checksum_labels)))
    axes[2].set_xticklabels(checksum_labels, rotation=60, ha="right")
    axes[2].grid(axis="y", linestyle="--", alpha=0.25)
    fig.text(
        0.5,
        -0.02,
        label(
            "Baselines explain bottlenecks; storage Gbps is converted from MB/s.",
            "Baseline 用于解释瓶颈来源；storage Gbps 为 MB/s 换算值。",
        ),
        ha="center",
        fontsize=10,
    )
    return save(fig, output_dir, "gridftp_vs_gridflux_baseline_context", fmt)


def checksum_impact_plot(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    conns = [1, 4, 8, 16]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8), sharey=False)
    for ax, direction in [(axes[0], "stor"), (axes[1], "retr")]:
        none_values = [find_median(rows, protocol="gridflux", direction=direction, size=1024**3, p=conn, checksum="none") for conn in conns]
        crc_values = [find_median(rows, protocol="gridflux", direction=direction, size=1024**3, p=conn, checksum="crc32c") for conn in conns]
        ax.plot(conns, none_values, marker="o", label="checksum none", color="#dd7f27")
        ax.plot(conns, crc_values, marker="o", label="crc32c", color="#2f9e68")
        ax.set_title(f"1GiB GridFlux {direction.upper()} checksum impact")
        ax.set_xlabel("connections")
        ax.set_ylabel("Median throughput / Gbps")
        ax.set_xticks(conns)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        ax.legend()
    fig.text(
        0.5,
        -0.02,
        label(
            "The crc32c curve includes chunk checksum plus manifest/recovery semantics.",
            "crc32c 曲线表示带 chunk 校验和 manifest/recovery 语义的可靠模式。",
        ),
        ha="center",
        fontsize=10,
    )
    return save(fig, output_dir, "gridflux_checksum_impact", fmt)


def ten_gib_time_plot(rows: list[dict[str, str]], output_dir: Path, fmt: str) -> list[Path]:
    configs = [
        ("GridFTP upload", find_best(rows, protocol="native_gridftp", direction="upload", size=10 * 1024**3)),
        ("GridFlux STOR none", find_best(rows, protocol="gridflux", direction="stor", size=10 * 1024**3, checksum="none")),
        ("GridFlux STOR crc32c", find_best(rows, protocol="gridflux", direction="stor", size=10 * 1024**3, checksum="crc32c")),
        ("GridFTP download", find_best(rows, protocol="native_gridftp", direction="download", size=10 * 1024**3)),
        ("GridFlux RETR none", find_best(rows, protocol="gridflux", direction="retr", size=10 * 1024**3, checksum="none")),
        ("GridFlux RETR crc32c", find_best(rows, protocol="gridflux", direction="retr", size=10 * 1024**3, checksum="crc32c")),
    ]
    labels = [item[0] for item in configs]
    values = []
    for _, row in configs:
        gbps = number(row, "best_Gbps")
        values.append(TEN_GIB * 8 / (gbps * 1_000_000_000) if gbps > 0.0 else 0.0)
    fig, ax = plt.subplots(figsize=(12.5, 6.0))
    ax.bar(range(len(values)), values, color=["#2f6fbb", "#dd7f27", "#2f9e68", "#2f6fbb", "#dd7f27", "#2f9e68"])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel(label("Seconds", "秒"))
    ax.set_title(label("10GiB measured best transfer time", "10GiB 实测 best 预计耗时"))
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    add_labels(ax, list(range(len(values))), values, suffix="s", digits=1)
    return save(fig, output_dir, "gridftp_vs_gridflux_10g_time", fmt)


def plot_all(summary_csv: Path, host_baseline_csv: Path, checksum_baseline_csv: Path, output_dir: Path, fmt: str) -> list[Path]:
    rows = read_csv(summary_csv)
    host_rows = read_csv(host_baseline_csv)
    checksum_rows = read_csv(checksum_baseline_csv)
    configure_style()
    outputs: list[Path] = []
    outputs.extend(
        grouped_best_plot(
            rows,
            output_dir,
            fmt,
            direction="upload",
            gridflux_direction="stor",
            stem="gridftp_vs_gridflux_upload_1g_10g",
            title=label("Upload/STOR best throughput", "上传 best 吞吐"),
        )
    )
    outputs.extend(
        grouped_best_plot(
            rows,
            output_dir,
            fmt,
            direction="download",
            gridflux_direction="retr",
            stem="gridftp_vs_gridflux_download_1g_10g",
            title=label("Download/RETR best throughput", "下载 best 吞吐"),
        )
    )
    outputs.extend(scaling_plot(rows, output_dir, fmt))
    outputs.extend(baseline_plot(host_rows, checksum_rows, output_dir, fmt))
    outputs.extend(checksum_impact_plot(rows, output_dir, fmt))
    outputs.extend(ten_gib_time_plot(rows, output_dir, fmt))
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-csv", required=True)
    parser.add_argument("--host-baseline-csv", required=True)
    parser.add_argument("--checksum-baseline-csv", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["png", "svg", "both"], default="both")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    outputs = plot_all(
        summary_csv=Path(args.summary_csv),
        host_baseline_csv=Path(args.host_baseline_csv),
        checksum_baseline_csv=Path(args.checksum_baseline_csv),
        output_dir=Path(args.output_dir),
        fmt=args.format,
    )
    for output in outputs:
        try:
            text = output.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            text = str(output.resolve())
        print(f"figure={text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
