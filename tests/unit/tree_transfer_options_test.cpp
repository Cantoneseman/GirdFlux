#include "gridflux/config/tree_transfer_options.h"

#include <gtest/gtest.h>

#include <filesystem>

TEST(TreeTransferOptionsTest, ParsesUploadOptions) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-tree-options-upload";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root);
    const std::string rootText = root.string();
    const char* argv[] = {"gridflux-tree-upload-client",
                          "--host",
                          "127.0.0.1",
                          "--port",
                          "2121",
                          "--source-dir",
                          rootText.c_str(),
                          "--dest-dir",
                          "remote/data",
                          "--connections",
                          "4",
                          "--file-parallelism",
                          "2",
                          "--chunk-size",
                          "4194304",
                          "--buffer-size",
                          "262144",
                          "--checksum",
                          "none",
                          "--checksum-backend",
                          "software",
                          "--max-files",
                          "1",
                          "--user",
                          "alice",
                          "--password",
                          "secret",
                          "--json-summary",
                          "/tmp/tree-summary.json"};
    auto parsed = gridflux::config::parseTreeTransferOptions(
        static_cast<int>(std::size(argv)), argv, gridflux::config::TreeTransferRole::Upload);
    ASSERT_TRUE(parsed.isOk()) << parsed.status().message();
    EXPECT_EQ(parsed.value().destDir, "remote/data");
    EXPECT_EQ(parsed.value().connections, 4U);
    EXPECT_EQ(parsed.value().fileParallelism, 2U);
    EXPECT_EQ(parsed.value().chunkSize, 4194304U);
    EXPECT_EQ(parsed.value().bufferSize, 262144U);
    EXPECT_EQ(parsed.value().checksumAlgorithm, gridflux::checksum::ChecksumAlgorithm::None);
    EXPECT_EQ(parsed.value().user, "alice");
    EXPECT_EQ(parsed.value().jsonSummaryPath, "/tmp/tree-summary.json");
    std::filesystem::remove_all(root);
}

TEST(TreeTransferOptionsTest, ParsesDownloadOptionsAndCreatesDestination) {
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "gridflux-tree-options-download";
    std::filesystem::remove_all(root);
    const std::string rootText = root.string();
    const char* argv[] = {"gridflux-tree-download-client",
                          "--source-dir",
                          "remote/data",
                          "--dest-dir",
                          rootText.c_str(),
                          "--resume",
                          "--summary-json",
                          "/tmp/tree-download-summary.json"};
    auto parsed = gridflux::config::parseTreeTransferOptions(
        static_cast<int>(std::size(argv)), argv, gridflux::config::TreeTransferRole::Download);
    ASSERT_TRUE(parsed.isOk()) << parsed.status().message();
    EXPECT_TRUE(parsed.value().resume);
    EXPECT_EQ(parsed.value().jsonSummaryPath, "/tmp/tree-download-summary.json");
    std::filesystem::remove_all(root);
}

TEST(TreeTransferOptionsTest, RejectsInvalidOptions) {
    const char* missing[] = {"gridflux-tree-upload-client"};
    EXPECT_FALSE(gridflux::config::parseTreeTransferOptions(
                     1, missing, gridflux::config::TreeTransferRole::Upload)
                     .isOk());

    const char* badParallelism[] = {"gridflux-tree-upload-client", "--source-dir", "/tmp",
                                    "--dest-dir", "remote", "--file-parallelism", "0"};
    EXPECT_FALSE(gridflux::config::parseTreeTransferOptions(
                     7, badParallelism, gridflux::config::TreeTransferRole::Upload)
                     .isOk());

    const char* badRemote[] = {"gridflux-tree-download-client", "--source-dir", "../escape",
                               "--dest-dir", "/tmp/out"};
    EXPECT_FALSE(gridflux::config::parseTreeTransferOptions(
                     5, badRemote, gridflux::config::TreeTransferRole::Download)
                     .isOk());

    const char* missingSummary[] = {"gridflux-tree-upload-client",
                                    "--source-dir",
                                    "/tmp",
                                    "--dest-dir",
                                    "remote",
                                    "--json-summary"};
    EXPECT_FALSE(gridflux::config::parseTreeTransferOptions(
                     6, missingSummary, gridflux::config::TreeTransferRole::Upload)
                     .isOk());
}
