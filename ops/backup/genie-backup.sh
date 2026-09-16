#!/usr/bin/env bash
# Nightly backup of one Genie tenant: the database, its LangGraph checkpoint
# database when there is one, and the media tree. Runs on the host as root
# from genie-backup@<slug>.timer and keeps KEEP_DAYS days in
# /var/backups/genie/<slug>/. Nothing here leaves the machine — copying a
# backup off-host is a separate, deliberate step, never part of the timer.
#
#   genie-backup khaled_test
#   KEEP_DAYS=30 genie-backup khaled_test
set -euo pipefail

slug="${1:?usage: genie-backup <slug>}"
keep_days="${KEEP_DAYS:-14}"
dest="/var/backups/genie/${slug}"
app="/srv/genie/${slug}"
stamp="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$dest"
chmod 700 "$dest"

dump_db() {
    local db="$1" out="$2"
    if sudo -u postgres psql -Atc "select 1 from pg_database where datname='${db}'" | grep -q 1; then
        sudo -u postgres pg_dump -Fc "$db" > "$out"
        echo "  ${db} -> $(du -h "$out" | cut -f1)"
    fi
}

echo "backup ${slug} @ ${stamp}"
dump_db "$slug" "${dest}/db-${stamp}.dump"
dump_db "${slug}_langgraph" "${dest}/langgraph-${stamp}.dump"

if [ -d "${app}/media" ]; then
    tar -czf "${dest}/media-${stamp}.tgz" -C "$app" media
    echo "  media -> $(du -h "${dest}/media-${stamp}.tgz" | cut -f1)"
fi

# The tenant .env carries the secret key and the API keys; a restore without
# it is a restore that cannot log anyone in. Root-only, like the rest.
if [ -f "/etc/genie/deployments/${slug}.env" ]; then
    cp "/etc/genie/deployments/${slug}.env" "${dest}/env-${stamp}"
    chmod 600 "${dest}/env-${stamp}"
fi

find "$dest" -type f -mtime +"$keep_days" -delete
echo "kept $(find "$dest" -type f | wc -l) file(s), $(du -sh "$dest" | cut -f1), ${keep_days}-day rotation"
