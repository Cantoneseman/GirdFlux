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

新接手请按 DESIGN → ROADMAP → ENGINEERING 顺序阅读。

## 项目状态

**当前阶段：** Phase 5A — 多文件/目录传输 alpha 能力（已完成）

**技术栈：** C++20 · epoll 网络基线 · POSIX file IO 默认后端 · 可选 file-IO-only io_uring · CMake · Linux only

**目标场景：** 专线 TB 级（主线）· 虚拟网络 · 广域网

**下一步：** 基于 alpha 级目录传输继续评估数据集级发布体验：更完整的私网目录性能矩阵、目录错误恢复 UX、changed-file 策略细化，或进入生产认证/TLS/GSI 设计。默认仍保持 POSIX backend，不切换网络 epoll 或 checksum/manifest/resume/final verify 语义。

## AI 协作

本地私有 [AGENTS.md](AGENTS.md) 包含 AI 协作的上下文指引和私有测试拓扑，不能公开发布。公开仓库使用 [AGENTS.example.md](AGENTS.example.md) 作为脱敏模板。接手时先读本索引和 [ROADMAP.md](docs/ROADMAP.md)。
