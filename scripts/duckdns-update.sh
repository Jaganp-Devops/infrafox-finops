#!/bin/bash
# Pushes this instance's current public IP to DuckDNS.
# Token is read from an environment file, never hardcoded or committed.
set -euo pipefail

source /etc/infrafox/duckdns.env

curl -s "https://www.duckdns.org/update?domains=infrafox&token=${DUCKDNS_TOKEN}&ip=" \
  -o /var/log/infrafox-duckdns.log

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) - DuckDNS update triggered" >> /var/log/infrafox-duckdns-cron.log
