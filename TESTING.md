# Tests

Four suites, each with its own runner and its coverage. CI runs all four (`.github/workflows/tests.yml`). Run them
from the repository's root unless a step says otherwise.

| Suite | Where | Runner |
|---|---|---|
| The mind and the tools | `mind/tests`, `tools/tests` | pytest (`pytest.ini`, `.coveragerc`) |
| The site | `web/apps/*/test*.py`, `web/godling_web/test_settings.py` | Django's `manage.py test` |
| The renderer and the viewer screen | `world/renderer/test` | vitest (`world/renderer/vitest.config.js`) |
| The world script | `world/tests/test_*.luau` | `world/tests/runner`, a small Rust program with Luau inside |

## The mind and the tools

```bash
python -m pip install pytest coverage zstandard
python -m coverage run -m pytest && python -m coverage report
```

- The body's skills run on a stand-in island (`mind/tests/island.py`): no physics, a body that walks straight to
  where it is sent, and actions whose outcome a test sets. Time is the island's own, so a long walk takes no time.
- The world's and the panel's HTTP sides are a fake server on a free port (`mind/tests/fakeworld.py`).
- `tools/tests/test_make_island.py` rebuilds the island from its seed and checks it is the committed
  `world/island.lua`.
- The run-analysis tests write recordings as `clawblox run --record` does; they need a zstd compressor (Python 3.14's
  own, or `pip install zstandard`).

## The site

```bash
cd web && python -m pip install -r requirements.txt coverage
python -m coverage run --source=. --omit='*/migrations/*,*/tests.py,*/test_*.py,manage.py' manage.py test
python -m coverage report --skip-empty
```

## The renderer and the viewer screen

```bash
cd world/renderer && npm ci && npm run coverage
```

There is no WebGL here: `test/gl.js` stands in for three.js's `WebGLRenderer` and for the 2D canvas. Everything else
(the scene, geometry, shader source, maths) is three.js's own. The viewer screen and the HUD prototypes are loaded
afresh for each test, with `fetch` answered and timers faked.

## The world script

```bash
cargo build --release --manifest-path world/tests/runner/Cargo.toml
world/tests/runner/target/release/luau-test world/tests/test_*.luau
```

- Add `--missed` to list the lines no test reached, and `--lcov out.info` to write the coverage as LCOV.
- Clawblox is not here: `world/tests/engine.luau` stands in for the parts of its API the script uses (parts, CFrames,
  overlap queries, players and humanoids, signals). There is no physics: a test moves time on with `step(dt)` and puts
  pieces where they would lie.
- `boot()` (`world/tests/lib.luau`) loads `world/main.lua` into a fresh engine, compiled with Luau's line coverage on.
  It adds `return { ... }` after the last line, so tests can reach the script's top-level locals; no line number
  changes. `patch` swaps a constant on its own line (`SKY_TEST_EVERY`, `SUPPLY_FROM_SKY`, an island save) for one boot.
- Randomness is the test's: `table.insert(e.randoms, 0.9)` sets the next `math.random()`.
