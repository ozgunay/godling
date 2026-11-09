-- Living on the island: hunger, hurt, death and rebirth, coconuts, the weather over many days (showers, wet spells,
-- storms, fog, wind, shelter and cold), driftwood, a passing ship, and the old supply drops.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

local function at(part)
    local p = part.Position
    return { p.X, p.Y, p.Z }
end

T.test("hunger empties, then health; well fed it mends; at none, Godling dies, lies dead, and is born again", function()
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
    -- Godling holds a block when it dies, starving on a cold night: the block drops where it fell
    local block = e.find("Block_1")
    local fell = block.Position + V.new(-2.5, 1.3, 0)
    e.hrp(g).Position = fell
    w.act(g, "Pickup", { position = at(block) })
    s.hunger, s.health = 0, 0.01
    e.step(1)
    T.eq(g:GetAttribute("Dead"), true)
    T.eq(g:GetAttribute("Deaths"), 1)
    T.eq(g:GetAttribute("DiedOf"), "HungerAndCold")
    T.eq(g:GetAttribute("DiedAt"), string.format("%.1f,%.1f", fell.X, fell.Z))
    T.eq(g:GetAttribute("DeadFor"), 30)
    T.eq(g:GetAttribute("Gesture"), "Stagger", "it falls where it died")
    T.eq(g:GetAttribute("Health"), 0)
    T.eq(block.CanCollide, true, "dropped where it died")
    T.logged(w, "DIED Godling of HungerAndCold at")
    -- Dead, it takes nothing in: no inputs, no hunger, no hurt, and no second death
    e.step(10, 1)
    T.eq(g:GetAttribute("DeadFor"), 20, "counts down")
    w.act(g, "MoveTo", { position = { 0, 2.5, 0 } })
    T.eq(g:GetAttribute("LastActionResult"), "Dead")
    T.eq(s.hunger, 0, "no hunger while dead")
    x.hurt(g, 50, "Lightning")
    T.eq(g:GetAttribute("Hurts"), nil, "the dead are not hurt")
    T.near(e.hrp(g).Position.X, fell.X, 1e-9, "it lies where it fell")
    T.eq(g:GetAttribute("Deaths"), 1)
    -- Thirty seconds on it is born again at the start spot: whole, but half fed
    e.step(21, 1)
    T.eq(g:GetAttribute("Dead"), false)
    T.eq(g:GetAttribute("DeadFor"), 0)
    T.eq(g:GetAttribute("Gesture"), "WakeUp")
    T.near(s.health, 100, 0.1, "whole (the cold night has taken a little since)")
    T.near(s.hunger, 50, 0.1)
    T.near(e.hrp(g).Position.X, x.PLAYER_SPAWN_POSITION.X, 1e-9, "born again at the start spot")
    T.near(e.humanoid(g).Health, 100, 0.1)
    T.logged(w, "REBORN Godling at the start spot")
    T.ok(x.death.since(g) >= 30 and x.death.since(g) < 40)
    -- fed but out in the cold night: the cold alone
    s.health = 0.001
    e.step(1)
    T.eq(g:GetAttribute("DiedOf"), "Cold")
    T.eq(g:GetAttribute("Deaths"), 2)
    e.step(31, 1)
    -- a bodiless player and the guest panel are not fed; a body without a character dies all the same
    local sky = w.skyPlayer()
    local ghost = e.player("Ghost", nil, { noCharacter = true })
    e.step(1)
    T.eq(x.surviving[sky], nil)
    x.surviving[ghost].hunger, x.surviving[ghost].health = 0, 0.001
    e.step(1)
    T.eq(ghost:GetAttribute("Deaths"), 1)
    T.eq(ghost:GetAttribute("DiedAt"), "")
    e.step(31, 1)
    T.eq(ghost:GetAttribute("Dead"), false, "and is born again")
    T.eq(x.death.since(sky), math.huge, "never died")
end)

T.test("starving by day, warm and dry, it dies of hunger alone", function()
    local w = T.boot()
    local g = w.godling(V.new(10, 2.55, 10))
    w.e.step(1)
    local s = w.x.surviving[g]
    s.hunger, s.health = 0, 0.001
    w.e.step(1)
    T.eq(g:GetAttribute("DiedOf"), "Hunger")
end)

T.test("hurt: from what struck close by; enough of it kills the body", function()
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
    T.eq(g:GetAttribute("Deaths"), 1)
    T.eq(g:GetAttribute("DiedOf"), "Meteor")
    w.skyPlayer()
    e.player("Spirit", nil, { noCharacter = true })
    x.hurtNear(10, 10, 500, 1, "Lightning") -- neither has a body to hurt
end)

T.test("death stops a climb and a turn already in progress; rebirth releases the body", function()
    local w = T.boot()
    local e, x = w.e, w.x
    e.part("Wall", { Size = V.new(7.5, 7.5, 7.5), Position = V.new(45, 3.75, -20), Anchored = true })
    local ladder = e.part("Ladder_9", { Size = V.new(1.5, 7.5, 0.4), Anchored = true,
        attrs = { RenderRole = "Ladder", IsPickupObject = true } })
    ladder.CFrame = T.CFrame.new(V.new(40.8, 3.77, -20)) * T.CFrame.fromOrientation(0, math.rad(90), 0)
    local g = w.godling(V.new(39, 2.55, -20))
    e.step(0.1)
    T.starts(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbStarted:up:")
    e.step(0.5, 0.1)
    e.hrp(g).AssemblyLinearVelocity, e.hrp(g).AssemblyAngularVelocity = V.new(1, 2, 3), V.new(3, 2, 1)
    x.hurt(g, 200, "Lightning")
    local fell = e.hrp(g).Position
    T.eq(g:GetAttribute("Climbing"), false)
    T.eq(e.hrp(g).Anchored, true, "the corpse cannot slide or be pushed")
    T.eq(e.hrp(g).AssemblyLinearVelocity, V.new())
    T.eq(e.hrp(g).AssemblyAngularVelocity, V.new())
    e.step(3, 0.1)
    T.eq(e.hrp(g).Position, fell, "the dead body does not finish its climb")
    e.step(27.1, 0.1)
    T.eq(g:GetAttribute("Dead"), false)
    T.eq(e.hrp(g).Anchored, false, "the reborn body can walk")
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:TooFar", "no unfinished climb holds it busy")
    w.act(g, "Face", { position = { e.hrp(g).Position.X + 10, 2.55, e.hrp(g).Position.Z } })
    x.hurt(g, 200, "Meteor")
    local look = e.hrp(g).CFrame.LookVector
    e.step(0.2, 0.1)
    T.eq(e.hrp(g).CFrame.LookVector, look, "the dead body does not finish its turn")
end)

T.test("a corpse stays put when trapped or out of bounds until its rebirth", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling(V.new(40, 2.55, -80))
    e.step(0.1)
    x.hurt(g, 200, "Meteor")
    local fell = e.hrp(g).Position
    e.part("Beam", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(40, 4, -80), Anchored = true })
    e.step(1.1, 0.5)
    T.eq(e.hrp(g).Position, fell, "the live-body escape does not move a corpse")
    T.eq(g:GetAttribute("Freed"), nil)
    local below = V.new(40, x.OUT_OF_BOUNDS_Y - 1, -80)
    e.hrp(g).Position = below
    e.step(1, 0.5)
    T.eq(e.hrp(g).Position, below, "the boundary reset does not move a corpse")
    e.step(28, 0.5)
    T.eq(g:GetAttribute("Dead"), false)
    T.eq(e.hrp(g).Position, x.PLAYER_SPAWN_POSITION, "rebirth still moves it to the start")
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
    local spot = w.openSpot(14)
    local cx, cz = math.floor(spot.X / 2.5 + 0.5) * 2.5, math.floor(spot.Z / 2.5 + 0.5) * 2.5
    local g = w.godling(V.new(cx, 2.55, cz))
    e.step(1400, 10) -- into the night, then build (the house check runs once a second under a roof)
    local n = 0
    local function piece(kind, size, dx, dz, layer)
        n = n + 1
        return e.part(kind .. "_" .. 900 + n, { Size = size, Position = V.new(cx + dx * 2.5, (layer - 0.5) * 2.5, cz + dz * 2.5),
            Anchored = true, attrs = { RenderRole = kind == "Log" and "Log" or "PickupObject", IsPickupObject = true } })
    end
    local BLOCK, ALONG_X = V.new(2.5, 2.5, 2.5), V.new(7.5, 2.5, 2.5)
    -- The benchmark house (mind/tests/test_house.py house()): a room two by two at cells (0..1, 0..1), walls three
    -- blocks high all round it, corners too, the doorway south at (0, -1), and the roof in layer 4 over all of it.
    local walls = {}
    for dx = -1, 2 do
        for dz = -1, 2 do
            local inRoom = dx >= 0 and dx <= 1 and dz >= 0 and dz <= 1
            if not inRoom and not (dx == 0 and dz == -1) then
                for layer = 1, 3 do
                    walls[dx .. "," .. dz .. "," .. layer] = piece("Block", BLOCK, dx, dz, layer)
                end
            end
        end
    end
    local roof = { piece("Log", ALONG_X, 0, -1, 4), piece("Block", BLOCK, 2, -1, 4), piece("Log", ALONG_X, 0, 2, 4),
        piece("Block", BLOCK, 2, 2, 4), piece("Log", ALONG_X, -1, 0, 4), piece("Log", ALONG_X, 2, 0, 4),
        piece("Log", ALONG_X, -1, 1, 4), piece("Log", ALONG_X, 2, 1, 4) }
    local s = x.surviving[g]
    s.wet, s.hunger, s.health = 0, 100, 50
    e.step(2, 1)
    T.eq(g:GetAttribute("InHouse"), true, "inside the house")
    T.eq(g:GetAttribute("Sheltered"), "roof", "a roof overhead; the room is wider than an arm's reach to the walls")
    T.eq(g:GetAttribute("Cold"), false, "warm in a house at night")
    local function over(seconds)
        local before = s.health
        e.step(seconds, 1)
        return s.health - before
    end
    T.near(over(10), 10 * 100 / 1800 * 2, 0.05, "mending twice as fast")
    walls["2,2,3"]:Destroy() -- the north-east corner a block short of the roof: a roof and walls, but no house
    e.step(2, 1)
    T.eq(g:GetAttribute("InHouse"), false, "a corner short of the roof")
    T.eq(g:GetAttribute("Sheltered"), "roof")
    T.eq(g:GetAttribute("Cold"), true, "cold, under a roof")
    T.near(over(10), -10 * 100 / 2400 * 0.5, 0.02, "a roof halves the cold")
    local log = e.part("Log_950", { Size = V.new(2.5, 2.5, 7.5), Position = V.new(cx - 5, 1.25, cz), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    x.lightFire(log)
    e.step(2, 1)
    T.eq(g:GetAttribute("ByFire"), true)
    T.near(over(10), -10 * 100 / 2400 * 0.25, 0.02, "and a fire close by halves it again")
    for _, part in ipairs(roof) do
        part:Destroy()
    end
    e.step(2, 1)
    T.eq(g:GetAttribute("Sheltered"), "")
    T.near(over(10), -10 * 100 / 2400 * 0.5, 0.02, "out in the open, a fire alone halves it")
end)

-- ADR-033: a room three cells wide, its roof held up by a post inside (mind/tests/test_house_posts.py hut()). It is a
-- house, and the more room inside a house, the faster a fed body mends there.
T.test("a house three cells wide on a post inside; the more room, the faster a fed body mends", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local cx, cz = 600, 600 -- away from the island's own terrain and pieces
    e.part("Ground_Posts", { Position = V.new(cx, -0.5, cz), Size = V.new(80, 1, 80), Anchored = true,
        attrs = { RenderRole = "Ground" } })
    local g = w.godling(V.new(cx, 2.55, cz)) -- in cell (0, 0), the room's south-west corner
    e.step(1400, 10) -- into the night, then build
    local n = 3000
    local function piece(kind, size, dx, dz, y)
        n = n + 1
        return e.part(kind .. "_" .. n, { Size = size, Position = V.new(cx + dx * 2.5, y, cz + dz * 2.5), Anchored = true,
            attrs = { RenderRole = kind == "Log" and "Log" or "PickupObject", IsPickupObject = true } })
    end
    local BLOCK, ALONG_X, ALONG_Z = V.new(2.5, 2.5, 2.5), V.new(7.5, 2.5, 2.5), V.new(2.5, 2.5, 7.5)
    for dx = -1, 3 do -- walls three blocks high round cells (0..2, 0..2), the doorway south at (1, -1)
        for dz = -1, 3 do
            if not (dx >= 0 and dx <= 2 and dz >= 0 and dz <= 2) and not (dx == 1 and dz == -1) then
                for layer = 1, 3 do
                    piece("Block", BLOCK, dx, dz, (layer - 0.5) * 2.5)
                end
            end
        end
    end
    local post = piece("Log", V.new(2.5, 7.5, 2.5), 1, 1, 3.75) -- a log stood on end in the middle
    piece("Log", ALONG_Z, 1, 1, 8.75) -- on the post's middle, over (1, 0) and (1, 2)
    piece("Log", ALONG_X, 1, -1, 8.75) -- the lintel
    for dz = 0, 2 do
        piece("Log", ALONG_X, -1, dz, 8.75) -- centred on the west wall, reaching one cell in
    end
    for dz = 0, 1 do
        piece("Log", ALONG_X, 3, dz, 8.75)
    end
    piece("Log", ALONG_Z, 2, 3, 8.75)
    for _, c in ipairs({ { -1, -1 }, { 3, -1 }, { -1, 3 }, { 0, 3 }, { 1, 3 }, { 3, 2 }, { 3, 3 } }) do
        piece("Block", BLOCK, c[1], c[2], 8.75)
    end
    local s = x.surviving[g]
    s.wet, s.hunger, s.health = 0, 100, 50
    e.step(2, 1)
    T.eq(g:GetAttribute("InHouse"), true, "inside a house three cells wide, its roof on a post")
    T.eq(g:GetAttribute("HouseRoom"), 8, "eight cells to stand in: nine inside, one of them the post")
    T.eq(g:GetAttribute("HouseMends"), 3, "three times as fast in eight cells")
    T.eq(g:GetAttribute("Cold"), false)
    local before = s.health
    e.step(10, 1)
    T.near(s.health - before, 10 * 100 / 1800 * 3, 0.05, "mending three times as fast")
    -- The post two blocks high, a gap under the log on it: no house.
    post:Destroy()
    piece("Block", BLOCK, 1, 1, 1.25)
    piece("Block", BLOCK, 1, 1, 3.75)
    e.step(2, 1)
    T.eq(g:GetAttribute("InHouse"), false, "a post short of the roof")
    T.eq(g:GetAttribute("HouseMends"), 0)
end)

-- The shelter run hp-proj8 built (ADR-019), which passed the first check: one cell between two posts and a wall, a
-- log over it. It keeps the rain off and the walls round it halve the cold, but it is no house.
T.test("a one-cell shelter between posts is enclosed, not a house", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local spot = w.openSpot(10)
    local cx, cz = math.floor(spot.X / 2.5 + 0.5) * 2.5, math.floor(spot.Z / 2.5 + 0.5) * 2.5
    local g = w.godling(V.new(cx, 2.55, cz))
    local n = 0
    local function block(dx, dz, layer)
        n = n + 1
        return e.part("Block_" .. 960 + n, { Size = V.new(2.5, 2.5, 2.5),
            Position = V.new(cx + dx * 2.5, (layer - 0.5) * 2.5, cz + dz * 2.5), Anchored = true,
            attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
    end
    for layer = 1, 3 do -- posts three blocks high, west and east
        block(-1, 0, layer)
        block(1, 0, layer)
    end
    block(0, 1, 1) -- a wall two blocks high north; the doorway south
    block(0, 1, 2)
    e.part("Log_961", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(cx, 8.75, cz), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    e.step(1400, 10)
    local s = x.surviving[g]
    s.wet, s.hunger, s.health = 0, 100, 50
    e.step(2, 1)
    T.eq(g:GetAttribute("Sheltered"), "enclosed")
    T.eq(g:GetAttribute("InHouse"), false, "a room one cell wide, open at the corners: no house")
    T.eq(g:GetAttribute("Cold"), true)
end)

-- Many days of weather, with Godling on the beach by the raft: it rains and dries, a wet spell sets in, storms
-- strike palms near it, fog comes some mornings, logs wash up, and a ship passes far out.
T.test("house material is continuous, settled and on a real level floor, matching the mind", function()
    for _, case in ipairs({ "complete", "seam", "fractional", "missing-floor", "uneven", "sparse", "unanchored", "unsettled", "tilted", "narrow" }) do
        local w = T.boot()
        local e = w.e
        local cx, cz = 600, 600 -- isolated from the island's own terrain and pieces
        local g = w.godling(V.new(cx, 2.55, cz))
        local function ground(name, x, size)
            return e.part(name, { Position = V.new(x, -0.5, cz), Size = V.new(size, 1, 80), Anchored = true,
                attrs = { RenderRole = "Ground" } })
        end
        if case == "seam" then
            ground("Ground_W", cx - 18.75, 40)
            ground("Ground_E", cx + 21.25, 40)
        elseif case ~= "missing-floor" then
            ground("Ground_Test", cx, 80)
        end
        if case == "uneven" then
            e.part("Raised", { Position = V.new(cx + 2.5, 0.5, cz + 2.5), Size = V.new(2.5, 1, 2.5), Anchored = true,
                attrs = { RenderRole = "Ground" } })
        end
        local n = 2000
        local function piece(kind, dx, dz, layer, roof)
            n = n + 1
            local size = V.new(kind == "Log" and 7.5 or 2.5, 2.5, 2.5)
            local y = (layer - 0.5) * 2.5
            if case == "fractional" then
                if roof then
                    y = y - 1.2
                else
                    y, size = y * 0.84, V.new(size.X, 2.1, size.Z)
                end
            elseif not roof and case == "sparse" then
                size = V.new(size.X, 0.5, size.Z)
            elseif not roof and case == "narrow" then
                size = V.new(0.5, size.Y, size.Z)
            end
            local p = e.part(kind .. "_" .. n, { Position = V.new(cx + dx * 2.5, y, cz + dz * 2.5), Size = size,
                Anchored = true, attrs = { RenderRole = kind == "Log" and "Log" or "PickupObject", IsPickupObject = true } })
            if not roof and case == "unanchored" then
                p.Anchored = false
                p.AssemblyLinearVelocity = V.new(1, 0, 0) -- it has not come to rest and cannot settle during this check
            elseif not roof and case == "unsettled" then
                p:SetAttribute("Settled", false)
            elseif not roof and case == "tilted" then
                p.CFrame = T.CFrame.new(p.Position) * T.CFrame.fromOrientation(0, 0, math.rad(10))
            end
            return p
        end
        for dx = -1, 2 do
            for dz = -1, 2 do
                if not (dx >= 0 and dx <= 1 and dz >= 0 and dz <= 1) and not (dx == 0 and dz == -1) then
                    for layer = 1, 3 do
                        piece("Block", dx, dz, layer, false)
                    end
                end
            end
        end
        piece("Log", 0, -1, 4, true)
        piece("Block", 2, -1, 4, true)
        piece("Log", 0, 2, 4, true)
        piece("Block", 2, 2, 4, true)
        for dz = 0, 1 do
            piece("Log", -1, dz, 4, true)
            piece("Log", 2, dz, 4, true)
        end
        e.step(2, 0.5)
        T.eq(g:GetAttribute("InHouse"), case == "complete" or case == "seam" or case == "fractional", case)
    end
end)

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

T.test("a dead body with nothing in its hands, and a body with no character to reset", function()
    local w = T.boot()
    local x = w.x
    local g = w.godling()
    local s = { hunger = 0, health = 0, beat = 0 }
    x.death.die(g, s, "Hunger")
    T.eq(g:GetAttribute("Deaths"), 1)
    x.death.die(g, s, "Hunger") -- already dead: nothing more
    T.eq(g:GetAttribute("Deaths"), 1)
    local ghost = w.e.player("Ghost", nil, { noCharacter = true })
    x.resetPlayerToSpawn(ghost)
    T.eq(x.getHumanoid(ghost), nil)
end)

return T.done("test_life")
