#!/usr/bin/env bash
# Checks a running deployment from outside, as anyone on the internet sees it (ADR-017): HTTPS and its certificates,
# which paths answer and which must not, the stream's door, and which ports are open. Run it from another machine.
#
#   deploy/check.sh <site domain> <island domain>
#   CHECK_IP=203.0.113.7 deploy/check.sh …     reach that address for both names (before DNS, or one server of several)
#   CHECK_CA=root.crt deploy/check.sh …        trust this CA too (a local run's Caddy CA: its *.localhost certificates)
#   CHECK_CERT_DAYS=0 deploy/check.sh …        days a certificate must still be good for (default 14; a local Caddy CA
#                                              signs for 12 hours at a time, Let's Encrypt for 90 days)
#   CHECK_PER_ADDRESS=64 deploy/check.sh …     the relay's RELAY_MAX_PER_IP (default 64): that many sockets are held
#   CHECK_ORIGIN=203.0.113.7 deploy/check.sh … with Cloudflare in front: the server's own address, which must answer
#                                              nobody but Cloudflare (its ports are checked from here, all closed)
#
# With Cloudflare in front (ADR-017), the names reach Cloudflare, not the server: the certificate, the redirect and the
# TLS versions seen are Cloudflare's, and so are the open ports, so those are checked on CHECK_ORIGIN instead.
# Needs curl and openssl. Prints PASS or FAIL per check and exits with the number of failures.
set -u
SITE=${1:?site domain}
ISLAND=${2:?island domain}
IP=${CHECK_IP:-}
FAILS=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }
note() { printf '      %s\n' "$*"; }
expect() { # what it should be, what it is, what is being checked
  if [ "$1" = "$2" ]; then pass "$3 ($2)"; else fail "$3: expected $1, got $2"; fi
}

bracketed() { if [[ "$1" == *:* ]]; then printf '[%s]' "$1"; else printf '%s' "$1"; fi; } # an IPv6 address in a URL
BASE=(curl -s --max-time 10)
[ -n "${CHECK_CA:-}" ] && BASE+=(--cacert "$CHECK_CA")
for host in "$SITE" "$ISLAND"; do
  [ -n "$IP" ] && BASE+=(--resolve "$host:443:$(bracketed "$IP")" --resolve "$host:80:$(bracketed "$IP")")
done
CURL=("${BASE[@]}" -o /dev/null)
status() { "${CURL[@]}" -w '%{http_code}' "$@"; }
header() { "${CURL[@]}" -D - -o /dev/null "${@:2}" | tr -d '\r' | grep -i "^$1:" | head -1 | cut -d' ' -f2-; }
# An IPv4 address first: many machines resolve IPv6 but cannot reach it.
TARGET=${IP:-$(getent ahostsv4 "$SITE" | awk '{print $1; exit}')}
TARGET=${TARGET:-$(getent hosts "$SITE" | awk '{print $1; exit}')}
CAFILE=()
[ -n "${CHECK_CA:-}" ] && CAFILE=(-CAfile "$CHECK_CA")
tls() { # server name, then extra openssl options: the handshake's first lines
  openssl s_client -connect "$(bracketed "$TARGET"):443" ${1:+-servername "$1"} "${CAFILE[@]}" "${@:2}" </dev/null 2>&1
}
if [ -z "$TARGET" ] || ! timeout 5 bash -c "</dev/tcp/$TARGET/443" 2>/dev/null; then
  fail "cannot reach ${TARGET:-$SITE} on port 443 at all: nothing else can be checked"
  exit "$FAILS"
fi

CLOUDFLARE=
[ "$(header server "https://$SITE/")" = cloudflare ] && CLOUDFLARE=1
EDGE="Cloudflare: SSL/TLS → Edge Certificates"

echo "== HTTPS ($SITE, $ISLAND at $TARGET${CLOUDFLARE:+, Cloudflare in front})"
for host in "$SITE" "$ISLAND"; do
  got=$(status "http://$host/")
  if [ "$got" = 308 ]; then pass "http://$host/ sends you to HTTPS (308)"
  elif [ -n "$CLOUDFLARE" ] && [ "$got" = 301 ]; then
    fail "http://$host/: Cloudflare redirects (301), not Caddy: turn off its Always Use HTTPS ($EDGE): Caddy renews its certificates over plain HTTP"
  else fail "http://$host/ sends you to HTTPS: expected 308, got $got"; fi
  out=$(tls "$host" -tls1_3)
  if grep -q "Verify return code: 0 (ok)" <<<"$out"; then pass "$host: TLS 1.3, a certificate the client trusts"
  else fail "$host: no trusted TLS 1.3 handshake: $(grep -m1 -E 'Verify return code|error|alert' <<<"$out")"; fi
  note "$(grep -m1 -E '^New, ' <<<"$out")"
  # Its names, one a line: the name itself, or a wildcard one level up (Cloudflare's *.<domain>) covers it.
  names=$(tls "$host" | openssl x509 -noout -ext subjectAltName 2>/dev/null | tr ',' '\n' | sed 's/^ *//')
  parent=${host#*.}
  if grep -qxF "DNS:$host" <<<"$names"; then pass "$host: the certificate names it"
  elif [[ "$parent" == *.* ]] && grep -qxF "DNS:*.$parent" <<<"$names"; then pass "$host: the certificate names it (*.$parent)"
  else fail "$host: the certificate does not name it"; fi
  days=${CHECK_CERT_DAYS:-14}
  if tls "$host" | openssl x509 -noout -checkend $((days * 86400)) >/dev/null 2>&1; then pass "$host: the certificate is good for $days days or more"
  else fail "$host: the certificate ends within $days days"; fi
  old=$(tls "$host" -tls1_1 -cipher 'DEFAULT:@SECLEVEL=0')
  if grep -q "no protocols available" <<<"$old"; then note "$host: this openssl cannot offer TLS 1.1 at all: not checked"
  elif grep -q "Cipher is (NONE)\|alert\|wrong version" <<<"$old"; then pass "$host: TLS 1.1 refused"
  elif [ -n "$CLOUDFLARE" ]; then fail "$host: TLS 1.1 accepted, by Cloudflare: set its Minimum TLS Version to 1.2 ($EDGE)"
  else fail "$host: TLS 1.1 accepted"; fi
done
for name in unknown.invalid ""; do
  out=$(tls "$name")
  if grep -q "BEGIN CERTIFICATE" <<<"$out"; then fail "a certificate for ${name:-no server name} (it should get none)"
  elif grep -qi "alert\|handshake failure" <<<"$out"; then pass "nothing for ${name:-no server name}: only the two names are served"
  else fail "no answer at all for ${name:-no server name}: $(grep -m1 -i error <<<"$out")"; fi
done

echo "== The site"
expect 200 "$(status "https://$SITE/")" "the front page"
expect 200 "$(status "https://$SITE/watch")" "the screen"
hsts=$(header strict-transport-security "https://$SITE/")
if [[ "$hsts" =~ max-age=([0-9]+) ]] && [ "${BASH_REMATCH[1]}" -ge 31536000 ]; then pass "HSTS for a year or more ($hsts)"
else fail "HSTS missing or short: '$hsts'"; fi
expect DENY "$(header x-frame-options "https://$SITE/accounts/login/")" "the site's pages are not framed by others"
expect nosniff "$(header x-content-type-options "https://$SITE/")" "no content sniffing"
expect 404 "$(status "https://$SITE/island/spectate/ws")" "the site does not answer for the island"

echo "== The island"
page=$(status "https://$ISLAND/island")
expect 200 "$page" "the page, with no token in the link"
csp=$(header content-security-policy "https://$ISLAND/island")
expect "frame-ancestors https://$SITE" "$csp" "only the site may frame it"
if [ "$page" = 200 ]; then expect "" "$(header x-frame-options "https://$ISLAND/island")" "no X-Frame-Options to stop the site's frame"
else fail "X-Frame-Options not checked: the page did not answer"; fi
for path in /island/renderer/manifest /island/spectate/chat/messages /island/replay/info; do
  expect 200 "$(status "https://$ISLAND$path")" "open: $path"
done
for path in /island/join /island/input /island/reset /island/chat /island/audio; do
  expect 404 "$(status -X POST "https://$ISLAND$path")" "closed: POST $path"
done
for path in /island/observe /island/observe/image /island/snapshot /island/spectate /island/chat/messages \
            /island/api.md /island/skill.md /island/relay/status /island/metrics /metrics /anything; do
  expect 404 "$(status "https://$ISLAND$path")" "closed: $path"
done

echo "== The stream"
ws() { # Origin, then extra curl options: the handshake's status
  status --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" ${1:+-H "Origin: $1"} "${@:2}" "https://$ISLAND/island/spectate/ws"
}
expect 101 "$(ws "https://$ISLAND" --max-time 3)" "the island's page opens the stream"
expect 403 "$(ws "https://elsewhere.example")" "another site's page may not"
expect 403 "$(ws "")" "nor a script that sends no Origin"
# Each socket claims another address (X-Forwarded-For, and CF-Connecting-IP unless Cloudflare is in front: it refuses
# a request that brings its own); the relay must count them all as ours, so one more than its per-address limit is
# refused, for holding too many or for opening them too fast (either way, ours). Which ones the pace refuses depends on
# timing, so every socket's answer counts: believed claims would open all of them.
most=${CHECK_PER_ADDRESS:-64}
claimed() { printf '198.51.%d.%d' $(($1 / 250)) $(($1 % 250 + 1)); }
claim() { printf -- '-H\nX-Forwarded-For: %s\n' "$1"; [ -n "$CLOUDFLARE" ] || printf -- '-H\nCF-Connecting-IP: %s\n' "$1"; }
codes=$(mktemp -d)
for ((i = 1; i <= most; i++)); do
  mapfile -t claims < <(claim "$(claimed "$i")")
  "${CURL[@]}" -w '%{http_code}' --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Origin: https://$ISLAND" "${claims[@]}" \
    --max-time $((8 + most / 20)) "https://$ISLAND/island/spectate/ws" > "$codes/$i" &
done
sleep $((2 + most / 20))
mapfile -t claims < <(claim 203.0.113.99)
extra=$("${BASE[@]}" -w ' %{http_code}' --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Origin: https://$ISLAND" \
  "${claims[@]}" --max-time 3 "https://$ISLAND/island/spectate/ws" | tr -d '\0')
wait # the held sockets end at their --max-time, and only then write their status
opened=$(cat "$codes"/* | grep -o 101 | wc -l)
refused=$(cat "$codes"/* | grep -o 429 | wc -l)
rm -rf "$codes"
[ "${extra: -3}" = 429 ] && refused=$((refused + 1))
if [ "$refused" -gt 0 ]; then
  why=$(grep -o -E "Too many sockets from here|Connecting too often" <<<"$extra")
  pass "claimed addresses are not believed: of $((most + 1)) sockets from here, $refused refused${why:+ ($why)}, $opened held"
else fail "all $((most + 1)) sockets from here opened, each claiming another address (is CHECK_PER_ADDRESS the relay's limit?)"; fi

closed() { # an address, then the ports that must not answer from here
  local address=$1 port
  for port in "${@:2}"; do
    if timeout 3 bash -c "</dev/tcp/$address/$port" 2>/dev/null; then
      case "$address:$port" in
        127.*:9090|127.*:9093) note "$port open on loopback: the monitoring's pages, for an SSH tunnel" ;;
        *) fail "$port open" ;;
      esac
    else pass "$port closed"; fi
  done
}
INSIDE=(2019 2020 5432 6379 8000 8080 8081 8082 9090 9093 9100)
if [ -z "$CLOUDFLARE" ]; then
  echo "== Ports on $TARGET (from outside, only 80 and 443)"
  for port in 80 443; do
    if timeout 3 bash -c "</dev/tcp/$TARGET/$port" 2>/dev/null; then pass "$port open"; else fail "$port closed"; fi
  done
  closed "$TARGET" "${INSIDE[@]}"
elif [ -n "${CHECK_ORIGIN:-}" ]; then
  echo "== Ports on the server, $CHECK_ORIGIN (from here, none: only Cloudflare may reach 80 and 443)"
  closed "$CHECK_ORIGIN" 80 443 "${INSIDE[@]}"
else
  echo "== Ports"
  note "$TARGET is Cloudflare's, and so are the ports it answers on. CHECK_ORIGIN=<the server's address> checks the server's."
fi

echo
[ "$FAILS" -eq 0 ] && echo "All checks passed." || echo "$FAILS check(s) failed."
exit "$FAILS"
