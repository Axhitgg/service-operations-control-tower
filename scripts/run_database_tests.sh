#!/usr/bin/env bash
# Start a separate synthetic-only PostgreSQL cluster; never use DATABASE_URL.
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
pg_bin="${CONTROL_TOWER_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
test_root="$(mktemp -d /private/tmp/ct-approval-test-XXXXXX)"
mkdir "$test_root/socket"
chmod 700 "$test_root" "$test_root/socket"

cleanup() {
    if [[ -f "$test_root/data/postmaster.pid" ]]; then
        "$pg_bin/pg_ctl" -D "$test_root/data" -m fast -w stop
    fi
    # Keep diagnostics/test-only cluster for inspection; no broad deletion.
    printf 'Stopped test cluster; diagnostics retained at %s\n' "$test_root"
}
trap cleanup EXIT

"$pg_bin/initdb" -D "$test_root/data" -U ct_test --auth-local=trust --auth-host=reject > "$test_root/initdb.log"
"$pg_bin/pg_ctl" -D "$test_root/data" -l "$test_root/postgres.log" \
    -o "-k $test_root/socket -c listen_addresses='' -p 55491" -w start
"$pg_bin/createdb" -h "$test_root/socket" -p 55491 -U ct_test ct_approval_test
cd "$project_dir"
CONTROL_TOWER_TEST_DATABASE_URL="host=$test_root/socket port=55491 dbname=ct_approval_test user=ct_test" \
    .venv/bin/python -m pytest -q test_service_api.py test_database_approval.py
