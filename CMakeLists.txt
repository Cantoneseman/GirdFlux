cmake_minimum_required(VERSION 3.20)

project(
    GridFlux
    VERSION 0.1.0
    DESCRIPTION "GridFTP-compatible high-performance transfer foundation"
    LANGUAGES CXX
)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "GridFlux is Linux-only.")
endif()

option(GRIDFLUX_BUILD_TESTS "Build GridFlux tests" ON)
option(GRIDFLUX_ENABLE_IO_URING "Enable optional file-IO-only io_uring backend" OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
find_package(Threads REQUIRED)

FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG v1.17.0
)

FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.17.0
)

FetchContent_MakeAvailable(spdlog)

set(GRIDFLUX_CRC32C_HW_SOURCE src/checksum/crc32c_hw_stub.cpp)
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|i[3-6]86"
   AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(GRIDFLUX_CRC32C_HW_SOURCE src/checksum/crc32c_hw_x86.cpp)
    set_source_files_properties(src/checksum/crc32c_hw_x86.cpp
        PROPERTIES
            COMPILE_OPTIONS "-msse4.2"
    )
endif()

set(GRIDFLUX_FILE_IO_URING_SOURCE src/storage/file_io_uring_stub.cpp)
set(GRIDFLUX_HAS_IO_URING 0)
if(GRIDFLUX_ENABLE_IO_URING)
    find_path(GRIDFLUX_LIBURING_INCLUDE_DIR NAMES liburing.h)
    find_library(GRIDFLUX_LIBURING_LIBRARY NAMES uring)
    if(GRIDFLUX_LIBURING_INCLUDE_DIR AND GRIDFLUX_LIBURING_LIBRARY)
        set(GRIDFLUX_FILE_IO_URING_SOURCE src/storage/file_io_uring.cpp)
        set(GRIDFLUX_HAS_IO_URING 1)
        message(STATUS "GridFlux io_uring backend enabled")
    else()
        message(WARNING "GRIDFLUX_ENABLE_IO_URING=ON but liburing was not found; building unavailable backend stub")
    endif()
endif()

add_library(gridflux_core STATIC
    src/checkpoint/download_manifest.cpp
    src/checkpoint/manifest_store.cpp
    src/checkpoint/transfer_manifest.cpp
    src/checksum/checksum.cpp
    src/checksum/crc32c.cpp
    ${GRIDFLUX_CRC32C_HW_SOURCE}
    src/common/throughput_counter.cpp
    src/common/version.cpp
    src/config/file_transfer_options.cpp
    src/config/file_download_options.cpp
    src/config/tree_transfer_options.cpp
    src/config/sink_options.cpp
    src/core/chunk/chunk_planner.cpp
    src/core/chunk/range_list.cpp
    src/core/chunk/transfer_progress.cpp
    src/core/io/connection_context.cpp
    src/core/io/file_download_client.cpp
    src/core/io/file_download_sender.cpp
    src/core/io/file_transfer_client.cpp
    src/core/io/file_transfer_server.cpp
    src/core/io/socket_utils.cpp
    src/core/io/tcp_sink_client.cpp
    src/core/io/tcp_sink_server.cpp
    src/core/io/tree_transfer_client.cpp
    src/core/metrics/transfer_phase_stats.cpp
    src/core/protocol/frame.cpp
    src/core/session/download_session.cpp
    src/core/session/commit_sync_policy.cpp
    src/core/session/final_verify_policy.cpp
    src/core/session/manifest_flush_policy.cpp
    src/core/session/transfer_session.cpp
    src/core/tree/tree_manifest.cpp
    src/core/tree/tree_scan.cpp
    src/protocol/control/control_command.cpp
    src/protocol/control/control_options.cpp
    src/protocol/control/control_server.cpp
    src/storage/file_io.cpp
    ${GRIDFLUX_FILE_IO_URING_SOURCE}
    src/storage/posix_file.cpp
    src/storage/preallocate_mode.cpp
)

add_library(GridFlux::core ALIAS gridflux_core)

target_include_directories(gridflux_core
    PUBLIC
        $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
)

target_link_libraries(gridflux_core
    PUBLIC
        Threads::Threads
        spdlog::spdlog
)

target_compile_definitions(gridflux_core
    PUBLIC
        GRIDFLUX_HAS_IO_URING=${GRIDFLUX_HAS_IO_URING}
)

if(GRIDFLUX_HAS_IO_URING)
    target_include_directories(gridflux_core
        PRIVATE
            ${GRIDFLUX_LIBURING_INCLUDE_DIR}
    )
    target_link_libraries(gridflux_core
        PRIVATE
            ${GRIDFLUX_LIBURING_LIBRARY}
    )
endif()

target_compile_features(gridflux_core PUBLIC cxx_std_20)

add_executable(gridflux
    src/main.cpp
)

target_link_libraries(gridflux
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-server
    src/apps/gridflux_server.cpp
)

target_link_libraries(gridflux-server
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-client
    src/apps/gridflux_client.cpp
)

target_link_libraries(gridflux-client
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-file-server
    src/apps/gridflux_file_server.cpp
)

target_link_libraries(gridflux-file-server
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-file-client
    src/apps/gridflux_file_client.cpp
)

target_link_libraries(gridflux-file-client
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-file-download-client
    src/apps/gridflux_file_download_client.cpp
)

target_link_libraries(gridflux-file-download-client
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-tree-upload-client
    src/apps/gridflux_tree_upload_client.cpp
)

target_link_libraries(gridflux-tree-upload-client
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-tree-download-client
    src/apps/gridflux_tree_download_client.cpp
)

target_link_libraries(gridflux-tree-download-client
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-checksum-bench
    src/apps/gridflux_checksum_bench.cpp
)

target_link_libraries(gridflux-checksum-bench
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-storage-bench
    src/apps/gridflux_storage_bench.cpp
)

target_link_libraries(gridflux-storage-bench
    PRIVATE
        GridFlux::core
)

add_executable(gridflux-gridftp-server
    src/apps/gridflux_gridftp_server.cpp
)

target_link_libraries(gridflux-gridftp-server
    PRIVATE
        GridFlux::core
)

if(GRIDFLUX_BUILD_TESTS)
    enable_testing()
    FetchContent_MakeAvailable(googletest)
    include(GoogleTest)

    add_executable(gridflux_unit_tests
        tests/unit/checksum_test.cpp
        tests/unit/chunk_planner_test.cpp
        tests/unit/connection_context_test.cpp
        tests/unit/control_command_test.cpp
        tests/unit/control_options_test.cpp
        tests/unit/control_session_test.cpp
        tests/unit/download_manifest_test.cpp
        tests/unit/download_session_test.cpp
        tests/unit/file_download_options_test.cpp
        tests/unit/file_io_test.cpp
        tests/unit/file_transfer_options_test.cpp
        tests/unit/frame_test.cpp
        tests/unit/manifest_store_test.cpp
        tests/unit/posix_file_test.cpp
        tests/unit/range_list_test.cpp
        tests/unit/sink_options_test.cpp
        tests/unit/throughput_counter_test.cpp
        tests/unit/transfer_manifest_test.cpp
        tests/unit/transfer_session_test.cpp
        tests/unit/transfer_progress_test.cpp
        tests/unit/tree_manifest_test.cpp
        tests/unit/tree_scan_test.cpp
        tests/unit/tree_transfer_options_test.cpp
        tests/unit/version_test.cpp
    )

    target_link_libraries(gridflux_unit_tests
        PRIVATE
            GridFlux::core
            GTest::gtest_main
    )

    gtest_discover_tests(gridflux_unit_tests)

    add_test(
        NAME gridflux_file_transfer_smoke
        COMMAND bash ${PROJECT_SOURCE_DIR}/tools/test/run_file_transfer_smoke.sh --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_file_resume_smoke
        COMMAND bash ${PROJECT_SOURCE_DIR}/tools/test/run_file_resume_smoke.sh --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_file_checksum_smoke
        COMMAND bash ${PROJECT_SOURCE_DIR}/tools/test/run_file_checksum_smoke.sh --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_stor_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_stor_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_resume_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_resume_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_retr_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_retr_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_retr_resume_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_retr_resume_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_retr_corrupt_resume_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_retr_corrupt_resume_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_metadata_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_metadata_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_gridftp_control_list_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_control_list_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_tree_upload_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_tree_upload_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_tree_download_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_tree_download_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_tree_resume_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_tree_resume_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_tree_manifest_corrupt_smoke
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/test/run_gridftp_tree_manifest_corrupt_smoke.py --build-dir ${CMAKE_BINARY_DIR}
    )
    add_test(
        NAME gridflux_release_hygiene
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/release/test_public_hygiene.py
    )
    add_test(
        NAME gridflux_alpha_release_helper_behavior
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/release/test_alpha_release_helpers.py
    )
    add_test(
        NAME gridflux_alpha_artifact_sync_behavior
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/release/test_alpha_release_helpers.py
    )
    add_test(
        NAME gridflux_storage_bench_wrapper_behavior
        COMMAND python3 ${PROJECT_SOURCE_DIR}/tools/benchmark/test_run_storage_bench.py --script ${PROJECT_SOURCE_DIR}/tools/benchmark/run_storage_bench.py
    )
endif()
