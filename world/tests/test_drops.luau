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
-- (corners too), the doorway on the south side and the cell outside it. `keep` is every cell it needs clear, as the
-- mind declares them (HouseSite).
local function house(w)
    local ix0, iz0 = math.floor(w.spot.X / CELL + 0.5) + 3, math.floor(w.spot.Z / CELL + 0.5)
    local h = { room = {}, ring = {}, door = { ix0 + 1, iz0 - 1 }, out = { ix0 + 1, iz0 - 2 }, keep = {} }
    for ix = ix0 - 1, ix0 + 2 do
        for iz = iz0 - 1, iz0 + 2 do
            local inside = ix >= ix0 and ix <= ix0 + 1 and iz >= iz0 and iz <= iz0 + 1
            table.insert(inside and h.room or h.ring, { ix, iz })
            table.insert(h.keep, { ix, iz })
        end
    end
    table.insert(h.keep, h.out)
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
    T.logged(w, "HOUSE SITE Godling keeps 17 cells clear")
    for _, nonsense in ipairs({ { cells = "west" }, { cells = { { 1.5, 2 } } }, { cells = { { "a", 2 } } }, {} }) do
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

return T.done("test_drops")
