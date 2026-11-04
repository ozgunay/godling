-- Living on the island: hunger, hurt and fainting, coconuts, the weather over many days (showers, wet spells,
-- storms, fog, wind, shelter and cold), driftwood, a passing ship, and the old supply drops.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

local function at(part)
    local p = part.Position
    return { p.X, p.Y, p.Z }
end

T.test("hunger empties, then health; well fed it mends; at none, Godling faints by the raft", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling(V.new(10, 2.55, 10))
    g:SetAttribute("Hunger", 1)
    g:SetAttribute("Health", 50)
    e.step(1)
    local s = x.surviving[g]
    T.near(s.hunger, 1 - 100 / 3600, 1e-9, "hunger empties in an hour")
    e.step(60, 1)
    T.eq(s.hunger, 0)
    T.ok(s.health < 50, "starving takes health")
    s.hunger, s.health = 80, 50
    e.step(10, 1)
    T.ok(s.health > 50, "well fed and warm, a body mends")
    e.step(1400, 10) -- into the night
    s.hunger, s.health = 100, 50
    e.step(1, 1)
    local before = s.health
    e.step(10, 1)
    T.eq(g:GetAttribute("Cold"), true, "nights are cold")
    T.ok(s.health < before, "cold wears it down")
    -- Godling holds a block when it faints: the block drops
    local block = e.find("Block_1")
    e.hrp(g).Position = block.Position + V.new(-2.5, 1.3, 0)
    w.act(g, "Pickup", { position = at(block) })
    s.hunger, s.health = 0, 0.01
    e.step(1)
    T.eq(g:GetAttribute("Faints"), 1)
    T.eq(g:GetAttribute("Gesture"), "WakeUp")
    T.eq(s.hunger, 50)
    T.eq(s.health, 30)
    T.eq(block.CanCollide, true, "dropped where it fainted")
    T.near(e.hrp(g).Position.X, x.PLAYER_SPAWN_POSITION.X, 1e-9, "wakes by the raft")
    T.eq(e.humanoid(g).Health, 30)
    -- a bodiless player and the guest panel are not fed; a body without a character faints all the same
    local sky = w.skyPlayer()
    local ghost = e.player("Ghost", nil, { noCharacter = true })
    e.step(1)
    T.eq(x.surviving[sky], nil)
    x.surviving[ghost].hunger, x.surviving[ghost].health = 0, 0.001
    e.step(1)
    T.eq(ghost:GetAttribute("Faints"), 1)
end)

T.test("hurt: from what struck close by; enough of it faints the body", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling(V.new(10, 2.55, 10))
    x.hurt(g, 10, "Lightning") -- not yet counted: nothing
    T.eq(g:GetAttribute("Hurts"), nil)
    e.step(0.1)
    x.hurtNear(10, 10, 5, 30, "Lightning")
    T.eq(g:GetAttribute("Hurt"), "Lightning")
    T.eq(g:GetAttribute("Health"), 70)
    T.logged(w, "HURT Godling by Lightning: health 70")
    x.hurtNear(100, 100, 5, 30, "Meteor") -- too far to be hurt
    T.eq(g:GetAttribute("Hurts"), 1)
    x.hurt(g, 200, "Meteor")
    T.eq(g:GetAttribute("Faints"), 1)
    w.skyPlayer()
    e.player("Spirit", nil, { noCharacter = true })
    x.hurtNear(10, 10, 500, 1, "Lightning") -- neither has a body to hurt
end)

T.test("shaking a palm: a ripe coconut drops between the palm and the shaker, once in five minutes", function()
    local w = T.boot()
    local e = w.e
    local palm = e.find("Palm_4")
    local g = w.godling(palm.Position + V.new(-3, -7.45, 0))
    T.eq(w.act(g, "Shake", nil), "ShakeFailed:NotAPalm")
    T.eq(w.act(g, "Shake", { name = "Block_1" }), "ShakeFailed:NotAPalm")
    e.part("Palm_99", { attrs = { RenderRole = "Stump" } })
    T.eq(w.act(g, "Shake", { name = "Palm_99" }), "ShakeFailed:NotAPalm", "a stump bears nothing")
    T.eq(w.act(g, "Shake", { name = "Palm_5" }), "ShakeFailed:OutOfRange")
    T.eq(w.act(g, "Shake", { name = "Palm_4" }), "ShakeCoconut:Coconut_1")
    T.eq(g:GetAttribute("Gesture"), "Shake")
    local nut = e.find("Coconut_1")
    T.ok(nut.Position.X < palm.Position.X, "on the shaker's side")
    T.eq(w.act(g, "Shake", { name = "Palm_4" }), "ShakeNothing")
    e.now = e.now + 301
    e.hrp(g).Position = V.new(palm.Position.X, 2.45, palm.Position.Z) -- right at the trunk: any side will do
    T.eq(w.act(g, "Shake", { name = "Palm_4" }), "ShakeCoconut:Coconut_2")
    local rootless = e.player("Ann", nil, { noRoot = true })
    T.eq(w.act(rootless, "Shake", { name = "Palm_4" }), "ShakeFailed:NotAPalm")
    T.eq(w.act(rootless, "Pickup", { position = at(nut) }), "PickupFailed:OutOfRange", "no body to reach with")
end)

T.test("shelter: a roof keeps the rain off; with walls round it, the cold too; a fire warms and dries", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local spot = w.openSpot(6)
    local g = w.godling(spot)
    e.step(0.5)
    T.eq(g:GetAttribute("Sheltered"), "")
    local roof = e.part("Roof", { Size = V.new(7.5, 1, 7.5), Position = spot + V.new(0, 5.45, 0), Anchored = true })
    e.step(0.5)
    T.eq(g:GetAttribute("Sheltered"), "roof")
    for i, d in ipairs({ V.new(1, 0, 0), V.new(-1, 0, 0), V.new(0, 0, 1) }) do
        e.part("Wall_" .. i, { Size = V.new(1, 4, 1), Position = spot + d * 2.4, Anchored = true })
    end
    e.step(0.5)
    T.eq(g:GetAttribute("Sheltered"), "enclosed")
    roof:Destroy()
    -- a fire close by: warm, and drying fast
    x.surviving[g].wet = 50
    local log = e.part("Log_9", { Size = V.new(7.5, 2.5, 2.5), Position = spot + V.new(4, -1.3, 4), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    x.lightFire(log)
    e.step(0.5)
    T.eq(g:GetAttribute("Cold"), false)
    T.ok(x.surviving[g].wet < 50, "drying by the fire")
end)

-- A house (ADR-019): the one-cell hut of mind/tests/test_house.py, held by the world's own copy of the check (houseAt).
T.test("a house: only inside one is the body warm at night, mending twice as fast; a roof or a fire halves the cold", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local spot = w.openSpot(10)
    local cx, cz = math.floor(spot.X / 2.5 + 0.5) * 2.5, math.floor(spot.Z / 2.5 + 0.5) * 2.5
    local g = w.godling(V.new(cx, 2.55, cz))
    local n = 0
    local function block(dx, dz, layer)
        n = n + 1
        return e.part("Block_" .. 900 + n, { Size = V.new(2.5, 2.5, 2.5),
            Position = V.new(cx + dx * 2.5, (layer - 0.5) * 2.5, cz + dz * 2.5), Anchored = true,
            attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
    end
    for layer = 1, 3 do -- posts three blocks high, west and east
        block(-1, 0, layer)
        block(1, 0, layer)
    end
    local north = { block(0, 1, 1), block(0, 1, 2) } -- the doorway is south
    local roof = e.part("Log_901", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(cx, 8.75, cz), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    e.step(1400, 10) -- into the night
    local s = x.surviving[g]
    s.wet, s.hunger, s.health = 0, 100, 50
    e.step(2, 1)
    T.eq(g:GetAttribute("Sheltered"), "house")
    T.eq(g:GetAttribute("Cold"), false, "warm in a house at night")
    local function over(seconds)
        local before = s.health
        e.step(seconds, 1)
        return s.health - before
    end
    T.near(over(10), 10 * 100 / 1800 * 2, 0.05, "mending twice as fast")
    north[2]:Destroy() -- the north wall one block high: walls on three sides and a roof, but no house
    e.step(2, 1)
    T.eq(g:GetAttribute("Sheltered"), "enclosed")
    T.eq(g:GetAttribute("Cold"), true, "cold, under a roof")
    T.near(over(10), -10 * 100 / 2400 * 0.5, 0.02, "a roof halves the cold")
    local log = e.part("Log_902", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(cx + 2, 1.25, cz - 6), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    x.lightFire(log)
    e.step(2, 1)
    T.eq(g:GetAttribute("ByFire"), true)
    T.near(over(10), -10 * 100 / 2400 * 0.25, 0.02, "and a fire close by halves it again")
    roof:Destroy()
    e.step(2, 1)
    T.eq(g:GetAttribute("Sheltered"), "")
    T.near(over(10), -10 * 100 / 2400 * 0.5, 0.02, "out in the open, a fire alone halves it")
end)

-- Many days of weather, with Godling on the beach by the raft: it rains and dries, a wet spell sets in, storms
-- strike palms near it, fog comes some mornings, logs wash up, and a ship passes far out.
T.test("the weather over nine days, the driftwood, and a passing ship", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local clock = e.find("Clock")
    local seen = { rain = false, fog = false, inRain = false, cold = false, ship = false, gone = false, wind = false,
        doused = false }
    local lit = false
    for _ = 1, 1080 do -- six hours, twenty seconds at a time
        e.step(20)
        if (clock:GetAttribute("Rain") or 0) > 0.3 then
            seen.rain = true
            if not lit then -- a fire lit in the rain does not last
                lit = true
                local log = e.part("Log_77", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(300, 1.25, 300),
                    Anchored = true, attrs = { RenderRole = "Log" } })
                x.lightFire(log)
            end
        end
        seen.fog = seen.fog or (clock:GetAttribute("Fog") or 0) > 0.5
        seen.inRain = seen.inRain or g:GetAttribute("InRain") == true
        seen.cold = seen.cold or g:GetAttribute("Cold") == true
        seen.wind = seen.wind or math.abs(clock:GetAttribute("WindX") or 0) > 0.5
        if e.find("Ship") then
            seen.ship = true
        elseif seen.ship then
            seen.gone = true
        end
        x.surviving[g].health, x.surviving[g].hunger = 100, 100 -- kept alive throughout
    end
    for what, ok in pairs(seen) do
        if what ~= "doused" then
            T.ok(ok, what)
        end
    end
    T.logged(w, "WEATHER a wet spell for")
    T.logged(w, "WEATHER fog until")
    T.logged(w, "SKY Lightning #%d+ felled Palm_")
    T.logged(w, "DOUSED Fire_")
    T.logged(w, "SHIP passing at")
    T.logged(w, "DRIFTWOOD Log_")
    T.eq(g:GetAttribute("RainPace") ~= nil, true)
    local drift = 0
    for _, inst in ipairs(e.Workspace:GetChildren()) do
        if inst:GetAttribute("Driftwood") then
            drift = drift + 1
        end
    end
    T.ok(drift >= 6, "the beach holds its share of driftwood, and no more washes up")
end)

T.test("a storm with nobody on the island strikes nothing; with no palm in range, the nearest beyond", function()
    local w = T.boot()
    local e, x = w.e, w.x
    x.stormStrike() -- nobody here
    local g = w.godling(V.new(600, 2.55, 600)) -- far out: every palm is beyond 45
    x.stormStrike()
    T.logged(w, "SKY Lightning #1 felled")
    e.hrp(g).Position = V.new(0, 2.55, 0)
    for _, t in ipairs(x.trees) do
        t.part:SetAttribute("RenderRole", "Stump")
    end
    x.stormStrike() -- no standing palm at all
end)

T.test("the old supply drops: a cube from the sky when few lie loose", function()
    local w = T.boot({ patch = { { "local SUPPLY_FROM_SKY = false", "local SUPPLY_FROM_SKY = true" } } })
    local e, x = w.e, w.x
    local g = w.godling(V.new(5, 2.55, 5))
    e.step(121, 1)
    T.eq(e.find("SupplyBlock_1"), nil, "twelve lie loose: no need")
    for i = 1, 9 do
        e.find("Block_" .. i):Destroy()
    end
    local held = e.find("Block_10")
    e.hrp(g).Position = held.Position + V.new(-2.5, 1.3, 0)
    w.act(g, "Pickup", { position = at(held) })
    e.step(121, 1)
    T.ok(e.find("SupplyBlock_1"), "a cube dropped")
    T.eq(x.looseGroundCubes(), 2)
    T.no(x.clearSupplySpot(e.hrp(g).Position.X, e.hrp(g).Position.Z), "not where someone stands")
    T.no(x.clearSupplySpot(500, 500), "not at sea")
    local m = x.mesas[1]
    T.no(x.clearSupplySpot(m.pos[1], m.pos[3]), "not on rock")
    local q = x.QUARRY
    T.no(x.clearSupplySpot(q.pos[1], q.pos[3] - 4), "not by the quarry")
end)

T.test("a palm on the grass inland, as the island had", function()
    local w = T.boot({ patch = { { "    trees = {},", "    trees = {{0, 0}}," } } })
    T.eq(w.e.find("Tree_1"):GetAttribute("ModelUrl"), "asset://tree.glb")
end)

T.test("setting the rock down keeps its impacts quiet a moment", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local rock = e.find("Rock_1")
    local g = w.godling(rock.Position + V.new(-2.8, 1.45, 0))
    w.act(g, "Pickup", { position = at(rock) })
    e.step(1.2)
    local p = e.hrp(g).Position
    T.eq(w.act(g, "Place", { position = { p.X - 4, 1.06, p.Z } }), "PlaceSuccess")
    e.step(1.3)
    T.ok(x.rockImpactStates[rock].ignoreUntil > e.now, "quiet a moment after landing")
end)

T.test("climbing up where the body would not fit at the top", function()
    local w = T.boot()
    local e = w.e
    e.part("Wall", { Size = V.new(7.5, 7.5, 7.5), Position = V.new(45, 3.75, -20), Anchored = true })
    e.part("Crate", { Size = V.new(7.5, 2.5, 7.5), Position = V.new(45, 8.75, -20), Anchored = true })
    local ladder = e.part("Ladder_9", { Size = V.new(1.5, 7.5, 0.4), Anchored = true,
        attrs = { RenderRole = "Ladder", IsPickupObject = true } })
    ladder.CFrame = T.CFrame.new(V.new(40.8, 3.77, -20)) * T.CFrame.fromOrientation(0, math.rad(90), 0)
    local g = w.godling(V.new(39, 2.55, -20))
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:NothingAtTop", "no room on the wall's top")
end)

T.test("moving several pieces into place at once, and one of them lost on the way", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local a, b = e.find("Block_1"), e.find("Block_2")
    table.insert(x.placingBlocks, { block = b, startCFrame = b.CFrame, targetCFrame = b.CFrame, elapsed = 0, duration = 1 })
    table.insert(x.placingBlocks, { block = a, startCFrame = a.CFrame, targetCFrame = a.CFrame, elapsed = 0, duration = 1 })
    x.destroyBlock(a)
    T.eq(#x.placingBlocks, 1, "only the lost one is dropped")
end)

T.test("a fainted body with nothing in its hands, and a body with no character to reset", function()
    local w = T.boot()
    local x = w.x
    local g = w.godling()
    local s = { hunger = 0, health = 0, beat = 0 }
    x.faint(g, s)
    T.eq(g:GetAttribute("Faints"), 1)
    local ghost = w.e.player("Ghost", nil, { noCharacter = true })
    x.resetPlayerToSpawn(ghost)
    T.eq(x.getHumanoid(ghost), nil)
end)

return T.done("test_life")
