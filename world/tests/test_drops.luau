-- Viewers' logs from the sky (ADR-029): an aim past Godling's reach comes in to the edge of it instead of being
-- refused, and a log keeps clear of what is built, as an unaimed one does, and off the house the mind is building.
-- From the live run of 2026-11-08/09: 19 of 32 log drops were refused as too far, and logs 94, 97, 99, 105 and 106
-- landed in and around the house, one of them (Log_94) on its north wall at Godling's feet.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3
local CELL = 2.5

-- An island with Godling on open grass, room round it for a house, and the guest panel joined.
local function sky()
    local w = T.boot()
    w.spot = w.openSpot(14)
    w.g = w.godling(w.spot)
    w.panel = w.skyPlayer()
    function w.power(name, data)
        local input = { power = name }
        for k, v in pairs(data or {}) do
            input[k] = v
        end
        return w.act(w.panel, "Sky", input)
    end
    return w
end

local function at(x, z)
    return { at = { x = x, z = z } }
end

local function piece(e, name, pos)
    return e.part(name, { Size = V.new(2.5, 2.5, 2.5), Position = pos, Anchored = true,
        attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
end

local function flat(a, b)
    local dx, dz = a.X - b.X, a.Z - b.Z
    return math.sqrt(dx * dx + dz * dz)
end

-- The log as it lies, seen from above, against a cell's square: whether they overlap (touching is not overlapping).
local function overlaps(log, ix, iz)
    local cf, h = log.CFrame, log.Size * 0.5
    local gx, gz = { cf.RightVector.X, cf.RightVector.Z }, { cf.LookVector.X, cf.LookVector.Z }
    local dx, dz = ix * CELL - log.Position.X, iz * CELL - log.Position.Z
    for _, d in ipairs({ { 1, 0 }, { 0, 1 }, gx, gz }) do
        local reach = math.abs(gx[1] * d[1] + gx[2] * d[2]) * h.X + math.abs(gz[1] * d[1] + gz[2] * d[2]) * h.Z
            + (math.abs(d[1]) + math.abs(d[2])) * CELL / 2
        if math.abs(dx * d[1] + dz * d[2]) >= reach - 1e-6 then
            return false
        end
    end
    return true
end

-- A house as the mind plans it (mind/godling/house.py), two by two, east of Godling: its room, the walls all round
-- (corners too), the doorway on the south side, the cell outside it and the cells round that (its apron: its two
-- flanks and the cell beyond, so that no log closes the way out). `keep` is every cell it needs clear, as the mind
-- declares them (HouseSite, mind/godling/site.py).
local function house(w)
    local ix0, iz0 = math.floor(w.spot.X / CELL + 0.5) + 3, math.floor(w.spot.Z / CELL + 0.5)
    local h = { room = {}, ring = {}, door = { ix0 + 1, iz0 - 1 }, out = { ix0 + 1, iz0 - 2 }, keep = {},
        apron = { { ix0, iz0 - 2 }, { ix0 + 2, iz0 - 2 }, { ix0 + 1, iz0 - 3 } } }
    for ix = ix0 - 1, ix0 + 2 do
        for iz = iz0 - 1, iz0 + 2 do
            local inside = ix >= ix0 and ix <= ix0 + 1 and iz >= iz0 and iz <= iz0 + 1
            table.insert(inside and h.room or h.ring, { ix, iz })
            table.insert(h.keep, { ix, iz })
        end
    end
    table.insert(h.keep, h.out)
    for _, c in ipairs(h.apron) do
        table.insert(h.keep, c)
    end
    h.middle = V.new((ix0 + 0.5) * CELL, 2.55, (iz0 + 0.5) * CELL)
    return h
end

local function onHouse(log, h)
    for _, c in ipairs(h.keep) do
        if overlaps(log, c[1], c[2]) then
            return c
        end
    end
    return nil
end

local function clearOf(log, pieces, clearance)
    for _, p in ipairs(pieces) do
        if flat(log.Position, p.Position) < clearance - 1e-6 then
            return p
        end
    end
    return nil
end

T.test("a log aimed past Godling's reach comes in to its edge; a stone is refused as before", function()
    local w = sky()
    local x, g = w.x, w.spot
    local reach = x.sky.aim.REACH
    local ux, uz -- a way from Godling with open land at the edge of its reach
    for k = 0, 31 do
        local a = k / 32 * 2 * math.pi
        if x.clearSupplySpot(g.X + math.cos(a) * reach, g.Z + math.sin(a) * reach) then
            ux, uz = math.cos(a), math.sin(a)
            break
        end
    end
    T.ok(ux, "open land at the edge of the reach somewhere")
    T.eq(w.power("Log", at(g.X + ux * 90, g.Z + uz * 90)), "SkyDone:Log:1", "brought in, not refused")
    local log = w.e.find("Log_1")
    local edge = V.new(g.X + ux * reach, 0, g.Z + uz * reach)
    T.ok(flat(log.Position, edge) <= x.sky.aim.SNAP, "near the edge of the reach, where the aim crossed it")
    T.ok(((log.Position.X - g.X) * ux + (log.Position.Z - g.Z) * uz) > reach - x.sky.aim.SNAP, "towards the aim")
    T.logged(w, "past its reach")
    T.eq(w.power("Stone", at(g.X + ux * 90, g.Z + uz * 90)), "SkyFailed:TooFar", "the other powers are as they were")
    T.eq(w.power("Log", at(g.X + ux * 30, g.Z + uz * 30)), "SkyDone:Log:2", "an aim within reach")
    local aimed = V.new(g.X + ux * 30, 0, g.Z + uz * 30)
    T.near(flat(w.e.find("Log_2").Position, aimed), 0, 1e-6, "lands where it was aimed")
end)

T.test("an aimed log keeps clear of what is built, as an unaimed one does", function()
    local w = sky()
    local e, x, p = w.e, w.x, w.spot
    local clearance = x.SKY_SPOT_CLEARANCE
    local block = piece(e, "Block_90", V.new(p.X + 12, 1.25, p.Z))
    -- Aimed 3.2 beside the block: the log fits there by the old gap (0.5 between outlines), but its middle is closer
    -- to the block's than an unaimed log ever lands.
    T.eq(w.power("Log", at(p.X + 12, p.Z + 3.2)), "SkyDone:Log:1")
    local log = e.find("Log_1")
    T.no(clearOf(log, { block }, clearance), "as far from the block as an unaimed log keeps")
    T.ok(flat(log.Position, V.new(p.X + 12, 0, p.Z + 3.2)) <= x.sky.aim.SNAP, "still near the aim")
    -- What Godling carries is not built: a log aimed at Godling still lands at its feet while its hands are full.
    local held = piece(e, "Stone_80", V.new(p.X, p.Y + 3.4, p.Z))
    held.Anchored = false
    x.heldBlocksByPlayer[w.g] = held
    T.eq(w.power("Log", at(p.X - 1, p.Z)), "SkyDone:Log:2", "aimed at Godling, its hands full")
    T.near(flat(e.find("Log_2").Position, p), x.sky.aim.FEET, 1e-6, "at its feet")
end)

T.test("an aimed log lands beside Godling's house, never on its room, walls, doorway or the way out", function()
    local w = sky()
    local e, x, p = w.e, w.x, w.spot
    local h = house(w)
    w.act(w.g, "HouseSite", { cells = h.keep })
    local walls = {}
    for i, c in ipairs(h.ring) do -- the walls half built: a block on every other wall cell
        if i % 2 == 1 and not (c[1] == h.door[1] and c[2] == h.door[2]) then
            table.insert(walls, piece(e, "Block_" .. (100 + i), V.new(c[1] * CELL, 1.25, c[2] * CELL)))
        end
    end
    local n = 0
    local function drop(aim, what)
        n = n + 1
        T.eq(w.power("Log", aim), "SkyDone:Log:" .. n, what)
        local log = e.find("Log_" .. n)
        local on = onHouse(log, h)
        T.no(on, what .. ": on the house's cell " .. (on and (on[1] .. "," .. on[2]) or ""))
        T.no(clearOf(log, walls, x.SKY_SPOT_CLEARANCE), what .. ": as far from its walls as an unaimed log keeps")
        return log
    end
    local log = drop(at(h.middle.X, h.middle.Z), "aimed at the room")
    T.ok(flat(log.Position, h.middle) <= x.sky.aim.SNAP_FAR, "beside the house, near the aim")
    drop(at(h.door[1] * CELL, h.door[2] * CELL), "aimed at the doorway")
    drop(at(h.out[1] * CELL, h.out[2] * CELL + 0.5), "aimed at the way out")
    for _, c in ipairs(h.apron) do -- nor across the way out, where one log and another beside it would close it
        drop(at(c[1] * CELL, c[2] * CELL), "aimed beside the way out")
    end
    -- Log_94: Godling in its room by the north wall, the log aimed at it.
    local by = V.new(h.room[2][1] * CELL, 2.55, h.room[2][2] * CELL)
    e.hrp(w.g).Position = by
    drop(at(by.X + 0.5, by.Z), "aimed at Godling in its room")
    -- Unaimed, the sky keeps off the house as well.
    e.hrp(w.g).Position = h.middle
    for _ = 1, 4 do
        drop(nil, "unaimed")
    end
end)

T.test("a log aimed into a crowd still lands, further out, rather than being refused", function()
    local w = sky()
    local e, x, p = w.e, w.x, w.spot
    local aim = V.new(p.X + 10, 0, p.Z)
    local crowd = {}
    -- Pieces 5 apart round the aim, out to 13 from it: no room for a log anywhere among them, and none within the
    -- old look (12) round the aim; there is beyond them.
    for dx = -12.5, 12.5, 5 do
        for dz = -12.5, 12.5, 5 do
            if dx * dx + dz * dz <= 13 * 13 and math.abs(aim.X + dx - p.X) + math.abs(dz) > 3 then
                table.insert(crowd, piece(e, "Crowd_" .. dx .. "_" .. dz, V.new(aim.X + dx, 1.25, aim.Z + dz)))
            end
        end
    end
    T.eq(w.power("Log", at(aim.X, aim.Z)), "SkyDone:Log:1")
    local log = e.find("Log_1")
    T.no(clearOf(log, crowd, x.SKY_SPOT_CLEARANCE), "clear of the crowd")
    T.ok(flat(log.Position, aim) <= x.sky.aim.SNAP_FAR, "within the wider look round the aim")
end)

T.test("the house site the mind declares: kept until changed, cleared by an empty one, nonsense ignored", function()
    local w = sky()
    local x = w.x
    local h = house(w)
    w.g:SetAttribute("LastActionResult", "PlaceSuccess")
    w.act(w.g, "HouseSite", { cells = h.keep })
    T.eq(#(x.sky.aim.sites[w.g] or {}), #h.keep, "every cell kept")
    T.eq(w.g:GetAttribute("LastActionResult"), "PlaceSuccess", "the body's own last result is left alone")
    T.logged(w, "HOUSE SITE Godling keeps 20 cells clear")
    local nonsense = { { cells = "west" }, { cells = { { 1.5, 2 } } }, { cells = { { "a", 2 } } }, {},
        { cells = { a = { 1, 2 } } }, -- a JSON object, not a list
        { cells = { { 1, 2 }, nil, { 3, 4 } } } } -- [[1, 2], null, [3, 4]]: a list with a hole
    for _, nonsense in ipairs(nonsense) do
        w.act(w.g, "HouseSite", nonsense)
        T.eq(#(x.sky.aim.sites[w.g] or {}), #h.keep, "nonsense leaves the site as it was")
    end
    local many = {}
    for i = 1, x.sky.aim.SITE_MOST + 1 do
        table.insert(many, { i, 0 })
    end
    w.act(w.g, "HouseSite", { cells = many })
    T.eq(#(x.sky.aim.sites[w.g] or {}), #h.keep, "more cells than any house needs")
    -- The mind's word, not the body's: it is taken while Godling lies dead too.
    x.death.die(w.g, { hunger = 0, health = 0, beat = 0 }, "Hunger")
    T.ok(x.death.is(w.g), "dead")
    w.act(w.g, "HouseSite", { cells = {} })
    T.eq(x.sky.aim.sites[w.g], nil, "an empty site: nothing kept")
    w.act(w.g, "HouseSite", { cells = h.keep })
    T.eq(#(x.sky.aim.sites[w.g] or {}), #h.keep, "declared while dead")
    w.act(w.panel, "HouseSite", { cells = h.keep })
    T.eq(x.sky.aim.sites[w.panel], nil, "the guest panel has no house")
end)

-- 79-CLEAN8: the site is kept by the body's player; one that left is let go (its mind declares it again on joining).
T.test("a body that left keeps no house site", function()
    local w = sky()
    w.act(w.g, "HouseSite", { cells = house(w).keep })
    T.ok(w.x.sky.aim.sites[w.g], "kept")
    w.e.leave(w.g)
    T.eq(w.x.sky.aim.sites[w.g], nil, "let go")
end)

-- Review of #79 (79-AB1): a log aimed at Godling lands at its feet, or, where its feet are on the house or among
-- pieces, at the nearest spot to Godling that keeps clear: never further off for being aimed at it.
T.test("a log aimed at Godling in its room lands as near its feet as the house allows", function()
    local w = sky()
    local e, x = w.e, w.x
    local h = house(w)
    w.act(w.g, "HouseSite", { cells = h.keep })
    -- The panel's bodiless player is parked under the island, here under Godling's first spot, and clearSupplySpot
    -- keeps 3 from every body's middle: out of the way, so that only the house decides.
    e.hrp(w.panel).Position = V.new(w.spot.X - 200, -40, w.spot.Z - 200)
    for i, c in ipairs(h.room) do
        local by = V.new(c[1] * CELL, 2.55, c[2] * CELL)
        e.hrp(w.g).Position = by
        T.eq(w.power("Log", at(by.X + 0.5, by.Z + 0.25)), "SkyDone:Log:" .. i)
        local log = e.find("Log_" .. i)
        T.no(onHouse(log, h), "off the house")
        -- From any cell of a two-by-two room the walls' outer face is at most 6.25 off on one side and 3.75 on
        -- another: a log lying along that face, its middle half a log's width out, is 5 off at best.
        T.ok(flat(log.Position, by) <= 5.01, "next to the house, by Godling: " .. flat(log.Position, by))
        log:Destroy()
    end
end)

-- 79-CDE1: settling squares a log where it lies (ADR-005), so a log at Godling's feet is dropped squared: the outline
-- the sky kept off the house is the one it keeps.
T.test("a log at Godling's feet is dropped along x or z, across the side it was aimed from", function()
    for k = 0, 7 do
        local w = sky()
        local p = w.spot
        local a = k / 8 * 2 * math.pi
        T.eq(w.power("Log", at(p.X + math.cos(a), p.Z + math.sin(a))), "SkyDone:Log:1")
        local log = w.e.find("Log_1")
        local rx = math.abs(log.CFrame.RightVector.X)
        T.ok(rx < 1e-6 or math.abs(rx - 1) < 1e-6, "squared, at " .. k * 45 .. " degrees: " .. rx)
        T.near(flat(log.Position, p), w.x.sky.aim.FEET, 1e-6, "at its feet")
    end
end)

-- 79-AB5: the screen says a log aimed past the ring lands on the ring; a crowd there moves it inwards, not out past it.
-- Every log lands within the reach and the look round it (72), as every gift did before.
T.test("a log brought in to a crowded edge lands on or inside the ring", function()
    local w = sky()
    local e, x, g = w.e, w.x, w.spot
    local reach = x.sky.aim.REACH
    local ux, uz
    for k = 0, 63 do
        local a = k / 64 * 2 * math.pi
        local ok = true
        for r = reach - 20, reach, 2.5 do -- open land inside the ring, where it may land
            ok = ok and x.clearSupplySpot(g.X + math.cos(a) * r, g.Z + math.sin(a) * r)
        end
        if ok then
            ux, uz = math.cos(a), math.sin(a)
            break
        end
    end
    T.ok(ux, "open land inside the edge of the reach somewhere")
    local edge = V.new(g.X + ux * reach, 0, g.Z + uz * reach)
    for dx = -12.5, 12.5, 5 do
        for dz = -12.5, 12.5, 5 do
            if dx * dx + dz * dz <= 13 * 13 then
                piece(e, "Crowd_" .. dx .. "_" .. dz, V.new(edge.X + dx, 1.25, edge.Z + dz))
            end
        end
    end
    T.eq(w.power("Log", at(g.X + ux * 90, g.Z + uz * 90)), "SkyDone:Log:1")
    local d = flat(e.find("Log_1").Position, g)
    T.ok(d <= reach + 1.25 + 1e-6, "on or inside the ring: " .. d)
    T.eq(w.power("Log", at(edge.X - ux * 0.5, edge.Z - uz * 0.5)), "SkyDone:Log:2", "aimed just inside the ring")
    d = flat(e.find("Log_2").Position, g)
    T.ok(d <= reach + x.sky.aim.SNAP + 1e-6, "within the reach and the look round it: " .. d)
end)

-- 79-AB6: a log with nowhere to land within SNAP_FAR is refused (and the site refunds it), however wide the search.
T.test("a log with no room anywhere near its aim is refused", function()
    local w = sky()
    local e, p = w.e, w.spot
    local aim = V.new(p.X + 10, 0, p.Z)
    for dx = -27.5, 27.5, 3.75 do
        for dz = -27.5, 27.5, 3.75 do
            if math.abs(aim.X + dx - p.X) + math.abs(dz) > 3 then
                piece(e, "Crowd_" .. dx .. "_" .. dz, V.new(aim.X + dx, 1.25, aim.Z + dz))
            end
        end
    end
    T.eq(w.power("Log", at(aim.X, aim.Z)), "SkyFailed:NoClearSpot")
    T.eq(w.power("Log"), "SkyFailed:NoClearSpot", "unaimed too")
end)

-- 79-SWEEP2: a log is 7.5 long; its ends keep off a palm's trunk and a mesa's foot, not only its middle.
T.test("a log lying beside a palm keeps its ends off the trunk", function()
    local w = T.boot()
    local x = w.x
    w.panel = w.skyPlayer()
    local placed = 0
    for _, t in ipairs(x.trees) do
        local tx, tz = t.pos[1], t.pos[3]
        -- north of the trunk, a block east: a log along x does not fit there, and along z it reaches the trunk
        local sx, sz = tx, tz + 3.8
        if placed == 0 and x.clearSupplySpot(sx, sz) and x.clearSupplySpot(sx + 20, sz)
            and x.clearSupplySpot(sx + 5.2, sz) then
            w.g = w.godling(V.new(sx + 20, 2.55, sz))
            piece(w.e, "Block_1", V.new(sx + 5.2, 1.25, sz))
            T.eq(w.act(w.panel, "Sky", { power = "Log", at = { x = sx, z = sz } }), "SkyDone:Log:1")
            local log = w.e.find("Log_1")
            local cf, hl = log.CFrame, log.Size * 0.5
            local gx, gz = { cf.RightVector.X, cf.RightVector.Z }, { cf.LookVector.X, cf.LookVector.Z }
            local dx, dz = tx - log.Position.X, tz - log.Position.Z
            local apart = false
            for _, d in ipairs({ { 1, 0 }, { 0, 1 }, gx, gz }) do
                local reach = math.abs(gx[1] * d[1] + gx[2] * d[2]) * hl.X
                    + math.abs(gz[1] * d[1] + gz[2] * d[2]) * hl.Z + (math.abs(d[1]) + math.abs(d[2])) * 1.25
                apart = apart or math.abs(dx * d[1] + dz * d[2]) >= reach + 0.5 - 1e-6
            end
            T.ok(apart, t.name .. ": the log's outline keeps 0.5 off the trunk")
            placed = 1
        end
    end
    T.eq(placed, 1, "a palm with room round it")
end)

-- 79-CLEAN6: keeping off the house is a rule for every gift; a stone keeps its reach and its gap as before.
T.test("a stone aimed at the house's room lands off the house too", function()
    local w = sky()
    local h = house(w)
    w.act(w.g, "HouseSite", { cells = h.keep })
    T.eq(w.power("Stone", at(h.middle.X, h.middle.Z)), "SkyDone:Stone:1")
    local stone = w.e.find("Stone_1")
    local on = onHouse(stone, h)
    T.no(on, "on the house's cell " .. (on and (on[1] .. "," .. on[2]) or ""))
    T.ok(flat(stone.Position, h.middle) <= w.x.sky.aim.SNAP, "within a stone's look round the aim, as before")
end)

-- 79-CLEAN10: the screen reads the reach from the world, so the ring cannot drift from it.
T.test("the Clock tells the screen how far a log may be aimed", function()
    local w = sky()
    T.eq(w.e.find("Clock"):GetAttribute("SkyReach"), w.x.sky.aim.REACH)
end)

return T.done("test_drops")
