#!/usr/bin/env bash
# Run a Ghidra script against an existing analyzed project (no re-import, no re-analysis).
# Usage: tools/gh.sh <ctrl|dongle> <Script.java> [args...]
set -e
R=/c/Users/lance/re-tools
P=/c/Users/lance/OneDrive/Documents/_CODE/8bitdo
export JAVA_HOME="$(cygpath -w "$R/jdk-25.0.4.1+1")"
export PATH="$R/jdk-25.0.4.1+1/bin:$PATH"
H="$(cygpath -w "$R/ghidra_12.2_PUBLIC/support/analyzeHeadless.bat")"
n=$1; shift; s=$1; shift
case "$n" in ctrl) f=payload-ctrl-v109.bin;; dongle) f=payload-dongle-v106.bin;; boot) f=bootloader-dump.bin;; esac
cmd //c "$H" "$(cygpath -w "$R/projects")" "u2w_$n" -process "$f" -noanalysis -readOnly \
  -scriptPath "$(cygpath -w "$P/tools")" -postScript "$s" "$@" < /dev/null 2>&1 \
  | grep -v -E '^INFO |WARN |ghidra_scripts|^    C:|^\s*$' || true
