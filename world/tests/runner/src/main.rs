//! Runs the world's Luau tests (world/tests/*.luau) in a plain Luau VM, with Luau's own line coverage (TESTING.md).
//!
//!     cargo run --release --manifest-path world/tests/runner/Cargo.toml -- [--lcov out.info] [--missed] tests...
//!
//! Each test file is a chunk that returns its number of failures. Tests load the world through
//! `load_covered(source, name, env)`, which compiles with coverage on; every chunk loaded that way counts towards
//! the report, by its name (several loads of one file add up). Clawblox is not here: world/tests/engine.luau stands
//! in for the parts of its API the world uses.
use mlua::{Compiler, Function, Lua, Table, Value};
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::process::ExitCode;
use std::rc::Rc;

type Loaded = Rc<RefCell<Vec<(String, Function)>>>;

fn main() -> ExitCode {
    let mut lcov = None;
    let mut missed = false;
    let mut files = Vec::new();
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--lcov" => lcov = args.next(),
            "--missed" => missed = true,
            _ => files.push(arg),
        }
    }
    let lua = Lua::new();
    let loaded: Loaded = Rc::new(RefCell::new(Vec::new()));
    if let Err(err) = install(&lua, &loaded) {
        eprintln!("runner: {err}");
        return ExitCode::FAILURE;
    }

    let mut failures = 0i64;
    for file in &files {
        let source = match std::fs::read_to_string(file) {
            Ok(source) => source,
            Err(err) => {
                eprintln!("{file}: {err}");
                failures += 1;
                continue;
            }
        };
        let result = lua.load(&source).set_name(format!("@{file}")).call::<Value>(());
        match result {
            Ok(Value::Integer(n)) => failures += n,
            Ok(Value::Number(n)) => failures += n as i64,
            Ok(_) => {}
            Err(err) => {
                eprintln!("{file}: {err}");
                failures += 1;
            }
        }
    }

    let lines = coverage(&loaded.borrow());
    report(&lines, missed);
    if let Some(path) = lcov {
        if let Err(err) = std::fs::write(&path, to_lcov(&lines)) {
            eprintln!("{path}: {err}");
            failures += 1;
        }
    }
    if failures > 0 {
        eprintln!("{failures} failed");
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn install(lua: &Lua, loaded: &Loaded) -> mlua::Result<()> {
    let globals = lua.globals();
    globals.set(
        "readfile",
        lua.create_function(|_, path: String| Ok(std::fs::read_to_string(&path).ok()))?,
    )?;
    let list = loaded.clone();
    globals.set(
        "load_covered",
        lua.create_function(move |lua, (source, name, env): (String, String, Option<Table>)| {
            let mut chunk = lua
                .load(&source)
                .set_name(format!("@{name}"))
                .set_compiler(Compiler::new().set_coverage_level(2));
            if let Some(env) = env {
                chunk = chunk.set_environment(env);
            }
            let function = chunk.into_function()?;
            list.borrow_mut().push((name, function.clone()));
            Ok(function)
        })?,
    )?;
    // Test helpers (the engine, the test library): compiled without coverage, so they stay out of the report.
    globals.set(
        "load_plain",
        lua.create_function(|lua, (source, name, env): (String, String, Option<Table>)| {
            let mut chunk = lua.load(&source).set_name(format!("@{name}"));
            if let Some(env) = env {
                chunk = chunk.set_environment(env);
            }
            chunk.into_function()
        })?,
    )?;
    // print through Rust's stdout, so test output and the report come out in order.
    globals.set(
        "print",
        lua.create_function(|lua, args: mlua::Variadic<Value>| {
            let tostring: Function = lua.globals().get("tostring")?;
            let parts = args
                .into_iter()
                .map(|v| tostring.call::<String>(v))
                .collect::<mlua::Result<Vec<_>>>()?;
            println!("{}", parts.join("\t"));
            Ok(())
        })?,
    )?;
    // The wall clock, for timing tests (the world's os.clock is the engine's fake one).
    let start = std::time::Instant::now();
    globals.set(
        "wallclock",
        lua.create_function(move |_, ()| Ok(start.elapsed().as_secs_f64()))?,
    )?;
    Ok(())
}

// file -> line -> hits, over every load of that file and every function inside it.
fn coverage(loaded: &[(String, Function)]) -> BTreeMap<String, BTreeMap<usize, i64>> {
    let mut lines: BTreeMap<String, BTreeMap<usize, i64>> = BTreeMap::new();
    for (name, function) in loaded {
        let file = lines.entry(name.clone()).or_default();
        function.coverage(|info| {
            for (line, &hits) in info.hits.iter().enumerate() {
                if hits >= 0 {
                    *file.entry(line).or_insert(0) += hits as i64;
                }
            }
        });
    }
    lines
}

fn report(lines: &BTreeMap<String, BTreeMap<usize, i64>>, missed: bool) {
    let (mut all, mut all_hit) = (0usize, 0usize);
    for (file, hits) in lines {
        let total = hits.len();
        let hit = hits.values().filter(|&&h| h > 0).count();
        all += total;
        all_hit += hit;
        println!("{file}: {hit}/{total} lines ({:.2}%)", percent(hit, total));
        if missed {
            let gaps: Vec<usize> = hits.iter().filter(|(_, &h)| h == 0).map(|(&l, _)| l).collect();
            if !gaps.is_empty() {
                println!("  missed: {}", ranges(&gaps));
            }
        }
    }
    println!("TOTAL: {all_hit}/{all} lines ({:.2}%)", percent(all_hit, all));
}

fn percent(hit: usize, total: usize) -> f64 {
    if total == 0 {
        100.0
    } else {
        100.0 * hit as f64 / total as f64
    }
}

fn ranges(lines: &[usize]) -> String {
    let mut out = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let start = lines[i];
        let mut end = start;
        while i + 1 < lines.len() && lines[i + 1] == end + 1 {
            i += 1;
            end = lines[i];
        }
        out.push(if start == end { start.to_string() } else { format!("{start}-{end}") });
        i += 1;
    }
    out.join(",")
}

fn to_lcov(lines: &BTreeMap<String, BTreeMap<usize, i64>>) -> String {
    let mut out = String::new();
    for (file, hits) in lines {
        out.push_str(&format!("SF:{file}\n"));
        for (line, count) in hits {
            out.push_str(&format!("DA:{line},{count}\n"));
        }
        out.push_str(&format!("LF:{}\nLH:{}\nend_of_record\n", hits.len(), hits.values().filter(|&&h| h > 0).count()));
    }
    out
}
