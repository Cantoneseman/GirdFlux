#pragma once

#include <cstdint>
#include <string_view>

#include "gridflux/common/status.h"

namespace gridflux::core::session {

enum class ReceiverWriteProfile {
    Default,
    Bounded,
};

enum class ReceiverWriteYieldPolicy {
    None,
    DirtyPoll,
};

struct ReceiverWritebackConfig {
    ReceiverWriteProfile profile = ReceiverWriteProfile::Default;
    std::uint64_t maxPendingBytes = 0;
    ReceiverWriteYieldPolicy yieldPolicy = ReceiverWriteYieldPolicy::None;
};

[[nodiscard]] common::Result<ReceiverWriteProfile> parseReceiverWriteProfile(
    std::string_view value);
[[nodiscard]] const char* receiverWriteProfileName(ReceiverWriteProfile profile);
[[nodiscard]] common::Result<ReceiverWriteYieldPolicy> parseReceiverWriteYieldPolicy(
    std::string_view value);
[[nodiscard]] const char* receiverWriteYieldPolicyName(ReceiverWriteYieldPolicy policy);
[[nodiscard]] common::Status validateReceiverWritebackConfig(
    const ReceiverWritebackConfig& config);

}  // namespace gridflux::core::session
