# Lab Beta 2B Checksum / Final Verify Diagnosis

时间戳：`20260523T065043Z`

## 问题与修复

- 已修复 20GiB STOR crc32c c4 的客户端 `recv: Resource temporarily unavailable`：plain `FramedDataSocket` 现在对 `EAGAIN/EWOULDBLOCK` 做 `poll()` 等待和重试，避免 server 完成后客户端等待最终 `Complete` frame 时误判失败。
- Focused 验收：20GiB STOR crc32c c4 repeat=3 全部 pass，sha mismatch=0，吞吐 `2.098 / 2.082 / 2.108 Gbps`。
- `verified_chunks` 仍为 opt-in；默认 `final_verify_policy=full` 未改变。
- `checksum=none + verified_chunks` 已验证回退：requested=`verified_chunks`，effective=`full`，STOR/RETR 均 pass。

## 结果路径

- 主矩阵 combined CSV：`tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/gridflux-beta2b-main-combined.csv`
- 全部 run combined CSV：`tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/gridflux-beta2b-all-runs-combined.csv`
- 分析 JSON：`tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/analysis_summary.json`
- 清理记录：`tools/perf/results/20260523T065043Z_lab-beta2b-checksum-final-verify/cleanup_check.txt`

主矩阵 `144/144 pass`，focused/fallback 合计后 `149/149 pass`，`sha_mismatch=0`。

## 后续测试分层

Beta 2B 的 `144/144` 主矩阵与 `149/149` focused/fallback 结果已作为实验室
checksum/final verify 证据保留。后续默认不再每轮重复全量大矩阵，改用
`tools/perf/run_lab_gridflux_profile.py` 分层执行：

| Profile | 默认大小 | 默认 repeat | 默认 rows | 用途 |
|---|---:|---:|---:|---|
| quick | 1GiB | 1 | 4 | 日常明显回归检查 |
| focused | 10GiB | 1 | 6 | EAGAIN、checksum、final verify、verified_chunks 关键路径 |
| release | 10GiB | 2 | 32 | 阶段验收；`--repeat 3` 为 48 rows |
| heavy | 20GiB | 3 | 90 | 重大版本、迁移前或明确要求时才运行 |

quick/focused 作为日常与重点回归入口，release 用于阶段 gate，heavy 只按需运行。
所有 profile 仍保持默认传输策略不变；`verified_chunks` 只作为 opt-in 对照，
不会改变默认 `final_verify_policy=full`。

## 关键数据

| Size | Direction | Mode | Best conn | Median Gbps | Best Gbps | Spread |
|---|---:|---|---:|---:|---:|---:|
| 10GiB | STOR | none+full | 1 | 7.102 | 7.178 | 2.5% |
| 10GiB | STOR | crc32c+full | 1 | 3.061 | 3.070 | 2.8% |
| 10GiB | STOR | crc32c+verified_chunks | 1 | 4.298 | 4.629 | 9.3% |
| 10GiB | RETR | none+full | 16 | 5.255 | 5.321 | 8.0% |
| 10GiB | RETR | crc32c+full | 16 | 3.578 | 3.682 | 7.0% |
| 10GiB | RETR | crc32c+verified_chunks | 16 | 5.343 | 5.452 | 5.1% |
| 20GiB | STOR | none+full | 1 | 4.655 | 4.679 | 0.5% |
| 20GiB | STOR | crc32c+full | 1 | 2.506 | 2.507 | 2.2% |
| 20GiB | STOR | crc32c+verified_chunks | 1 | 3.324 | 3.369 | 2.0% |
| 20GiB | RETR | none+full | 16 | 3.442 | 3.538 | 5.9% |
| 20GiB | RETR | crc32c+full | 16 | 2.636 | 2.686 | 2.7% |
| 20GiB | RETR | crc32c+verified_chunks | 16 | 3.580 | 3.649 | 2.4% |

阶段耗时字段是跨连接/线程累计的 work/wait mass，不是单一 wall-clock。典型 best-conn 中，crc32c+full 的 final verify 成本为：10GiB STOR `8.50s`、10GiB RETR `7.70s`、20GiB STOR `17.32s`、20GiB RETR `14.96s`；verified_chunks 下 `bytes_final_verified=0` 且 final verify 约 `0s`。

## 判断

- crc32c+full 相比 none+full：10GiB STOR 掉 `56.9%`，10GiB RETR 掉 `31.9%`，20GiB STOR 掉 `46.2%`，20GiB RETR 掉 `23.4%`。
- verified_chunks 相比 crc32c+full：10GiB STOR 提升 `40.4%`，10GiB RETR 提升 `49.3%`，20GiB STOR 提升 `32.6%`，20GiB RETR 提升 `35.8%`。
- RETR verified_chunks 已基本恢复到 none 水平；STOR verified_chunks 仍低于 none，剩余差距主要来自在线 crc32c、双端 checksum work 和当前存储/网络 baseline。
- Threaded checksum worker 仍值得作为后续 opt-in prototype，但本轮数据优先说明：full final verify 是最明显、已可 opt-in 拆掉的成本；默认策略暂不改变。

## 100GiB Repeat 建议

不建议立刻进入 100GiB repeat。当前实验室 baseline 仍未调满：TCP 约 `36-41Gbps`、RDMA 单向约 `59.8Gbps`、main PCIe x8 downgraded、direct storage 低于 `1GB/s`，small 端根分区约 `65GiB` 可用。建议先修网络/PCIe/storage baseline，再做 100GiB repeat。

## 清理

- 已删除本轮 `/mnt/aim_sdc/gridflux-test/beta2b-20260523T065043Z-*` run-root。
- 双端 `/tmp` 未发现本轮 `gridflux_phase4a_*` / `gridflux_beta1a_*` 残留。
- 双端未发现 `gridflux-gridftp-server`、`gridflux-file-*`、`iperf3`、`ib_write_bw`、`ib_read_bw` 残留。
