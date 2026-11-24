#!/usr/bin/env bash
set -euo pipefail

case "${1:?Specify P or D}" in
    P) task=${ITASK_P_TASK:?Set ITASK_P_TASK} ;;
    D) task=${ITASK_D_TASK:?Set ITASK_D_TASK} ;;
    *) printf '%s\n' "Specify P or D" >&2; exit 2 ;;
esac
shift
exec "${ITASK_CLI:-itask-guian}" exec "$task" --tty=false -- "$@"
