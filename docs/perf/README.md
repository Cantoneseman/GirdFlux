# GridFlux 性能基线工具

本目录记录 GridFlux 的可复现性能工具。`run_loopback_matrix.py` 和 `run_private_once.sh` 仍用于 memory-to-memory TCP sink；`run_file_loopback_matrix.py` 和 `run_file_private_once.sh` 用于文件传输基线；`run_gridftp_private_matrix.py` 用于 GridFTP-like framed STOR/RETR 私网矩阵。Phase 2B 起文件传输默认启用 CRC32C chunk checksum，并支持 `--checksum none` 做性能对照。Phase 2C 起 CRC32C 支持 `auto` / `software` / `hardware` backend，`auto` 在 x86 SSE4.2 可用时选择 hardware。Phase 4F 新增可选 file-IO-only `io_uring` prototype；Phase 4G 已在真实 liburing 环境下验证；Phase 4H 增加 queue depth / batching opt-in 维度。默认仍是 POSIX backend，网络仍是 epoll，STOR/RETR 文件数据仍只走 GridFlux framed data channel。

## 基础构建验证

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13
cmake --build build
ctest --test-dir build --output-on-failure
```

## 环境采集

```bash
tools/perf/collect_env.sh --output tools/perf/results/env-local.md
```

输出为 Markdown，包含 OS/kernel、CPU、内存、IP、TCP sysctl，以及可用时的 `iperf3`、`fio`、`numactl`、`ethtool` 信息。

## Loopback Smoke Matrix

```bash
tools/perf/run_loopback_matrix.py --build-dir build --smoke --output-dir tools/perf/results
```

默认运行两组参数：`1 x 64KB` 和 `4 x 256KB`，默认总字节数为 `8388608`。输出 CSV 写入 `tools/perf/results/`。

## Loopback Full Matrix

```bash
tools/perf/run_loopback_matrix.py --build-dir build --bytes 1073741824 --output-dir tools/perf/results
```

默认扫描：

- connections：`1,4,8,16,32`
- buffer-size：`65536,262144,1048576,4194304`

## <redacted>二同步

远程同步需要人工确认后运行。脚本不会打印密码；如需密码登录，使用 `GRIDFLUX_SSH_PASSWORD` 环境变量。

```bash
export GRIDFLUX_SSH_PASSWORD='***'
tools/perf/sync_remote.sh --host root@<redacted> --source /root/projects/GridFlux --target /root/projects/GridFlux
```

同步后需要在<redacted>二构建：

```bash
ssh root@<redacted> 'cd /root/projects/GridFlux && cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=g++-13 && cmake --build build && ctest --test-dir build --output-on-failure'
```

## 私网单次测试

跨机测试需要人工确认<redacted>二已经同步并构建完成。默认从<redacted>一启动 server，并通过 SSH 在<redacted>二运行 client。

```bash
tools/perf/run_private_once.sh --remote root@<redacted> --server-host <redacted> --build-dir /root/projects/GridFlux/build --connections 8 --bytes 1073741824 --buffer-size 65536
```

输出 CSV 以及 server/client 原始日志写入 `tools/perf/results/`。

## 文件传输 Loopback Smoke Matrix

```bash
tools/perf/run_file_loopback_matrix.py \
  --build-dir build \
  --smoke \
  --bytes 67108864 \
  --connections 1,4,8 \
  --chunk-sizes 1048576,4194304 \
  --buffer-sizes 65536 \
  --checksum crc32c \
  --checksum-backend auto \
  --output-dir tools/perf/results
```

默认 smoke 覆盖 `connections=1,4,8`、`chunk_size=1MiB,4MiB`、`buffer_size=64KiB`。脚本为每个 case 生成源文件，运行 `gridflux-file-server` / `gridflux-file-client`，计算源/目标 sha256，并写 CSV。

如需和无 checksum 路径对照：

```bash
tools/perf/run_file_loopback_matrix.py \
  --build-dir build \
  --smoke \
  --bytes 67108864 \
  --connections 1,4 \
  --chunk-sizes 1048576 \
  --buffer-sizes 65536 \
  --checksum none \
  --output-dir tools/perf/results
```

## CRC32C Backend Microbenchmark

```bash
tools/benchmark/run_checksum_bench.py \
  --build-dir build \
  --bytes 67108864,268435456 \
  --output-dir tools/perf/results
```

脚本调用 `gridflux-checksum-bench`，默认扫描 `software,auto,hardware` backend，输出 CSV 到 `tools/perf/results/`。如果显式 `hardware` 在当前<redacted>不可用，会记录为 `skip`；`auto` 应回退到 software。单次命令也可直接运行：

```bash
./build/gridflux-checksum-bench --backend auto --bytes 67108864 --iterations 5
```

## Native Storage Benchmark

Phase 4C 新增 `gridflux-storage-bench`，它直接使用项目 `PosixFile` 路径测顺序写、读和 rewrite，不再用 Python IO 作为主要磁盘口径。Phase 4D 起 bench 输出每次 iteration raw 行和 aggregate 行，并记录 file IO call count、average bytes per call 与 file IO wait time。

```bash
python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build \
  --remote-build-dir /root/projects/GridFlux/build \
  --bytes 1073741824 \
  --modes write,read \
  --preallocates off,full \
  --file-io-advices off,sequential \
  --buffer-sizes 1048576 \
  --iterations 3 \
  --output-dir tools/perf/results
```

单次 C++ 命令也可直接运行：

```bash
./build/gridflux-storage-bench \
  --path /tmp/gridflux-storage-bench.bin \
  --mode all \
  --bytes 1073741824 \
  --buffer-size 1048576 \
  --iterations 1 \
  --preallocate off \
  --file-io-backend posix \
  --file-io-advice off
```

`--preallocate full` 使用 `posix_fallocate`。如果系统或文件系统返回错误，命令会失败并记录错误，不会静默降级为 off。
`--file-io-advice` 支持 `off`、`sequential`、`noreuse`、`dontneed`、`sequential_dontneed`；非 off 会显式调用 `posix_fadvise`，调用失败则当前 case 失败。
Phase 4F 起 `--file-io-backend` 支持 `posix|io_uring`。`posix` 是默认值；`io_uring` 只有在构建时显式启用 `-DGRIDFLUX_ENABLE_IO_URING=ON` 且探测到 liburing 时可用。Phase 4G 中本机和<redacted>二均已安装 `liburing-dev` 并完成真实 io_uring 构建、CTest 与 POSIX/io_uring 对比；即便如此，默认 backend 仍保持 POSIX。Phase 4H 起 storage bench 和 private matrix 支持 `--file-io-queue-depths` 与 `--file-io-batch-sizes`；未显式传 batch size 时默认跟随 queue depth。queue/batch 只影响 `io_uring` backend，POSIX 路径仅记录参数用于公平 CSV 对照。

Phase 4F/4G no-liburing fallback 验证：

```bash
cmake -S . -B build-iouring-probe -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_COMPILER=g++-13 \
  -DGRIDFLUX_ENABLE_IO_URING=ON
cmake --build build-iouring-probe
ctest --test-dir build-iouring-probe --output-on-failure

./build-iouring-probe/gridflux-storage-bench \
  --path /tmp/gridflux-iouring-unavailable.bin \
  --mode write \
  --bytes 1048576 \
  --buffer-size 65536 \
  --iterations 1 \
  --preallocate off \
  --file-io-backend io_uring
```

最后一条命令在无 liburing 环境下应非零退出，并包含 `file IO backend unavailable: io_uring`。

安装 liburing 后，可用如下方式采集 POSIX / io_uring 对照：

```bash
python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build \
  --remote-build-dir /root/projects/GridFlux/build \
  --bytes 1073741824 \
  --modes write,read \
  --preallocates off \
  --file-io-backends posix,io_uring \
  --file-io-queue-depths 1,4,8,16 \
  --file-io-advices off \
  --buffer-sizes 262144,1048576 \
  --iterations 3 \
  --output-dir tools/perf/results
```

Phase 4H queue-depth storage bench：

```bash
python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --bytes 1073741824 \
  --modes write,read,rewrite \
  --preallocates off \
  --file-io-backends posix,io_uring \
  --file-io-queue-depths 1,4,8,16 \
  --file-io-advices off \
  --buffer-sizes 262144,1048576 \
  --iterations 3 \
  --output-dir tools/perf/results
```

Phase 4I heavy queue-depth gate storage bench（注意：`--side local` 不再探测远端；只有 `remote|both` 会 SSH）：

```bash
python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --bytes 1073741824 \
  --modes write,read,rewrite \
  --file-io-backends posix,io_uring \
  --file-io-queue-depths 1,4,8,16 \
  --file-io-batch-sizes 1,4,8,16 \
  --buffer-sizes 262144,1048576 \
  --preallocates off \
  --iterations 3 \
  --output-dir tools/perf/results
```

Phase 4G 真实 liburing storage bench 命令：

```bash
cmake -S . -B build-io-uring-real -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=g++-13 \
  -DGRIDFLUX_ENABLE_IO_URING=ON
cmake --build build-io-uring-real
ctest --test-dir build-io-uring-real --output-on-failure

python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --bytes 1073741824 \
  --modes write,read,all \
  --preallocates off,full \
  --file-io-backends posix,io_uring \
  --file-io-advices off \
  --buffer-sizes 262144,1048576 \
  --iterations 3 \
  --output-dir tools/perf/results
```

## 文件传输私网单次测试

跨机文件测试需要人工确认<redacted>二已同步并构建。源文件生成在 client 所在<redacted>二，目标文件生成在 server 所在<redacted>一；脚本不会打印密码，如需密码登录使用 `GRIDFLUX_SSH_PASSWORD`。

```bash
export GRIDFLUX_SSH_PASSWORD='***'
tools/perf/run_file_private_once.sh \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --connections 4 \
  --bytes 268435456 \
  --chunk-size 1048576 \
  --buffer-size 65536 \
  --checksum crc32c \
  --checksum-backend auto \
  --output-dir tools/perf/results
```

输出 CSV 以及 server/client 原始日志写入 `tools/perf/results/`。结果只有在 server/client 均成功且 `source_sha256 == dest_sha256` 时才标记为 `pass`。

## 文件传输私网 checksum resume smoke

该脚本从<redacted>一启动 server，在<redacted>二生成 source，并先用 `--max-chunks` 制造 partial transfer，再双端 `--resume` 补传。它用于可靠性 smoke，不属于性能矩阵。

```bash
export GRIDFLUX_SSH_PASSWORD='***'
tools/test/run_file_checksum_private_once.sh \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --connections 4 \
  --bytes 67108864 \
  --chunk-size 1048576 \
  --buffer-size 65536 \
  --checksum crc32c \
  --checksum-backend auto
```

## GridFTP-like Framed 私网矩阵

Phase 4A/4B 使用 `gridflux-gridftp-server` 控制面发起 STOR/RETR，但文件数据仍走 GridFlux framed data channel。脚本从<redacted>一启动 control server，通过 SSH 在<redacted>二运行 GridFlux-aware framed client，并为每个 case 分配唯一端口、root、transfer id、日志和临时路径。

Phase 4B 新增 host/link baseline：

```bash
export GRIDFLUX_SSH_PASSWORD='***'
tools/perf/run_private_host_baseline.py \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --bytes 1073741824 \
  --output-dir tools/perf/results
```

该脚本优先使用 `iperf3` / `fio`；如果任一端缺工具，会自动标记 fallback 并使用 GridFlux memory sink 或 Python 顺序 IO 探针，不安装系统软件。

Smoke 模式默认覆盖：

- direction：`stor,retr`
- bytes：`64MiB,128MiB`
- connections：`1,4`
- chunk size：`1MiB`
- buffer size：`64KiB`
- checksum：`crc32c,none`

```bash
export GRIDFLUX_SSH_PASSWORD='***'
tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --output-dir tools/perf/results
```

代表性 1GiB 样本：

```bash
tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor,retr \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c \
  --final-verify-policy full \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --output-dir tools/perf/results
```

Full matrix 必须显式传 `--full`，默认覆盖：

- direction：`stor,retr,stor-resume,retr-resume`
- bytes：`256MiB,1GiB`
- connections：`1,2,4,8,16`
- chunk size：`1MiB,4MiB,16MiB`
- buffer size：`64KiB,256KiB,1MiB`
- checksum：`crc32c,none`

```bash
tools/perf/run_gridftp_private_matrix.py --full ...
```

Phase 4B 的诊断/优化参数：

- `--final-verify-policy full|verified_chunks`：默认 `full`，保持完整 temp 重读验证。`verified_chunks` 只在 checksum 启用、verified chunks 覆盖完整文件且 manifest 已成功 flush 时跳过最终重读，否则 C++ 路径会回退到 `full` 并输出 `final_verify_policy_effective=full`。
- `--manifest-flush-interval-chunks <N>`：默认 `16`，控制 upload/download manifest 批量 flush 间隔；失败、resume precheck 和 commit 前仍强制 flush。
- `--host-baseline-csv <path>`：把对应 host/link baseline CSV 路径写入每个 matrix row，便于报告关联。

Phase 4C 的矩阵稳定性与存储参数：

- `--repeat <N>`：每个参数点重复运行 N 次，raw CSV 写 `repeat_index`。
- `--preallocates off,full`：扫描 STOR server temp 和 RETR download temp 的 preallocation 策略。默认 `off`。
- `--final-verify-policies full,verified_chunks`：扫描 final verify policy 维度。`verified_chunks` 仍为 opt-in，不作为默认可靠性语义。
- `--storage-bench-csv <path>`：把 native storage bench CSV 关联到每个 matrix row。
- 每次运行额外生成 `*-summary.csv`，按参数分组统计 throughput/elapsed 的 min、median、max 和 pass/fail count。

Phase 4D/4F 的 file IO 参数：

- `--file-io-backends posix,io_uring`：扫描 file IO backend。默认只跑 `posix`。无 liburing 时显式 `io_uring` case 会记录为 fail，不会静默跳过。
- `--file-io-buffer-sizes 0,1048576`：扫描文件 IO buffer 策略。`0` 表示关闭新增 buffering，保持 Phase 4C 默认；大于 0 时接收端会合并同一连接、同一 chunk 内连续 DATA 后再落盘。
- `--file-io-advices off,sequential`：扫描 POSIX advice。默认 `off`；非 off 调用失败则 case 失败。
- `--file-io-queue-depths 1,4,8,16`：Phase 4H 起扫描 io_uring queue depth。默认 `1`。对 POSIX 只记录，不改变行为。
- `--file-io-batch-sizes 1,4`：Phase 4H 起扫描 batch size。未传时每个 case 的 batch size 跟随 queue depth；实际每轮 submit 上限为 `min(batch_size, queue_depth)`。

Phase 4E 重型采样命令：

```bash
python3 tools/benchmark/run_storage_bench.py \
  --side both \
  --remote root@<redacted> \
  --build-dir build \
  --remote-build-dir /root/projects/GridFlux/build \
  --bytes 1073741824 \
  --modes write,read \
  --preallocates off,full \
  --file-io-advices off,sequential,sequential_dontneed \
  --buffer-sizes 65536,262144,1048576,4194304 \
  --iterations 3 \
  --output-dir tools/perf/results
```

```bash
python3 tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c \
  --checksum-backend auto \
  --preallocates off,full \
  --final-verify-policies full,verified_chunks \
  --file-io-buffer-sizes 0,1048576,4194304 \
  --file-io-advices off,sequential,sequential_dontneed \
  --repeat 3 \
  --case-timeout 600 \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --output-dir tools/perf/results
```

将上面矩阵命令分别替换为 `--directions stor --checksums none`、`--directions retr --checksums crc32c`、`--directions retr --checksums none`，分 4 批保存 raw/summary CSV。

Phase 4E 分析报告：

```bash
python3 tools/perf/analyze_phase4e.py \
  --storage-summary-csv <storage-summary.csv> \
  --matrix-summary-csv <stor-crc-summary.csv>,<stor-none-summary.csv>,<retr-crc-summary.csv>,<retr-none-summary.csv> \
  --matrix-raw-csv <stor-crc.csv>,<stor-none.csv>,<retr-crc.csv>,<retr-none.csv> \
  --output docs/perf/PHASE4E_IO_URING_GATE.md
```

Phase 4E 实测结论记录在 `docs/perf/PHASE4E_IO_URING_GATE.md`：默认仍保持 `file_io_buffer_size=0`、`file_io_advice=off`、`preallocate=off`、`final_verify_policy=full`，`verified_chunks` 继续 opt-in。

Phase 4G 真实 liburing 私网对比命令：

```bash
python3 tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor,retr \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c,none \
  --checksum-backend auto \
  --file-io-backends posix,io_uring \
  --file-io-buffer-sizes 0 \
  --file-io-advices off \
  --preallocates off \
  --final-verify-policies full \
  --repeat 3 \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --output-dir tools/perf/results
```

Phase 4G 结果记录在 `docs/perf/PHASE4G_IO_URING_REAL_VALIDATION.md`。当前结论：真实 io_uring 路径可编译、可运行、可测试、可对比，但同步 submit-and-wait v1 未证明适合替代默认 POSIX；如继续，应进入 queue depth / batching 原型。

Phase 4H queue-depth 私网 sample：

```bash
python3 tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor,retr \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c,none \
  --checksum-backend auto \
  --file-io-backends posix,io_uring \
  --file-io-queue-depths 1,4,8,16 \
  --file-io-buffer-sizes 0 \
  --file-io-advices off \
  --preallocates off \
  --final-verify-policies full \
  --repeat 3 \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --output-dir tools/perf/results
```

Phase 4H 当前实测报告见 `docs/perf/PHASE4H_IO_URING_QUEUE_DEPTH_RESULTS.md`。默认仍保持 `file_io_backend=posix`。

Phase 4I fixed the RETR queue/batch pass-through limitation from the Phase 4H sample and reran heavy repeat=3 sampling:

```bash
python3 tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor,retr \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c,none \
  --checksum-backend auto \
  --file-io-backends posix,io_uring \
  --file-io-queue-depths 1,4,8,16 \
  --file-io-buffer-sizes 262144 \
  --file-io-advices off \
  --preallocates off \
  --final-verify-policies full \
  --repeat 3 \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build-io-uring-real \
  --remote-build-dir /root/projects/GridFlux/build-io-uring-real \
  --output-dir tools/perf/results
```

Phase 4I analysis:

```bash
python3 tools/perf/analyze_phase4i.py \
  --storage-summary-csv tools/perf/results/20260517T122107Z_storage-bench-summary.csv \
  --matrix-summary-csv tools/perf/results/20260517T141550Z_gridftp-private-matrix-smoke-summary.csv \
  --output docs/perf/PHASE4I_HEAVY_QUEUE_DEPTH_GATE.md
```

Phase 4I 结论记录在 `docs/perf/PHASE4I_HEAVY_QUEUE_DEPTH_GATE.md`：queue-depth/batching 收益不稳定，未贯穿 STOR/RETR 和 crc32c/none，默认仍保持 POSIX。

## Public Release Hygiene

本地 `AGENTS.md` 是私有协作上下文，不得公开发布。公开发布前使用 export gate：

```bash
python3 tools/release/check_public_hygiene.py --path .
python3 tools/release/export_public_repo.py --output /tmp/gridflux-public --force
python3 tools/release/check_public_hygiene.py --path /tmp/gridflux-public --strict
test ! -f /tmp/gridflux-public/AGENTS.md
test -f /tmp/gridflux-public/AGENTS.example.md
```

私有工作区的 hygiene check 可能因本地 `AGENTS.md` 和历史私网拓扑记录失败；这是预期的发布闸门。公开目录必须由 `export_public_repo.py` 生成并通过 strict check。

Phase 4C repeat=3 代表性矩阵：

```bash
python3 tools/perf/run_gridftp_private_matrix.py \
  --smoke \
  --directions stor,retr \
  --bytes 1073741824 \
  --connections 8 \
  --chunk-sizes 4194304 \
  --buffer-sizes 262144 \
  --checksums crc32c,none \
  --preallocates off,full \
  --final-verify-policies full,verified_chunks \
  --file-io-buffer-sizes 0,1048576 \
  --file-io-advices off,sequential \
  --repeat 3 \
  --remote root@<redacted> \
  --server-host <redacted> \
  --local-build-dir /root/projects/GridFlux/build \
  --remote-build-dir /root/projects/GridFlux/build \
  --output-dir tools/perf/results
```

失败时脚本保留日志与临时路径并在 CSV 写入 `result=fail` 和错误摘要；成功 case 默认清理临时数据。脚本结束会检查本机与<redacted>二是否有遗留 `gridflux-gridftp-server` / `gridflux-file-*` 进程。

## CSV 字段

```text
timestamp,hostname,mode,host,port,connections,buffer_size,bytes,client_elapsed_seconds,client_throughput_gbps,server_elapsed_seconds,server_throughput_gbps,client_bytes,server_bytes,result
```

文件传输 CSV 字段：

```text
timestamp,mode,host,port,connections,chunk_size,buffer_size,bytes,checksum_enabled,checksum_algorithm,checksum_backend,skipped_bytes,resent_bytes,verified_bytes,manifest_flush_policy,manifest_flush_count,elapsed,throughput_gbps,source_sha256,dest_sha256,result
```

实际文件传输 CSV 还会附加 client/server 独立耗时、吞吐和日志路径，便于后续分析。CSV 内的 `source_sha256` / `dest_sha256` 是测试验收手段；内部恢复事实源是 manifest v2 `verified_chunks` 和 chunk checksum。

GridFTP-like 私网矩阵 CSV 字段：

```text
timestamp,mode,direction,bytes,connections,chunk_size,buffer_size,checksum_algorithm,checksum_backend,preallocate,file_io_backend,file_io_buffer_size,file_io_queue_depth,file_io_batch_size,file_io_advice,repeat_index,elapsed,throughput_gbps,skipped_bytes,resent_bytes,verified_bytes,manifest_flush_count,manifest_flush_policy,final_verify_policy,final_verify_policy_effective,stage_recv_seconds,stage_recv_bytes,stage_send_seconds,stage_send_bytes,stage_read_seconds,stage_read_bytes,stage_write_seconds,stage_write_bytes,stage_checksum_seconds,stage_checksum_bytes,stage_manifest_flush_seconds,stage_manifest_flush_bytes,stage_resume_precheck_seconds,stage_resume_precheck_bytes,stage_final_verify_seconds,stage_final_verify_bytes,stage_rename_commit_seconds,stage_rename_commit_bytes,stage_overall_seconds,stage_overall_bytes,stage_read_calls,stage_write_calls,stage_read_avg_bytes_per_call,stage_write_avg_bytes_per_call,file_io_wait_seconds,file_io_wait_bytes,io_uring_submit_count,io_uring_wait_count,io_uring_completion_count,io_uring_sqe_count,io_uring_partial_completion_count,io_uring_retry_count,io_uring_avg_bytes_per_sqe,host_baseline_csv,storage_bench_csv,source_sha256,dest_sha256,result,server_log,client_log,server_hostname,client_hostname,server_kernel,client_kernel,server_cpu_flags,client_cpu_flags,server_fs_type,client_fs_type,server_free_bytes,client_free_bytes
```

实际 CSV 还会附加 `transfer_id`、端口、临时路径和错误摘要。`throughput_gbps` / `elapsed` 优先使用接收端语义：STOR 取 server receiver，RETR 取 download client receiver。RETR sender 的 `verified_bytes` 表示 sender 已确认/发送的 verified range 字节；download client 的 `verified_bytes` 表示接收端本地校验完成字节。CSV 优先取接收端/client 语义，sender 值保留在原始日志中。

Phase 4B host baseline CSV 字段：

```text
timestamp,side,category,tool,bytes,elapsed_seconds,throughput_gbps,checksum_backend,hostname,kernel,cpu_flags,fs_type,free_bytes,log,result,error
```

Checksum benchmark CSV 字段：

```text
timestamp,hostname,algorithm,backend,bytes,iterations,buffer_size,elapsed_seconds,throughput_gbps,checksum,result,log
```

Storage benchmark CSV 字段：

```text
timestamp,side,operation,bytes,iterations,buffer_size,preallocate,file_io_backend,file_io_queue_depth,file_io_batch_size,file_io_advice,iteration,aggregate,elapsed_seconds,throughput_gbps,read_call_count,write_call_count,avg_read_bytes_per_call,avg_write_bytes_per_call,file_io_wait_seconds,io_uring_submit_count,io_uring_wait_count,io_uring_completion_count,io_uring_sqe_count,io_uring_partial_completion_count,io_uring_retry_count,io_uring_avg_bytes_per_sqe,hostname,kernel,fs_type,free_bytes,path,log,result,error
```

Storage bench wrapper 同时生成 `*-summary.csv`，按 side/operation/bytes/buffer/preallocate/file_io_backend/file_io_queue_depth/file_io_batch_size/file_io_advice 分组统计 throughput/elapsed 的 min、median、max。Phase 4I 起 summary 还聚合 io_uring submit/wait/completion/SQE/partial/retry/avg bytes per SQE 的 min、median、max。
