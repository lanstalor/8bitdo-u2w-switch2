#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test_dir=$(mktemp -d /tmp/u2w-tests.XXXXXX)
trap 'rm -rf -- "$test_dir"' EXIT
for suite in protocol pairing_crypto session runtime phy_ram; do
    gcc -Wall -Wextra -Werror -fsanitize=address,undefined \
        -fno-sanitize-recover=all -g \
        src/sw2/protocol.c src/sw2/pairing_crypto.c src/sw2/session.c \
        "src/test/${suite}_test.c" -o "$test_dir/$suite"
    "$test_dir/$suite"
done
