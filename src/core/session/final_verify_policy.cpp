#include "gridflux/core/session/final_verify_policy.h"

namespace gridflux::core::session {

common::Result<FinalVerifyPolicy> parseFinalVerifyPolicy(std::string_view text) {
    if (text == "full") {
        return FinalVerifyPolicy::Full;
    }
    if (text == "verified_chunks") {
        return FinalVerifyPolicy::VerifiedChunks;
    }
    return common::Status::invalidArgument("final verify policy must be full or verified_chunks");
}

std::string finalVerifyPolicyName(FinalVerifyPolicy policy) {
    switch (policy) {
        case FinalVerifyPolicy::Full:
            return "full";
        case FinalVerifyPolicy::VerifiedChunks:
            return "verified_chunks";
    }
    return "full";
}

bool canUseVerifiedChunksFinalVerify(FinalVerifyPolicy requested,
                                     checksum::ChecksumAlgorithm algorithm, std::uint64_t totalSize,
                                     std::uint64_t verifiedBytes, bool hasMissingRanges) noexcept {
    return requested == FinalVerifyPolicy::VerifiedChunks &&
           algorithm == checksum::ChecksumAlgorithm::Crc32c && !hasMissingRanges &&
           verifiedBytes == totalSize;
}

bool canUseCurrentSessionVerifiedChunksFinalVerify(
    FinalVerifyPolicy requested, checksum::ChecksumAlgorithm algorithm, std::uint64_t totalSize,
    std::uint64_t verifiedBytes, bool hasMissingRanges, std::uint64_t loadedVerifiedChunks,
    std::uint64_t removedCorruptChunks) noexcept {
    return loadedVerifiedChunks == 0 && removedCorruptChunks == 0 &&
           canUseVerifiedChunksFinalVerify(requested, algorithm, totalSize, verifiedBytes,
                                           hasMissingRanges);
}

bool canCommitWithVerifiedChunksFinalVerify(FinalVerifyPolicy requested,
                                            checksum::ChecksumAlgorithm algorithm,
                                            std::uint64_t totalSize, std::uint64_t verifiedBytes,
                                            bool hasMissingRanges, bool manifestFlushOk) noexcept {
    return manifestFlushOk && canUseVerifiedChunksFinalVerify(requested, algorithm, totalSize,
                                                              verifiedBytes, hasMissingRanges);
}

}  // namespace gridflux::core::session
