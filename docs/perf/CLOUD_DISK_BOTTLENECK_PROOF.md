# Cloud Disk Bottleneck Proof

生成时间：`2026-05-21T18:12:23Z`

## 1. 实验目的

本实验在当前两台阿里云云服务器私网环境下做分层对照，目标是判断 GridFlux 长文件 STOR 主要瓶颈是否符合云盘、文件系统、Linux page cache/writeback 限制，而不是网络、CPU、CRC32C 指令算力或 GridFlux 协议本身。

## 2. 实验假设

- H1：当前 STOR 主瓶颈在云服务器硬盘写入 / 文件系统 / OS writeback。
- H0：当前 STOR 主瓶颈在网络 / CPU / checksum / GridFlux 协议调度。

## 3. 输入文件

- `tools/perf/results/20260521T145615Z_cloud-disk-proof-network.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-checksum.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-memory-or-sink.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-storage.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-storage-summary.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-gridflux-stor.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-gridflux-stor-summary.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-gridflux-retr.csv`
- `tools/perf/results/20260521T145615Z_cloud-disk-proof-gridflux-retr-summary.csv`

## 4. 关键结果

| 指标 | 数值 | 单位 | 说明 |
| --- | --- | --- | --- |
| 上传方向 TCP best | 15.686 | Gbps | upload direction |
| 下载方向 TCP best | 15.695 | Gbps | download direction |
| CRC32C hardware best | 47.821 | Gbps | gridflux-checksum-bench |
| memory/sink best | 15.692 | Gbps | available |
| storage write median | 0.954 | Gbps | gridflux-storage-bench POSIX write |
| storage read median | 0.923 | Gbps | gridflux-storage-bench POSIX read |
| STOR e2e median | 0.977 | Gbps | GridFlux STOR summary |
| STOR temp-write median | 2.077 | Gbps | bytes / temp_write_seconds |
| STOR temp-write 占比 | 37.3% | ratio | 37.3% |
| STOR data_receive 占比 | 1.1% | ratio | 1.1% |
| hash mismatch | 0 | count | GridFlux raw transfer rows |
| 数据范围 | focused_long_file | text | 64MiB/256MiB rows are smoke only; 1GiB/4GiB rows are formal attribution |
| RETR e2e median | 0.928 | Gbps | GridFlux RETR summary |
| RETR temp-write 占比 | 5.5% | ratio | 5.5% |
| RETR network_send 占比 | 1.8% | ratio | 1.8% |
| 归因结论 | inconclusive_or_mixed | text | 证据链不足以单独归因到云盘/writeback；缺失或未满足：STOR temp_write share 未超过 60%。 |


> 数据范围提示：本次输入包含长文件样本，可用于 focused 归因；仍需结合 repeat 稳定性和 hash 一致性判断。

## 5. 正式 Focused 结果与证据链总表

正式 focused 归因使用 `1GiB/4GiB repeat=3`；64MiB smoke 只用于工具链闭环验证，不作为瓶颈归因结论。

| evidence | expected if disk bottleneck | observed |
| --- | --- | --- |
| iperf3 best | much higher than STOR | 15.686 Gbps |
| CRC32C hardware best | much higher than STOR | 47.821 Gbps |
| storage write median | same order as STOR | 0.954 Gbps |
| STOR e2e median | close to storage write | 0.977 Gbps |
| STOR temp-write share | >60%, ideally >70% | 37.3% |
| STOR data_receive share | small, ideally <10% | 1.1% |
| hash mismatch | 0 | 0 |


判定规则：只有 network 和 CRC32C 明显高于 STOR、storage write 与 STOR 同量级、STOR temp-write share 超过 60%、data_receive share 低于 10%、hash mismatch 为 0，且输入包含 focused 长文件样本时，verdict 才会变为 `cloud_disk_writeback_dominated`。

## 6. 网络上限对照

| 方向 | 并发 | 时长 | Gbps | 状态 |
| --- | --- | --- | --- | --- |
| client_to_server | 1 | 10 | 15.686 | pass |
| client_to_server | 4 | 10 | 15.358 | pass |
| client_to_server | 8 | 10 | 9.657 | pass |
| client_to_server | 16 | 10 | 10.209 | pass |
| server_to_client | 1 | 10 | 15.695 | pass |
| server_to_client | 4 | 10 | 15.693 | pass |
| server_to_client | 8 | 10 | 9.589 | pass |
| server_to_client | 16 | 10 | 10.029 | pass |


如果上传方向 iperf3 明显高于 STOR 长文件吞吐，例如十几 Gbps 对 1-2 Gbps，则网络不是当前 STOR 主瓶颈。

## 7. CRC32C / CPU 对照

| <redacted> | backend | effective | 大小 | iterations | Gbps | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| server | hardware | hardware | 1GiB | 3 | 44.2321 | pass |
| server | software | software | 1GiB | 3 | 2.32992 | pass |
| server | auto | hardware | 1GiB | 3 | 42.5575 | pass |
| client | hardware | hardware | 1GiB | 3 | 47.821 | pass |
| client | software | software | 1GiB | 3 | 2.52233 | pass |
| client | auto | hardware | 1GiB | 3 | 47.2746 | pass |


这里证明的是 CRC32C 指令算力不是主瓶颈；checksum 集成路径仍可能存在局部开销，需要通过 `crc32c` 与 `none` 的传输行继续观察。

## 8. Memory / Sink 对照

| side | category | tool | bytes | Gbps | status |
| --- | --- | --- | --- | --- | --- |
| link | network | iperf3 | 19694092288 | 15.692391 | pass |
| server | disk_write | python | 1GiB | 1.037959 | pass |
| server | disk_read | python | 1GiB | 0.925192 | pass |
| client | disk_write | python | 1GiB | 1.029594 | pass |
| client | disk_read | python | 1GiB | 78.473415 | pass |
| server | checksum | gridflux-checksum-bench | 1GiB | 43.5086 | pass |
| client | checksum | gridflux-checksum-bench | 1GiB | 47.1115 | pass |


memory/sink 对照不可用时不作为失败项；它只是用来辅助判断协议和内存路径的潜在上限。

## 9. 原生存储写入/读取对照

| 目录 | 方向 | 大小 | buffer | preallocate | median Gbps | p95 Gbps | 挂载点 | iostat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| project_temp | read | 1GiB | 1048576 | full | 1.010 | 29.985 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b1073741824_buf1048576_prefull_posix_after.log |
| project_temp | read | 1GiB | 1048576 | off | 0.957 | 1.345 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b1073741824_buf1048576_preoff_posix_after.log |
| project_temp | read | 1GiB | 262144 | full | 0.945 | 0.987 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b1073741824_buf262144_prefull_posix_after.log |
| project_temp | read | 1GiB | 262144 | off | 0.948 | 0.965 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b1073741824_buf262144_preoff_posix_after.log |
| project_temp | read | 4GiB | 1048576 | full | 0.918 | 0.919 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b4294967296_buf1048576_prefull_posix_after.log |
| project_temp | read | 4GiB | 1048576 | off | 0.919 | 0.920 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b4294967296_buf1048576_preoff_posix_after.log |
| project_temp | read | 4GiB | 262144 | full | 0.917 | 0.920 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b4294967296_buf262144_prefull_posix_after.log |
| project_temp | read | 4GiB | 262144 | off | 0.919 | 0.920 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_read_b4294967296_buf262144_preoff_posix_after.log |
| project_temp | write | 1GiB | 1048576 | full | 1.187 | 1.237 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b1073741824_buf1048576_prefull_posix_after.log |
| project_temp | write | 1GiB | 1048576 | off | 0.927 | 1.290 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b1073741824_buf1048576_preoff_posix_after.log |
| project_temp | write | 1GiB | 262144 | full | 1.211 | 1.260 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b1073741824_buf262144_prefull_posix_after.log |
| project_temp | write | 1GiB | 262144 | off | 0.924 | 1.428 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b1073741824_buf262144_preoff_posix_after.log |
| project_temp | write | 4GiB | 1048576 | full | 0.973 | 0.982 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b4294967296_buf1048576_prefull_posix_after.log |
| project_temp | write | 4GiB | 1048576 | off | 0.919 | 0.981 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b4294967296_buf1048576_preoff_posix_after.log |
| project_temp | write | 4GiB | 262144 | full | 0.973 | 0.985 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b4294967296_buf262144_prefull_posix_after.log |
| project_temp | write | 4GiB | 262144 | off | 0.913 | 0.972 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/project_temp_gridflux_storage_bench_write_b4294967296_buf262144_preoff_posix_after.log |
| target_root | read | 1GiB | 1048576 | full | 1.899 | 35.709 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b1073741824_buf1048576_prefull_posix_after.log |
| target_root | read | 1GiB | 1048576 | off | 1.118 | 10.444 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b1073741824_buf1048576_preoff_posix_after.log |
| target_root | read | 1GiB | 262144 | full | 1.037 | 50.877 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b1073741824_buf262144_prefull_posix_after.log |
| target_root | read | 1GiB | 262144 | off | 29.355 | 36.592 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b1073741824_buf262144_preoff_posix_after.log |
| target_root | read | 4GiB | 1048576 | full | 0.915 | 0.921 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b4294967296_buf1048576_prefull_posix_after.log |
| target_root | read | 4GiB | 1048576 | off | 0.920 | 0.920 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b4294967296_buf1048576_preoff_posix_after.log |
| target_root | read | 4GiB | 262144 | full | 0.920 | 0.921 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b4294967296_buf262144_prefull_posix_after.log |
| target_root | read | 4GiB | 262144 | off | 0.918 | 0.921 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_read_b4294967296_buf262144_preoff_posix_after.log |
| target_root | write | 1GiB | 1048576 | full | 1.222 | 1.226 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b1073741824_buf1048576_prefull_posix_after.log |
| target_root | write | 1GiB | 1048576 | off | 0.926 | 1.295 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b1073741824_buf1048576_preoff_posix_after.log |
| target_root | write | 1GiB | 262144 | full | 1.208 | 1.273 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b1073741824_buf262144_prefull_posix_after.log |
| target_root | write | 1GiB | 262144 | off | 0.935 | 1.237 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b1073741824_buf262144_preoff_posix_after.log |
| target_root | write | 4GiB | 1048576 | full | 0.974 | 0.978 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b4294967296_buf1048576_prefull_posix_after.log |
| target_root | write | 4GiB | 1048576 | off | 0.923 | 0.978 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b4294967296_buf1048576_preoff_posix_after.log |
| target_root | write | 4GiB | 262144 | full | 0.979 | 0.983 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b4294967296_buf262144_prefull_posix_after.log |
| target_root | write | 4GiB | 262144 | off | 0.913 | 0.976 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/target_root_gridflux_storage_bench_write_b4294967296_buf262144_preoff_posix_after.log |
| tmp | read | 1GiB | 1048576 | full | 0.925 | 6.597 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b1073741824_buf1048576_prefull_posix_after.log |
| tmp | read | 1GiB | 1048576 | off | 1.029 | 29.796 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b1073741824_buf1048576_preoff_posix_after.log |
| tmp | read | 1GiB | 262144 | full | 2.457 | 53.250 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b1073741824_buf262144_prefull_posix_after.log |
| tmp | read | 1GiB | 262144 | off | 8.159 | 11.698 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b1073741824_buf262144_preoff_posix_after.log |
| tmp | read | 4GiB | 1048576 | full | 0.919 | 0.920 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b4294967296_buf1048576_prefull_posix_after.log |
| tmp | read | 4GiB | 1048576 | off | 0.918 | 0.919 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b4294967296_buf1048576_preoff_posix_after.log |
| tmp | read | 4GiB | 262144 | full | 0.916 | 0.917 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b4294967296_buf262144_prefull_posix_after.log |
| tmp | read | 4GiB | 262144 | off | 0.919 | 0.921 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_read_b4294967296_buf262144_preoff_posix_after.log |
| tmp | write | 1GiB | 1048576 | full | 1.208 | 1.217 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b1073741824_buf1048576_prefull_posix_after.log |
| tmp | write | 1GiB | 1048576 | off | 0.919 | 1.267 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b1073741824_buf1048576_preoff_posix_after.log |
| tmp | write | 1GiB | 262144 | full | 1.216 | 1.258 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b1073741824_buf262144_prefull_posix_after.log |
| tmp | write | 1GiB | 262144 | off | 0.926 | 1.234 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b1073741824_buf262144_preoff_posix_after.log |
| tmp | write | 4GiB | 1048576 | full | 0.979 | 0.986 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b4294967296_buf1048576_prefull_posix_after.log |
| tmp | write | 4GiB | 1048576 | off | 0.918 | 0.988 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b4294967296_buf1048576_preoff_posix_after.log |
| tmp | write | 4GiB | 262144 | full | 0.981 | 0.989 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b4294967296_buf262144_prefull_posix_after.log |
| tmp | write | 4GiB | 262144 | off | 0.912 | 0.979 | / | /root/projects/GridFlux/tools/perf/results/20260521T145615Z_cloud-disk-proof/storage-sidecars/tmp_gridflux_storage_bench_write_b4294967296_buf262144_preoff_posix_after.log |


storage write 与 STOR e2e/temp-write 如果长期处于同一数量级，说明继续优化 GridFlux 协议本身的收益可能被云盘/writeback 天花板吸收。

## 10. GridFlux STOR 阶段拆解

| case | median Gbps | temp_write | data_receive | manifest | final_verify | rename |
| --- | --- | --- | --- | --- | --- | --- |
| 1GiB conn=1 checksum=crc32c | 0.482 | 30.6% | 0.5% | 1.3% | 66.4% | 0.0% |
| 1GiB conn=1 checksum=none | 1.405 | 92.9% | 1.7% | 5.3% |  | 0.6% |
| 1GiB conn=4 checksum=crc32c | 0.917 | 59.1% | 1.0% | 1.1% | 36.6% | 0.0% |
| 1GiB conn=4 checksum=none | 1.438 | 91.6% | 1.7% | 6.1% |  | 0.3% |
| 1GiB conn=8 checksum=crc32c | 0.960 | 60.2% | 1.0% | 2.5% | 33.0% | 0.0% |
| 1GiB conn=8 checksum=none | 1.449 | 93.6% | 1.7% | 4.2% |  | 0.3% |
| 4GiB conn=1 checksum=crc32c | 0.465 | 15.8% | 0.5% | 0.9% | 53.8% | 0.0% |
| 4GiB conn=1 checksum=none | 1.001 | 35.4% | 1.2% | 3.5% |  | 0.1% |
| 4GiB conn=4 checksum=crc32c | 0.467 | 15.3% | 0.6% | 1.5% | 53.8% | 0.0% |
| 4GiB conn=4 checksum=none | 0.993 | 32.2% | 1.3% | 3.2% |  | 0.1% |
| 4GiB conn=8 checksum=crc32c | 0.467 | 17.5% | 0.6% | 1.4% | 53.4% | 0.0% |
| 4GiB conn=8 checksum=none | 1.002 | 39.2% | 1.3% | 2.7% |  | 0.0% |


判定重点是 `temp_write_seconds` 是否占大头，以及 `data_receive_seconds` 是否很小。若 temp_write 超过 60%-70%，STOR 的 wall time 更符合 receiver 写盘/writeback 限制。

## 11. GridFlux RETR 阶段拆解

| case | median Gbps | source_read | network_send | download_temp_write | final_verify | rename |
| --- | --- | --- | --- | --- | --- | --- |
| 1GiB conn=1 checksum=crc32c | 0.926 | 92.0% | 2.5% | 4.5% | 3.4% | 0.0% |
| 1GiB conn=1 checksum=none | 0.956 | 97.7% | 2.2% | 4.1% |  | 0.0% |
| 1GiB conn=4 checksum=crc32c | 0.924 | 375.8% | 5.1% | 13.5% | 3.4% | 0.0% |
| 1GiB conn=4 checksum=none | 0.934 | 393.6% | 1.9% | 5.1% |  | 0.0% |
| 1GiB conn=8 checksum=crc32c | 0.905 | 755.6% | 1.6% | 17.8% | 3.4% | 0.0% |
| 1GiB conn=8 checksum=none | 0.940 | 785.4% | 1.7% | 5.8% |  | 0.0% |
| 4GiB conn=1 checksum=crc32c | 0.457 | 46.1% | 1.8% | 3.2% | 51.3% | 0.0% |
| 4GiB conn=1 checksum=none | 0.932 | 96.9% | 2.5% | 3.9% |  | 0.5% |
| 4GiB conn=4 checksum=crc32c | 0.456 | 192.1% | 0.8% | 3.2% | 51.2% | 0.0% |
| 4GiB conn=4 checksum=none | 0.932 | 395.4% | 1.7% | 8.6% |  | 0.5% |
| 4GiB conn=8 checksum=crc32c | 0.456 | 383.8% | 0.8% | 7.7% | 51.4% | 0.0% |
| 4GiB conn=8 checksum=none | 0.930 | 788.5% | 1.7% | 25.7% |  | 0.5% |


RETR 不强行归因到写盘：需要分别看 source read、sender network send、receiver download temp write 和 final verify。

## 12. 证据链结论

- Verdict: `inconclusive_or_mixed`。
- 说明：证据链不足以单独归因到云盘/writeback；缺失或未满足：STOR temp_write share 未超过 60%。
- Dirty/Writeback 相关性：Pearson r=-0.022，paired rows=258

当前结论只针对这组阿里云服务器和本次测试窗口。它不是 100G 外推，也不是证明 GridFlux 在更强硬件上不会遇到网络、CPU、checksum、内存拷贝或协议实现瓶颈。

## 13. 局限性

- 当前云服务器裸 TCP 不是 100G 环境。
- 云盘、文件系统、page cache 状态会影响 storage 和 STOR 结果。
- fio 缺失时只记录 unavailable，不安装系统依赖。
- memory/sink 不可用时，协议非落盘路径证据会弱一些。
- 所有传输结论只使用 hash 一致且 status pass 的 GridFlux rows。

## 14. 后续 R750 / 100G 验证计划

- 先跑 iperf3 双向 p1/p4/p8/p16，确认链路上限。
- 再跑 NVMe/fio/storage bench，确认写入和读取上限是否达到预期。
- 跑 memory sink 与 CRC32C benchmark，确认 CPU/checksum 余量。
- 先做 10GiB GridFlux smoke，再做 100GiB repeat；观察瓶颈是否从写盘转移到网络、CPU、checksum 或数据面。
