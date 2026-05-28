# GridFlux 项目索引

> 面向算力网的高速可靠数据传输底座。对外兼容 GridFTP 接口，对内采用自研高性能传输引擎。
> 覆盖三种传输场景：专线 TB 级网络、虚拟网络、广域网。

## 文档

| 文档 | 内容 |
|------|------|
| [DESIGN.md](docs/DESIGN.md) | 项目背景、目标场景、系统架构、技术选型、可行性与风险 |
| [ROADMAP.md](docs/ROADMAP.md) | 分阶段路线图、当前状态、决策记录 |
| [ENGINEERING.md](docs/ENGINEERING.md) | 工程规范、性能基准、验证方案、开发策略 |
| [DIRECTORY_TRANSFER.md](docs/DIRECTORY_TRANSFER.md) | 多文件/目录传输 alpha 用法、manifest 与恢复边界 |
| [DEMO.md](docs/DEMO.md) | Alpha demo 数据集、local/private demo runner 与 operator quickstart |
| [ARCHITECTURE_ALPHA.md](docs/ARCHITECTURE_ALPHA.md) | 完整 alpha 原型架构：控制面、framed data、manifest、目录、安全和 release gate |
| [SECURITY.md](docs/SECURITY.md) | Phase 6A token auth、Phase 6C control TLS 与 Phase 6D STOR/RETR data TLS alpha 安全边界 |
| [OBSERVABILITY.md](docs/OBSERVABILITY.md) | Phase 6B/6C/6D JSONL event log、稳定错误码、demo/gate/soak 排障入口 |
| [BETA1A_100G_READINESS.md](docs/perf/BETA1A_100G_READINESS.md) | Beta 1A 私网性能专项与 100G readiness 诊断报告 |
| [BETA1B_DATA_TLS_RESUME_AND_STOR_WRITE.md](docs/perf/BETA1B_DATA_TLS_RESUME_AND_STOR_WRITE.md) | Beta 1B data TLS resume blocker 修复与 STOR write/writeback 诊断 |
| [BETA1B_STOR_WRITEBACK_DIAGNOSIS.md](docs/perf/BETA1B_STOR_WRITEBACK_DIAGNOSIS.md) | Beta 1B-2 STOR receiver temp write/writeback focused A/B 诊断 |
| [BETA1B_RECEIVER_WRITEBACK_OPTIN.md](docs/perf/BETA1B_RECEIVER_WRITEBACK_OPTIN.md) | Beta 1B-3 opt-in drain-budget receiver writeback/backpressure 诊断 |
| [BETA1B_RECEIVER_WRITEBACK_STABILITY.md](docs/perf/BETA1B_RECEIVER_WRITEBACK_STABILITY.md) | Beta 1B-4 receiver writeback opt-in 稳定候选矩阵 |
| [BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md](docs/perf/BETA1B_STORAGE_SYSTEM_ATTRIBUTION.md) | Beta 1B-5 storage/system writeback 瓶颈归因 |
| [BETA1C_RETR_STABILITY.md](docs/perf/BETA1C_RETR_STABILITY.md) | Beta 1C RETR 稳定性复核与 beta 性能收口 |
| [BETA_PERFORMANCE_SUMMARY.md](docs/perf/BETA_PERFORMANCE_SUMMARY.md) | Beta 性能总览：host/storage、三方对比、STOR/RETR、TLS/checksum/io_uring 结论 |
| [100G_MIGRATION_CHECKLIST.md](docs/perf/100G_MIGRATION_CHECKLIST.md) | 100G 迁移前置检查清单，不执行迁移或 100G 测试 |
| [BASELINE_FTP_GRIDFTP_SMOKE.md](docs/perf/BASELINE_FTP_GRIDFTP_SMOKE.md) | 普通 FTP / 系统包 GridFTP 轻量对比摸底，不属于正式 release gate |
| [FTP_GRIDFTP_GRIDFLUX_COMPARISON.md](docs/perf/FTP_GRIDFTP_GRIDFLUX_COMPARISON.md) | 普通 FTP、原生 GridFTP、当前 GridFlux 三方吞吐对比 |
| [GRIDFTP_VS_GRIDFLUX_CLOUD_COMPARISON.md](docs/perf/GRIDFTP_VS_GRIDFLUX_CLOUD_COMPARISON.md) | Beta 云服务器原生 GridFTP vs GridFlux 完整对比实验 |
| [CLOUD_DISK_BOTTLENECK_PROOF.md](docs/perf/CLOUD_DISK_BOTTLENECK_PROOF.md) | 阿里云双机分层归因实验：网络、CRC32C、storage、STOR/RETR 阶段对照 |
| [ALPHA_LIMITATIONS.md](docs/release/ALPHA_LIMITATIONS.md) | 完整 alpha 限制清单与后续路线 |
| [BETA_LIMITATIONS.md](docs/release/BETA_LIMITATIONS.md) | Beta 限制清单、默认策略和 100G 前置边界 |
| [BETA_RELEASE_GATE.md](docs/release/BETA_RELEASE_GATE.md) | Beta gate 验收报告 |
| [BETA_RELEASE_CANDIDATE.md](docs/release/BETA_RELEASE_CANDIDATE.md) | Beta RC 收口报告 |
| [BETA_FREEZE.md](docs/release/BETA_FREEZE.md) | Beta 1E 长时间稳定性与迁移前冻结说明 |

新接手请按 DESIGN → ROADMAP → ENGINEERING 顺序阅读。

## 项目状态

**当前阶段：** Beta 针对性归因实验 — 云盘 / 文件系统 / OS writeback bottleneck proof

**技术栈：** C++20 · epoll 网络基线 · POSIX file IO 默认后端 · 可选 file-IO-only io_uring · CMake · Linux only

**目标场景：** 专线 TB 级（主线）· 虚拟网络 · 广域网

**下一步：** 在现有两台云服务器私网上运行 cloud disk bottleneck proof：用 iperf3、CRC32C、memory/sink、storage bench、GridFlux STOR/RETR 阶段指标证明当前 STOR 是否主要受硬盘写入 / 文件系统 / OS writeback 限制。当前不迁移 100G、不做 100G 测试、不改默认策略；结论只能代表当前云服务器环境。`verified_chunks`、io_uring、bounded/dirty_poll、preallocate full 均继续只作为 opt-in。

## AI 协作

本地私有 [AGENTS.md](AGENTS.md) 包含 AI 协作的上下文指引和私有测试拓扑，不能公开发布。公开仓库使用 [AGENTS.example.md](AGENTS.example.md) 作为脱敏模板。接手时先读本索引和 [ROADMAP.md](docs/ROADMAP.md)。
