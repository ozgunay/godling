#!/bin/sh
# Alertmanager's config from the environment (it reads none itself), then Alertmanager. Without GODLING_ALERT_EMAIL or
# an SMTP host, alerts are kept (its page shows them) but not sent.
set -eu
esc() { printf '%s' "$1" | sed -e "s/'/''/g" -e 's/[&|\\]/\\&/g'; } # inside YAML single quotes, and for sed
printf '%s' "${GODLING_EMAIL_PASSWORD:-}" > /tmp/smtp_password
if [ -z "${GODLING_ALERT_EMAIL:-}" ] || [ -z "${GODLING_EMAIL_HOST:-}" ]; then
  echo "alertmanager: GODLING_ALERT_EMAIL or GODLING_EMAIL_HOST is not set: alerts are kept, not emailed" >&2
  printf 'route:\n  receiver: kept\nreceivers:\n  - name: kept\n' > /tmp/alertmanager.yml
else
  starttls=true
  [ "${GODLING_EMAIL_SSL:-0}" = 1 ] && starttls=false # port 465: TLS from the first byte, which Alertmanager does by itself
  [ "${GODLING_EMAIL_TLS:-1}" = 1 ] || [ "${GODLING_EMAIL_SSL:-0}" = 1 ] || starttls=false
  sed -e "s|__SMTP_HOST__|$(esc "$GODLING_EMAIL_HOST")|" -e "s|__SMTP_PORT__|$(esc "${GODLING_EMAIL_PORT:-587}")|" \
      -e "s|__SMTP_FROM__|$(esc "${GODLING_FROM_EMAIL:-godling@localhost}")|" \
      -e "s|__SMTP_USER__|$(esc "${GODLING_EMAIL_USER:-}")|" -e "s|__SMTP_STARTTLS__|$starttls|" \
      -e "s|__ALERT_TO__|$(esc "$GODLING_ALERT_EMAIL")|" /etc/alertmanager/alertmanager.yml.template > /tmp/alertmanager.yml
fi
exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
