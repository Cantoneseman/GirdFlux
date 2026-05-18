#include "gridflux/config/tree_transfer_options.h"

#include <charconv>
#include <filesystem>
#include <limits>
#include <string_view>

#include "gridflux/core/tree/tree_scan.h"
#include "gridflux/protocol/control/control_auth.h"

namespace gridflux::config {
namespace {

constexpr std::uint32_t kMaxConnections = 64;
constexpr std::uint32_t kMaxFileParallelism = 16;
constexpr std::uint32_t kMaxBufferSize = 16 * 1024 * 1024;
constexpr std::uint64_t kMaxChunkSize = 1024ULL * 1024ULL * 1024ULL * 1024ULL;

common::Result<std::uint64_t> parseUnsigned(std::string_view value, std::string_view name) {
    if (value.empty()) {
        return common::Status::invalidArgument(std::string(name) + " must not be empty");
    }
    std::uint64_t parsed = 0;
    const char* begin = value.data();
    const char* end = value.data() + value.size();
    const auto result = std::from_chars(begin, end, parsed, 10);
    if (result.ec != std::errc() || result.ptr != end) {
        return common::Status::invalidArgument(std::string(name) + " must be a decimal integer");
    }
    return parsed;
}

common::Status requireValue(int argc, int index, std::string_view option) {
    if (index + 1 >= argc) {
        return common::Status::invalidArgument(std::string(option) + " requires a value");
    }
    return common::Status::ok();
}

common::Status validateLocalDirectory(const std::string& path, std::string_view option) {
    std::error_code error;
    if (!std::filesystem::exists(path, error) || error) {
        return common::Status::invalidArgument(std::string(option) + " must exist");
    }
    if (!std::filesystem::is_directory(path, error) || error) {
        return common::Status::invalidArgument(std::string(option) + " must be a directory");
    }
    return common::Status::ok();
}

common::Status validateRemoteDirArgument(const std::string& path, std::string_view option) {
    if (path.empty()) {
        return common::Status::invalidArgument(std::string(option) + " must not be empty");
    }
    if (path == "/") {
        return common::Status::ok();
    }
    return core::tree::validateTreeRelativePath(path);
}

}  // namespace

common::Result<TreeTransferOptions> parseTreeTransferOptions(int argc, const char* const* argv,
                                                             TreeTransferRole role) {
    TreeTransferOptions options;
    bool hasSourceDir = false;
    bool hasDestDir = false;
    int index = 1;
    while (index < argc) {
        const std::string_view option(argv[index]);
        if (option == "--resume") {
            options.resume = true;
            index += 1;
            continue;
        }

        const common::Status valueStatus = requireValue(argc, index, option);
        if (!valueStatus.isOk()) {
            return valueStatus;
        }
        const std::string_view value(argv[index + 1]);

        if (option == "--host") {
            if (value.empty()) {
                return common::Status::invalidArgument("--host must not be empty");
            }
            options.host = std::string(value);
        } else if (option == "--port") {
            auto parsed = parseUnsigned(value, "--port");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0 || parsed.value() > std::numeric_limits<std::uint16_t>::max()) {
                return common::Status::invalidArgument("--port must be in range 1..65535");
            }
            options.port = static_cast<std::uint16_t>(parsed.value());
        } else if (option == "--source-dir") {
            if (value.empty()) {
                return common::Status::invalidArgument("--source-dir must not be empty");
            }
            options.sourceDir = std::string(value);
            hasSourceDir = true;
        } else if (option == "--dest-dir") {
            if (value.empty()) {
                return common::Status::invalidArgument("--dest-dir must not be empty");
            }
            options.destDir = std::string(value);
            hasDestDir = true;
        } else if (option == "--connections") {
            auto parsed = parseUnsigned(value, "--connections");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0 || parsed.value() > kMaxConnections) {
                return common::Status::invalidArgument("--connections must be in range 1..64");
            }
            options.connections = static_cast<std::uint32_t>(parsed.value());
        } else if (option == "--file-parallelism") {
            auto parsed = parseUnsigned(value, "--file-parallelism");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0 || parsed.value() > kMaxFileParallelism) {
                return common::Status::invalidArgument(
                    "--file-parallelism must be in range 1..16");
            }
            options.fileParallelism = static_cast<std::uint32_t>(parsed.value());
        } else if (option == "--chunk-size") {
            auto parsed = parseUnsigned(value, "--chunk-size");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0 || parsed.value() > kMaxChunkSize) {
                return common::Status::invalidArgument(
                    "--chunk-size must be in range 1..1099511627776");
            }
            options.chunkSize = parsed.value();
        } else if (option == "--buffer-size") {
            auto parsed = parseUnsigned(value, "--buffer-size");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0 || parsed.value() > kMaxBufferSize) {
                return common::Status::invalidArgument(
                    "--buffer-size must be in range 1..16777216");
            }
            options.bufferSize = static_cast<std::uint32_t>(parsed.value());
        } else if (option == "--checksum") {
            auto parsed = checksum::parseChecksumAlgorithm(value);
            if (!parsed.isOk()) {
                return parsed.status();
            }
            options.checksumAlgorithm = parsed.value();
        } else if (option == "--checksum-backend") {
            auto parsed = checksum::parseChecksumBackend(value);
            if (!parsed.isOk()) {
                return parsed.status();
            }
            options.checksumBackend = parsed.value();
        } else if (option == "--max-files") {
            auto parsed = parseUnsigned(value, "--max-files");
            if (!parsed.isOk()) {
                return parsed.status();
            }
            if (parsed.value() == 0) {
                return common::Status::invalidArgument("--max-files must be greater than zero");
            }
            options.maxFiles = parsed.value();
        } else if (option == "--auth-mode") {
            auto parsed = protocol::control::parseAuthMode(value);
            if (!parsed.isOk()) {
                return parsed.status();
            }
            options.authMode = protocol::control::authModeName(parsed.value());
        } else if (option == "--auth-token-file") {
            if (value.empty()) {
                return common::Status::invalidArgument("--auth-token-file must not be empty");
            }
            options.authTokenFile = std::string(value);
        } else if (option == "--user") {
            if (value.empty()) {
                return common::Status::invalidArgument("--user must not be empty");
            }
            options.user = std::string(value);
        } else if (option == "--password") {
            if (value.empty()) {
                return common::Status::invalidArgument("--password must not be empty");
            }
            options.password = std::string(value);
        } else if (option == "--json-summary" || option == "--summary-json") {
            if (value.empty()) {
                return common::Status::invalidArgument(std::string(option) + " must not be empty");
            }
            options.jsonSummaryPath = std::string(value);
        } else {
            return common::Status::invalidArgument("unknown option: " + std::string(option));
        }
        index += 2;
    }

    if (!hasSourceDir) {
        return common::Status::invalidArgument("--source-dir is required");
    }
    if (!hasDestDir) {
        return common::Status::invalidArgument("--dest-dir is required");
    }
    if (options.authMode == "token") {
        if (options.authTokenFile.empty()) {
            return common::Status::invalidArgument("--auth-token-file is required in token mode");
        }
        auto token = protocol::control::loadTokenFile(options.authTokenFile);
        if (!token.isOk()) {
            return token.status();
        }
    }
    if (role == TreeTransferRole::Upload) {
        const common::Status sourceStatus = validateLocalDirectory(options.sourceDir, "--source-dir");
        if (!sourceStatus.isOk()) {
            return sourceStatus;
        }
        const common::Status destStatus = validateRemoteDirArgument(options.destDir, "--dest-dir");
        if (!destStatus.isOk()) {
            return destStatus;
        }
    } else {
        const common::Status sourceStatus = validateRemoteDirArgument(options.sourceDir, "--source-dir");
        if (!sourceStatus.isOk()) {
            return sourceStatus;
        }
        if (!options.resume) {
            std::error_code error;
            std::filesystem::create_directories(options.destDir, error);
            if (error) {
                return common::Status::systemError("create destination directory failed: " +
                                                       error.message(),
                                                   error.value());
            }
        }
    }
    return options;
}

std::string treeTransferUsage(const char* programName, TreeTransferRole role) {
    const char* sourceText = role == TreeTransferRole::Upload ? "<local_dir>" : "<remote_dir>";
    const char* destText = role == TreeTransferRole::Upload ? "<remote_dir>" : "<local_dir>";
    return std::string("Usage: ") + programName +
           " --host <server-ip> --port <port> --source-dir " + sourceText + " --dest-dir " +
           destText +
           " [--connections <N>] [--file-parallelism <N>] [--chunk-size <bytes>] "
           "[--buffer-size <bytes>] [--checksum <crc32c|none>] "
           "[--checksum-backend <auto|software|hardware>] [--resume] [--max-files <N>] "
           "[--auth-mode anonymous|token] [--auth-token-file <path>] "
           "[--user <name>] [--password <password>] [--json-summary <path>]";
}

}  // namespace gridflux::config
