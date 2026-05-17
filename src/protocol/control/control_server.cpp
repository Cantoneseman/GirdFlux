#include "gridflux/protocol/control/control_server.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <limits>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "gridflux/checkpoint/transfer_manifest.h"
#include "gridflux/config/file_transfer_options.h"
#include "gridflux/core/io/file_download_sender.h"
#include "gridflux/core/io/file_transfer_server.h"
#include "gridflux/core/io/socket_utils.h"
#include "gridflux/protocol/control/control_command.h"
#include "gridflux/storage/posix_file.h"

namespace gridflux::protocol::control {
namespace {

constexpr std::uint16_t kPassiveScanLimit = 512;

struct PassiveListener {
    core::io::UniqueFd fd;
    std::uint16_t port = 0;
};

common::Status systemStatus(const char* operation, int errorNumber) {
    return common::Status::systemError(std::string(operation) + ": " + std::strerror(errorNumber),
                                       errorNumber);
}

common::Status sendAll(int fd, const std::string& text) {
    std::size_t completed = 0;
    while (completed < text.size()) {
        const ssize_t sent =
            ::send(fd, text.data() + completed, text.size() - completed, MSG_NOSIGNAL);
        if (sent > 0) {
            completed += static_cast<std::size_t>(sent);
            continue;
        }
        if (sent < 0 && errno == EINTR) {
            continue;
        }
        if (sent < 0) {
            return systemStatus("send control", errno);
        }
        return common::Status::runtimeError("control send returned zero bytes");
    }
    return common::Status::ok();
}

common::Status sendLine(int fd, const std::string& line) { return sendAll(fd, line + "\r\n"); }

common::Status sendResponse(int fd, const ControlResponse& response) {
    for (const std::string& line : response.lines) {
        const common::Status status = sendLine(fd, line);
        if (!status.isOk()) {
            return status;
        }
    }
    return common::Status::ok();
}

common::Result<std::string> readLine(int fd, std::string* buffer) {
    while (true) {
        const std::size_t newline = buffer->find('\n');
        if (newline != std::string::npos) {
            std::string line = buffer->substr(0, newline + 1);
            buffer->erase(0, newline + 1);
            while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
                line.pop_back();
            }
            return line;
        }

        char chunk[512];
        const ssize_t received = ::recv(fd, chunk, sizeof(chunk), 0);
        if (received > 0) {
            buffer->append(chunk, static_cast<std::size_t>(received));
            if (buffer->size() > 8192) {
                return common::Status::invalidArgument("control line exceeds 8192 bytes");
            }
            continue;
        }
        if (received == 0) {
            return common::Status::runtimeError("control connection closed");
        }
        if (errno == EINTR) {
            continue;
        }
        return systemStatus("recv control", errno);
    }
}

std::string generateTransferId() {
    constexpr char kDigits[] = "0123456789abcdef";
    std::random_device random;
    std::string id(32, '0');
    for (char& value : id) {
        value = kDigits[random() & 0x0F];
    }
    return id;
}

common::Result<PassiveListener> openPassiveListener(const ControlServerOptions& options,
                                                    std::uint32_t connections) {
    const std::uint32_t maxPort = std::numeric_limits<std::uint16_t>::max();
    for (std::uint32_t offset = 0; offset < kPassiveScanLimit; ++offset) {
        const std::uint32_t port = static_cast<std::uint32_t>(options.dataPortBase) + offset;
        if (port == 0 || port > maxPort) {
            break;
        }
        auto listener = core::io::createListener(
            options.host.c_str(), static_cast<std::uint16_t>(port), static_cast<int>(connections));
        if (!listener.isOk()) {
            continue;
        }
        PassiveListener passive;
        passive.fd = std::move(listener.value());
        passive.port = static_cast<std::uint16_t>(port);
        return passive;
    }
    return common::Status::runtimeError("no passive data port available");
}

std::string epsvReply(std::uint16_t port) {
    return formatReply(229, "Entering Extended Passive Mode (|||" + std::to_string(port) + "|)");
}

std::string pasvHostForReply(int controlFd, const std::string& configuredHost) {
    if (configuredHost != "0.0.0.0" && configuredHost != "::") {
        return configuredHost;
    }

    sockaddr_storage address{};
    socklen_t length = sizeof(address);
    if (::getsockname(controlFd, reinterpret_cast<sockaddr*>(&address), &length) != 0) {
        return "127.0.0.1";
    }
    if (address.ss_family == AF_INET) {
        char text[INET_ADDRSTRLEN];
        const auto* ipv4 = reinterpret_cast<const sockaddr_in*>(&address);
        if (::inet_ntop(AF_INET, &ipv4->sin_addr, text, sizeof(text)) != nullptr) {
            return text;
        }
    }
    return "127.0.0.1";
}

common::Result<std::string> pasvReply(int controlFd, const std::string& configuredHost,
                                      std::uint16_t port) {
    const std::string host = pasvHostForReply(controlFd, configuredHost);
    in_addr address{};
    if (::inet_pton(AF_INET, host.c_str(), &address) != 1) {
        return common::Status::invalidArgument("PASV requires an IPv4 bind address");
    }

    const auto* octets = reinterpret_cast<const unsigned char*>(&address.s_addr);
    std::ostringstream payload;
    payload << "Entering Passive Mode (" << static_cast<int>(octets[0]) << ","
            << static_cast<int>(octets[1]) << "," << static_cast<int>(octets[2]) << ","
            << static_cast<int>(octets[3]) << "," << (port / 256) << "," << (port % 256) << ")";
    return formatReply(227, payload.str());
}

common::Result<core::io::UniqueFd> acceptDataConnection(int listenerFd) {
    while (true) {
        const int acceptedFd = ::accept4(listenerFd, nullptr, nullptr, SOCK_CLOEXEC);
        if (acceptedFd >= 0) {
            return core::io::UniqueFd(acceptedFd);
        }
        if (errno == EINTR) {
            continue;
        }
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            pollfd pollFd{};
            pollFd.fd = listenerFd;
            pollFd.events = POLLIN;
            const int ready = ::poll(&pollFd, 1, 30000);
            if (ready > 0) {
                continue;
            }
            if (ready == 0) {
                return common::Status::runtimeError("timed out waiting for data connection");
            }
            if (errno == EINTR) {
                continue;
            }
            return systemStatus("poll data listener", errno);
        }
        return systemStatus("accept data", errno);
    }
}

common::Status sendAsciiData(PassiveListener* passive, const std::string& payload) {
    if (passive == nullptr || !passive->fd.isValid()) {
        return common::Status::runtimeError("passive data listener is not ready");
    }
    auto dataFd = acceptDataConnection(passive->fd.get());
    if (!dataFd.isOk()) {
        return dataFd.status();
    }
    passive->fd.reset();
    passive->port = 0;
    return sendAll(dataFd.value().get(), payload);
}

common::Result<std::uint64_t> fileSizeOfPath(const std::string& path) {
    struct stat statBuffer {};
    if (::stat(path.c_str(), &statBuffer) != 0) {
        return systemStatus("stat file", errno);
    }
    if (statBuffer.st_size < 0) {
        return common::Status::runtimeError("file size is negative");
    }
    return static_cast<std::uint64_t>(statBuffer.st_size);
}

common::Result<std::int64_t> mtimeOfPath(const std::string& path) {
    struct stat statBuffer {};
    if (::stat(path.c_str(), &statBuffer) != 0) {
        return systemStatus("stat file", errno);
    }
    return static_cast<std::int64_t>(statBuffer.st_mtime);
}

common::Result<std::vector<ControlListEntry>> readDirectoryEntries(const std::string& directory) {
    std::vector<ControlListEntry> entries;
    std::error_code error;
    for (const std::filesystem::directory_entry& entry :
         std::filesystem::directory_iterator(directory, error)) {
        if (error) {
            return common::Status::systemError("directory iteration failed: " + error.message(),
                                               error.value());
        }
        const std::string name = entry.path().filename().string();
        if (name.empty() || name == "." || name == "..") {
            continue;
        }
        ControlListEntry item;
        item.name = name;
        item.isDirectory = entry.is_directory(error);
        if (error) {
            return common::Status::systemError("directory entry type failed: " + error.message(),
                                               error.value());
        }
        if (!item.isDirectory && entry.is_regular_file(error)) {
            item.size = entry.file_size(error);
            if (error) {
                return common::Status::systemError(
                    "directory entry size failed: " + error.message(), error.value());
            }
        }
        auto mtime = mtimeOfPath(entry.path().string());
        if (!mtime.isOk()) {
            return mtime.status();
        }
        item.mtimeUnixSeconds = mtime.value();
        entries.push_back(std::move(item));
    }
    if (error) {
        return common::Status::systemError("directory iteration failed: " + error.message(),
                                           error.value());
    }
    std::sort(entries.begin(), entries.end(),
              [](const ControlListEntry& left, const ControlListEntry& right) {
                  return left.name < right.name;
              });
    return entries;
}

common::Status validateOutputBeforeStor(const std::string& outputPath, bool resume) {
    auto outputExists = storage::PosixFile::pathExists(outputPath);
    if (!outputExists.isOk()) {
        return outputExists.status();
    }
    if (outputExists.value()) {
        return common::Status::invalidArgument("output file already exists");
    }

    const std::string manifestPath = checkpoint::manifestPathForOutput(outputPath);
    auto manifestExists = storage::PosixFile::pathExists(manifestPath);
    if (!manifestExists.isOk()) {
        return manifestExists.status();
    }
    if (resume && !manifestExists.value()) {
        return common::Status::invalidArgument("manifest is required for REST resume");
    }
    if (!resume && manifestExists.value()) {
        return common::Status::invalidArgument("manifest already exists; use REST GFID token");
    }
    return common::Status::ok();
}

common::Status runSize(int controlFd, const ControlServerOptions& controlOptions,
                       const ControlSession& session, const ControlResponse& response) {
    auto path = resolveControlPath(controlOptions.root, session.workingDirectory(), response.path,
                                   ControlPathKind::ExistingFile, "SIZE");
    if (!path.isOk()) {
        return sendLine(controlFd, formatReply(550, path.status().message()));
    }
    auto size = fileSizeOfPath(path.value().fullPath);
    if (!size.isOk()) {
        return sendLine(controlFd, formatReply(550, size.status().message()));
    }
    return sendLine(controlFd, formatReply(213, std::to_string(size.value())));
}

common::Status runMdtm(int controlFd, const ControlServerOptions& controlOptions,
                       const ControlSession& session, const ControlResponse& response) {
    auto path = resolveControlPath(controlOptions.root, session.workingDirectory(), response.path,
                                   ControlPathKind::ExistingFile, "MDTM");
    if (!path.isOk()) {
        return sendLine(controlFd, formatReply(550, path.status().message()));
    }
    auto mtime = mtimeOfPath(path.value().fullPath);
    if (!mtime.isOk()) {
        return sendLine(controlFd, formatReply(550, mtime.status().message()));
    }
    return sendLine(controlFd, formatReply(213, formatMdtmTime(mtime.value())));
}

common::Status runCwd(int controlFd, const ControlServerOptions& controlOptions,
                      ControlSession* session, const ControlResponse& response) {
    if (response.path == ".." && session->workingDirectory() == "/") {
        session->setWorkingDirectory("/");
        return sendLine(controlFd, formatReply(250, "Directory changed to /"));
    }
    auto path = resolveControlPath(controlOptions.root, session->workingDirectory(), response.path,
                                   ControlPathKind::ExistingDirectory, "CWD");
    if (!path.isOk()) {
        return sendLine(controlFd, formatReply(550, path.status().message()));
    }
    session->setWorkingDirectory(path.value().virtualPath);
    return sendLine(controlFd,
                    formatReply(250, "Directory changed to " + path.value().virtualPath));
}

common::Status runListLike(int controlFd, ControlSession& session, PassiveListener* passive,
                           const ControlServerOptions& controlOptions,
                           const ControlResponse& response, bool namesOnly) {
    if (passive == nullptr || !passive->fd.isValid()) {
        return sendLine(controlFd, formatReply(550, "Passive data listener is not ready"));
    }
    auto path = resolveControlPath(controlOptions.root, session.workingDirectory(), response.path,
                                   ControlPathKind::ExistingDirectory, namesOnly ? "NLST" : "LIST");
    if (!path.isOk()) {
        passive->fd.reset();
        session.clearPassiveReady();
        return sendLine(controlFd, formatReply(550, path.status().message()));
    }
    auto entries = readDirectoryEntries(path.value().fullPath);
    if (!entries.isOk()) {
        passive->fd.reset();
        session.clearPassiveReady();
        return sendLine(controlFd, formatReply(550, entries.status().message()));
    }

    const std::string payload =
        namesOnly ? formatNlst(entries.value()) : formatList(entries.value());
    common::Status status = sendLine(
        controlFd, formatReply(150, namesOnly ? "Opening NLST data" : "Opening LIST data"));
    if (!status.isOk()) {
        return status;
    }
    status = sendAsciiData(passive, payload);
    session.clearPassiveReady();
    if (!status.isOk()) {
        (void)sendLine(controlFd, formatReply(425, status.message()));
        return status;
    }
    return sendLine(controlFd, formatReply(226, namesOnly ? "NLST complete" : "LIST complete"));
}

common::Status runStor(int controlFd, ControlSession& session, PassiveListener* passive,
                       const ControlServerOptions& controlOptions,
                       const ControlResponse& response) {
    if (passive == nullptr || !passive->fd.isValid()) {
        return sendLine(controlFd, formatReply(550, "Passive data listener is not ready"));
    }

    auto outputPath =
        resolveStorPath(controlOptions.root, session.workingDirectory(), response.path);
    if (!outputPath.isOk()) {
        return sendLine(controlFd, formatReply(550, outputPath.status().message()));
    }

    const std::string transferId = response.resume ? response.transferId : generateTransferId();
    const common::Status outputStatus =
        validateOutputBeforeStor(outputPath.value(), response.resume);
    if (!outputStatus.isOk()) {
        return sendLine(controlFd, formatReply(550, outputStatus.message()));
    }

    config::FileTransferOptions fileOptions;
    fileOptions.host = controlOptions.host;
    fileOptions.port = passive->port;
    fileOptions.connections = response.connections;
    fileOptions.bufferSize = controlOptions.bufferSize;
    fileOptions.chunkSize = controlOptions.chunkSize;
    fileOptions.path = outputPath.value();
    fileOptions.transferId = transferId;
    fileOptions.checksumAlgorithm = controlOptions.checksumAlgorithm;
    fileOptions.checksumBackend = controlOptions.checksumBackend;
    fileOptions.manifestFlushIntervalChunks = controlOptions.manifestFlushIntervalChunks;
    fileOptions.finalVerifyPolicy = controlOptions.finalVerifyPolicy;
    fileOptions.preallocateMode = controlOptions.preallocateMode;
    fileOptions.fileIo = controlOptions.fileIo;
    fileOptions.resume = response.resume;

    const std::string prelude = "Opening GridFlux data connection transfer_id=GFID:" + transferId +
                                " connections=" + std::to_string(response.connections);
    common::Status status = sendLine(controlFd, formatReply(150, prelude));
    if (!status.isOk()) {
        return status;
    }

    core::io::UniqueFd listener = std::move(passive->fd);
    passive->port = 0;
    status = core::io::runFileTransferServerOnListener(fileOptions, std::move(listener));
    if (!status.isOk()) {
        (void)sendLine(controlFd, formatReply(550, "Transfer failed: " + status.message()));
        return status;
    }

    session.clearPassiveReady();
    return sendLine(controlFd,
                    formatReply(226, "Transfer complete transfer_id=GFID:" + transferId));
}

common::Status runRetr(int controlFd, ControlSession& session, PassiveListener* passive,
                       const ControlServerOptions& controlOptions,
                       const ControlResponse& response) {
    if (passive == nullptr || !passive->fd.isValid()) {
        return sendLine(controlFd, formatReply(550, "Passive data listener is not ready"));
    }

    auto inputPath =
        resolveRetrPath(controlOptions.root, session.workingDirectory(), response.path);
    if (!inputPath.isOk()) {
        return sendLine(controlFd, formatReply(550, inputPath.status().message()));
    }

    const std::string transferId = response.resume ? response.transferId : generateTransferId();
    auto sourceVirtualPath = resolveVirtualPath(session.workingDirectory(), response.path, false);
    if (!sourceVirtualPath.isOk()) {
        return sendLine(controlFd, formatReply(550, sourceVirtualPath.status().message()));
    }
    std::string sourcePath = sourceVirtualPath.value();
    if (!sourcePath.empty() && sourcePath.front() == '/') {
        sourcePath.erase(sourcePath.begin());
    }
    core::io::FileDownloadSenderOptions senderOptions;
    senderOptions.path = inputPath.value();
    senderOptions.transferId = transferId;
    senderOptions.connections = response.connections;
    senderOptions.chunkSize = controlOptions.chunkSize;
    senderOptions.bufferSize = controlOptions.bufferSize;
    senderOptions.checksumAlgorithm = controlOptions.checksumAlgorithm;
    senderOptions.checksumBackend = controlOptions.checksumBackend;
    senderOptions.fileIo = controlOptions.fileIo;
    senderOptions.resume = response.resume;
    senderOptions.sourcePath = sourcePath;

    const std::string prelude =
        "Opening GridFlux download data connection transfer_id=GFID:" + transferId +
        " connections=" + std::to_string(response.connections);
    common::Status status = sendLine(controlFd, formatReply(150, prelude));
    if (!status.isOk()) {
        return status;
    }

    core::io::UniqueFd listener = std::move(passive->fd);
    passive->port = 0;
    status = core::io::runFramedFileSenderOnListener(senderOptions, std::move(listener));
    if (!status.isOk()) {
        (void)sendLine(controlFd, formatReply(550, "Transfer failed: " + status.message()));
        return status;
    }

    session.clearPassiveReady();
    return sendLine(controlFd,
                    formatReply(226, "Transfer complete transfer_id=GFID:" + transferId));
}

void handleControlConnection(core::io::UniqueFd controlFd, ControlServerOptions options) {
    ControlSession session(options.user, options.password, options.connections);
    PassiveListener passive;
    std::string inputBuffer;

    if (!sendLine(controlFd.get(), formatReply(220, "GridFlux GridFTP control ready")).isOk()) {
        return;
    }

    while (controlFd.isValid()) {
        auto line = readLine(controlFd.get(), &inputBuffer);
        if (!line.isOk()) {
            return;
        }

        auto command = parseControlCommand(line.value());
        if (!command.isOk()) {
            (void)sendLine(controlFd.get(), formatReply(550, command.status().message()));
            continue;
        }

        ControlResponse response = session.handleCommand(command.value());
        if (response.action == ControlAction::OpenPassiveEpsv ||
            response.action == ControlAction::OpenPassivePasv) {
            passive.fd.reset();
            auto passiveResult = openPassiveListener(options, session.connections());
            if (!passiveResult.isOk()) {
                (void)sendLine(controlFd.get(),
                               formatReply(421, "Cannot open passive data listener"));
                return;
            }
            passive = std::move(passiveResult.value());
            session.markPassiveReady();
            if (response.action == ControlAction::OpenPassiveEpsv) {
                (void)sendLine(controlFd.get(), epsvReply(passive.port));
            } else {
                auto reply = pasvReply(controlFd.get(), options.host, passive.port);
                if (!reply.isOk()) {
                    (void)sendLine(controlFd.get(), formatReply(550, reply.status().message()));
                    passive.fd.reset();
                    session.clearPassiveReady();
                } else {
                    (void)sendLine(controlFd.get(), reply.value());
                }
            }
            continue;
        }

        if (response.action == ControlAction::StartStor) {
            (void)runStor(controlFd.get(), session, &passive, options, response);
            continue;
        }

        if (response.action == ControlAction::StartRetr) {
            (void)runRetr(controlFd.get(), session, &passive, options, response);
            continue;
        }

        if (response.action == ControlAction::QuerySize) {
            (void)runSize(controlFd.get(), options, session, response);
            continue;
        }

        if (response.action == ControlAction::QueryMdtm) {
            (void)runMdtm(controlFd.get(), options, session, response);
            continue;
        }

        if (response.action == ControlAction::ChangeDirectory) {
            (void)runCwd(controlFd.get(), options, &session, response);
            continue;
        }

        if (response.action == ControlAction::StartList) {
            (void)runListLike(controlFd.get(), session, &passive, options, response, false);
            continue;
        }

        if (response.action == ControlAction::StartNlst) {
            (void)runListLike(controlFd.get(), session, &passive, options, response, true);
            continue;
        }

        const common::Status sendStatus = sendResponse(controlFd.get(), response);
        if (!sendStatus.isOk() || response.action == ControlAction::Quit) {
            return;
        }
    }
}

}  // namespace

common::Status runControlServer(const ControlServerOptions& options) {
    auto listenerResult = core::io::createListener(options.host.c_str(), options.port, 32);
    if (!listenerResult.isOk()) {
        return listenerResult.status();
    }
    core::io::UniqueFd listener = std::move(listenerResult.value());

    std::cout << "gridftp_control_server listening host=" << options.host
              << " port=" << options.port << " root=" << options.root
              << " data_port_base=" << options.dataPortBase
              << " connections=" << options.connections << '\n'
              << std::flush;

    while (true) {
        pollfd pollFd{};
        pollFd.fd = listener.get();
        pollFd.events = POLLIN;
        const int ready = ::poll(&pollFd, 1, -1);
        if (ready < 0) {
            if (errno == EINTR) {
                continue;
            }
            return systemStatus("poll control listener", errno);
        }

        while (true) {
            const int acceptedFd = ::accept4(listener.get(), nullptr, nullptr, SOCK_CLOEXEC);
            if (acceptedFd < 0) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    break;
                }
                if (errno == EINTR) {
                    continue;
                }
                return systemStatus("accept control", errno);
            }

            std::thread(handleControlConnection, core::io::UniqueFd(acceptedFd), options).detach();
        }
    }
}

}  // namespace gridflux::protocol::control
