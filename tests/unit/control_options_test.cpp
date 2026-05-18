#include "gridflux/protocol/control/control_options.h"

#include <gtest/gtest.h>

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "gridflux/storage/file_io.h"

namespace {

using gridflux::checksum::ChecksumAlgorithm;
using gridflux::checksum::ChecksumBackend;
using gridflux::core::session::CommitSyncPolicy;
using gridflux::core::session::FinalVerifyPolicy;
using gridflux::core::session::ManifestFlushPolicy;
using gridflux::protocol::control::ControlListEntry;
using gridflux::protocol::control::ControlPathKind;
using gridflux::protocol::control::formatList;
using gridflux::protocol::control::formatMdtmTime;
using gridflux::protocol::control::formatNlst;
using gridflux::protocol::control::parseControlServerOptions;
using gridflux::protocol::control::resolveControlPath;
using gridflux::protocol::control::resolveRetrPath;
using gridflux::protocol::control::resolveStorPath;
using gridflux::protocol::control::resolveVirtualPath;

TEST(ControlOptionsTest, ParsesDefaultsAndRequiredRoot) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-options-root";
    std::filesystem::create_directories(root);

    const std::string rootText = root.string();
    const char* argv[] = {"gridflux-gridftp-server", "--root", rootText.c_str()};
    auto parsed = parseControlServerOptions(3, argv);
    ASSERT_TRUE(parsed.isOk()) << parsed.status().message();
    EXPECT_EQ(parsed.value().host, "127.0.0.1");
    EXPECT_EQ(parsed.value().port, 2121);
    EXPECT_EQ(parsed.value().dataPortBase, 20200);
    EXPECT_EQ(parsed.value().connections, 1U);
    EXPECT_EQ(parsed.value().checksumAlgorithm, ChecksumAlgorithm::Crc32c);
    EXPECT_EQ(parsed.value().checksumBackend, ChecksumBackend::Auto);
    EXPECT_EQ(parsed.value().manifestFlushPolicy, ManifestFlushPolicy::EveryNChunks);
    EXPECT_EQ(parsed.value().manifestFlushIntervalChunks, 16U);
    EXPECT_EQ(parsed.value().finalVerifyPolicy, FinalVerifyPolicy::Full);
    EXPECT_EQ(parsed.value().commitSyncPolicy, CommitSyncPolicy::None);
    EXPECT_EQ(parsed.value().preallocateMode, gridflux::storage::PreallocateMode::Off);
    EXPECT_EQ(parsed.value().fileIo.backend, gridflux::storage::FileIoBackendKind::Posix);
    EXPECT_EQ(parsed.value().fileIo.bufferSize, 0U);
    EXPECT_EQ(parsed.value().fileIo.advice, gridflux::storage::FileIoAdvice::Off);
    EXPECT_EQ(parsed.value().fileIo.posixWriteStrategy,
              gridflux::storage::PosixWriteStrategy::Auto);
    EXPECT_EQ(parsed.value().user, "gridflux");

    std::filesystem::remove_all(root);
}

TEST(ControlOptionsTest, ParsesExplicitOptions) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-options-explicit";
    std::filesystem::create_directories(root);
    const std::string rootText = root.string();
    const char* argv[] = {"gridflux-gridftp-server",
                          "--root",
                          rootText.c_str(),
                          "--host",
                          "0.0.0.0",
                          "--port",
                          "2221",
                          "--data-port-base",
                          "20300",
                          "--connections",
                          "8",
                          "--chunk-size",
                          "4194304",
                          "--buffer-size",
                          "131072",
                          "--checksum",
                          "none",
                          "--checksum-backend",
                          "software",
                          "--manifest-flush-policy",
                          "final_only",
                          "--manifest-flush-interval-chunks",
                          "32",
                          "--final-verify-policy",
                          "verified_chunks",
                          "--commit-sync-policy",
                          "fsync_file",
                          "--preallocate",
                          "full",
                          "--file-io-backend",
                          "io_uring",
                          "--file-io-buffer-size",
                          "1048576",
                          "--file-io-queue-depth",
                          "8",
                          "--file-io-advice",
                          "noreuse",
                          "--posix-write-strategy",
                          "coalesced",
                          "--user",
                          "alice",
                          "--password",
                          "secret"};
    auto parsed = parseControlServerOptions(static_cast<int>(std::size(argv)), argv);
    ASSERT_TRUE(parsed.isOk()) << parsed.status().message();
    EXPECT_EQ(parsed.value().host, "0.0.0.0");
    EXPECT_EQ(parsed.value().port, 2221);
    EXPECT_EQ(parsed.value().dataPortBase, 20300);
    EXPECT_EQ(parsed.value().connections, 8U);
    EXPECT_EQ(parsed.value().chunkSize, 4194304U);
    EXPECT_EQ(parsed.value().bufferSize, 131072U);
    EXPECT_EQ(parsed.value().checksumAlgorithm, ChecksumAlgorithm::None);
    EXPECT_EQ(parsed.value().checksumBackend, ChecksumBackend::Software);
    EXPECT_EQ(parsed.value().manifestFlushPolicy, ManifestFlushPolicy::FinalOnly);
    EXPECT_EQ(parsed.value().manifestFlushIntervalChunks, 32U);
    EXPECT_EQ(parsed.value().finalVerifyPolicy, FinalVerifyPolicy::VerifiedChunks);
    EXPECT_EQ(parsed.value().commitSyncPolicy, CommitSyncPolicy::FsyncFile);
    EXPECT_EQ(parsed.value().preallocateMode, gridflux::storage::PreallocateMode::Full);
    EXPECT_EQ(parsed.value().fileIo.backend, gridflux::storage::FileIoBackendKind::IoUring);
    EXPECT_EQ(parsed.value().fileIo.bufferSize, 1048576U);
    EXPECT_EQ(parsed.value().fileIo.queueDepth, 8U);
    EXPECT_EQ(parsed.value().fileIo.batchSize, 8U);
    EXPECT_EQ(parsed.value().fileIo.advice, gridflux::storage::FileIoAdvice::Noreuse);
    EXPECT_EQ(parsed.value().fileIo.posixWriteStrategy,
              gridflux::storage::PosixWriteStrategy::Coalesced);
    EXPECT_EQ(parsed.value().user, "alice");

    std::filesystem::remove_all(root);
}

TEST(ControlOptionsTest, RejectsInvalidOptions) {
    const char* missingRoot[] = {"gridflux-gridftp-server"};
    EXPECT_FALSE(parseControlServerOptions(1, missingRoot).isOk());

    const char* badConnections[] = {"gridflux-gridftp-server", "--root", "/tmp", "--connections",
                                    "65"};
    EXPECT_FALSE(parseControlServerOptions(5, badConnections).isOk());

    const char* badBackend[] = {"gridflux-gridftp-server", "--root", "/tmp", "--checksum-backend",
                                "fast"};
    EXPECT_FALSE(parseControlServerOptions(5, badBackend).isOk());

    const char* badFinalVerify[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                    "--final-verify-policy", "fast"};
    EXPECT_FALSE(parseControlServerOptions(5, badFinalVerify).isOk());

    const char* badFlushPolicy[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                    "--manifest-flush-policy", "sometimes"};
    EXPECT_FALSE(parseControlServerOptions(5, badFlushPolicy).isOk());

    const char* badCommitSync[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                   "--commit-sync-policy", "sync_everything"};
    EXPECT_FALSE(parseControlServerOptions(5, badCommitSync).isOk());

    const char* badPreallocate[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                    "--preallocate", "yes"};
    EXPECT_FALSE(parseControlServerOptions(5, badPreallocate).isOk());

    const char* badFileIoBackend[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                      "--file-io-backend", "uring"};
    EXPECT_FALSE(parseControlServerOptions(5, badFileIoBackend).isOk());

    const char* badFileIoBuffer[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                     "--file-io-buffer-size", "67108865"};
    EXPECT_FALSE(parseControlServerOptions(5, badFileIoBuffer).isOk());

    const char* badFileIoQueueDepth[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                         "--file-io-queue-depth", "0"};
    EXPECT_FALSE(parseControlServerOptions(5, badFileIoQueueDepth).isOk());

    const char* badFileIoBatchSize[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                        "--file-io-batch-size", "257"};
    EXPECT_FALSE(parseControlServerOptions(5, badFileIoBatchSize).isOk());

    const char* badFileIoAdvice[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                     "--file-io-advice", "random"};
    EXPECT_FALSE(parseControlServerOptions(5, badFileIoAdvice).isOk());

    const char* badPosixWriteStrategy[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                           "--posix-write-strategy", "buffered"};
    EXPECT_FALSE(parseControlServerOptions(5, badPosixWriteStrategy).isOk());

    const char* badCoalescedWithoutBuffer[] = {"gridflux-gridftp-server", "--root", "/tmp",
                                               "--posix-write-strategy", "coalesced"};
    EXPECT_FALSE(parseControlServerOptions(5, badCoalescedWithoutBuffer).isOk());
}

TEST(ControlOptionsTest, ResolvesStorPathInsideRoot) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-path-root";
    std::filesystem::create_directories(root / "subdir");

    auto resolved = resolveStorPath(root.string(), "subdir/file.bin");
    ASSERT_TRUE(resolved.isOk()) << resolved.status().message();
    EXPECT_EQ(resolved.value(), (root / "subdir/file.bin").string());

    EXPECT_FALSE(resolveStorPath(root.string(), "../escape.bin").isOk());
    EXPECT_FALSE(resolveStorPath(root.string(), "/tmp/escape.bin").isOk());
    EXPECT_FALSE(resolveStorPath(root.string(), "").isOk());
    auto nested = resolveStorPath(root.string(), "missing/file.bin");
    ASSERT_TRUE(nested.isOk()) << nested.status().message();
    EXPECT_EQ(nested.value(), (root / "missing/file.bin").string());
    EXPECT_TRUE(std::filesystem::is_directory(root / "missing"));

    std::filesystem::remove_all(root);
}

TEST(ControlOptionsTest, ResolvesRetrPathInsideRoot) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-retr-path-root";
    std::filesystem::create_directories(root / "subdir");
    const std::filesystem::path file = root / "subdir/source.bin";
    std::filesystem::path directory = root / "subdir";
    {
        std::ofstream output(file);
        output << "hello";
    }

    auto resolved = resolveRetrPath(root.string(), "subdir/source.bin");
    ASSERT_TRUE(resolved.isOk()) << resolved.status().message();
    EXPECT_EQ(resolved.value(), file.string());

    EXPECT_FALSE(resolveRetrPath(root.string(), "../escape.bin").isOk());
    EXPECT_FALSE(resolveRetrPath(root.string(), "/tmp/escape.bin").isOk());
    EXPECT_FALSE(resolveRetrPath(root.string(), "").isOk());
    EXPECT_FALSE(resolveRetrPath(root.string(), "missing.bin").isOk());
    EXPECT_FALSE(resolveRetrPath(root.string(), "subdir").isOk());

    std::filesystem::remove_all(root);
}

TEST(ControlOptionsTest, ResolvesPathsRelativeToWorkingDirectory) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-cwd-path-root";
    std::filesystem::create_directories(root / "subdir" / "nested");
    const std::filesystem::path file = root / "subdir" / "nested" / "source.bin";
    {
        std::ofstream output(file);
        output << "hello";
    }

    auto virtualPath = resolveVirtualPath("/subdir", "nested/source.bin", false);
    ASSERT_TRUE(virtualPath.isOk()) << virtualPath.status().message();
    EXPECT_EQ(virtualPath.value(), "/subdir/nested/source.bin");

    auto resolved = resolveRetrPath(root.string(), "/subdir", "nested/source.bin");
    ASSERT_TRUE(resolved.isOk()) << resolved.status().message();
    EXPECT_EQ(resolved.value(), file.string());

    auto directory = resolveControlPath(root.string(), "/subdir", "nested",
                                        ControlPathKind::ExistingDirectory, "CWD");
    ASSERT_TRUE(directory.isOk()) << directory.status().message();
    EXPECT_EQ(directory.value().virtualPath, "/subdir/nested");

    directory = resolveControlPath(root.string(), "/subdir/nested", "..",
                                   ControlPathKind::ExistingDirectory, "CWD");
    ASSERT_TRUE(directory.isOk()) << directory.status().message();
    EXPECT_EQ(directory.value().virtualPath, "/subdir");

    std::filesystem::remove_all(root);
}

TEST(ControlOptionsTest, RejectsSymlinkEscape) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-control-symlink-root";
    const std::filesystem::path outside =
        std::filesystem::temp_directory_path() / "gridflux-control-symlink-outside";
    std::filesystem::remove_all(root);
    std::filesystem::remove_all(outside);
    std::filesystem::create_directories(root);
    std::filesystem::create_directories(outside);
    {
        std::ofstream output(outside / "secret.bin");
        output << "secret";
    }
    std::error_code error;
    std::filesystem::create_directory_symlink(outside, root / "escape", error);
    if (error) {
        GTEST_SKIP() << "symlink creation is unavailable: " << error.message();
    }

    EXPECT_FALSE(resolveControlPath(root.string(), "/", "escape/secret.bin",
                                    ControlPathKind::ExistingFile, "SIZE")
                     .isOk());
    EXPECT_FALSE(
        resolveControlPath(root.string(), "/", "escape", ControlPathKind::ExistingDirectory, "LIST")
            .isOk());

    std::filesystem::remove_all(root);
    std::filesystem::remove_all(outside);
}

TEST(ControlOptionsTest, FormatsMdtmAndListings) {
    EXPECT_EQ(formatMdtmTime(0), "19700101000000");

    std::vector<ControlListEntry> entries;
    entries.push_back(ControlListEntry{"alpha.bin", false, 5, 0});
    entries.push_back(ControlListEntry{"subdir", true, 0, 0});

    EXPECT_EQ(formatNlst(entries), "alpha.bin\r\nsubdir\r\n");
    const std::string list = formatList(entries);
    EXPECT_NE(list.find("- 5 19700101000000 alpha.bin\r\n"), std::string::npos);
    EXPECT_NE(list.find("d 0 19700101000000 subdir\r\n"), std::string::npos);
    EXPECT_EQ(list.find("/tmp/"), std::string::npos);
}

}  // namespace
