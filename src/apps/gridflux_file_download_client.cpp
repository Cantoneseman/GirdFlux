#include <iostream>

#include "gridflux/config/file_download_options.h"
#include "gridflux/core/io/file_download_client.h"

int main(int argc, char** argv) {
    const auto options = gridflux::config::parseFileDownloadOptions(argc, argv);
    if (!options.isOk()) {
        std::cerr << options.status().message() << '\n'
                  << gridflux::config::fileDownloadUsage(argv[0]) << '\n';
        return 2;
    }

    const auto status = gridflux::core::io::runFileDownloadClient(options.value());
    if (!status.isOk()) {
        std::cerr << status.message() << '\n';
        return 1;
    }

    return 0;
}
