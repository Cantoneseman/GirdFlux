#include <iostream>

#include "gridflux/config/file_transfer_options.h"
#include "gridflux/core/io/file_transfer_client.h"

int main(int argc, char** argv) {
    const auto options = gridflux::config::parseFileTransferOptions(
        argc, argv, gridflux::config::FileTransferRole::Client);
    if (!options.isOk()) {
        std::cerr << options.status().message() << '\n'
                  << gridflux::config::fileTransferUsage(argv[0],
                                                         gridflux::config::FileTransferRole::Client)
                  << '\n';
        return 2;
    }

    const auto status = gridflux::core::io::runFileTransferClient(options.value());
    if (!status.isOk()) {
        std::cerr << status.message() << '\n';
        return 1;
    }

    return 0;
}
