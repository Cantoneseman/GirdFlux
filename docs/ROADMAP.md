# GridFlux 路线图

## 当前状态

**阶段：** Phase 4K — POSIX temp write/writeback 专项优化（已完成）

**已完成：** 项目设计、技术选型、工程规范制定、CMake 工程骨架初始化、GoogleTest 工具链测试、本机与<redacted>二构建验证、GridFTP 源码学习经验整理入设计文档、Phase 1.0 多连接 TCP sink 与本机 loopback 验证、Phase 1.1 性能基线脚本与 loopback smoke matrix、Phase 1.2A offset-aware 单文件传输闭环、Phase 1.2B 文件传输健壮性、Phase 1.3A 文件性能基线自动化、Phase 2A manifest/range-based 断点续传核心、Phase 2B CRC32C chunk checksum 与损坏注入验证、Phase 2C CRC32C backend 自动选择、manifest 批量 flush、恢复统计与 checksum benchmark、Phase 3A GridFTP 风格控制面 STOR 上传与 REST/GFID resume 映射、Phase 3B GridFTP 风格控制面 framed RETR 完整下载、Phase 3C 下载端 manifest/verified_chunks 与 RETR REST/GFID resume、Phase 3D 控制面 SIZE/MDTM/CWD/CDUP/LIST/NLST 与测试工具收敛。

**已完成补充：** Phase 4A 私网 GridFTP-like framed STOR/RETR 性能矩阵脚本、环境指标采集、smoke 矩阵、代表性 1GiB 样本和初步瓶颈判断；Phase 4B 阶段级诊断指标、host/link baseline、download manifest 批量 flush、final verify opt-in policy 和瓶颈报告；Phase 4C 原生 storage benchmark、temp preallocation opt-in、私网矩阵 repeat/summary CSV 和 verified_chunks 可靠性护栏；Phase 4D 文件 IO backend 抽象前置、POSIX file IO advice/buffering 选项、IO call 指标和 storage bench summary；Phase 4E 重型 1GiB repeat=3 storage/private matrix、POSIX knob 默认策略判断和 io_uring Phase 4F 设计闸门；Phase 4F 可选 file-IO-only io_uring backend 原型、CMake/liburing 探测、无 liburing stub fallback、脚本 backend 扫描维度和默认 POSIX 回归验证；Phase 4G 在真实 liburing 环境下完成 POSIX/io_uring storage bench 与私网 STOR/RETR 对照，并新增公开发布脱敏/export 工具链；Phase 4H 完成 file-IO-only io_uring queue depth / batching opt-in prototype、CSV 指标扩展和 smoke/1GiB sample；Phase 4I 完成 storage bench wrapper 修复、1GiB repeat=3 storage/private heavy matrix 和 queue-depth gate 报告；Phase 4J 完成 POSIX storage/writeback、checksum、manifest flush 和 final verify 路径诊断，新增双侧 sender/receiver 阶段字段、manifest flush policy 与 commit sync policy opt-in 诊断参数，以及 Phase 4J median 分析报告；Phase 4K 完成 POSIX temp write/writeback 专项优化实验，新增 POSIX write syscall 级指标、`posix_write_strategy=auto|direct|coalesced` opt-in 策略、storage/private matrix 维度和 Phase 4K median gate 报告。

**未开始：** 系统级文件传输调优、raw FTP stream STOR/RETR、GridFTP TLS/GSI、MLST/MLSD、网络 io_uring、多文件目录同步。

**下一步：** Phase 4L 继续围绕 POSIX 写回路径、RETR 发送/接收阶段和可靠性默认策略做专项评估；不改网络 epoll，不默认启用 io_uring，不改变 checksum/manifest/resume 语义。

---

## Phase 0：工程骨架

**目标：** 可编译、可测试、可运行的空项目。

- 初始化 CMake 项目结构。
- 配置 FetchContent 依赖（spdlog、googletest）。
- 建立 src/ 目录骨架。
- 配置 clang-format 和 clang-tidy。
- 编写第一个 GoogleTest 用例验证工具链。

**产出：** `cmake --build` 成功 + 测试通过。

---

## Phase 1：TCP 多流传输原型（6-8 周）

**目标：** 用最小复杂度打通端到端闭环，验证性能可行性。先 epoll，不依赖 io_uring。

**1.0 最小网络闭环（Week 1）**
- 多连接 TCP sink 程序（POSIX socket / epoll）。
- 内存到内存吞吐验证。
- 建立最小 `ConnectionContext`，集中管理单连接状态、EOF/错误和吞吐计数。

状态：已完成。本阶段产物为 `gridflux-server` / `gridflux-client`，用于多连接 memory-to-memory TCP sink smoke test。

**1.1 裸性能基线（Week 1-2）**
- 并发连接数扫描（4/8/16/32）。
- Buffer 大小扫描（64KB-4MB）。
- CPU/NUMA/中断分布记录。
- iperf3、fio 对比数据。
- 输出基线报告。

状态：工具已完成。已支持环境采集、loopback smoke/full matrix、rsync 远程同步脚本、私网单次测试脚本；完整 matrix 和跨机测试待人工确认后执行。

**1.2 最小传输引擎（Week 3-6）**
- Worker 模型 + 连接归属。
- 预分配 buffer 池。
- 固定 chunk + offset-aware frame 协议。
- `ChunkTask {transfer_id, chunk_id, offset, length}` 调度。
- 客户端/服务端框架。
- 单文件分块传输 + 多连接并行。
- 命令行参数（路径、连接数、chunk 大小）。

状态：Phase 1.2A 已完成。当前产物为 `gridflux-file-server` / `gridflux-file-client`，支持固定 64 字节 frame header、按 offset 写入、静态 chunk 分配、POSIX `pread/pwrite` 单文件 loopback 传输；未实现 manifest、断点续传、checksum pipeline、ACK/重传、GridFTP 控制面和 io_uring。

状态补充：Phase 1.2B 已完成。文件传输新增最终 `Complete/Error` 状态帧、`TransferProgress` range 完整性校验、临时文件 + rename 原子输出、默认拒绝覆盖、CTest 文件传输 smoke 回归。仍未实现 per-chunk ACK、ACK 重传窗口、manifest 和断点续传。

**1.3 性能验证与调优（Week 7-8）**
- 文件到文件性能测试。
- perf/flamegraph 瓶颈分析。
- socket buffer / chunk / 并发度调优。
- NUMA 绑定 + IRQ/RSS 亲和性。

状态：Phase 1.3A 已完成。新增文件传输 loopback matrix 和私网单次测试脚本，CSV 记录连接数、chunk size、buffer size、字节数、吞吐、耗时和源/目标 sha256；已完成 64MiB loopback smoke matrix 与 256MiB 私网 smoke。

**产出：** hpt-server / hpt-client v0.1，性能报告，调优参数模板。

---

## Phase 2：断点续传与可靠性（6-8 周）

**目标：** 从"能跑"到"能恢复"。

- Manifest 格式设计与持久化。
- 任务状态机（Created → Transferring → Verifying → Committed / Failed）。
- Chunk 级状态跟踪与断点续传。
- completed chunk 合并为 range list，用于恢复协商和减少状态体积。
- Chunk 级 checksum（XXH3 / CRC32C）。
- 临时文件 + 原子提交（rename）。
- 故障注入测试（kill -9 恢复）。

状态：Phase 2A 已完成。当前 `gridflux-file-server` / `gridflux-file-client` 支持 `SessionInit` / `ResumeResponse` 控制帧、`transfer_id`、服务端 manifest 持久化、stable temp path、completed range list、missing range 恢复计算、失败后保留 temp + manifest、`--resume` 补传缺失范围、`--max-chunks` 故障注入和 CTest resume smoke。

状态补充：Phase 2B 已完成。新增默认启用的 CRC32C chunk checksum、`ChunkComplete=7` 控制帧、manifest v2 `verified_chunks` 与 `manifest_body_crc32c`、resume 前 temp verified chunk 预检、client corruption 注入参数、checksum 故障注入 CTest、文件 perf CSV checksum 字段和可选 `--checksum none` 性能对照。仍未实现 per-chunk ACK/重传窗口、GridFTP 控制面、多文件目录同步和异步 checksum pipeline。

状态补充：Phase 2C 已完成。新增 CRC32C backend 选择（`auto` / `software` / `hardware`）、x86 SSE4.2 runtime dispatch、`gridflux-checksum-bench`、`TransferSessionConfig`、manifest 每 16 个 verified chunk 默认批量 flush、恢复统计输出和文件 perf CSV 扩展。`auto` 在本机与<redacted>二均选择 hardware；完整 1GiB 矩阵、异步 checksum worker、GridFTP 控制面和 io_uring 仍未实现。

**产出：** v0.2，断点续传 + 完整性保证。

---

## Phase 3：GridFTP 兼容控制面（4-6 周）

**目标：** 对外暴露 GridFTP 接口。

支持命令子集：

| 命令 | 用途 |
|------|------|
| USER/PASS | 基础认证 |
| TYPE I | 二进制模式 |
| SIZE | 文件大小查询 |
| PASV/EPSV | 被动模式 |
| STOR | 上传 |
| RETR | 下载 |
| REST | 断点偏移 |
| OPTS PARALLELISM | 并行流协商 |
| QUIT | 断开 |

不支持的命令返回 502。

状态：Phase 3A 已完成。新增 `gridflux-gridftp-server`，支持 USER/PASS、TYPE I、SYST、FEAT、PWD、NOOP、QUIT、EPSV/PASV、OPTS PARALLELISM、REST GFID token 和 STOR 上传。控制面采用 FTP/GridFTP 风格回复码，数据面继续使用 GridFlux framed protocol，不兼容普通 FTP raw STOR。`REST GFID:<transfer_id>` 映射到 manifest v2 `verified_chunks` / missing ranges；不支持 `REST offset` 假恢复。

状态补充：Phase 3B 已完成。`gridflux-gridftp-server` 新增 `RETR <path>`，支持从 `--root` 内读取普通文件并通过 GridFlux framed data channel 下载到 GridFlux-aware client。新增 `gridflux-file-download-client` 作为 framed RETR 接收端，默认 CRC32C auto/hardware 校验，成功后临时文件 rename 到目标路径。Phase 3B 不支持普通 FTP raw RETR，也不支持 RETR resume；`REST GFID:<transfer_id>` 后执行 `RETR` 会返回 `550`，下载恢复留到 Phase 3C。

状态补充：Phase 3C 已完成。`RETR` 下载方向新增接收端 download manifest：`<output>.gridflux.download.manifest` 记录 `transfer_id`、root-relative `source_path`、target/temp path、total size、chunk size、checksum algorithm、`verified_chunks` 与 `manifest_body_crc32c`。`gridflux-file-download-client --resume --transfer-id <id>` 会加载本地 manifest，预检 temp 中已 verified chunk，坏 chunk 移出 verified set 并作为 missing range 请求补传。`REST GFID:<transfer_id> + RETR <path>` 现在映射到下载端 manifest/verified_chunks 恢复流程；`REST offset` 仍拒绝。Phase 3C 仍不支持普通 FTP raw RETR、Mode E、SPAS/SPOR、GSI/DCAU/PROT 或第三方 server-to-server。

状态补充：Phase 3D 已完成。`gridflux-gridftp-server` 新增 `SIZE`、`MDTM`、`CWD`、`CDUP`、`LIST` 和 `NLST`。`CWD/PWD` 在 control session 内维护 root-relative 当前目录；所有路径通过统一 root-confined resolver 校验，拒绝绝对路径、`..` 和符号链接逃逸。`LIST/NLST` 使用 FTP-style ASCII metadata data channel，仅返回目录元数据；STOR/RETR 文件数据仍只支持 GridFlux framed protocol。新增 metadata/list loopback smoke 与私网 metadata/list smoke，并保持 STOR/RETR resume 回归通过。

兼容边界：

- Phase 3A 仅支持 `REST GFID:<transfer_id>`，映射到 manifest/chunk plan；不支持 `REST offset` 单偏移恢复。
- Phase 3B 的 `RETR` 为完整 framed download；Phase 3C 起 `REST GFID + RETR` 支持真正 resume，恢复事实源在下载接收端 manifest/verified_chunks。
- Phase 3D 的 `LIST/NLST` 为 ASCII 目录元数据通道，不改变 STOR/RETR framed data channel 边界，也不代表支持普通 FTP raw STOR/RETR。
- `OPTS PARALLELISM=N` / `OPTS RETR parallelism=N` 映射到内部连接数，并设置上限。
- 第一版不支持 `SPAS`、`SPOR`、完整 Mode E、GSI/DCAU/PROT、server-to-server 第三方传输。

**产出：** v0.3，上层系统可通过 GridFTP 接口调用。

---

## Phase 4：高性能后端与多场景适配（8-12 周）

**目标：** io_uring 高性能后端 + 虚拟网络/广域网适配。

- io_uring 传输后端（网络 + 文件 IO）。
- epoll vs io_uring 基准对比。
- 虚拟网络适配（自适应并发度、动态 chunk）。
- 广域网实验（QUIC / FEC 原型）。
- per-core worker 演进。
- HugePages / fixed buffer / O_DIRECT。

**4A 私网性能基线矩阵、指标收敛与 io_uring 前置评估**

- 新增私网 GridFTP-like framed transfer matrix，覆盖 `STOR`、`RETR`、`STOR resume`、`RETR resume`。
- 扫描 bytes、connections、chunk size、buffer size、checksum algorithm/backend。
- 输出 CSV、原始日志、环境字段和代表性 1GiB 样本。
- 先基于现有 POSIX socket + epoll + pread/pwrite 判断瓶颈，不直接引入 io_uring。

状态：已完成。新增 `tools/perf/run_gridftp_private_matrix.py`，支持 smoke/full、STOR/RETR/STOR resume/RETR resume、环境字段、CSV 与日志归档。已完成私网 smoke 矩阵、代表性 1GiB 样本、resume 指标探针、本机与<redacted>二 full CTest。full 私网矩阵和 fio/iperf 对照留给后续人工确认后运行。

**4B 性能瓶颈拆解与低风险优化**

- STOR server、upload client、RETR sender、download client 增加阶段级诊断字段。
- 新增私网 host/link baseline，优先 iperf3/fio，缺失时使用 GridFlux memory sink 和 Python 顺序 IO fallback。
- download manifest flush 与 upload manifest flush 对齐，默认每 16 个 verified chunk 批量保存。
- 新增 `final_verify_policy=full|verified_chunks`。默认 `full` 保持 Phase 4A 语义；`verified_chunks` 仅在 checksum 非 none、verified chunks 完整覆盖且 manifest 已 flush 时跳过最终 full temp reread。
- `run_gridftp_private_matrix.py` 扩展阶段字段、host baseline 引用、final verify policy 和 manifest flush interval 参数。

状态：已完成。私网 baseline 显示 memory sink 约 19.1Gbps、CRC32C hardware 约 47.6Gbps，而 Python fallback 顺序写约 1.03Gbps。1GiB STOR checksum none 与 crc32c 接近，阶段日志显示主要时间在 temp 写入/落盘；1GiB RETR crc32c 的 full final verify 明显拖慢，opt-in `verified_chunks` 将 RETR 1GiB 从约 1.68Gbps 提升到约 3.36Gbps。Phase 4B 未引入 io_uring。

**4C 存储路径优化、重复采样稳定性、verified_chunks 可靠性硬化**

- 新增 `gridflux-storage-bench`，用项目 `PosixFile` / `pread/pwrite` 路径测 sequential write/read/rewrite。
- 新增 `--preallocate off|full`，默认 off；full 使用 `posix_fallocate`，失败不静默 fallback。
- `run_gridftp_private_matrix.py` 支持 `--repeat`、preallocate 维度、final verify policy 维度和 summary CSV。
- `verified_chunks` 仍为 opt-in；checksum none、missing ranges、manifest flush 失败均不得进入 verified_chunks commit。

状态：已完成。已完成本机 build、126/126 CTest、双机 1GiB native storage bench 和 1GiB repeat=3 私网 STOR/RETR matrix。median 结论记录在 `docs/perf/PHASE4C_STORAGE.md`：STOR 仍以写入/落盘路径为主瓶颈，`preallocate=full` 不适合作为默认，RETR 在 checksum 启用时可受益于 opt-in `verified_chunks`，但默认仍保持 `final_verify_policy=full`。

**4D 存储落盘路径优化与 IO 后端抽象前置**

- 新增非虚函数文件 IO backend/config/stats 抽象，Phase 4D 只实现 POSIX `pread/pwrite` concrete backend。
- 新增 `--file-io-backend posix`、`--file-io-buffer-size` 和 `--file-io-advice`，默认保持 Phase 4C 行为。
- STOR temp write、upload source read、RETR source read、download temp write 统一经过 file IO helper。
- STOR/RETR 日志和私网矩阵 CSV 追加 read/write call count、average bytes per call 和 file IO wait 指标。
- `gridflux-storage-bench` 输出 iteration raw 行与 aggregate 行，wrapper 生成 raw + summary CSV。

状态：已完成。本阶段未实现 io_uring；只完成 POSIX 路径可插拔边界、显式 file IO advice、同连接同 chunk 的写入 coalescing、IO call 指标和性能脚本扩展。验收与 median 结论记录在 `docs/perf/PHASE4D_FILE_IO.md`。

**4E 重型性能验收与 io_uring 设计闸门**

- 补跑 Phase 4D 未完成的 1GiB repeat=3 重型采样。
- storage bench 覆盖本机/<redacted>二、write/read、64KiB/256KiB/1MiB/4MiB buffer、preallocate off/full、file IO advice off/sequential/sequential_dontneed。
- GridFTP-like private matrix 覆盖 STOR/RETR、crc32c/none、preallocate off/full、final verify full/verified_chunks、file IO buffer 0/1MiB/4MiB、file IO advice off/sequential/sequential_dontneed。
- 新增 `tools/perf/analyze_phase4e.py`，将 raw/summary CSV 汇总为 gate 报告。

状态：已完成。重型 storage bench 384/384 pass，GridFTP-like 1GiB matrix 432/432 pass，报告见 `docs/perf/PHASE4E_IO_URING_GATE.md`。结论：`file_io_buffer_size`、`file_io_advice`、`preallocate=full` 均不满足默认启用门槛，`verified_chunks` 仍保持 opt-in；数据支持 Phase 4F 做可选 file-IO-only io_uring 原型设计和实现评审，但不支持 Phase 4E 直接切主路径。

**4F 可选 file-IO-only io_uring prototype**

- 新增 `GRIDFLUX_ENABLE_IO_URING` CMake 选项，默认 `OFF`。
- `ON` 时探测 `liburing.h` 与 `uring` library；缺失时不 fatal，继续编译 unavailable stub。
- `FileIoBackendKind` 支持 `posix|io_uring`，默认仍为 `posix`；热路径使用 concrete context + switch，不引入虚函数。
- io_uring v1 只覆盖 regular file `readAtAll` / `writeAtAll` 等价语义，不处理 socket IO，不改变网络 epoll。
- `gridflux-storage-bench`、storage bench wrapper 和 GridFTP-like private matrix 支持 backend 维度。
- 无 liburing 环境下，显式 `--file-io-backend io_uring` 返回清晰 unavailable 错误；默认 POSIX build/CTest 不受影响。

状态：已完成。本机与<redacted>二均未发现 liburing pkg-config、头文件或动态库；Phase 4F 验收以 fallback 路径为主。默认 build 与 `GRIDFLUX_ENABLE_IO_URING=ON` stub build 均通过 full CTest，显式 io_uring storage bench 清晰失败。报告见 `docs/perf/PHASE4F_IO_URING_PROTOTYPE.md`。

**4G 真实 liburing 验证与公开发布脱敏闸门**

- 新增公开发布 hygiene/export 工具：`tools/release/check_public_hygiene.py` 与 `tools/release/export_public_repo.py`。
- `AGENTS.md` 明确为本地私有文件，`.gitignore` 排除本地 AGENTS、build 产物、perf 结果、认证材料和大文件；新增公开安全模板 `AGENTS.example.md`。
- 本机与<redacted>二安装并探测 liburing，使用 `build-io-uring-real` 独立 Release 构建验证 `GRIDFLUX_ENABLE_IO_URING=ON`。
- 扩展 io_uring correctness test：真实可用时 `FileIoTest.IoUringContextReadWriteSmokeWhenAvailable` 实际运行，completion loop fake test 覆盖 partial completion、retry 和错误传播。
- 跑 1GiB storage bench 与 GridFTP-like STOR/RETR private matrix 的 POSIX/io_uring 对照，以 median 为判断口径。

状态：已完成。本机与<redacted>二均安装 liburing 并完成 `build-io-uring-real` Release full CTest，Phase 4G-fix 后 full CTest 为 `136/136` passed。storage bench 320/320 pass，GridFTP-like private matrix 24/24 pass。结论记录在 `docs/perf/PHASE4G_IO_URING_REAL_VALIDATION.md`：io_uring v1 同步 submit-and-wait 原型正确可用，但未证明应替代 POSIX 默认；继续保持 `file_io_backend=posix` 默认，io_uring 仅 opt-in。Phase 4G-fix 已修复公开发布闸门：export 现在排除任意层级 build-like 目录、CMake/Ninja 产物和未知二进制，strict hygiene 对这些内容直接失败，并新增 release hygiene fixture 测试。Phase 4H 设计草案见 `docs/perf/PHASE4H_IO_URING_QUEUE_DEPTH_PLAN.md`。

**4H file-IO-only io_uring queue depth / batching opt-in prototype**

- `FileIoConfig` 新增 `queueDepth` 与 `batchSize`，默认均为 `1`；CLI 新增 `--file-io-queue-depth` 与 `--file-io-batch-size`，合法范围 `1..256`。
- io_uring backend 在单次 `readAtAll` / `writeAtAll` 内按 contiguous range 拆分 SQE，并按 queue depth / batch size 提交；调用返回语义仍为完整 range 成功或明确错误。
- `FileIoStats`、C++ key=value 日志、storage bench 和 GridFTP-like private matrix CSV 追加 submit/wait/completion/SQE/partial/retry/avg bytes per SQE 指标。
- POSIX backend 默认不变；queue/batch 对 POSIX 只记录，不改变行为。网络 epoll、STOR/RETR framed data path、checksum、manifest、resume、final verify 均不变。

状态：已完成。本机与<redacted>二默认 Debug full CTest 均为 `139/139` passed；`build-io-uring-real` Release full CTest 均为 `139/139` passed，`FileIoTest.IoUringContextReadWriteSmokeWhenAvailable` 为 `Passed`。公开 export strict hygiene 继续通过。已完成 64MiB storage bench queue-depth smoke、64MiB private STOR/RETR queue-depth smoke、1GiB private STOR/RETR queue-depth sample。结论记录在 `docs/perf/PHASE4H_IO_URING_QUEUE_DEPTH_RESULTS.md`：queue depth 原型正确可用，但小样本和 1GiB sample 未证明应替代 POSIX 默认；io_uring 继续 explicit opt-in。

**4I io_uring queue-depth 重型采样与决策闸门**

- 修复 `tools/benchmark/run_storage_bench.py --side local` 误触发远端 SSH/fs snapshot/cleanup 的问题。
- storage bench wrapper 与 GridFTP private matrix summary CSV 增加 io_uring submit/wait/completion/SQE/partial/retry/avg bytes per SQE 聚合字段。
- 新增 `tools/perf/analyze_phase4i.py` 和 `docs/perf/PHASE4I_HEAVY_QUEUE_DEPTH_GATE.md`，以 repeat=3 median 判断是否继续 io_uring batching 深化。
- 跑 1GiB storage bench heavy matrix：local+remote、write/read/rewrite、posix/io_uring、qd/batch 1/4/8/16、buffer 256KiB/1MiB、repeat=3。
- 跑 1GiB GridFTP-like private matrix：STOR/RETR、crc32c/none、posix/io_uring、qd=batch 1/4/8/16、repeat=3。

状态：已完成。本机与<redacted>二默认 Debug full CTest 均为 `140/140` passed；`build-io-uring-real` Release full CTest 均为 `140/140` passed，真实 io_uring smoke 为 `Passed`。storage heavy `1536` rows / `0` failures；private matrix `96` cases / `0` failures，sha256 全一致。结论：queue-depth/batching 收益不稳定，未贯穿 STOR/RETR 与 crc32c/none；默认继续保持 POSIX，io_uring 仍 explicit opt-in，下一步回到 POSIX storage/writeback、checksum、final verify 路径分析。

**4J POSIX storage/writeback、checksum 与 final verify 路径瓶颈拆解**

- STOR/RETR 日志追加角色语义别名：STOR receiver 的 data receive/temp write/checksum/manifest/final verify/finalize；RETR sender 的 source read/network send/checksum；RETR receiver 的 download temp write/manifest/final verify/finalize。
- `run_gridftp_private_matrix.py` raw CSV 保留接收端主指标，同时新增 `sender_*` / `receiver_*` 阶段、file IO 和 io_uring 指标；summary CSV 对阶段字段输出 min/median/max。
- 新增 `--manifest-flush-policy every_n_chunks|final_only`，默认 `every_n_chunks`；`final_only` 仅用于诊断，失败/commit 前仍强制 flush，不允许误提交。
- 新增 `--commit-sync-policy none|fsync_file|fsync_file_and_dir`，默认 `none`；仅用于测量 rename/fsync 成本。
- 新增 `tools/perf/analyze_phase4j.py` 和 `docs/perf/PHASE4J_POSIX_PIPELINE_DIAGNOSIS.md`，按 repeat=3 median 输出阶段占比和 gate 结论。

状态：已完成。本机与<redacted>二默认 Debug full CTest 均为 `142/142` passed；`build-io-uring-real` Release full CTest 均为 `142/142` passed，真实 io_uring smoke 为 `Passed`。Phase 4J 主私网矩阵 `96/96` pass，writeback add-on `12/12` pass，sha256 全一致。median 结论：STOR 主要瓶颈是 temp write/writeback，最佳 STOR 约 `1.45 Gbps` 且 temp write 占已测阶段约 `89%`；RETR 最佳约 `4.58 Gbps`，主要由 receiver download write 与 sender network send 构成；checksum 对 STOR 影响很小，final verify/verified_chunks 对 RETR 有 opt-in 收益但不改变默认。默认继续保持 POSIX、`final_verify_policy=full`、`preallocate=off`、`manifest_flush_policy=every_n_chunks`。

**4K POSIX temp write/writeback 专项优化**

- `FileIoStats` 追加 POSIX write syscall 级诊断字段：logical write call、pwrite syscall、retry、short、zero、total bytes 和平均每次 syscall 字节数。
- POSIX backend 的 `writeAtAll` 统一走可统计 `pwrite` loop；`PosixFile::writeAtAll` 保持兼容。
- 新增 `--posix-write-strategy auto|direct|coalesced`。默认 `auto` 保持既有语义：`file_io_buffer_size=0` 直写，`>0` 使用 contiguous coalescing；`direct` 用于强制直写 A/B，`coalesced` 需要显式 file IO buffer。
- `gridflux-storage-bench`、`run_storage_bench.py` 和 `run_gridftp_private_matrix.py` 均增加 write strategy 维度，raw/summary CSV 保留 write syscall 指标。
- 新增 `tools/perf/analyze_phase4k.py` 和 `docs/perf/PHASE4K_POSIX_WRITEBACK_OPTIMIZATION.md`，以 1GiB repeat=3 median 判断是否存在可默认启用的 POSIX 写入策略。

状态：已完成。本机与<redacted>二默认 Debug full CTest 均为 `144/144` passed；`build-io-uring-real` Release full CTest 均为 `144/144` passed，真实 io_uring smoke 为 `Passed`。Phase 4K storage bench `384` cases / `0` failures，GridFTP-like private matrix `96` cases / `0` failures，sha256 全一致。median 结论：没有发现同时稳定改善 STOR 与 RETR 的默认策略候选；STOR crc32c 下 `coalesced` 256KiB 有约 `10%` median 提升，但 checksum none 下退化，RETR 也不稳定。默认继续保持 `posix_write_strategy=auto` 且 `file_io_buffer_size=0`；`direct` / `coalesced` 保留为 opt-in 诊断策略。

**产出：** 多后端可切换引擎，各场景性能数据。

---

## Phase 5：产品化加固

- TLS 1.3 / token 认证。
- 容错容灾（自动重连、超时重试、死任务清理）。
- 结构化日志 + Prometheus 指标。
- systemd 集成、优雅停机、配置热加载。
- 长稳测试（72h+）、ASan/LSan。
- CI/CD。

**产出：** v1.0 生产可用。

---

## Phase 6：高级能力（持续演进）

- 多文件批量传输与目录同步。
- 小文件聚合传输（tar-streaming）。
- Server-to-server 第三方传输。
- 多节点并行（分布式）。
- QoS 与带宽限速。
- 国密 SM4。
- Web 管理界面 / SDK。

---

## 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-15 | C++20 | coroutine 支持异步，底层控制力 |
| 2026-05-15 | Phase 1 用 epoll，io_uring 后续引入 | 降低初期复杂度，先闭环再优化 |
| 2026-05-15 | CMake 3.20+ | 兼容 Ubuntu 22.04 系统源，同时满足工程骨架需求 |
| 2026-05-15 | Linux only | 算力网节点均为 Linux |
| 2026-05-15 | 数据面裸字节流 | 零序列化开销 |
| 2026-05-15 | 控制面 Protobuf | 版本演进，manifest 持久化 |
| 2026-05-15 | 三场景分阶段覆盖 | 专线优先，虚拟网络和广域网后续 |
| 2026-05-15 | Transport Adapter 抽象 | TCP/QUIC/RDMA 多后端可插拔 |
| 2026-05-15 | GridFTP 源码只借鉴模型，不复制实现 | 保留分层经验，规避历史包袱与许可证风险 |
| 2026-05-15 | 内部数据面不复刻完整 Mode E | 用 offset-aware chunk frame 降低复杂度 |
| 2026-05-15 | Manifest 是断点恢复事实源 | 单 offset 不适合多流乱序恢复 |
| 2026-05-16 | 文件传输成功必须等待 server 最终状态帧 | 避免 client 只因发送完字节就误判成功 |
| 2026-05-16 | Phase 2A 使用 manifest + range list 恢复，不使用单 REST offset | 借鉴 GridFTP restart marker/range list 思想，内部事实源保持可恢复、可合并 |
| 2026-05-16 | transfer_id 通过 SessionInit payload 传递 | 不破坏既有 64 字节 Data/Fin frame header 和类型编号 |
| 2026-05-16 | Phase 2 manifest 使用稳定 key=value 文本格式 | 断点恢复核心先避免引入额外依赖，后续控制面可独立评估 Protobuf |
| 2026-05-16 | Phase 2B 默认启用 CRC32C chunk checksum | 以轻量内置实现先建立 chunk 级完整性事实源，后续可替换硬件 CRC32C 或 XXH3 |
| 2026-05-16 | manifest v2 的 verified_chunks 是恢复事实源 | `completed_ranges` 仅作为派生可读字段，最终 sha256 只作为测试验收手段 |
| 2026-05-16 | CRC32C backend 使用 runtime dispatch | x86 SSE4.2 可用时 `auto` 选择 hardware；不可用时回退 software，不让整个 core 依赖 `-msse4.2` |
| 2026-05-16 | manifest flush 默认每 16 个 verified chunk 批量保存 | 减少热路径 manifest 写入；崩溃后最多重传未 flush 的 chunk，不会误提交 output |
| 2026-05-16 | Phase 3A 控制面 STOR 使用 GridFlux framed data channel | 先复用 manifest/checksum/resume 数据面，不为 raw FTP stream 另造低可靠路径 |
| 2026-05-16 | REST marker 使用 `GFID:<transfer_id>` | 明确映射到 manifest v2 `verified_chunks` 和 missing ranges，不支持单 offset 假恢复 |
| 2026-05-16 | Phase 3B 控制面 RETR 使用 GridFlux framed data channel | 复用 chunk frame/checksum/chunk planner，避免普通 FTP raw stream 旁路可靠性语义 |
| 2026-05-16 | RETR resume 延后到 Phase 3C | 下载恢复需要接收端 manifest/verified_chunks 事实源，Phase 3B 先交付完整 framed download 并明确 `REST GFID + RETR` 返回 550 |
| 2026-05-16 | Phase 3C 下载恢复事实源放在 download client 本地 manifest | RETR sender 不维护下载状态，接收端根据 verified_chunks 派生 missing ranges，避免单 offset 或完整重传伪恢复 |
| 2026-05-16 | SessionInit payload 可选携带 `source_path` | RETR resume 需要校验 REST token 对应的源路径；旧 STOR/upload payload 不带该字段仍兼容 |
| 2026-05-16 | Phase 3D LIST/NLST 使用 ASCII metadata data channel | 目录元数据兼容常用 GridFTP/FTP 控制面行为，但文件 STOR/RETR 仍只走 GridFlux framed data channel |
| 2026-05-16 | Phase 3D 统一 root-confined path resolver | CWD、SIZE、MDTM、LIST、NLST、STOR 和 RETR 共用路径安全规则，防止 `..` 或符号链接逃逸 root |
| 2026-05-16 | Phase 4A 不直接引入 io_uring | 先用现有 epoll/pread/pwrite framed STOR/RETR 私网矩阵定位 checksum、磁盘 IO、socket/epoll、buffer/chunk 或控制面调度瓶颈 |
| 2026-05-16 | Phase 4A CSV 以接收端吞吐为主指标 | STOR 取 server receiver，RETR 取 download client receiver；sender 统计保留在原始日志用于交叉分析 |
| 2026-05-16 | Phase 4B 增加阶段级诊断后仍不引入 io_uring | host/link baseline 与阶段日志显示 1GiB 主要瓶颈在落盘写入、manifest flush 和 final verify，不是 epoll/syscall 优先 |
| 2026-05-16 | final verify 默认保持 `full`，`verified_chunks` 仅 opt-in | 不削弱 checksum/resume/manifest 可靠性；只有 verified chunks 完整覆盖、manifest 已 flush 且 checksum 启用时才跳过最终重读 |
| 2026-05-16 | download manifest flush 默认每 16 个 verified chunk 批量保存 | 与 upload manifest 策略对齐，减少热路径 manifest 写入；崩溃后最多重传未 flush chunk，不会误提交 |
| 2026-05-16 | Phase 4C preallocation 默认 off，full 失败即失败 | 保持 Phase 4B 行为默认不变；显式 preallocate 用于诊断/优化，不把失败伪装成成功 |
| 2026-05-16 | Phase 4C 以 repeat median 作为性能报告主口径 | fresh 样本波动较大，单次最好值不足以指导是否进入 io_uring |
| 2026-05-17 | Phase 4D 文件 IO backend 先抽象为 POSIX concrete backend | 为后续 io_uring 接入准备边界，但不在热路径引入虚函数，也不盲目替换网络层 |
| 2026-05-17 | Phase 4D 默认 `file_io_buffer_size=0`、`file_io_advice=off` | 保持 Phase 4C 默认语义；buffering/advice 只作为显式诊断和优化开关 |
| 2026-05-17 | Phase 4E 不默认启用 file IO buffer/advice/preallocate | 1GiB repeat=3 median 未显示这些 POSIX knobs 同时改善 STOR 和 RETR；`sequential_dontneed` 明显有害 |
| 2026-05-17 | Phase 4E 允许 Phase 4F 设计可选 file-IO-only io_uring prototype | POSIX file IO wait/write mass 仍高，低风险 POSIX knobs 未解决双向瓶颈；但主路径和默认 backend 仍保持 POSIX |
| 2026-05-17 | Phase 4F io_uring backend 可选、file-IO-only、默认关闭 | 当前两机缺 liburing，必须保证默认 POSIX 完整可用；io_uring 只作为显式 backend 原型，不改变网络 epoll 或可靠性语义 |
| 2026-05-17 | `GRIDFLUX_ENABLE_IO_URING=ON` 缺依赖时 build stub fallback | 便于同一源码在无 liburing 节点继续构建和测试，显式请求 io_uring 时运行时报清晰 unavailable |
| 2026-05-17 | Phase 4G 公开发布必须通过 export hygiene gate | 本地 `AGENTS.md` 含私有测试拓扑，公开发布只能使用脱敏 `AGENTS.example.md` 和 export 工具生成的目录 |
| 2026-05-17 | Phase 4G 真实 liburing 验证后仍保持 POSIX 默认 | storage bench 与私网 STOR/RETR median 未证明同步等待式 io_uring v1 可稳定替代 POSIX；io_uring 继续 opt-in |
| 2026-05-17 | Phase 4H 若继续 io_uring，应聚焦 queue depth / batching | 当前 v1 只验证接口正确性；若继续优化，应在 file-IO-only 边界内评估异步深度和批量 SQE，而不是切网络 epoll |
| 2026-05-17 | Phase 4G-fix strict hygiene 不再跳过 build artifacts | 公开 export 曾因 build-* 历史目录混入失败；strict 模式必须将 build-like 目录、CMake/Ninja 产物和未知二进制视为发布阻断项 |
| 2026-05-17 | Phase 4H 先以 queue depth/batching opt-in 设计推进 | 只扩展 file-IO-only io_uring 原型，不改网络 epoll、不改默认 POSIX、不改变可靠性事实源 |
| 2026-05-17 | Phase 4H queue depth/batching 原型保持 opt-in | storage/private smoke 和 1GiB sample 均通过，但 median 未证明 queue depth 可稳定替代 POSIX 默认；下一步若继续需做 repeat=3 重型采样或优化 SQE batching |
| 2026-05-17 | Phase 4I 不继续深化 io_uring batching 默认路径 | repeat=3 1GiB storage/private matrix 全部通过，但 io_uring queue-depth 收益不稳定且未贯穿 STOR/RETR 与 crc32c/none；默认 POSIX 保持不变，下一步回到 POSIX storage/writeback、checksum、final verify 分析 |
| 2026-05-17 | Phase 4J 继续保持 POSIX 默认并聚焦写入路径 | repeat=3 私网 median 显示 STOR 主要耗时在 temp write/writeback，checksum 不是主瓶颈；RETR 可通过 opt-in verified_chunks 改善但默认仍保持 full final verify |
| 2026-05-17 | `manifest_flush_policy=final_only` 和 `commit_sync_policy=*` 仅为诊断开关 | final_only 失败/commit 前仍强制 flush，不改变恢复事实源；commit fsync 用于测量 rename/fsync 成本，默认继续 `none` |
| 2026-05-17 | Phase 4K 不默认启用 POSIX coalesced write strategy | 1GiB repeat=3 显示 coalescing 的收益不贯穿 STOR/RETR 与 crc32c/none；默认继续 `auto` + `file_io_buffer_size=0`，`direct`/`coalesced` 仅保留 opt-in 诊断 |

---

## 文档更新规则

- 完成一个 Phase → 更新"当前状态"。
- 新技术决策 → 追加"决策记录"。
- 发现阻塞 → 在"当前状态"下记录。
- 计划调整 → 更新对应 Phase。
