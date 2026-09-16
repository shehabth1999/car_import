# Backups — on the host, nightly, fourteen days

    install -m 755 <(tr -d '\r' < ops/backup/genie-backup.sh) /usr/local/bin/genie-backup
    install -m 644 ops/backup/genie-backup@.service ops/backup/genie-backup@.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now genie-backup@khaled_test.timer
    systemctl start genie-backup@khaled_test.service      # one run now, to see it work
    ls -lh /var/backups/genie/khaled_test/

What lands there, every night at 03:30 host time (the host is on CEST, so 04:30 Cairo; ±20 min): `db-*.dump` (the tenant
database, `pg_dump -Fc`), `langgraph-*.dump` (the AI conversation checkpoints),
`media-*.tgz` (uploads: contracts, photos, call recordings), `env-*` (the
tenant secrets, root-only). Files older than fourteen days are removed.

Restore a database: `sudo -u postgres pg_restore -d khaled_test --clean --if-exists db-<stamp>.dump`
with the four `genie-*@khaled_test` units stopped first. Restore media:
`tar -xzf media-<stamp>.tgz -C /srv/genie/khaled_test/` then `chown -R genie_khaled_test:`.

The backups stay on the host. Copying one elsewhere is a decision somebody
takes on purpose, with the client's data-handling rules in front of them.
