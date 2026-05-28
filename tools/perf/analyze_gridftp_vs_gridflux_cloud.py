#!/usr/bin/env python3
"""Analyze native GridFTP vs GridFlux cloud comparison results."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "docs" / "perf" / "GRIDFTP_VS_GRIDFLUX_CLOUD_COMPARISON.md"
DEFAULT_FIGURE_DIR = ROOT / "docs" / "perf" / "figures"
TEN_GIB = 10 * 1024**3

COMPARISON_FIELDS = [
    "kind",
    "direction",
    "size_bytes",
    "parallelism_or_connections",
    "checksum",
    "native_median_Gbps",
    "gridflux_median_Gbps",
    "delta_pct",
    "native_best_Gbps",
    "gridflux_best_Gbps",
    "status",
    "notes",
]


def timestamp_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_csv(path_text: str | Path) -> list[dict[str, str]]:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["_source_csv"] = str(path)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


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


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if math.isfinite(value) else ""


def pct_delta(value: float, base: float) -> str:
    if base <= 0.0:
        return ""
    return f"{((value - base) / base) * 100.0:+.1f}%"


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_暂无有效数据。_\n"
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def size_label(size_text: str) -> str:
    try:
        size = int(size_text)
    except ValueError:
        return size_text
    if size % (1024**3) == 0:
        return f"{size // (1024**3)}GiB"
    if size % (1024**2) == 0:
        return f"{size // (1024**2)}MiB"
    return str(size)


def valid_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if integer(row, "fail_count") == 0
        and integer(row, "sha256_mismatch_count") == 0
        and number(row, "median_Gbps") > 0.0
    ]


def best_row(
    rows: list[dict[str, str]],
    *,
    protocol: str,
    direction: str,
    size: str = "",
    checksum: str = "",
    min_size: int = 0,
) -> dict[str, str] | None:
    candidates = [
        row
        for row in valid_summary_rows(rows)
        if row.get("protocol") == protocol
        and row.get("direction") == direction
        and (not size or row.get("size_bytes") == size)
        and (not checksum or row.get("checksum") == checksum)
        and int(row.get("size_bytes") or "0") >= min_size
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: number(row, "best_Gbps"))


def matched_gridflux(rows: list[dict[str, str]], direction: str, size: str, p: str, checksum: str) -> dict[str, str] | None:
    candidates = [
        row
        for row in valid_summary_rows(rows)
        if row.get("protocol") == "gridflux"
        and row.get("direction") == direction
        and row.get("size_bytes") == size
        and row.get("connections") == p
        and row.get("checksum") == checksum
        and row.get("file_io_backend") == "posix"
        and row.get("tls_mode") == "off"
        and row.get("data_tls_mode") == "off"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: number(row, "median_Gbps"))


def matched_native(rows: list[dict[str, str]], direction: str, size: str, p: str) -> dict[str, str] | None:
    candidates = [
        row
        for row in valid_summary_rows(rows)
        if row.get("protocol") == "native_gridftp"
        and row.get("direction") == direction
        and row.get("size_bytes") == size
        and row.get("parallelism") == p
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: number(row, "median_Gbps"))


def comparison_rows(summary_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    sizes = sorted({row.get("size_bytes", "") for row in summary_rows if row.get("size_bytes")}, key=lambda item: int(item or "0"))
    p_values = sorted(
        {row.get("parallelism") or row.get("connections") for row in summary_rows if row.get("parallelism") or row.get("connections")},
        key=lambda item: int(item or "0"),
    )
    output: list[dict[str, str]] = []
    for native_direction, gridflux_direction in [("upload", "stor"), ("download", "retr")]:
        for size in sizes:
            for p in p_values:
                native = matched_native(summary_rows, native_direction, size, p)
                for checksum in ["none", "crc32c"]:
                    gridflux = matched_gridflux(summary_rows, gridflux_direction, size, p, checksum)
                    if not native and not gridflux:
                        continue
                    native_median = number(native, "median_Gbps")
                    gridflux_median = number(gridflux, "median_Gbps")
                    output.append(
                        {
                            "kind": "matched",
                            "direction": f"{native_direction}/{gridflux_direction}",
                            "size_bytes": size,
                            "parallelism_or_connections": p,
                            "checksum": checksum,
                            "native_median_Gbps": fmt(native_median),
                            "gridflux_median_Gbps": fmt(gridflux_median),
                            "delta_pct": pct_delta(gridflux_median, native_median),
                            "native_best_Gbps": fmt(number(native, "best_Gbps")),
                            "gridflux_best_Gbps": fmt(number(gridflux, "best_Gbps")),
                            "status": "matched" if native and gridflux else "unmatched",
                            "notes": "",
                        }
                    )
    return output


def checksum_impact_rows(summary_rows: list[dict[str, str]]) -> list[list[str]]:
    output: list[list[str]] = []
    keys = sorted(
        {
            (row.get("direction", ""), row.get("size_bytes", ""), row.get("connections", ""))
            for row in valid_summary_rows(summary_rows)
            if row.get("protocol") == "gridflux"
            and row.get("file_io_backend") == "posix"
            and row.get("tls_mode") == "off"
            and row.get("data_tls_mode") == "off"
        },
        key=lambda key: (key[0], int(key[1] or "0"), int(key[2] or "0")),
    )
    for direction, size, conn in keys:
        none = matched_gridflux(summary_rows, direction, size, conn, "none")
        crc = matched_gridflux(summary_rows, direction, size, conn, "crc32c")
        if not none or not crc:
            continue
        output.append(
            [
                direction.upper(),
                size_label(size),
                conn,
                fmt(number(none, "median_Gbps")),
                fmt(number(crc, "median_Gbps")),
                pct_delta(number(crc, "median_Gbps"), number(none, "median_Gbps")),
            ]
        )
    return output


def host_baseline_table(host_rows: list[dict[str, str]]) -> str:
    rows: list[list[str]] = []
    for row in host_rows:
        rows.append(
            [
                row.get("kind", ""),
                row.get("machine", ""),
                row.get("operation", ""),
                row.get("parallelism", ""),
                size_label(row.get("size_bytes", "")),
                row.get("MBps", ""),
                row.get("Gbps", ""),
                row.get("status", ""),
            ]
        )
    return table(["kind", "machine", "operation", "p", "size", "MB/s", "Gbps", "status"], rows)


def checksum_table(rows: list[dict[str, str]]) -> str:
    output = [
        [
            row.get("machine", ""),
            row.get("backend", ""),
            size_label(row.get("size_bytes", "")),
            row.get("throughput_Gbps", ""),
            row.get("status", ""),
        ]
        for row in rows
    ]
    return table(["machine", "backend", "size", "Gbps", "status"], output)


def protocol_table(summary_rows: list[dict[str, str]], protocol: str) -> str:
    output: list[list[str]] = []
    for row in sorted(
        [row for row in summary_rows if row.get("protocol") == protocol],
        key=lambda item: (
            item.get("direction", ""),
            int(item.get("size_bytes") or "0"),
            int(item.get("parallelism") or item.get("connections") or "0"),
            item.get("checksum", ""),
            item.get("file_io_backend", ""),
            item.get("tls_mode", ""),
        ),
    ):
        output.append(
            [
                row.get("direction", ""),
                size_label(row.get("size_bytes", "")),
                row.get("parallelism") or row.get("connections", ""),
                row.get("checksum", ""),
                row.get("file_io_backend", ""),
                f"{row.get('tls_mode','')}/{row.get('data_tls_mode','')}",
                row.get("median_Gbps", ""),
                row.get("best_Gbps", ""),
                row.get("p95_Gbps", ""),
                row.get("spread_pct", ""),
                row.get("sample_count", ""),
                row.get("fail_count", ""),
                row.get("sha256_mismatch_count", ""),
            ]
        )
    return table(
        ["direction", "size", "p/conn", "checksum", "backend", "tls", "median Gbps", "best Gbps", "p95", "spread %", "n", "fail", "mismatch"],
        output,
    )


def matched_table(rows: list[dict[str, str]], sizes: set[str] | None = None) -> str:
    output: list[list[str]] = []
    for row in rows:
        if sizes and row.get("size_bytes") not in sizes:
            continue
        output.append(
            [
                row.get("direction", ""),
                size_label(row.get("size_bytes", "")),
                row.get("parallelism_or_connections", ""),
                row.get("checksum", ""),
                row.get("native_median_Gbps", ""),
                row.get("gridflux_median_Gbps", ""),
                row.get("delta_pct", ""),
                row.get("status", ""),
            ]
        )
    return table(["方向", "大小", "p/conn", "GridFlux checksum", "GridFTP median", "GridFlux median", "GridFlux delta", "status"], output)


def estimate_10g_time(row: dict[str, str] | None) -> str:
    gbps = number(row, "best_Gbps")
    if gbps <= 0.0:
        return ""
    seconds = TEN_GIB * 8 / (gbps * 1_000_000_000)
    return f"{seconds:.1f}s"


def summarize_best(summary_rows: list[dict[str, str]]) -> list[list[str]]:
    output: list[list[str]] = []
    for label, protocol, direction, checksum in [
        ("GridFTP upload", "native_gridftp", "upload", ""),
        ("GridFTP download", "native_gridftp", "download", ""),
        ("GridFlux STOR none", "gridflux", "stor", "none"),
        ("GridFlux STOR crc32c", "gridflux", "stor", "crc32c"),
        ("GridFlux RETR none", "gridflux", "retr", "none"),
        ("GridFlux RETR crc32c", "gridflux", "retr", "crc32c"),
    ]:
        row = best_row(summary_rows, protocol=protocol, direction=direction, checksum=checksum, min_size=1024**3)
        output.append(
            [
                label,
                size_label(row.get("size_bytes", "")) if row else "",
                row.get("parallelism") or row.get("connections", "") if row else "",
                row.get("median_Gbps", "") if row else "",
                row.get("best_Gbps", "") if row else "",
                estimate_10g_time(row),
            ]
        )
    return output


def bottleneck_notes(host_rows: list[dict[str, str]], checksum_rows: list[dict[str, str]], summary_rows: list[dict[str, str]]) -> list[str]:
    iperf = [number(row, "Gbps") for row in host_rows if row.get("kind") == "iperf3" and row.get("status") == "pass"]
    storage_write = [number(row, "Gbps") for row in host_rows if row.get("kind") == "storage" and row.get("operation") == "write" and row.get("status") == "pass"]
    checksum = [number(row, "throughput_Gbps") for row in checksum_rows if row.get("status") == "pass"]
    stor_best = best_row(summary_rows, protocol="gridflux", direction="stor")
    retr_best = best_row(summary_rows, protocol="gridflux", direction="retr")
    notes = []
    if iperf:
        notes.append(f"裸 TCP baseline best 为 `{max(iperf):.3f} Gbps`，当前实验首先受云服务器私网能力约束，不代表 100G。")
    if storage_write:
        notes.append(f"本地 storage write best 为 `{max(storage_write):.3f} Gbps`，STOR/upload 结果需要放在写盘/writeback 背景下理解。")
    if checksum:
        notes.append(f"CRC32C benchmark best 为 `{max(checksum):.3f} Gbps`，若远高于传输吞吐，则 checksum 通常不是主瓶颈。")
    if stor_best:
        notes.append(f"GridFlux STOR best 为 `{stor_best.get('best_Gbps')} Gbps`；若接近 storage write 上限，优先怀疑云盘、文件系统和 page cache/writeback。")
    if retr_best:
        notes.append(f"GridFlux RETR best 为 `{retr_best.get('best_Gbps')} Gbps`；下载方向更接近网络发送、接收端落盘和多连接调度共同作用。")
    return notes


def load_wrapper(path: str) -> dict[str, object]:
    if not path:
        return {}
    parsed = Path(path)
    if not parsed.is_absolute():
        parsed = ROOT / parsed
    if not parsed.is_file():
        return {}
    return json.loads(parsed.read_text(encoding="utf-8"))


def infer_paths(args: argparse.Namespace) -> dict[str, str]:
    wrapper = load_wrapper(args.wrapper_json)
    paths = wrapper.get("paths", {}) if isinstance(wrapper.get("paths"), dict) else {}
    return {
        "summary": args.summary_csv or str(paths.get("summary", "")),
        "host_baseline": args.host_baseline_csv or str(paths.get("host_baseline", "")),
        "checksum_baseline": args.checksum_baseline_csv or str(paths.get("checksum_baseline", "")),
        "environment": args.env_txt or str(paths.get("environment", "")),
    }


def write_report(
    *,
    report_path: Path,
    paths: dict[str, str],
    summary_rows: list[dict[str, str]],
    host_rows: list[dict[str, str]],
    checksum_rows: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    figure_dir: Path,
) -> None:
    notes = bottleneck_notes(host_rows, checksum_rows, summary_rows)
    present_sizes = sorted({int(row.get("size_bytes") or "0") for row in summary_rows if row.get("size_bytes")}, reverse=False)
    size_text = ", ".join(size_label(str(size)) for size in present_sizes)
    full_sizes = {256 * 1024**2, 1024**3, 4 * 1024**3, 10 * 1024**3}
    data_status = (
        "当前输入 CSV 覆盖默认完整大小集合。"
        if full_sizes.issubset(set(present_sizes))
        else f"当前输入 CSV 只覆盖 `{size_text}`；若这是 smoke run，4GiB/10GiB 完整展示结论仍需默认完整矩阵补齐。"
    )
    lines = [
        "# 原生 GridFTP vs GridFlux 云服务器对比实验",
        "",
        f"生成时间：`{timestamp_utc()}`",
        "",
        f"数据状态：{data_status}",
        "",
        "## 1. 实验目的",
        "",
        "在现有两台云服务器私网环境下，对比原生 Globus GridFTP 与当前 GridFlux Beta 冻结版的上传/下载吞吐、并发扩展、checksum 开销和大文件表现。本报告不是 100G 认证，也不改变 GridFlux 默认策略。",
        "",
        "## 2. 实验环境",
        "",
        f"- 环境记录：`{paths.get('environment','')}`",
        f"- Host baseline CSV：`{paths.get('host_baseline','')}`",
        f"- Checksum baseline CSV：`{paths.get('checksum_baseline','')}`",
        f"- Summary CSV：`{paths.get('summary','')}`",
        "- 测试链路：<redacted>一 `<redacted>` 与<redacted>二 `<redacted>` 的私网链路。",
        "",
        "## 3. 技术路径简述",
        "",
        "- 原生 GridFTP：使用 `globus-gridftp-server` 与 `globus-url-copy`，通过 parallelism `1/4/8/16` 扩展数据传输。",
        "- GridFlux：使用 GridFTP-like 控制面和 framed STOR/RETR 数据面；`checksum none` 更接近裸传输，`crc32c` 是带 chunk 校验、manifest 和恢复语义的可靠模式。",
        "- 默认策略保持保守：anonymous、TLS off、data TLS off、POSIX、full final verify、manifest every_n_chunks、preallocate off、posix auto、receiver default/none。",
        "",
        "## 4. 实验矩阵",
        "",
        "- 文件大小：256MiB、1GiB、4GiB、10GiB。256MiB 仅作短文件/cache 观察。",
        "- 原生 GridFTP：upload/download，parallelism `1/4/8/16`，1GiB repeat=3，其余默认 repeat=1。",
        "- GridFlux：STOR/RETR，connections `1/4/8/16`，checksum `none/crc32c`，POSIX/off/off 主矩阵。",
        "- GridFlux 小子集：1GiB io_uring、1GiB TLS/data TLS required/required，只用于说明 opt-in 开销或差异。",
        "",
        "## 5. Baseline 结果",
        "",
        host_baseline_table(host_rows),
        "",
        "### CRC32C baseline",
        "",
        checksum_table(checksum_rows),
        "",
        "## 6. 原生 GridFTP 结果",
        "",
        protocol_table(summary_rows, "native_gridftp"),
        "",
        "## 7. GridFlux 结果",
        "",
        protocol_table(summary_rows, "gridflux"),
        "",
        "## 8. GridFTP vs GridFlux 对比",
        "",
        "### 1GiB / 4GiB / 10GiB matched rows",
        "",
        matched_table(comparisons, {str(1024**3), str(4 * 1024**3), str(10 * 1024**3)}),
        "",
        "### 最佳结果与 10GiB 预计耗时",
        "",
        table(["场景", "最佳样本大小", "p/conn", "median Gbps", "best Gbps", "按 best 传 10GiB"], summarize_best(summary_rows)),
        "",
        "### GridFlux checksum 影响",
        "",
        table(["方向", "大小", "conn", "none median", "crc32c median", "crc32c delta"], checksum_impact_rows(summary_rows)),
        "",
        "## 9. 结果分析",
        "",
        *[f"- {note}" for note in notes],
        "- 并发是否有效以 matched rows 和 parallel scaling 图为准；p16 若没有继续提升，不应解释为协议绝对上限，可能是云服务器网络、CPU、写盘或 GridFTP 配置共同限制。",
        "- 256MiB 短文件结果可能受 page cache 和短文件启动成本影响，不作为长期稳定上限承诺。",
        "",
        "## 10. 图表",
        "",
        f"- ![upload](figures/gridftp_vs_gridflux_upload_1g_10g.png)",
        f"- ![download](figures/gridftp_vs_gridflux_download_1g_10g.png)",
        f"- ![scaling](figures/gridftp_vs_gridflux_parallel_scaling.png)",
        f"- ![baseline](figures/gridftp_vs_gridflux_baseline_context.png)",
        f"- ![checksum](figures/gridflux_checksum_impact.png)",
        f"- ![10GiB time](figures/gridftp_vs_gridflux_10g_time.png)",
        "",
        "## 11. 结论",
        "",
        "本轮结论必须以 hash 一致且 status pass 的 CSV 行为准。如果 GridFlux 在部分场景快于原生 GridFTP，可以作为当前 Beta 原型在该云服务器环境下的实测优势；如果没有全面更快，则应强调 GridFlux 的可靠恢复、manifest、checksum、event log、目录传输和后续优化空间，而不是伪造性能优势。",
        "",
        "## 12. 局限性",
        "",
        "- 当前云服务器裸 TCP 通常只有十几 Gbps 量级，不是 100G 环境。",
        "- 当前 storage write 约 1Gbps 级时，上传/STOR 结论强烈受写盘和 OS writeback 影响。",
        "- 原生 GridFTP 采用本轮临时 anonymous/no-GSI 配置，不代表所有生产 GridFTP 部署方式。",
        "- GridFlux Beta 仍是云服务器候选版，不是 100G 认证版。",
        "",
        "## 13. 后续 100G 环境验证计划",
        "",
        "迁移 100G 前先跑 iperf3、storage bench、memory sink 和 CRC32C benchmark；100G 上先做 10GiB smoke，再做 100GiB repeat。只有当网络、磁盘、CPU、TLS 和 checksum baseline 都足够清晰后，才能判断 GridFlux 数据面是否成为主瓶颈。",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrapper-json", default="")
    parser.add_argument("--summary-csv", default="")
    parser.add_argument("--host-baseline-csv", default="")
    parser.add_argument("--checksum-baseline-csv", default="")
    parser.add_argument("--env-txt", default="")
    parser.add_argument("--output-summary-csv", default="")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIGURE_DIR))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    paths = infer_paths(args)
    summary_rows = read_csv(paths["summary"])
    host_rows = read_csv(paths["host_baseline"])
    checksum_rows = read_csv(paths["checksum_baseline"])
    comparisons = comparison_rows(summary_rows)
    output_summary = Path(args.output_summary_csv) if args.output_summary_csv else Path(paths["summary"]).with_name(Path(paths["summary"]).stem + "-comparison.csv")
    if not output_summary.is_absolute():
        output_summary = ROOT / output_summary
    write_csv(output_summary, comparisons, COMPARISON_FIELDS)
    write_report(
        report_path=Path(args.report) if Path(args.report).is_absolute() else ROOT / args.report,
        paths={**paths, "comparison_summary": relative_path(output_summary)},
        summary_rows=summary_rows,
        host_rows=host_rows,
        checksum_rows=checksum_rows,
        comparisons=comparisons,
        figure_dir=Path(args.figure_dir),
    )
    print(f"comparison_csv={relative_path(output_summary)}")
    print(f"report={relative_path(Path(args.report) if Path(args.report).is_absolute() else ROOT / args.report)}")
    return 0


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
