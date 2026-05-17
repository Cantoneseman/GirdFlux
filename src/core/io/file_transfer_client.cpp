#include "gridflux/core/io/file_transfer_client.h"

#include <netdb.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <random>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "gridflux/checkpoint/transfer_manifest.h"
#include "gridflux/checksum/checksum.h"
#include "gridflux/common/throughput_counter.h"
#include "gridflux/core/chunk/chunk_planner.h"
#include "gridflux/core/io/socket_utils.h"
#include "gridflux/core/metrics/transfer_phase_stats.h"
#include "gridflux/core/protocol/frame.h"
#include "gridflux/storage/file_io.h"
#include "gridflux/storage/posix_file.h"

namespace gridflux::core::io {
namespace {

struct StreamStats {
    std::uint64_t sentBytes = 0;
    std::uint64_t skippedBytes = 0;
    std::uint64_t resentBytes = 0;
    std::uint64_t verifiedBytes = 0;
};

common::Status systemStatus(const char* operation, int errorNumber) {
    return common::Status::systemError(std::string(operation) + ": " + std::strerror(errorNumber),
                                       errorNumber);
}

common::Result<UniqueFd> createBlockingConnection(const char* host, std::uint16_t port) {
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    addrinfo* results = nullptr;
    const std::string portText = std::to_string(port);
    const int gaiStatus = ::getaddrinfo(host, portText.c_str(), &hints, &results);
    if (gaiStatus != 0) {
        return common::Status::runtimeError(std::string("getaddrinfo: ") + gai_strerror(gaiStatus));
    }

    UniqueFd connection;
    int lastError = 0;
    for (addrinfo* item = results; item != nullptr; item = item->ai_next) {
        UniqueFd candidate(
            ::socket(item->ai_family, item->ai_socktype | SOCK_CLOEXEC, item->ai_protocol));
        if (!candidate.isValid()) {
            lastError = errno;
            continue;
        }

        if (::connect(candidate.get(), item->ai_addr, item->ai_addrlen) == 0) {
            connection = std::move(candidate);
            break;
        }

        lastError = errno;
    }

    ::freeaddrinfo(results);
    if (!connection.isValid()) {
        return common::Status::systemError("connect: " + std::string(std::strerror(lastError)),
                                           lastError);
    }

    return connection;
}

common::Status sendAll(int fd, const std::uint8_t* data, std::size_t length,
                       metrics::TransferPhaseStats* phaseStats = nullptr) {
    metrics::ScopedPhaseTimer timer(phaseStats, metrics::TransferPhase::Send, length);
    std::size_t completed = 0;
    while (completed < length) {
        const ssize_t sent = ::send(fd, data + completed, length - completed, MSG_NOSIGNAL);
        if (sent > 0) {
            completed += static_cast<std::size_t>(sent);
            continue;
        }
        if (sent < 0 && errno == EINTR) {
            continue;
        }
        if (sent < 0) {
            return systemStatus("send", errno);
        }
        return common::Status::runtimeError("send returned zero bytes");
    }
    return common::Status::ok();
}

common::Status sendFrame(int fd, const protocol::FrameHeader& header,
                         const std::vector<std::uint8_t>& payload,
                         metrics::TransferPhaseStats* phaseStats = nullptr) {
    const protocol::EncodedFrameHeader encoded = protocol::encodeFrameHeader(header);
    const common::Status headerStatus = sendAll(fd, encoded.data(), encoded.size(), phaseStats);
    if (!headerStatus.isOk()) {
        return headerStatus;
    }
    if (!payload.empty()) {
        return sendAll(fd, payload.data(), payload.size(), phaseStats);
    }
    return common::Status::ok();
}

common::Status recvAll(int fd, std::uint8_t* data, std::size_t length,
                       metrics::TransferPhaseStats* phaseStats = nullptr) {
    metrics::ScopedPhaseTimer timer(phaseStats, metrics::TransferPhase::Recv, length);
    std::size_t completed = 0;
    while (completed < length) {
        const ssize_t received = ::recv(fd, data + completed, length - completed, 0);
        if (received > 0) {
            completed += static_cast<std::size_t>(received);
            continue;
        }
        if (received == 0) {
            return common::Status::runtimeError("server closed connection");
        }
        if (errno == EINTR) {
            continue;
        }
        return systemStatus("recv", errno);
    }
    return common::Status::ok();
}

common::Result<protocol::FrameHeader> recvHeader(int fd, std::uint32_t maxPayloadSize,
                                                 metrics::TransferPhaseStats* phaseStats) {
    protocol::EncodedFrameHeader encoded{};
    const common::Status recvStatus = recvAll(fd, encoded.data(), encoded.size(), phaseStats);
    if (!recvStatus.isOk()) {
        return recvStatus;
    }

    auto decoded = protocol::decodeFrameHeader(encoded);
    if (!decoded.isOk()) {
        return decoded.status();
    }
    const common::Status validateStatus =
        protocol::validateFrameHeader(decoded.value(), maxPayloadSize);
    if (!validateStatus.isOk()) {
        return validateStatus;
    }
    return decoded.value();
}

common::Status setReceiveTimeout(int fd) {
    timeval timeout{};
    timeout.tv_sec = 60;
    timeout.tv_usec = 0;
    if (::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) != 0) {
        return systemStatus("setsockopt(SO_RCVTIMEO)", errno);
    }
    return common::Status::ok();
}

std::string generateTransferId() {
    constexpr char kDigits[] = "0123456789abcdef";
    std::random_device random;
    std::string id;
    id.resize(32);
    for (char& value : id) {
        value = kDigits[random() & 0x0F];
    }
    return id;
}

common::Result<std::vector<chunk::CompletedRange>> sendSessionInitAndReadMissingRanges(
    int fd, const config::FileTransferOptions& options, const std::string& transferId,
    std::uint32_t streamId, std::uint64_t totalSize,
    metrics::TransferPhaseStats* phaseStats) {
    protocol::SessionInitPayload init;
    init.mode = options.resume ? protocol::SessionMode::Resume : protocol::SessionMode::New;
    init.transferId = transferId;
    init.totalSize = totalSize;
    init.chunkSize = options.chunkSize;
    init.checksumAlgorithm = options.checksumAlgorithm;
    auto payload = protocol::encodeSessionInitPayload(init);
    if (!payload.isOk()) {
        return payload.status();
    }
    if (payload.value().size() > options.bufferSize) {
        return common::Status::invalidArgument("SessionInit payload exceeds buffer size");
    }

    protocol::FrameHeader header;
    header.type = protocol::FrameType::SessionInit;
    header.streamId = streamId;
    header.payloadSize = static_cast<std::uint32_t>(payload.value().size());
    header.totalSize = totalSize;
    const common::Status sendStatus = sendFrame(fd, header, payload.value(), phaseStats);
    if (!sendStatus.isOk()) {
        return sendStatus;
    }

    auto responseHeader = recvHeader(fd, options.bufferSize, phaseStats);
    if (!responseHeader.isOk()) {
        return responseHeader.status();
    }
    if (responseHeader.value().type == protocol::FrameType::Error) {
        return common::Status::runtimeError("server rejected transfer session");
    }
    if (responseHeader.value().type != protocol::FrameType::ResumeResponse) {
        return common::Status::runtimeError("server returned unexpected session response");
    }

    std::vector<std::uint8_t> responsePayload(responseHeader.value().payloadSize);
    const common::Status recvStatus =
        recvAll(fd, responsePayload.data(), responsePayload.size(), phaseStats);
    if (!recvStatus.isOk()) {
        return recvStatus;
    }
    auto decoded =
        protocol::decodeResumeResponsePayload(responsePayload.data(), responsePayload.size());
    if (!decoded.isOk()) {
        return decoded.status();
    }
    if (decoded.value().statusCode != protocol::FrameStatusCode::Ok) {
        return common::Status::runtimeError("server returned non-OK resume response");
    }
    return decoded.value().missingRanges;
}

bool intersects(const chunk::ChunkRange& chunk, const chunk::CompletedRange& range,
                std::uint64_t* begin, std::uint64_t* end) noexcept {
    const std::uint64_t chunkEnd = chunk.offset + chunk.length;
    *begin = std::max(chunk.offset, range.begin);
    *end = std::min(chunkEnd, range.end);
    return *begin < *end;
}

common::Status sendChunkRange(int fd, const storage::PosixFile& inputFile,
                              const chunk::ChunkRange& chunk, std::uint64_t begin,
                              std::uint64_t end, std::uint32_t streamId, std::uint64_t totalSize,
                              checksum::ChecksumAlgorithm checksumAlgorithm,
                              checksum::ChecksumBackend checksumBackend, bool corruptPayload,
                              const storage::FileIoContext& fileIoContext,
                              std::vector<std::uint8_t>& buffer,
                              metrics::TransferPhaseStats* phaseStats,
                              storage::FileIoStats* fileIoStats) {
    checksum::ChecksumComputer checksumComputer(checksumAlgorithm, checksumBackend);
    bool corrupted = false;
    std::uint64_t completed = begin;
    while (completed < end) {
        const std::uint64_t remaining = end - completed;
        const std::uint32_t payloadSize =
            static_cast<std::uint32_t>(std::min<std::uint64_t>(remaining, buffer.size()));

        common::Status readStatus;
        {
            metrics::ScopedPhaseTimer timer(phaseStats, metrics::TransferPhase::Read,
                                            payloadSize);
            readStatus = storage::readAtAll(inputFile, completed, buffer.data(), payloadSize,
                                            fileIoContext, fileIoStats);
        }
        if (!readStatus.isOk()) {
            return readStatus;
        }
        {
            metrics::ScopedPhaseTimer timer(phaseStats, metrics::TransferPhase::Checksum,
                                            payloadSize);
            checksumComputer.update(buffer.data(), payloadSize);
        }
        if (corruptPayload && !corrupted && payloadSize > 0) {
            buffer[0] ^= 0xFFU;
            corrupted = true;
        }

        protocol::FrameHeader header;
        header.type = protocol::FrameType::Data;
        header.streamId = streamId;
        header.chunkId = chunk.chunkId;
        header.offset = completed;
        header.payloadSize = payloadSize;
        header.totalSize = totalSize;
        const common::Status headerStatus = sendFrame(fd, header, {}, phaseStats);
        if (!headerStatus.isOk()) {
            return headerStatus;
        }

        const common::Status payloadStatus = sendAll(fd, buffer.data(), payloadSize, phaseStats);
        if (!payloadStatus.isOk()) {
            return payloadStatus;
        }

        completed += payloadSize;
    }

    protocol::ChunkCompletePayload complete;
    complete.chunkId = chunk.chunkId;
    complete.offset = begin;
    complete.length = end - begin;
    {
        metrics::ScopedPhaseTimer timer(phaseStats, metrics::TransferPhase::Checksum);
        complete.checksum = checksumComputer.finalize();
    }
    auto payload = protocol::encodeChunkCompletePayload(complete);
    if (!payload.isOk()) {
        return payload.status();
    }

    protocol::FrameHeader header;
    header.type = protocol::FrameType::ChunkComplete;
    header.streamId = streamId;
    header.chunkId = chunk.chunkId;
    header.offset = begin;
    header.payloadSize = static_cast<std::uint32_t>(payload.value().size());
    header.totalSize = totalSize;
    return sendFrame(fd, header, payload.value(), phaseStats);
}

common::Status waitForFinalStatus(int fd, std::uint32_t maxPayloadSize,
                                  metrics::TransferPhaseStats* phaseStats) {
    auto header = recvHeader(fd, maxPayloadSize, phaseStats);
    if (!header.isOk()) {
        return header.status();
    }

    if (header.value().type == protocol::FrameType::Complete &&
        header.value().statusCode == protocol::FrameStatusCode::Ok) {
        return common::Status::ok();
    }
    if (header.value().type == protocol::FrameType::Error) {
        return common::Status::runtimeError("server returned transfer error status");
    }
    return common::Status::runtimeError("server returned unexpected final status frame");
}

common::Status sendStream(const config::FileTransferOptions& options,
                          const storage::PosixFile& inputFile,
                          const std::vector<chunk::ChunkRange>& chunks,
                          const std::string& transferId, std::uint32_t streamId,
                          checksum::ChecksumBackend checksumBackend, std::uint64_t totalSize,
                          std::atomic<std::uint64_t>& chunksStarted, StreamStats* stats,
                          metrics::TransferPhaseStats* phaseStats,
                          const storage::FileIoContext& fileIoContext,
                          storage::FileIoStats* fileIoStats) {
    auto connectionResult = createBlockingConnection(options.host.c_str(), options.port);
    if (!connectionResult.isOk()) {
        return connectionResult.status();
    }
    UniqueFd connection = std::move(connectionResult.value());
    const common::Status timeoutStatus = setReceiveTimeout(connection.get());
    if (!timeoutStatus.isOk()) {
        return timeoutStatus;
    }

    auto missingRanges = sendSessionInitAndReadMissingRanges(
        connection.get(), options, transferId, streamId, totalSize, phaseStats);
    if (!missingRanges.isOk()) {
        return missingRanges.status();
    }

    std::vector<std::uint8_t> buffer(options.bufferSize);
    std::uint64_t streamSent = 0;
    std::uint64_t streamAssigned = 0;
    std::uint64_t streamMissing = 0;

    for (const chunk::ChunkRange& chunk : chunks) {
        if (chunk.streamId != streamId) {
            continue;
        }
        streamAssigned += chunk.length;

        bool chunkHasWork = false;
        for (const chunk::CompletedRange& range : missingRanges.value()) {
            std::uint64_t begin = 0;
            std::uint64_t end = 0;
            if (!intersects(chunk, range, &begin, &end)) {
                continue;
            }
            streamMissing += end - begin;
            if (!chunkHasWork && options.maxChunks != 0) {
                const std::uint64_t previous = chunksStarted.fetch_add(1);
                if (previous >= options.maxChunks) {
                    return common::Status::runtimeError("max chunks reached");
                }
            }
            chunkHasWork = true;
            const bool corruptPayload =
                options.hasCorruptChunk && options.corruptChunk == chunk.chunkId;
            const common::Status sendStatus =
                sendChunkRange(connection.get(), inputFile, chunk, begin, end, streamId, totalSize,
                               options.checksumAlgorithm, checksumBackend, corruptPayload,
                               fileIoContext, buffer, phaseStats, fileIoStats);
            if (!sendStatus.isOk()) {
                return sendStatus;
            }
            streamSent += end - begin;
            if (options.hasDuplicateCorruptChunk &&
                options.duplicateCorruptChunk == chunk.chunkId) {
                const common::Status duplicateStatus = sendChunkRange(
                    connection.get(), inputFile, chunk, begin, end, streamId, totalSize,
                    options.checksumAlgorithm, checksumBackend, true, fileIoContext, buffer,
                    phaseStats, fileIoStats);
                if (!duplicateStatus.isOk()) {
                    return duplicateStatus;
                }
            }
        }
    }

    protocol::FrameHeader fin;
    fin.type = protocol::FrameType::Fin;
    fin.streamId = streamId;
    fin.payloadSize = 0;
    fin.totalSize = totalSize;
    const common::Status finStatus = sendFrame(connection.get(), fin, {}, phaseStats);
    if (!finStatus.isOk()) {
        return finStatus;
    }

    const common::Status finalStatus =
        waitForFinalStatus(connection.get(), options.bufferSize, phaseStats);
    if (!finalStatus.isOk()) {
        return finalStatus;
    }

    stats->sentBytes = streamSent;
    stats->resentBytes = streamSent;
    stats->skippedBytes = streamAssigned >= streamMissing ? streamAssigned - streamMissing : 0;
    stats->verifiedBytes = streamAssigned;
    return common::Status::ok();
}

}  // namespace

common::Status runFileTransferClient(const config::FileTransferOptions& options) {
    auto fileResult = storage::PosixFile::openReadOnly(options.path);
    if (!fileResult.isOk()) {
        return fileResult.status();
    }
    storage::PosixFile inputFile = std::move(fileResult.value());

    auto sizeResult = inputFile.fileSize();
    if (!sizeResult.isOk()) {
        return sizeResult.status();
    }
    const std::uint64_t totalSize = sizeResult.value();
    const common::Status adviceStatus =
        storage::applyFileIoAdvice(inputFile, options.fileIo.advice, 0, totalSize);
    if (!adviceStatus.isOk()) {
        return adviceStatus;
    }

    auto chunksResult = chunk::planChunks(totalSize, options.chunkSize, options.connections);
    if (!chunksResult.isOk()) {
        return chunksResult.status();
    }
    const std::vector<chunk::ChunkRange> chunks = std::move(chunksResult.value());

    std::string transferId = options.transferId;
    if (transferId.empty()) {
        transferId = generateTransferId();
    }
    if (!checkpoint::isValidTransferId(transferId)) {
        return common::Status::invalidArgument("invalid transfer_id");
    }
    if (options.resume && options.transferId.empty()) {
        return common::Status::invalidArgument("--resume requires --transfer-id");
    }
    auto resolvedBackend =
        checksum::resolveChecksumBackend(options.checksumAlgorithm, options.checksumBackend);
    if (!resolvedBackend.isOk()) {
        return resolvedBackend.status();
    }

    std::vector<common::Status> statuses(options.connections);
    std::vector<StreamStats> streamStats(options.connections);
    std::vector<std::thread> threads;
    threads.reserve(options.connections);
    std::atomic<std::uint64_t> chunksStarted{0};
    metrics::TransferPhaseStats phaseStats;
    storage::FileIoStats fileIoStats;
    const storage::FileIoContext fileIoContext(options.fileIo);
    const common::Status fileIoStatus = fileIoContext.validateAvailable();
    if (!fileIoStatus.isOk()) {
        return fileIoStatus;
    }
    metrics::ScopedPhaseTimer overallTimer(&phaseStats, metrics::TransferPhase::Overall);

    common::ThroughputCounter counter;
    counter.start(common::ThroughputCounter::Clock::now());

    for (std::uint32_t streamId = 0; streamId < options.connections; ++streamId) {
        threads.emplace_back([&, streamId]() {
            statuses[streamId] = sendStream(options, inputFile, chunks, transferId, streamId,
                                            resolvedBackend.value(), totalSize, chunksStarted,
                                            &streamStats[streamId], &phaseStats, fileIoContext,
                                            &fileIoStats);
        });
    }

    for (std::thread& thread : threads) {
        thread.join();
    }

    for (const common::Status& status : statuses) {
        if (!status.isOk()) {
            return status;
        }
    }

    std::uint64_t totalSent = 0;
    std::uint64_t skippedBytes = 0;
    std::uint64_t resentBytes = 0;
    std::uint64_t verifiedBytes = 0;
    for (const StreamStats& stats : streamStats) {
        totalSent += stats.sentBytes;
        skippedBytes += stats.skippedBytes;
        resentBytes += stats.resentBytes;
        verifiedBytes += stats.verifiedBytes;
    }
    counter.addBytes(totalSent);
    const auto end = common::ThroughputCounter::Clock::now();
    counter.stop(end);
    overallTimer.stop();

    const char* backendName = options.checksumAlgorithm == checksum::ChecksumAlgorithm::None
                                  ? "none"
                                  : checksum::checksumBackendName(resolvedBackend.value());
    std::cout << "file_client sent_bytes=" << totalSent
              << " elapsed_seconds=" << counter.elapsedSeconds(end)
              << " throughput_gbps=" << counter.gigabitsPerSecond(end)
              << " transfer_id=" << transferId << " checksum_backend=" << backendName
              << " skipped_bytes=" << skippedBytes << " resent_bytes=" << resentBytes
              << " verified_bytes=" << verifiedBytes
              << " file_io_backend=" << storage::fileIoBackendName(options.fileIo.backend)
              << " file_io_buffer_size=" << options.fileIo.bufferSize
              << " file_io_queue_depth=" << options.fileIo.queueDepth
              << " file_io_batch_size=" << options.fileIo.batchSize
              << " file_io_advice=" << storage::fileIoAdviceName(options.fileIo.advice);
    metrics::appendPhaseStats(std::cout, phaseStats);
    storage::appendFileIoStats(std::cout, fileIoStats);
    std::cout << '\n';

    return common::Status::ok();
}

}  // namespace gridflux::core::io
