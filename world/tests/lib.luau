-- The world's test library: checks, and boot(), which starts world/main.lua in a fresh stand-in engine (engine.luau).
-- Run from the repository's root (TESTING.md). main.lua is compiled with coverage on; the line
-- `return {...}` added after its last line hands its top-level locals to the tests, and changes no line number.

local Engine = load_plain(readfile("world/tests/engine.luau"), "world/tests/engine.luau")()
local SOURCE = assert(readfile("world/main.lua"), "run the tests from the repository's root")

local T = { failures = 0, passed = 0, Engine = Engine, Vector3 = Engine.Vector3, CFrame = Engine.CFrame }

-- The script's top-level locals, read off its source: `local a, b = ...`, `local function f`, `local x -- later`.
local exportNames = {}
do
    local seen = {}
    local function add(name)
        if not seen[name] and name ~= "_" then
            seen[name] = true
            table.insert(exportNames, name)
        end
    end
    for line in SOURCE:gmatch("[^\n]*") do
        local fn = line:match("^local function ([%a_][%w_]*)")
        if fn then
            add(fn)
        else
            local names = line:match("^local ([%a_][%w_,%s]*)=") or line:match("^local ([%a_][%w_]*)%s*%-%-")
                or line:match("^local ([%a_][%w_]*)%s*$")
            if names then
                for name in names:gmatch("[%a_][%w_]*") do
                    add(name)
                end
            end
        end
    end
end
local parts = {}
for _, name in ipairs(exportNames) do
    table.insert(parts, name .. " = " .. name)
end
local EXPORTS = "\nreturn { " .. table.concat(parts, ", ") .. " }\n"
T.exportNames = exportNames

-- A fresh island. options.patch: { {from, to}, ... } replaced once each in the source (on one line: the line numbers
-- stay); options.before(engine): what lies in the world before the script runs; options.engine: Engine.new's options.
function T.boot(options)
    options = options or {}
    local src = SOURCE
    for _, p in ipairs(options.patch or {}) do
        local i, j = src:find(p[1], 1, true)
        assert(i, "patch not found: " .. p[1])
        src = src:sub(1, i - 1) .. p[2] .. src:sub(j + 1)
    end
    local e = Engine.new(options.engine)
    if options.before then
        options.before(e)
    end
    local fn = load_covered(src .. EXPORTS, "world/main.lua", e.env)
    local x = fn()
    local w = { e = e, x = x, sky = x.sky }
    -- Godling, standing at `at` (feet on the grass there unless at.Y says otherwise).
    function w.godling(at, opts)
        local p = e.player("Godling", nil, opts)
        if at and e.hrp(p) then
            e.hrp(p).Position = at
        end
        return p
    end
    function w.skyPlayer()
        return e.player("Sky")
    end
    function w.act(player, kind, data)
        return e.input(player, kind, data)
    end
    -- Open, flat grass: ground at 0 and nothing standing within `clearance` (searched from the island's middle out).
    function w.openSpot(clearance, from)
        clearance = clearance or 6
        from = from or T.Vector3.new(0, 0, 0)
        for r = 0, 120, 2.5 do
            for k = 0, math.max(0, math.floor(r) - 1) do
                local a = r == 0 and 0 or k / math.floor(r) * 2 * math.pi
                local px, pz = from.X + r * math.cos(a), from.Z + r * math.sin(a)
                local ground = x.surfaceTopAt(px, pz, -1, 0.5)
                if ground and math.abs(ground) < 0.05 then
                    local clear = true
                    for dx = -clearance, clearance, 2.5 do
                        for dz = -clearance, clearance, 2.5 do
                            local top = x.surfaceTopAt(px + dx, pz + dz, -1, 200)
                            if top == nil or math.abs(top) > 0.05 then
                                clear = false
                                break
                            end
                        end
                        if not clear then
                            break
                        end
                    end
                    if clear then
                        return T.Vector3.new(px, 2.55, pz)
                    end
                end
            end
        end
        error("no open spot")
    end
    return w
end

-- ---- checks ------------------------------------------------------------------------------------------------------
local function show(v)
    if type(v) == "string" then
        return string.format("%q", v)
    end
    return tostring(v)
end

function T.eq(actual, expected, what)
    if actual ~= expected then
        error(string.format("%s: expected %s, got %s", what or "value", show(expected), show(actual)), 2)
    end
end

function T.ok(value, what)
    if not value then
        error((what or "expected a true value") .. " (got " .. show(value) .. ")", 2)
    end
end

function T.no(value, what)
    if value then
        error((what or "expected a false value") .. " (got " .. show(value) .. ")", 2)
    end
end

function T.near(actual, expected, eps, what)
    if type(actual) ~= "number" or math.abs(actual - expected) > (eps or 1e-6) then
        error(string.format("%s: expected %s (within %s), got %s", what or "value", show(expected), show(eps or 1e-6),
            show(actual)), 2)
    end
end

function T.starts(text, prefix, what)
    if type(text) ~= "string" or text:sub(1, #prefix) ~= prefix then
        error(string.format("%s: expected something starting with %s, got %s", what or "text", show(prefix), show(text)), 2)
    end
end

function T.logged(w, pattern, what)
    for _, line in ipairs(w.e.log) do
        if line:find(pattern) then
            return line
        end
    end
    error(string.format("%s: nothing logged like %s", what or "log", show(pattern)), 2)
end

function T.test(name, fn)
    local started = wallclock()
    local ok, err = xpcall(fn, debug.traceback)
    if ok then
        T.passed = T.passed + 1
        if wallclock() - started > 1 then
            print(string.format("  slow (%.1fs): %s", wallclock() - started, name))
        end
    else
        T.failures = T.failures + 1
        print("FAIL " .. name .. "\n  " .. tostring(err):gsub("\n", "\n  "))
    end
end

function T.done(file)
    print(string.format("%s: %d passed, %d failed", file, T.passed, T.failures))
    return T.failures
end

return T
