# gamebeat deployment

Source: `/root/gamebeat`. Runtime: `/srv/apps/gamebeat`. Runtime settings belong in `app.env` outside Git. Store generated passwords and keys in `secrets/` outside Git; the filenames required by Compose are listed in `compose.yaml`. The example file contains variable names without live values.

`compose.yaml` and `host-update.sh` mirror the running server configuration. Copy the application build/settings files to the runtime `deploy-overlay/` directory, excluding `host/`, `compose.yaml`, `host-update.sh`, and `app.env.example`. Install `host-update.sh` as the runtime `update.sh` and copy the repository root `update` wrapper to runtime `update-wrapper`. Host Nginx configuration is in `host/nginx.conf`; issue valid certificates before enabling its HTTPS listeners.

Build with `docker compose --project-directory /srv/apps/gamebeat -f /srv/apps/gamebeat/compose.yaml build`. Initialize/migrate the database before starting the web service. Run `update` from the project directory for subsequent deployments. The updater resets tracked source changes to the current remote branch, preserves database/media volumes, and creates no data backups. If migrations fail, inspect the release log before recovery. Logs, data, credentials, and certificate private keys are excluded from this package.
