#include "gridflux/core/io/framed_data_socket.h"

#include <gtest/gtest.h>
#include <sys/socket.h>
#include <sys/time.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <thread>

namespace {

using gridflux::core::io::FramedDataSocket;
using gridflux::core::io::UniqueFd;

}  // namespace

TEST(FramedDataSocketTest, ReadAllRetriesAfterReceiveTimeout) {
    int rawFds[2] = {-1, -1};
    ASSERT_EQ(::socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, rawFds), 0);

    UniqueFd reader(rawFds[0]);
    UniqueFd writer(rawFds[1]);

    timeval timeout{};
    timeout.tv_sec = 0;
    timeout.tv_usec = 1000;
    ASSERT_EQ(::setsockopt(reader.get(), SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)), 0);

    FramedDataSocket socket(std::move(reader));
    std::array<std::uint8_t, 4> buffer{};

    std::thread delayedWriter([writer = std::move(writer)]() mutable {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        const std::array<std::uint8_t, 4> payload{'o', 'k', 'a', 'y'};
        ASSERT_EQ(::send(writer.get(), payload.data(), payload.size(), MSG_NOSIGNAL),
                  static_cast<ssize_t>(payload.size()));
    });

    const auto status = socket.readAll(buffer.data(), buffer.size());
    delayedWriter.join();

    ASSERT_TRUE(status.isOk()) << status.message();
    EXPECT_EQ(buffer, (std::array<std::uint8_t, 4>{'o', 'k', 'a', 'y'}));
}
