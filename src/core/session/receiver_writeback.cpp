#include "gridflux/core/session/receiver_writeback.h"

#include <string>

namespace gridflux::core::session {

common::Result<ReceiverWriteProfile> parseReceiverWriteProfile(std::string_view value) {
    if (value == "default") {
        return ReceiverWriteProfile::Default;
    }
    if (value == "bounded") {
        return ReceiverWriteProfile::Bounded;
    }
    return common::Status::invalidArgument(
        "receiver write profile must be default or bounded");
}

const char* receiverWriteProfileName(ReceiverWriteProfile profile) {
    switch (profile) {
        case ReceiverWriteProfile::Default:
            return "default";
        case ReceiverWriteProfile::Bounded:
            return "bounded";
    }
    return "default";
}

common::Result<ReceiverWriteYieldPolicy> parseReceiverWriteYieldPolicy(
    std::string_view value) {
    if (value == "none") {
        return ReceiverWriteYieldPolicy::None;
    }
    if (value == "dirty_poll") {
        return ReceiverWriteYieldPolicy::DirtyPoll;
    }
    return common::Status::invalidArgument(
        "receiver write yield policy must be none or dirty_poll");
}

const char* receiverWriteYieldPolicyName(ReceiverWriteYieldPolicy policy) {
    switch (policy) {
        case ReceiverWriteYieldPolicy::None:
            return "none";
        case ReceiverWriteYieldPolicy::DirtyPoll:
            return "dirty_poll";
    }
    return "none";
}

common::Status validateReceiverWritebackConfig(const ReceiverWritebackConfig& config) {
    if (config.profile == ReceiverWriteProfile::Default) {
        if (config.maxPendingBytes != 0) {
            return common::Status::invalidArgument(
                "receiver max pending bytes requires --receiver-write-profile bounded");
        }
        if (config.yieldPolicy != ReceiverWriteYieldPolicy::None) {
            return common::Status::invalidArgument(
                "receiver write yield policy dirty_poll requires --receiver-write-profile bounded");
        }
        return common::Status::ok();
    }

    if (config.maxPendingBytes == 0) {
        return common::Status::invalidArgument(
            "--receiver-write-profile bounded requires --receiver-max-pending-bytes > 0");
    }
    return common::Status::ok();
}

}  // namespace gridflux::core::session
