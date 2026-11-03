//! The `godling-relay` program as a deployment starts it: its settings from the environment, what it says when one
//! is wrong, and a run that serves under its base path and stops when the launcher asks.
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command, Stdio};

const RELAY: &str = env!("CARGO_BIN_EXE_godling-relay");
const SETTINGS: [&str; 13] = [
    "RELAY_LISTEN", "RELAY_UPSTREAM", "RELAY_SPECTATOR_TOKEN", "WORLD_SPECTATOR_TOKEN", "RELAY_BASE_PATH",
    "RELAY_ORIGINS", "RELAY_MAX_VIEWERS", "RELAY_MAX_PER_IP", "RELAY_CONNECTS_PER_MINUTE", "RELAY_TRUSTED_PROXIES",
    "RELAY_BUFFER", "RELAY_RESUME_FRAMES", "RELAY_UPDATES_PER_SECOND",
];

/// The relay with only these settings, none of the test runner's own.
fn relay(settings: &[(&str, &str)]) -> Command {
    let mut command = Command::new(RELAY);
    for name in SETTINGS {
        command.env_remove(name);
    }
    command.envs(settings.iter().copied());
    command
}

/// A running relay, stopped if a test ends early.
struct Running(Child);

impl Drop for Running {
    fn drop(&mut self) {
        if matches!(self.0.try_wait(), Ok(None)) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
}

/// The first line of the relay's answer to `request`.
fn answer(port: u16, request: &str) -> String {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).unwrap();
    stream.write_all(request.as_bytes()).unwrap();
    let mut line = String::new();
    BufReader::new(stream).read_line(&mut line).unwrap();
    line
}

fn socket_from(origin: &str) -> String {
    format!("GET /island/spectate/ws HTTP/1.1\r\nHost: relay\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\
             Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nOrigin: {origin}\r\n\r\n")
}

#[test]
fn help_names_every_setting() {
    let out = relay(&[]).arg("--help").output().unwrap();
    assert!(out.status.success());
    let help = String::from_utf8(out.stdout).unwrap();
    for name in SETTINGS {
        assert!(help.contains(name), "{name} is in the help");
    }
}

#[test]
fn a_setting_that_is_not_a_number_stops_it() {
    let out = relay(&[("RELAY_MAX_VIEWERS", "lots")]).output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("RELAY_MAX_VIEWERS is not a number"));
    // Too many updates a second would make the flush's period zero (or wrap): refused at the start, not frozen later.
    let out = relay(&[("RELAY_UPDATES_PER_SECOND", "10000000000")]).output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("RELAY_UPDATES_PER_SECOND is at most 60"));
}

#[test]
fn an_address_it_cannot_listen_on_stops_it() {
    let out = relay(&[("RELAY_LISTEN", "999.1.1.1:80")]).output().unwrap();
    assert_eq!(out.status.code(), Some(1));
    let said = String::from_utf8_lossy(&out.stderr);
    assert!(said.contains("no spectator token set"), "{said}");
    assert!(said.contains("cannot listen on 999.1.1.1:80"), "{said}");
}

/// A free port, a moment ago.
fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0").unwrap().local_addr().unwrap().port()
}

/// The relay listening on `port` with these settings, once it has said so.
fn started(port: u16, settings: &[(&str, &str)]) -> (Running, String) {
    let listen = format!("127.0.0.1:{port}");
    let child = relay(&[&[("RELAY_LISTEN", listen.as_str())], settings].concat())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut running = Running(child);
    let mut said = String::new();
    BufReader::new(running.0.stdout.take().unwrap()).read_line(&mut said).unwrap(); // once it listens
    (running, said)
}

#[test]
fn it_serves_as_its_settings_say_and_stops_when_asked() {
    let port = free_port();
    let (mut running, said) = started(port, &[
        ("RELAY_UPSTREAM", "ws://127.0.0.1:9/spectate/ws"), // no world there: down
        ("WORLD_SPECTATOR_TOKEN", " the-worlds-token "),
        ("RELAY_BASE_PATH", "/island/"),
        ("RELAY_ORIGINS", " http://a.test, ,http://b.test "),
        ("RELAY_MAX_VIEWERS", "10"),
        ("RELAY_MAX_PER_IP", " 3 "),
        ("RELAY_CONNECTS_PER_MINUTE", "30"),
        ("RELAY_TRUSTED_PROXIES", "1"),
        ("RELAY_BUFFER", "32"),
        ("RELAY_RESUME_FRAMES", "40"),
    ]);
    assert!(said.contains(&format!("at most 10 viewers; they connect to ws://127.0.0.1:{port}/island/spectate/ws")),
            "{said}");
    let status = answer(port, "GET /island/relay/status HTTP/1.1\r\nHost: relay\r\nConnection: close\r\n\r\n");
    assert!(status.starts_with("HTTP/1.1 200"), "{status}");
    assert!(answer(port, &socket_from("http://elsewhere.test")).starts_with("HTTP/1.1 403"), "another site's page");
    assert!(answer(port, &socket_from("http://b.test")).starts_with("HTTP/1.1 101"), "a page origin it was given");
    stop(&mut running.0);
}

#[cfg(unix)]
#[test]
fn ctrl_c_stops_it_too() {
    let (mut running, _) = started(free_port(), &[("RELAY_UPSTREAM", "ws://127.0.0.1:9/spectate/ws")]);
    signal(&mut running.0, "-INT");
}

/// As the launcher stops it (SIGTERM): it finishes on its own.
#[cfg(unix)]
fn stop(child: &mut Child) {
    signal(child, "-TERM");
}

#[cfg(unix)]
fn signal(child: &mut Child, which: &str) {
    assert!(Command::new("kill").args([which, &child.id().to_string()]).status().unwrap().success());
    assert!(child.wait().unwrap().success(), "stopped cleanly");
}

/// Windows cannot send Ctrl+C to a process of another console: it is ended.
#[cfg(not(unix))]
fn stop(child: &mut Child) {
    child.kill().unwrap();
    child.wait().unwrap();
}
