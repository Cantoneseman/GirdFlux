#include "gridflux/core/io/tree_transfer_client.h"

#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <random>
#include <regex>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "gridflux/checkpoint/transfer_manifest.h"
#include "gridflux/config/file_download_options.h"
#include "gridflux/config/file_transfer_options.h"
#include "gridflux/core/io/file_download_client.h"
#include "gridflux/core/io/file_transfer_client.h"
#include "gridflux/core/io/socket_utils.h"
#include "gridflux/core/tree/tree_manifest.h"
#include "gridflux/core/tree/tree_scan.h"

namespace gridflux::core::io {
namespace {

struct ControlReply {
    int code = 0;
    std::vector<std::string> lines;
};

class ControlClient {
   public:
    [[nodiscard]] common::Status connectTo(const std::string& host, std::uint16_t port) {
        host_ = host;
        addrinfo hints{};
        hints.ai_family = AF_UNSPEC;
        hints.ai_socktype = SOCK_STREAM;
        addrinfo* results = nullptr;
        const std::string portText = std::to_string(port);
        const int gaiStatus = ::getaddrinfo(host.c_str(), portText.c_str(), &hints, &results);
        if (gaiStatus != 0) {
            return common::Status::runtimeError(std::string("getaddrinfo: ") +
                                                gai_strerror(gaiStatus));
        }
        int lastError = 0;
        for (addrinfo* item = results; item != nullptr; item = item->ai_next) {
            UniqueFd candidate(
                ::socket(item->ai_family, item->ai_socktype | SOCK_CLOEXEC, item->ai_protocol));
            if (!candidate.isValid()) {
                lastError = errno;
                continue;
            }
            if (::connect(candidate.get(), item->ai_addr, item->ai_addrlen) == 0) {
                fd_ = std::move(candidate);
                break;
            }
            lastError = errno;
        }
        ::freeaddrinfo(results);
        if (!fd_.isValid()) {
            return common::Status::systemError("connect: " + std::string(std::strerror(lastError)),
                                               lastError);
        }
        auto greeting = readReply();
        if (!greeting.isOk()) {
            return greeting.status();
        }
        if (greeting.value().code != 220) {
            return common::Status::runtimeError("unexpected control greeting");
        }
        return common::Status::ok();
    }

    [[nodiscard]] common::Status login(const std::string& user, const std::string& password,
                                       std::uint32_t connections) {
        auto userReply = command("USER " + user);
        if (!userReply.isOk() || userReply.value().code != 331) {
            return userReply.isOk() ? common::Status::runtimeError("USER rejected")
                                    : userReply.status();
        }
        auto passReply = command("PASS " + password);
        if (!passReply.isOk() || passReply.value().code != 230) {
            return passReply.isOk() ? common::Status::runtimeError("PASS rejected")
                                    : passReply.status();
        }
        auto typeReply = command("TYPE I");
        if (!typeReply.isOk() || typeReply.value().code != 200) {
            return typeReply.isOk() ? common::Status::runtimeError("TYPE I rejected")
                                    : typeReply.status();
        }
        auto optsReply = command("OPTS PARALLELISM=" + std::to_string(connections));
        if (!optsReply.isOk() || optsReply.value().code != 200) {
            return optsReply.isOk() ? common::Status::runtimeError("OPTS PARALLELISM rejected")
                                    : optsReply.status();
        }
        return common::Status::ok();
    }

    [[nodiscard]] common::Result<std::uint16_t> epsv() {
        auto reply = command("EPSV");
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 229) {
            return common::Status::runtimeError("EPSV rejected");
        }
        static const std::regex pattern(R"(\(\|\|\|([0-9]+)\|\))");
        std::smatch match;
        const std::string text = joined(reply.value());
        if (!std::regex_search(text, match, pattern)) {
            return common::Status::runtimeError("failed to parse EPSV port");
        }
        const auto port = static_cast<unsigned long>(std::stoul(match[1].str()));
        if (port == 0 || port > 65535) {
            return common::Status::runtimeError("EPSV port out of range");
        }
        return static_cast<std::uint16_t>(port);
    }

    [[nodiscard]] common::Status rest(const std::string& transferId) {
        auto reply = command("REST GFID:" + transferId);
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 350) {
            return common::Status::runtimeError("REST GFID rejected");
        }
        return common::Status::ok();
    }

    [[nodiscard]] common::Result<std::string> startTransfer(const std::string& verb,
                                                            const std::string& path) {
        auto reply = command(verb + " " + path);
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 150) {
            return common::Status::runtimeError(verb + " rejected: " + joined(reply.value()));
        }
        static const std::regex pattern(R"(transfer_id=GFID:([A-Za-z0-9._-]+))");
        std::smatch match;
        const std::string text = joined(reply.value());
        if (!std::regex_search(text, match, pattern)) {
            return common::Status::runtimeError("failed to parse transfer_id");
        }
        return match[1].str();
    }

    [[nodiscard]] common::Status waitTransferComplete() {
        auto reply = readReply();
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 226) {
            return common::Status::runtimeError("transfer did not complete: " + joined(reply.value()));
        }
        return common::Status::ok();
    }

    [[nodiscard]] common::Result<std::vector<std::string>> nlst(const std::string& path) {
        auto port = epsv();
        if (!port.isOk()) {
            return port.status();
        }
        auto openReply = sendOnly("NLST " + path);
        if (!openReply.isOk()) {
            return openReply;
        }
        auto opening = readReply();
        if (!opening.isOk()) {
            return opening.status();
        }
        if (opening.value().code != 150) {
            return common::Status::runtimeError("NLST rejected");
        }
        auto payload = readAsciiData(port.value());
        if (!payload.isOk()) {
            return payload.status();
        }
        auto complete = readReply();
        if (!complete.isOk()) {
            return complete.status();
        }
        if (complete.value().code != 226) {
            return common::Status::runtimeError("NLST did not complete");
        }
        std::vector<std::string> names;
        std::istringstream input(payload.value());
        std::string line;
        while (std::getline(input, line)) {
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }
            if (!line.empty()) {
                names.push_back(line);
            }
        }
        return names;
    }

    [[nodiscard]] common::Result<std::uint64_t> size(const std::string& path) {
        auto reply = command("SIZE " + path);
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 213 || reply.value().lines.empty()) {
            return common::Status::runtimeError("SIZE rejected");
        }
        const std::string line = reply.value().lines.front();
        const std::size_t space = line.find(' ');
        if (space == std::string::npos) {
            return common::Status::runtimeError("SIZE response missing value");
        }
        return static_cast<std::uint64_t>(std::stoull(line.substr(space + 1)));
    }

    [[nodiscard]] common::Result<std::int64_t> mdtm(const std::string& path) {
        auto reply = command("MDTM " + path);
        if (!reply.isOk()) {
            return reply.status();
        }
        if (reply.value().code != 213 || reply.value().lines.empty()) {
            return common::Status::runtimeError("MDTM rejected");
        }
        return 0;
    }

   private:
    [[nodiscard]] common::Status sendOnly(const std::string& commandText) {
        const std::string text = commandText + "\r\n";
        std::size_t completed = 0;
        while (completed < text.size()) {
            const ssize_t sent =
                ::send(fd_.get(), text.data() + completed, text.size() - completed, MSG_NOSIGNAL);
            if (sent > 0) {
                completed += static_cast<std::size_t>(sent);
                continue;
            }
            if (sent < 0 && errno == EINTR) {
                continue;
            }
            if (sent < 0) {
                return common::Status::systemError("send control: " +
                                                       std::string(std::strerror(errno)),
                                                   errno);
            }
            return common::Status::runtimeError("send control returned zero bytes");
        }
        return common::Status::ok();
    }

    [[nodiscard]] common::Result<ControlReply> command(const std::string& commandText) {
        const common::Status sendStatus = sendOnly(commandText);
        if (!sendStatus.isOk()) {
            return sendStatus;
        }
        return readReply();
    }

    [[nodiscard]] common::Result<ControlReply> readReply() {
        auto first = readLine();
        if (!first.isOk()) {
            return first.status();
        }
        ControlReply reply;
        reply.lines.push_back(first.value());
        if (first.value().size() >= 3 && std::isdigit(static_cast<unsigned char>(first.value()[0])) &&
            std::isdigit(static_cast<unsigned char>(first.value()[1])) &&
            std::isdigit(static_cast<unsigned char>(first.value()[2]))) {
            reply.code = std::stoi(first.value().substr(0, 3));
        }
        if (first.value().size() >= 4 && first.value()[3] == '-') {
            const std::string expected = first.value().substr(0, 3) + " ";
            while (true) {
                auto line = readLine();
                if (!line.isOk()) {
                    return line.status();
                }
                reply.lines.push_back(line.value());
                if (line.value().starts_with(expected)) {
                    break;
                }
            }
        }
        return reply;
    }

    [[nodiscard]] common::Result<std::string> readLine() {
        while (true) {
            const std::size_t newline = buffer_.find('\n');
            if (newline != std::string::npos) {
                std::string line = buffer_.substr(0, newline + 1);
                buffer_.erase(0, newline + 1);
                while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
                    line.pop_back();
                }
                return line;
            }
            char chunk[512];
            const ssize_t received = ::recv(fd_.get(), chunk, sizeof(chunk), 0);
            if (received > 0) {
                buffer_.append(chunk, static_cast<std::size_t>(received));
                continue;
            }
            if (received == 0) {
                return common::Status::runtimeError("control connection closed");
            }
            if (errno == EINTR) {
                continue;
            }
            return common::Status::systemError("recv control: " + std::string(std::strerror(errno)),
                                               errno);
        }
    }

    [[nodiscard]] common::Result<std::string> readAsciiData(std::uint16_t port) const {
        addrinfo hints{};
        hints.ai_family = AF_UNSPEC;
        hints.ai_socktype = SOCK_STREAM;
        addrinfo* results = nullptr;
        const std::string portText = std::to_string(port);
        const int gaiStatus = ::getaddrinfo(host_.c_str(), portText.c_str(), &hints, &results);
        if (gaiStatus != 0) {
            return common::Status::runtimeError(std::string("getaddrinfo data: ") +
                                                gai_strerror(gaiStatus));
        }
        UniqueFd dataFd;
        int lastError = 0;
        for (addrinfo* item = results; item != nullptr; item = item->ai_next) {
            UniqueFd candidate(
                ::socket(item->ai_family, item->ai_socktype | SOCK_CLOEXEC, item->ai_protocol));
            if (!candidate.isValid()) {
                lastError = errno;
                continue;
            }
            if (::connect(candidate.get(), item->ai_addr, item->ai_addrlen) == 0) {
                dataFd = std::move(candidate);
                break;
            }
            lastError = errno;
        }
        ::freeaddrinfo(results);
        if (!dataFd.isValid()) {
            return common::Status::systemError("connect data: " + std::string(std::strerror(lastError)),
                                               lastError);
        }
        std::string payload;
        char chunk[4096];
        while (true) {
            const ssize_t received = ::recv(dataFd.get(), chunk, sizeof(chunk), 0);
            if (received > 0) {
                payload.append(chunk, static_cast<std::size_t>(received));
                continue;
            }
            if (received == 0) {
                return payload;
            }
            if (errno == EINTR) {
                continue;
            }
            return common::Status::systemError("recv data: " + std::string(std::strerror(errno)),
                                               errno);
        }
    }

    static std::string joined(const ControlReply& reply) {
        std::ostringstream output;
        for (const std::string& line : reply.lines) {
            output << line << '\n';
        }
        return output.str();
    }

    UniqueFd fd_;
    std::string host_;
    std::string buffer_;
};

std::string generateTransferId() {
    constexpr char kDigits[] = "0123456789abcdef";
    std::random_device random;
    std::string id(32, '0');
    for (char& value : id) {
        value = kDigits[random() & 0x0F];
    }
    return id;
}

std::string joinRemotePath(const std::string& root, const std::string& relative) {
    if (root == "/") {
        return relative;
    }
    if (root.empty()) {
        return relative;
    }
    return root + "/" + relative;
}

common::Result<std::string> remoteRelativePath(const std::string& root, const std::string& path) {
    if (root == "/" || root.empty()) {
        const common::Status status = core::tree::validateTreeRelativePath(path);
        if (!status.isOk()) {
            return status;
        }
        return path;
    }
    if (path == root) {
        return common::Status::invalidArgument("remote file path equals tree root");
    }
    const std::string prefix = root + "/";
    if (!path.starts_with(prefix)) {
        return common::Status::invalidArgument("remote file path is outside tree root");
    }
    const std::string relative = path.substr(prefix.size());
    const common::Status status = core::tree::validateTreeRelativePath(relative);
    if (!status.isOk()) {
        return status;
    }
    return relative;
}

common::Status saveManifest(core::tree::TreeManifest* manifest, const std::string& path) {
    manifest->updatedAtUnixNanos = checkpoint::nowUnixNanos();
    return core::tree::saveTreeManifestAtomic(path, *manifest);
}

common::Status ensureControlReady(ControlClient* client, const config::TreeTransferOptions& options) {
    const common::Status connectStatus = client->connectTo(options.host, options.port);
    if (!connectStatus.isOk()) {
        return connectStatus;
    }
    return client->login(options.user, options.password, options.connections);
}

common::Status validateCompletedUploadFile(ControlClient* client, const std::string& remotePath,
                                           const core::tree::TreeFileRecord& record) {
    auto size = client->size(remotePath);
    if (!size.isOk()) {
        return size.status();
    }
    if (size.value() != record.size) {
        return common::Status::invalidArgument("completed upload file changed: " + record.relativePath);
    }
    return common::Status::ok();
}

common::Status validateCompletedDownloadFile(const std::string& localRoot,
                                             const core::tree::TreeFileRecord& record) {
    std::error_code error;
    const std::filesystem::path path = std::filesystem::path(localRoot) / record.relativePath;
    if (!std::filesystem::exists(path, error) || error) {
        return common::Status::invalidArgument("completed download file missing: " +
                                               record.relativePath);
    }
    if (!std::filesystem::is_regular_file(path, error) || error) {
        return common::Status::invalidArgument("completed download path is not a file: " +
                                               record.relativePath);
    }
    const std::uint64_t size = std::filesystem::file_size(path, error);
    if (error || size != record.size) {
        return common::Status::invalidArgument("completed download file changed: " +
                                               record.relativePath);
    }
    return common::Status::ok();
}

common::Status createParentDirectory(const std::filesystem::path& path) {
    std::error_code error;
    std::filesystem::create_directories(path.parent_path(), error);
    if (error) {
        return common::Status::systemError("create parent directory failed: " + error.message(),
                                           error.value());
    }
    return common::Status::ok();
}

}  // namespace

common::Status runTreeUploadClient(const config::TreeTransferOptions& options) {
    const std::string manifestPath = core::tree::treeManifestPathForUpload(options.sourceDir);
    core::tree::TreeManifest manifest;
    if (options.resume) {
        auto loaded = core::tree::loadTreeManifest(manifestPath);
        if (!loaded.isOk()) {
            return loaded.status();
        }
        manifest = loaded.value();
        if (manifest.mode != core::tree::TreeTransferMode::Upload ||
            manifest.rootLogicalPath != options.sourceDir ||
            manifest.checksumAlgorithm != options.checksumAlgorithm) {
            return common::Status::invalidArgument("tree upload manifest does not match request");
        }
    } else {
        auto files = core::tree::scanLocalTree(options.sourceDir);
        if (!files.isOk()) {
            return files.status();
        }
        manifest.mode = core::tree::TreeTransferMode::Upload;
        manifest.rootLogicalPath = options.sourceDir;
        manifest.checksumAlgorithm = options.checksumAlgorithm;
        manifest.createdAtUnixNanos = checkpoint::nowUnixNanos();
        manifest.updatedAtUnixNanos = manifest.createdAtUnixNanos;
        for (const auto& file : files.value()) {
            manifest.files.push_back(core::tree::TreeFileRecord{
                file.relativePath, file.size, file.mtimeUnixSeconds, generateTransferId(),
                core::tree::TreeFileStatus::Pending, ""});
        }
        const common::Status saveStatus = saveManifest(&manifest, manifestPath);
        if (!saveStatus.isOk()) {
            return saveStatus;
        }
    }

    ControlClient control;
    const common::Status readyStatus = ensureControlReady(&control, options);
    if (!readyStatus.isOk()) {
        return readyStatus;
    }

    std::uint64_t completedThisRun = 0;
    for (core::tree::TreeFileRecord& record : manifest.files) {
        const std::filesystem::path localPath = std::filesystem::path(options.sourceDir) / record.relativePath;
        if (options.resume) {
            std::error_code error;
            const std::uint64_t currentSize = std::filesystem::file_size(localPath, error);
            if (error || currentSize != record.size) {
                record.status = core::tree::TreeFileStatus::Changed;
                record.error = "source file changed";
                (void)saveManifest(&manifest, manifestPath);
                return common::Status::invalidArgument("source file changed: " + record.relativePath);
            }
        }
        const std::string remotePath = joinRemotePath(options.destDir, record.relativePath);
        if (record.status == core::tree::TreeFileStatus::Completed) {
            const common::Status status = validateCompletedUploadFile(&control, remotePath, record);
            if (!status.isOk()) {
                record.status = core::tree::TreeFileStatus::Changed;
                record.error = status.message();
                (void)saveManifest(&manifest, manifestPath);
                return status;
            }
            continue;
        }

        auto port = control.epsv();
        if (!port.isOk()) {
            return port.status();
        }
        const bool resumeFile = options.resume && record.status != core::tree::TreeFileStatus::Pending;
        if (resumeFile) {
            const common::Status restStatus = control.rest(record.transferId);
            if (!restStatus.isOk()) {
                return restStatus;
            }
        }
        auto transferId = control.startTransfer("STOR", remotePath);
        if (!transferId.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = transferId.status().message();
            (void)saveManifest(&manifest, manifestPath);
            return transferId.status();
        }
        if (!resumeFile) {
            record.transferId = transferId.value();
        }
        record.status = core::tree::TreeFileStatus::Transferring;
        record.error.clear();
        const common::Status saveStatus = saveManifest(&manifest, manifestPath);
        if (!saveStatus.isOk()) {
            return saveStatus;
        }

        config::FileTransferOptions fileOptions;
        fileOptions.host = options.host;
        fileOptions.port = port.value();
        fileOptions.connections = options.connections;
        fileOptions.bufferSize = options.bufferSize;
        fileOptions.chunkSize = options.chunkSize;
        fileOptions.path = localPath.string();
        fileOptions.transferId = record.transferId;
        fileOptions.checksumAlgorithm = options.checksumAlgorithm;
        fileOptions.checksumBackend = options.checksumBackend;
        fileOptions.resume = resumeFile;

        const common::Status transferStatus = runFileTransferClient(fileOptions);
        if (!transferStatus.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = transferStatus.message();
            (void)saveManifest(&manifest, manifestPath);
            return transferStatus;
        }
        const common::Status completeStatus = control.waitTransferComplete();
        if (!completeStatus.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = completeStatus.message();
            (void)saveManifest(&manifest, manifestPath);
            return completeStatus;
        }
        record.status = core::tree::TreeFileStatus::Completed;
        record.error.clear();
        const common::Status doneStatus = saveManifest(&manifest, manifestPath);
        if (!doneStatus.isOk()) {
            return doneStatus;
        }
        ++completedThisRun;
        if (options.maxFiles != 0 && completedThisRun >= options.maxFiles) {
            return common::Status::runtimeError("tree upload stopped after --max-files");
        }
    }
    std::cout << "tree_upload_complete files=" << manifest.files.size() << '\n';
    return common::Status::ok();
}

common::Status runTreeDownloadClient(const config::TreeTransferOptions& options) {
    const std::string manifestPath = core::tree::treeManifestPathForDownload(options.destDir);
    core::tree::TreeManifest manifest;
    ControlClient control;
    const common::Status readyStatus = ensureControlReady(&control, options);
    if (!readyStatus.isOk()) {
        return readyStatus;
    }

    if (options.resume) {
        auto loaded = core::tree::loadTreeManifest(manifestPath);
        if (!loaded.isOk()) {
            return loaded.status();
        }
        manifest = loaded.value();
        if (manifest.mode != core::tree::TreeTransferMode::Download ||
            manifest.rootLogicalPath != options.sourceDir ||
            manifest.checksumAlgorithm != options.checksumAlgorithm) {
            return common::Status::invalidArgument("tree download manifest does not match request");
        }
    } else {
        std::vector<std::string> stack{options.sourceDir};
        std::vector<core::tree::TreeFileRecord> records;
        while (!stack.empty()) {
            const std::string current = stack.back();
            stack.pop_back();
            auto names = control.nlst(current);
            if (!names.isOk()) {
                return names.status();
            }
            for (const std::string& name : names.value()) {
                const std::string candidate = joinRemotePath(current, name);
                auto size = control.size(candidate);
                if (size.isOk()) {
                    auto relative = remoteRelativePath(options.sourceDir, candidate);
                    if (!relative.isOk()) {
                        return relative.status();
                    }
                    records.push_back(core::tree::TreeFileRecord{
                        relative.value(), size.value(), 0, generateTransferId(),
                        core::tree::TreeFileStatus::Pending, ""});
                } else {
                    stack.push_back(candidate);
                }
            }
        }
        std::sort(records.begin(), records.end(),
                  [](const auto& left, const auto& right) {
                      return left.relativePath < right.relativePath;
                  });
        manifest.mode = core::tree::TreeTransferMode::Download;
        manifest.rootLogicalPath = options.sourceDir;
        manifest.checksumAlgorithm = options.checksumAlgorithm;
        manifest.createdAtUnixNanos = checkpoint::nowUnixNanos();
        manifest.updatedAtUnixNanos = manifest.createdAtUnixNanos;
        manifest.files = std::move(records);
        const common::Status saveStatus = saveManifest(&manifest, manifestPath);
        if (!saveStatus.isOk()) {
            return saveStatus;
        }
    }

    std::uint64_t completedThisRun = 0;
    for (core::tree::TreeFileRecord& record : manifest.files) {
        const std::filesystem::path localPath = std::filesystem::path(options.destDir) / record.relativePath;
        const std::string remotePath = joinRemotePath(options.sourceDir, record.relativePath);
        if (record.status == core::tree::TreeFileStatus::Completed) {
            const common::Status status = validateCompletedDownloadFile(options.destDir, record);
            if (!status.isOk()) {
                record.status = core::tree::TreeFileStatus::Changed;
                record.error = status.message();
                (void)saveManifest(&manifest, manifestPath);
                return status;
            }
            continue;
        }
        auto remoteSize = control.size(remotePath);
        if (!remoteSize.isOk()) {
            return remoteSize.status();
        }
        if (remoteSize.value() != record.size) {
            record.status = core::tree::TreeFileStatus::Changed;
            record.error = "remote file changed";
            (void)saveManifest(&manifest, manifestPath);
            return common::Status::invalidArgument("remote file changed: " + record.relativePath);
        }
        const common::Status parentStatus = createParentDirectory(localPath);
        if (!parentStatus.isOk()) {
            return parentStatus;
        }
        auto port = control.epsv();
        if (!port.isOk()) {
            return port.status();
        }
        const bool resumeFile = options.resume && record.status != core::tree::TreeFileStatus::Pending;
        if (resumeFile) {
            const common::Status restStatus = control.rest(record.transferId);
            if (!restStatus.isOk()) {
                return restStatus;
            }
        }
        auto transferId = control.startTransfer("RETR", remotePath);
        if (!transferId.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = transferId.status().message();
            (void)saveManifest(&manifest, manifestPath);
            return transferId.status();
        }
        if (!resumeFile) {
            record.transferId = transferId.value();
        }
        record.status = core::tree::TreeFileStatus::Transferring;
        record.error.clear();
        const common::Status saveStatus = saveManifest(&manifest, manifestPath);
        if (!saveStatus.isOk()) {
            return saveStatus;
        }

        config::FileDownloadOptions fileOptions;
        fileOptions.host = options.host;
        fileOptions.port = port.value();
        fileOptions.connections = options.connections;
        fileOptions.bufferSize = options.bufferSize;
        fileOptions.path = localPath.string();
        fileOptions.transferId = record.transferId;
        fileOptions.checksumAlgorithm = options.checksumAlgorithm;
        fileOptions.checksumBackend = options.checksumBackend;
        fileOptions.resume = resumeFile;

        const common::Status transferStatus = runFileDownloadClient(fileOptions);
        if (!transferStatus.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = transferStatus.message();
            (void)saveManifest(&manifest, manifestPath);
            return transferStatus;
        }
        const common::Status completeStatus = control.waitTransferComplete();
        if (!completeStatus.isOk()) {
            record.status = core::tree::TreeFileStatus::Failed;
            record.error = completeStatus.message();
            (void)saveManifest(&manifest, manifestPath);
            return completeStatus;
        }
        record.status = core::tree::TreeFileStatus::Completed;
        record.error.clear();
        const common::Status doneStatus = saveManifest(&manifest, manifestPath);
        if (!doneStatus.isOk()) {
            return doneStatus;
        }
        ++completedThisRun;
        if (options.maxFiles != 0 && completedThisRun >= options.maxFiles) {
            return common::Status::runtimeError("tree download stopped after --max-files");
        }
    }
    std::cout << "tree_download_complete files=" << manifest.files.size() << '\n';
    return common::Status::ok();
}

}  // namespace gridflux::core::io
