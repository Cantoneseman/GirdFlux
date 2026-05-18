#include <iostream>

#include "gridflux/config/tree_transfer_options.h"
#include "gridflux/core/io/tree_transfer_client.h"

int main(int argc, char** argv) {
    const auto options = gridflux::config::parseTreeTransferOptions(
        argc, argv, gridflux::config::TreeTransferRole::Upload);
    if (!options.isOk()) {
        std::cerr << options.status().message() << '\n'
                  << gridflux::config::treeTransferUsage(
                         argv[0], gridflux::config::TreeTransferRole::Upload)
                  << '\n';
        return 2;
    }
    const auto status = gridflux::core::io::runTreeUploadClient(options.value());
    if (!status.isOk()) {
        std::cerr << status.message() << '\n';
        return 1;
    }
    return 0;
}
