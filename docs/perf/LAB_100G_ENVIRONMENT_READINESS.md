# 实验室 100G/RDMA 环境 Readiness 与 GridFlux 10GiB Smoke

生成时间：2026-05-22T14:05:53Z

## 结论

本轮私有迁移已完成，`AGENTS.md` 已同步到两台实验室服务器并设置为 `600`。报告和结果文件不包含 `AGENTS.md` 内容、密码、私钥或 token。

100G 物理链路和 RDMA verbs 基本可用：两端目标网口均为 `100000Mb/s`、`Link detected: yes`，目标 RDMA 设备均为 `ACTIVE/LINK_UP`，`ib_write_bw` small->main 可跑通，平均约 `59.80 Gbps`。

但本轮不能声明 100G 吞吐 ready：`iperf3` TCP 双向最好约 `35.4 Gbps`，GridFlux 10GiB crc32c smoke 全部正确通过但吞吐约 `2.64-3.39 Gbps`。下一轮应先做 TCP/RSS/MTU/CPU 与存储写入路径归因，再扩大到 100GiB repeat。

## 环境与构建

| 项目 | 大服务器 | 小服务器 |
| --- | --- | --- |
| hostname | `nodeb.grid` | `r730` |
| 管理网 | `192.168.1.203` | `192.168.1.112` |
| RDMA/100G IP | `192.168.100.2/30` | `192.168.100.1/30` |
| 100G 网口 | `enp177s0np0` | `enp130s0np0` |
| RDMA device | `rocep177s0` | `rocep130s0` |
| OS | Ubuntu 22.04.5 LTS | Ubuntu 22.04.5 LTS |
| kernel | `6.8.0-111-generic` | `5.15.0-177-generic` |
| Debug build | pass, `/usr/bin/g++-13` | pass, `/usr/bin/g++-13` |

依赖已在两端补齐：`g++-13`、`cmake`、`ninja-build`、`libssl-dev`、`liburing-dev`、`iperf3`、`fio`、`rdma-core`、`perftest`。`g++-13` 来自 `ppa:ubuntu-toolchain-r/test`，版本为 `13.4.0-6ubuntu1~22~ppa2`。

迁移验收通过：两台 `/home/Su/projects/GridFlux` 下均存在 `AGENTS.md`、`INDEX.md`、`docs/`、`src/`、`tools/`；`AGENTS.md` 权限为 `600`。同步排除了 `.git/`、`build*/`、`tools/perf/results/`、缓存和临时大文件。

## 链路 Readiness

| 检查 | 结果 |
| --- | --- |
| 大服务器 `ethtool enp177s0np0` | `Speed: 100000Mb/s`，`Link detected: yes` |
| 小服务器 `ethtool enp130s0np0` | `Speed: 100000Mb/s`，`Link detected: yes` |
| 大服务器 `rdma link` | `rocep177s0/1 state ACTIVE physical_state LINK_UP` |
| 小服务器 `rdma link` | `rocep130s0/1 state ACTIVE physical_state LINK_UP` |
| `ibv_devinfo` | 两端目标 HCA port 均为 `PORT_ACTIVE`，MTU `4096`，link layer `Ethernet` |
| RDMA IP ping | 双向通过 |
| `ib_write_bw` | small->main，RoCE v2 GID index `3`，平均 `59.80 Gbps` |

`iperf3` TCP baseline：

| 方向 | parallel 1 | parallel 4 | parallel 8 | parallel 16 |
| --- | ---: | ---: | ---: | ---: |
| main -> small | 35.4 Gbps | 30.6 Gbps | 27.1 Gbps | 27.5 Gbps |
| small -> main | 27.7 Gbps | 25.4 Gbps | 21.5 Gbps | 22.9 Gbps |

解释：链路协商和 RDMA verbs 已打通，但 TCP baseline 明显低于 100G，需要继续检查 MTU、RSS/IRQ、CPU 亲和、socket buffer、拥塞控制和中间路径配置。

## GridFlux 10GiB Smoke

命令使用 `tools/perf/run_gridftp_private_matrix.py --full`，固定默认保守策略：POSIX、TLS off、data TLS off、`checksum=crc32c`、`checksum_backend=auto`、`final_verify=full`、`manifest_flush=every_n_chunks`，不使用 `--keep-files`。

| direction | connections | bytes | result | throughput |
| --- | ---: | ---: | --- | ---: |
| STOR | 1 | 10GiB | pass | 2.993 Gbps |
| STOR | 4 | 10GiB | pass | 2.776 Gbps |
| STOR | 8 | 10GiB | pass | 2.959 Gbps |
| RETR | 1 | 10GiB | pass | 2.644 Gbps |
| RETR | 4 | 10GiB | pass | 3.385 Gbps |
| RETR | 8 | 10GiB | pass | 3.306 Gbps |

验收结果：6/6 pass，`source_sha256 == dest_sha256`，hash mismatch 为 `0`。runner 在全部 case 通过后输出过一次 `leftover gridflux process detected` 并以非零退出；随后立即检查两台服务器进程，未发现残留 GridFlux 进程。因此本轮传输正确性按 pass 记录，同时保留该 cleanup warning。

## 产物

- 环境采集：`tools/perf/results/20260522T134000Z_lab-env.txt`
- smoke raw CSV：`tools/perf/results/20260522T135246Z_gridftp-private-matrix-full.csv`
- smoke summary CSV：`tools/perf/results/20260522T135246Z_gridftp-private-matrix-full-summary.csv`
- 本报告：`docs/perf/LAB_100G_ENVIRONMENT_READINESS.md`

## 下一步

1. 先优化/归因 TCP baseline，目标是让 `iperf3` 明显接近 100G，再扩大 GridFlux 矩阵。
2. 对 GridFlux 当前 2.6-3.4 Gbps 做分层归因：存储读写、CRC32C、manifest flush、final verify、buffer/chunk size、CPU 和 NUMA。
3. 在 TCP 与 10GiB 阶段解释清楚前，不启动小服务器根分区上的 100GiB repeat。
