#!/usr/bin/env bash
# Checks a running deployment from outside, as anyone on the internet sees it (ADR-016): HTTPS and its certificates,
# which paths answer and which must not, the stream's door, and which ports are open. Run it from another machine.
#
#   deploy/check.sh <site domain> <island domain>
#   CHECK_IP=203.0.113.7 deploy/check.sh …     reach that address for both names (before DNS, or one server of several)
#   CHECK_CA=root.crt deploy/check.sh …        trust this CA too (a local run's Caddy CA: its *.localhost certificates)
#   CHECK_CERT_DAYS=0 deploy/check.sh …        days a certificate must still be good for (default 14; a local Caddy CA
#                                              signs for 12 hours at a time, Let's Encrypt for 90 days)
#
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
TARGET=${IP:-$(getent hosts "$SITE" | awk '{print $1; exit}')}
CAFILE=()
[ -n "${CHECK_CA:-}" ] && CAFILE=(-CAfile "$CHECK_CA")
tls() { # server name, then extra openssl options: the handshake's first lines
  openssl s_client -connect "$(bracketed "$TARGET"):443" ${1:+-servername "$1"} "${CAFILE[@]}" "${@:2}" </dev/null 2>&1
}
if [ -z "$TARGET" ] || ! timeout 5 bash -c "</dev/tcp/$TARGET/443" 2>/dev/null; then
  fail "cannot reach ${TARGET:-$SITE} on port 443 at all: nothing else can be checked"
  exit "$FAILS"
fi

echo "== HTTPS ($SITE, $ISLAND at $TARGET)"
for host in "$SITE" "$ISLAND"; do
  expect 308 "$(status "http://$host/")" "http://$host/ sends you to HTTPS"
  out=$(tls "$host" -tls1_3)
  if grep -q "Verify return code: 0 (ok)" <<<"$out"; then pass "$host: TLS 1.3, a certificate the client trusts"
  else fail "$host: no trusted TLS 1.3 handshake: $(grep -m1 -E 'Verify return code|error|alert' <<<"$out")"; fi
  note "$(grep -m1 -E '^New, ' <<<"$out")"
  cert=$(tls "$host" | openssl x509 -noout -ext subjectAltName -enddate 2>/dev/null)
  if grep -q "DNS:$host" <<<"$cert"; then pass "$host: the certificate names $host"; else fail "$host: the certificate does not name it"; fi
  days=${CHECK_CERT_DAYS:-14}
  if tls "$host" | openssl x509 -noout -checkend $((days * 86400)) >/dev/null 2>&1; then pass "$host: the certificate is good for $days days or more"
  else fail "$host: the certificate ends within $days days"; fi
  old=$(tls "$host" -tls1_1 -cipher 'DEFAULT:@SECLEVEL=0')
  if grep -q "no protocols available" <<<"$old"; then note "$host: this openssl cannot offer TLS 1.1 at all: not checked"
  elif grep -q "Cipher is (NONE)\|alert\|wrong version" <<<"$old"; then pass "$host: TLS 1.1 refused"
  else fail "$host: TLS 1.1 accepted"; fi
done
for name in unknown.invalid ""; do
  out=$(tls "$name")
  if grep -q "BEGIN CERTIFICATE" <<<"$out"; then fail "a certificate for ${name:-no server name} (it should get none)"
  elif grep -qi "alert\|handshake failure" <<<"$out"; then pass "nothing for ${name:-no server name}: only the two names are served"
  else fail "no answer at all for ${name:-no server name}: $(grep -m1 -i error <<<"$out")"; fi
done

echo "== The site"
expect 200 "$(status "https://$SITE/")" "the screen"
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
# Each socket claims another address (X-Forwarded-For, CF-Connecting-IP); the relay must count them all as ours.
held=()
for i in 1 2 3 4 5 6 7 8; do
  "${CURL[@]}" --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Origin: https://$ISLAND" -H "X-Forwarded-For: 198.51.100.$i" \
    -H "CF-Connecting-IP: 198.51.100.$i" --max-time 8 "https://$ISLAND/island/spectate/ws" &
  held+=($!)
done
sleep 2
ninth=$("${BASE[@]}" -w ' %{http_code}' --http1.1 -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Origin: https://$ISLAND" \
  -H "X-Forwarded-For: 198.51.100.99" -H "CF-Connecting-IP: 198.51.100.99" --max-time 3 "https://$ISLAND/island/spectate/ws")
kill "${held[@]}" 2>/dev/null; wait "${held[@]}" 2>/dev/null
if [[ "$ninth" == *"Too many sockets from here."*429 ]]; then pass "claimed addresses are not believed: a 9th socket from here is refused"
elif [[ "$ninth" == *429 ]]; then pass "a 9th socket from here is refused (paced: run the check less often)"
else fail "a 9th socket with yet another claimed address got through: ${ninth: -3}"; fi

echo "== Ports on $TARGET (from outside, only 80 and 443)"
for port in 80 443; do
  if timeout 3 bash -c "</dev/tcp/$TARGET/$port" 2>/dev/null; then pass "$port open"; else fail "$port closed"; fi
done
for port in 2019 2020 5432 6379 8000 8080 8081 8082 9090 9093 9100; do
  if timeout 3 bash -c "</dev/tcp/$TARGET/$port" 2>/dev/null; then
    case "$TARGET:$port" in
      127.*:9090|127.*:9093) note "$port open on loopback: the monitoring's pages, for an SSH tunnel" ;;
      *) fail "$port open" ;;
    esac
  else pass "$port closed"; fi
done

echo
[ "$FAILS" -eq 0 ] && echo "All checks passed." || echo "$FAILS check(s) failed."
exit "$FAILS"
