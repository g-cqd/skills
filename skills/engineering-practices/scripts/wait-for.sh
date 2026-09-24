#!/bin/sh
# wait-for: wait for long-running work, and return the moment it is done.
#
# A fixed `sleep` waits too long or not long enough. wait-for checks its condition every INTERVAL seconds and
# returns as soon as the condition holds, or once TIMEOUT seconds have passed, whichever comes first. Keep TIMEOUT
# under the limit of the tool call that runs it, and call wait-for again while the work goes on.
#
# Usage:
#   wait-for.sh [options] run STATUS LOG -- COMMAND [ARGUMENT...]
#       Start COMMAND in the background, its output in LOG; when it ends, write its exit status to STATUS.
#       Then wait for STATUS, as `file` does. The command keeps running if the wait times out.
#   wait-for.sh [options] file PATH...
#       Wait until every PATH exists and is not empty. With one PATH holding a number, as `run` writes, exit
#       with that number.
#   wait-for.sh [options] gone PATH...
#       Wait until no PATH exists, as for a lock file that a finished phase deletes.
#   wait-for.sh [options] pid PID...
#       Wait until every process PID has exited.
#   wait-for.sh [options] log PATH PATTERN
#       Wait until PATH holds a line that matches the extended regular expression PATTERN.
#
# Options:
#   --timeout SECONDS    stop waiting after this long; default 570, under a 10-minute tool call
#   --interval SECONDS   time between checks; default 1
#   --tail LINES         lines of the log to print when it returns; default 5 (`run` and `log` only)
#
# Exit status: 0 when the condition holds; the command's own status for `run`, and for `file` with one status
# file; 124 when the timeout passed first, so call again to keep waiting; 2 for a usage error.
# The last line printed says what happened and how long the wait took.

set -u

timeout=570
interval=1
tail_lines=5

usage() {
    sed -n '2,/^$/s/^# \{0,1\}//p' "$0" >&2
    exit 2
}

while [ $# -gt 0 ]; do
    case $1 in
        --timeout) [ $# -ge 2 ] || usage; timeout=$2; shift 2 ;;
        --interval) [ $# -ge 2 ] || usage; interval=$2; shift 2 ;;
        --tail) [ $# -ge 2 ] || usage; tail_lines=$2; shift 2 ;;
        -h|--help) usage ;;
        *) break ;;
    esac
done
[ $# -ge 1 ] || usage
mode=$1
shift

start=$(date +%s)
elapsed() { echo $(( $(date +%s) - start )); }

# Prints the end of a log, if there is one.
show_tail() {
    if [ -n "${1:-}" ] && [ -f "$1" ] && [ "$tail_lines" -gt 0 ]; then
        tail -n "$tail_lines" "$1"
    fi
}

# Runs the check "$@" until it succeeds or the timeout passes; returns 0 or 124.
poll() {
    while :; do
        if "$@"; then return 0; fi
        if [ "$(elapsed)" -ge "$timeout" ]; then return 124; fi
        sleep "$interval"
    done
}

# The checks below run through poll, which shellcheck cannot follow.
# shellcheck disable=SC2329
files_ready() {
    for path in "$@"; do
        [ -s "$path" ] || return 1
    done
    return 0
}

# shellcheck disable=SC2329
paths_gone() {
    for path in "$@"; do
        [ -e "$path" ] && return 1
    done
    return 0
}

# shellcheck disable=SC2329
pids_gone() {
    for pid in "$@"; do
        kill -0 "$pid" 2>/dev/null || continue
        # A zombie has exited; it still answers kill -0 until its parent reaps it.
        case $(ps -o stat= -p "$pid" 2>/dev/null) in
            Z*) continue ;;
        esac
        return 1
    done
    return 0
}

# shellcheck disable=SC2329
log_matches() {
    [ -f "$1" ] && grep -E -q -- "$2" "$1"
}

# Waits for status files; with one file holding a number, exits with that number.
wait_files() {
    log=$1
    shift
    if poll files_ready "$@"; then
        show_tail "$log"
        if [ $# -eq 1 ]; then
            status=$(tr -d ' \n' < "$1")
            case $status in
                ''|*[!0-9]*) echo "wait-for: $1 is ready after $(elapsed) s"; exit 0 ;;
                *) echo "wait-for: finished with status $status after $(elapsed) s"; exit "$status" ;;
            esac
        fi
        echo "wait-for: every file is ready after $(elapsed) s"
        exit 0
    fi
    show_tail "$log"
    echo "wait-for: still running after $(elapsed) s; call again to keep waiting"
    exit 124
}

case $mode in
    run)
        [ $# -ge 4 ] && [ "$3" = "--" ] || usage
        status_file=$1
        log_file=$2
        shift 3
        rm -f "$status_file"
        # The subshell outlives this call, so the command runs on if the wait times out.
        (
            "$@" > "$log_file" 2>&1
            echo $? > "$status_file.partial" && mv "$status_file.partial" "$status_file"
        ) > /dev/null 2>&1 &
        echo "wait-for: started \"$*\" as process $!; output in $log_file, status in $status_file"
        wait_files "$log_file" "$status_file"
        ;;
    file)
        [ $# -ge 1 ] || usage
        wait_files "" "$@"
        ;;
    gone)
        [ $# -ge 1 ] || usage
        if poll paths_gone "$@"; then
            echo "wait-for: every path is gone after $(elapsed) s"
            exit 0
        fi
        echo "wait-for: still present after $(elapsed) s; call again to keep waiting"
        exit 124
        ;;
    pid)
        [ $# -ge 1 ] || usage
        if poll pids_gone "$@"; then
            echo "wait-for: every process exited after $(elapsed) s"
            exit 0
        fi
        echo "wait-for: still running after $(elapsed) s; call again to keep waiting"
        exit 124
        ;;
    log)
        [ $# -eq 2 ] || usage
        if poll log_matches "$1" "$2"; then
            show_tail "$1"
            echo "wait-for: $1 matched after $(elapsed) s"
            exit 0
        fi
        show_tail "$1"
        echo "wait-for: no match after $(elapsed) s; call again to keep waiting"
        exit 124
        ;;
    *)
        usage
        ;;
esac
