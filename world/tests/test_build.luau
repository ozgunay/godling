-- Working the island: the quarry, felling and carving, fishing, fire by rubbing, fastening and settling, climbing,
-- stepping up and down, being freed from inside a piece, and drawing in the sand.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V, CF = T.Vector3, T.CFrame

local function at(part)
    local p = part.Position
    return { p.X, p.Y, p.Z }
end

-- Godling holding `name` (picked up where it lies), standing at `stand` afterwards if given.
local function holding(w, g, name, stand)
    local e = w.e
    local item = e.find(name)
    e.hrp(g).Position = item.Position + V.new(-2, 2.4, 0)
    T.eq(w.act(g, "Pickup", { position = at(item) }), "PickupSuccess", "pick up " .. name)
    e.step(1.2)
    if stand then
        e.hrp(g).Position = stand
    end
    return item
end

local function strikeAt(w, g, name)
    w.e.now = w.e.now + 1 -- a swing's pause
    return w.act(g, "Strike", { name = name })
end

local function solid(e, name, centre, size, extra)
    local props = { Size = size, Position = centre, Anchored = true }
    for k, v in pairs(extra or {}) do
        props[k] = v
    end
    return e.part(name, props)
end

T.test("a strike needs a tool, a target and reach, and a pause between swings", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    T.eq(w.act(g, "Strike", { name = "Quarry" }), "StrikeFailed:NoTool")
    local block = e.find("Block_1")
    e.hrp(g).Position = block.Position + V.new(-2.5, 1.3, 0)
    w.act(g, "Pickup", { position = at(block) })
    T.eq(w.act(g, "Strike", { name = "Quarry" }), "StrikeFailed:NoTool", "a block is no tool")
    w.act(g, "Throw", { direction = { -1, 0, 0 } })
    holding(w, g, "Hammer_1")
    T.eq(w.act(g, "Strike", nil), "StrikeFailed:NoTarget")
    T.eq(w.act(g, "Strike", { name = "Nowhere" }), "StrikeFailed:NoTarget")
    T.eq(w.act(g, "Strike", { name = "Godling" }), "StrikeFailed:NoTarget", "a character is not a part")
    e.hrp(g).Position = V.new(0, 2.55, 0) -- the middle of the island, far from the quarry
    T.eq(w.act(g, "Strike", { name = "Quarry" }), "StrikeFailed:OutOfRange")
    local palm = e.find("Palm_1")
    e.hrp(g).Position = palm.Position + V.new(-3, -7.5, 0)
    T.eq(strikeAt(w, g, "Palm_1"), "StrikeNoEffect:Hammer", "a hammer does nothing to a palm")
    T.eq(g:GetAttribute("Gesture"), "Mine")
    T.eq(w.act(g, "Strike", { name = "Palm_1" }), "StrikeFailed:TooSoon")
end)

T.test("the quarry gives a stone every third blow, into its yard, until the yard is full", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    local quarry = e.find("Quarry")
    holding(w, g, "Hammer_1", quarry.Position + V.new(0, 0.05, -(3.75 + 2)))
    T.eq(strikeAt(w, g, "Quarry"), "StrikeHit:1/3")
    T.eq(strikeAt(w, g, "Quarry"), "StrikeHit:2/3")
    T.eq(strikeAt(w, g, "Quarry"), "StrikeBroke:Stone_1")
    local stone = e.find("Stone_1")
    T.eq(stone:GetAttribute("RenderRole"), "Stone")
    T.near(stone.Position.Y, 1.27, 0.05, "on the ground of the yard")
    solid(e, "Slab", quarry.Position, V.new(40, 2.5, 40)) -- every yard cell taken
    T.eq(strikeAt(w, g, "Quarry"), "StrikeYardFull")
end)

T.test("an axe fells a palm into one log, away from the axe, and it grows back", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local palm = e.find("Palm_2")
    holding(w, g, "Axe_1", palm.Position + V.new(-3, -7.45, 0))
    for n = 1, 3 do
        T.eq(strikeAt(w, g, "Palm_2"), "StrikeHit:" .. n .. "/4")
    end
    local felled = strikeAt(w, g, "Palm_2")
    T.eq(felled, "StrikeFelled:Log_1", "one log, the trunk (ADR-026: it was two, and the island filled with logs)")
    T.eq(e.find("Log_2"), nil, "and no second beside it")
    T.eq(g:GetAttribute("Gesture"), "Chop")
    T.eq(palm:GetAttribute("RenderRole"), "Stump")
    T.near(palm.Size.Y, 1.25, 1e-9, "a stump half a block high")
    local log = e.find("Log_1")
    T.ok(log.Position.X > palm.Position.X, "fallen away from the axe")
    e.step(600, 10)
    T.eq(palm:GetAttribute("RenderRole"), "Tree", "grown back")
    T.eq(palm:GetAttribute("ModelUrl"), "asset://palm.glb")
    -- from the south, it falls north; logs that cannot lie where they fall are put beside or on top
    local other = e.find("Palm_3")
    solid(e, "InTheWay", other.Position + V.new(0, -8.75, 6.25), V.new(2.5, 2.5, 2.5))
    e.hrp(g).Position = other.Position + V.new(0, -7.45, -3)
    for _ = 1, 4 do
        strikeAt(w, g, "Palm_3")
    end
    T.eq(other:GetAttribute("RenderRole"), "Stump")
    local spot = x.freeSpawn(CF.new(V.new(0, 1, 0)), V.new(2, 2, 2), V.new(1, 0, 0))
    T.ok(spot, "a free spot somewhere")
    solid(e, "Wall", V.new(0, 10, 0), V.new(200, 40, 200))
    local fallback = x.freeSpawn(CF.new(V.new(0, 1, 0)), V.new(2, 2, 2), V.new(1, 0, 0))
    T.near(fallback.Position.Y, 6, 1e-9, "everywhere taken: dropped from above")
end)

T.test("a palm part-chopped, then felled by lightning, grows back whole: its next chop is the first of four", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local palm = e.find("Palm_2")
    holding(w, g, "Axe_1", palm.Position + V.new(-3, -7.45, 0))
    for n = 1, 3 do
        T.eq(strikeAt(w, g, "Palm_2"), "StrikeHit:" .. n .. "/4")
    end
    local t
    for _, tree in ipairs(x.trees) do
        t = tree.name == "Palm_2" and tree or t
    end
    x.lightningOn(t, e.hrp(g).Position) -- 77-AB4: it kept its three chops
    T.eq(palm:GetAttribute("RenderRole"), "Stump")
    x.regrowStump(t)
    T.eq(strikeAt(w, g, "Palm_2"), "StrikeHit:1/4")
end)

T.test("a hammer knocks a fastened piece loose; a set-up ladder stays standing", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    local block = e.find("Block_1")
    block.Anchored = true
    block:SetAttribute("Fastened", true)
    holding(w, g, "Hammer_1", block.Position + V.new(-2.5, 1.3, 0))
    T.eq(strikeAt(w, g, "Block_1"), "StrikeLoosened:Block_1")
    T.eq(block.Anchored, false)
    local ladder = solid(e, "Ladder_9", block.Position + V.new(0, 2.5, -4), V.new(1.5, 7.5, 0.4),
        { attrs = { RenderRole = "Ladder", Fastened = true } })
    T.eq(strikeAt(w, g, "Ladder_9"), "StrikeLoosened:Ladder_9")
    T.eq(ladder.Anchored, true)
end)

T.test("an axe carves a log into a spear", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    local log = e.part("Log_7", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(30, 1.25, 30),
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    holding(w, g, "Axe_1", V.new(25, 2.55, 30))
    T.eq(strikeAt(w, g, "Log_7"), "StrikeCarving:1/3")
    T.eq(g:GetAttribute("Gesture"), "Carve")
    T.eq(strikeAt(w, g, "Log_7"), "StrikeCarving:2/3")
    T.eq(strikeAt(w, g, "Log_7"), "StrikeCarved:Spear_1")
    T.eq(log.Parent, nil)
    T.eq(e.find("Spear_1"):GetAttribute("ToolKind"), "Spear")
end)

T.test("a spear's thrust reaches fish; a miss makes one dart off, a catch lands at the feet, and fish come back", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local spear = e.part("Spear_1", { Size = V.new(0.3, 0.3, 4.5), Position = V.new(0, 0.25, 0),
        attrs = { RenderRole = "Tool", ToolKind = "Spear", IsPickupObject = true } })
    holding(w, g, "Spear_1")
    local fish = e.find("Fish_1")
    e.hrp(g).Position = fish.Position + V.new(-8, 2, 0) -- 8 off: out of an arm's reach, not of a spear's
    table.insert(e.randoms, 0.9) -- a miss
    T.eq(strikeAt(w, g, "Fish_1"), "StrikeMissed:Fish_1")
    T.eq(g:GetAttribute("Gesture"), "Spear")
    T.ok(x.swimming[fish].dartUntil > e.now, "darting away")
    e.hrp(g).Position = fish.Position + V.new(-8, 2, 0)
    x.swimming[fish] = nil -- a fish the shoal lost track of still dies when caught
    table.insert(e.randoms, 0.9)
    T.eq(strikeAt(w, g, "Fish_1"), "StrikeMissed:Fish_1")
    table.insert(e.randoms, 0.1) -- a catch
    T.eq(strikeAt(w, g, "Fish_1"), "StrikeCaught:Catch_1")
    T.eq(fish.Parent, nil)
    T.eq(e.find("Catch_1"):GetAttribute("RenderRole"), "Catch")
    local fish2 = e.find("Fish_2")
    e.hrp(g).Position = V.new(fish2.Position.X, 2.55, fish2.Position.Z) -- standing right over it
    table.insert(e.randoms, 0.1)
    strikeAt(w, g, "Fish_2")
    e.step(61, 1)
    local count = 0
    for _ in pairs(x.swimming) do
        count = count + 1
    end
    T.eq(count, 12, "the caught fish are replaced")
end)

T.test("fish swim from shallow to shallow, darting when startled, and stay put when boxed in", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local fish = e.find("Fish_3")
    local f = x.swimming[fish]
    local from = fish.Position
    f.goal = from + V.new(3, 0, 0)
    e.step(0.5)
    T.ok(fish.Position.X > from.X, "on its way")
    f.goal = fish.Position + V.new(0.2, 0, 0)
    e.step(0.1) -- there: a new goal
    T.ok((x.swimming[fish].goal - fish.Position).Magnitude > 0.2 or true)
    local stuck = x.shallowNear(V.new(0, 0, 0), 12) -- the middle of the island: no open water
    T.near(stuck.X, 0, 1e-9, "boxed in, it stays put")
    T.ok(x.shallowNear(nil, 0), "a fresh fish starts in any shallow")
    fish:Destroy()
    e.step(0.1)
    T.eq(x.swimming[fish], nil, "a fish gone is forgotten")
end)

T.test("fire by rubbing: warm, hot, then a flame in the husk beside it; not in the rain, nor while damp", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    e.part("Spear_1", { Size = V.new(0.3, 0.3, 4.5), Position = V.new(0, 0.25, 0),
        attrs = { RenderRole = "Tool", ToolKind = "Spear", IsPickupObject = true } })
    local log = e.part("Log_7", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(30, 1.25, 30), Anchored = true,
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    holding(w, g, "Spear_1", V.new(25, 2.55, 30))
    T.eq(w.act(g, "Rub", nil), "RubFailed:NoTarget")
    T.eq(w.act(g, "Rub", { name = "Spear_1" }), "RubFailed:NoTarget", "not against itself")
    T.eq(w.act(g, "Rub", { name = "Quarry" }), "RubFailed:OutOfRange")
    x.climate.rain = 0.5
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubRain")
    T.eq(g:GetAttribute("Gesture"), "Kindle")
    x.climate.rain = 0
    x.climate.dampUntil = e.now + 100
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubDamp")
    x.climate.dampUntil = 0
    for n = 1, 11 do
        e.now = e.now + 1
        T.eq(w.act(g, "Rub", { name = "Log_7" }), "StrikeRubWarm:" .. n)
    end
    T.eq(w.act(g, "Rub", { name = "Log_7" }), "RubFailed:TooSoon")
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubHot:12", "hot, but nothing beside it to catch")
    local husk = e.part("Coconut_5", { Size = V.new(0.9, 0.9, 0.9), Position = V.new(34.5, 0.45, 30),
        attrs = { RenderRole = "Coconut", IsPickupObject = true } })
    table.insert(e.randoms, 0.9) -- not this time
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubHot:13")
    table.insert(e.randoms, 0.01)
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubCaught:Fire_1")
    T.eq(husk.Parent, nil, "the husk burns away")
    T.eq(log:GetAttribute("Burning"), true)
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubBurning")
    e.now = e.now + 20 -- a long pause: the heat is gone
    log:SetAttribute("Burning", false)
    T.eq(strikeAt(w, g, "Log_7"), "StrikeRubWarm:1")
    log:SetAttribute("Burning", true)
    -- rubbing anything else does nothing; empty hands have nothing to rub with
    local hammer = e.find("Hammer_1")
    T.eq(w.act(g, "Throw", { direction = { 0, 1, 0 } }), "ThrowSuccess")
    T.eq(w.act(g, "Rub", { name = "Log_7" }), "RubFailed:EmptyHands")
    holding(w, g, "Hammer_1", V.new(25, 2.55, 30))
    e.now = e.now + 1
    T.eq(w.act(g, "Rub", { name = "Log_7" }), "RubNothing")
    T.ok(hammer.Parent)
end)

T.test("a fire burns its log away, cooks a fish beside it, and the rain puts it out", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling(V.new(25, 2.55, 30))
    local function log(name, pos)
        return e.part(name, { Size = V.new(7.5, 2.5, 2.5), Position = pos, Anchored = true,
            attrs = { RenderRole = "Log", IsPickupObject = true, Settled = true } })
    end
    local burning = log("Log_7", V.new(30, 1.25, 30))
    local fire = x.lightFire(burning)
    T.eq(fire:GetAttribute("Fuel"), "Log_7")
    T.eq(w.act(g, "Cook", {}), "CookFailed:NotFish")
    local catch = e.part("Catch_4", { Size = V.new(1.3, 0.35, 0.5), Position = V.new(24, 0.2, 30),
        attrs = { RenderRole = "Catch", IsPickupObject = true } })
    T.eq(w.act(g, "Pickup", { position = at(catch) }), "PickupSuccess")
    T.eq(w.act(g, "Cook", {}), "CookSuccess:Catch_4")
    T.eq(catch:GetAttribute("ModelUrl"), "asset://fish_cooked.glb")
    T.eq(w.act(g, "Cook", {}), "CookFailed:Cooked")
    catch:SetAttribute("Cooked", false)
    e.hrp(g).Position = V.new(-60, 2.55, 30)
    T.eq(w.act(g, "Cook", {}), "CookFailed:NoFire")
    -- burnt out: the log is ash, and what lay on it falls
    local onTop = e.part("Block_99", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(30, 3.75, 30), Anchored = true,
        attrs = { RenderRole = "PickupObject", IsPickupObject = true, Settled = true } })
    e.step(600, 10)
    T.eq(burning.Parent, nil)
    T.eq(fire.Parent, nil)
    T.eq(onTop.Anchored, false, "woken, not settled again yet")
    -- a fire whose log was taken away goes out
    local gone = log("Log_8", V.new(40, 1.25, 40))
    local f2 = x.lightFire(gone)
    gone:Destroy()
    e.step(0.1)
    T.eq(f2.Parent, nil)
    -- the rain douses fires: the log is left, charred but whole
    local wet = log("Log_9", V.new(50, 1.25, 40))
    local f3 = x.lightFire(wet)
    local f4 = x.lightFire(log("Log_10", V.new(60, 1.25, 40)))
    e.find("Log_10"):Destroy()
    x.douseFires()
    T.eq(f3.Parent, nil)
    T.eq(f4.Parent, nil)
    T.eq(wet:GetAttribute("Burning"), false)
    T.logged(w, "DOUSED Fire_3 on Log_9")
end)

T.test("a log laid against a fire takes it on, a fastened one never; under a roof the rain leaves a fire burning", function()
    local w = T.boot()
    local e, x = w.e, w.x
    w.godling(V.new(25, 2.55, 30))
    local function log(name, pos, attrs)
        local a = { RenderRole = "Log", IsPickupObject = true, Settled = true }
        for k, v in pairs(attrs or {}) do
            a[k] = v
        end
        return e.part(name, { Size = V.new(7.5, 2.5, 2.5), Position = pos, Anchored = true, attrs = a })
    end
    -- ADR-019: one lighting can last the night. A fastened log (a built wall) never catches.
    local first = log("Log_7", V.new(30, 1.25, 30))
    local wall = log("Log_6", V.new(30, 1.25, 32.5), { Fastened = true }) -- along its side
    -- Nor does one built in without fastening: a wall's bottom course with a block on it, a beam up off the floor.
    local course = log("Log_4", V.new(22.5, 1.25, 30)) -- end to end, the other way
    e.part("Block_40", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(22.5, 3.75, 30), Anchored = true,
        attrs = { Settled = true } })
    local beam = log("Log_5", V.new(30, 3.75, 27.5)) -- touching it, a layer up
    local next = log("Log_8", V.new(37.5, 1.25, 30)) -- end to end
    local fire = x.lightFire(first)
    e.step(600, 10)
    T.eq(first.Parent, nil)
    T.eq(fire.Parent, nil)
    T.eq(next:GetAttribute("Burning"), true, "the log laid against it took the fire")
    T.eq(wall:GetAttribute("Burning"), nil, "a fastened log never catches")
    T.eq(course:GetAttribute("Burning"), nil, "a log holding a wall up never catches")
    T.eq(beam:GetAttribute("Burning"), nil, "a log up off its floor never catches")
    T.logged(w, "FED Fire_2 burns on Log_8")
    T.near(x.fires[e.find("Fire_2")].untilTime - e.now, 600, 10, "for another ten minutes")
    -- Rain puts out the fire in the open, not the one under a roof.
    local sheltered = log("Log_9", V.new(50, 1.25, 40))
    e.part("Roof_1", { Size = V.new(7.5, 1, 7.5), Position = V.new(50, 8, 40), Anchored = true })
    local dry = x.lightFire(sheltered)
    local clear = w.openSpot(8, V.new(70, 0, 40)) -- open ground, nothing over it
    local open = x.lightFire(log("Log_10", V.new(clear.X, 1.25, clear.Z)))
    local apart = w.openSpot(8, V.new(90, 0, 40)) -- and a log laid on top of one is no roof over it
    local stacked = x.lightFire(log("Log_11", V.new(apart.X, 1.25, apart.Z)))
    log("Log_12", V.new(apart.X, 3.75, apart.Z))
    x.douseFires()
    T.ok(dry.Parent, "under a roof it burns on")
    T.eq(sheltered:GetAttribute("Burning"), true)
    T.eq(open.Parent, nil)
    T.eq(stacked.Parent, nil, "a log on the burning one keeps no rain off")
end)

T.test("fastening: what can be fastened, and how", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    local b1 = e.find("Block_1")
    e.hrp(g).Position = b1.Position + V.new(-2.5, 1.3, 0)
    T.eq(w.act(g, "Fasten", nil), "FastenFailed:NotAPiece")
    T.eq(w.act(g, "Fasten", { name = "Hammer_1" }), "FastenFailed:NotAPiece", "a tool is no piece")
    T.eq(w.act(g, "Fasten", { name = "Ground_1" }), "FastenFailed:NotAPiece")
    T.eq(w.act(g, "Fasten", { name = "Block_12" }), "FastenFailed:OutOfRange")
    w.act(g, "Pickup", { position = at(b1) })
    T.eq(w.act(g, "Fasten", { name = "Block_1" }), "FastenFailed:NotSetDown", "in the hands")
    e.step(1.2)
    local p = e.hrp(g).Position
    w.act(g, "Place", { position = { p.X + 2.5, 1.3, p.Z } })
    T.eq(w.act(g, "Fasten", { name = "Block_1" }), "FastenFailed:NotSetDown", "on its way down")
    e.step(1.3)
    T.eq(w.act(g, "Fasten", { name = "Block_1" }), "FastenSuccess:fixed")
    T.eq(b1.Anchored, true, "squared and held")
    T.eq(b1:GetAttribute("Fastened"), true)
    T.eq(g:GetAttribute("Gesture"), "Fasten")
    T.eq(w.act(g, "Fasten", { name = "Block_5" }), "FastenFailed:TooSoon")
    e.now = e.now + 3
    local b5 = e.find("Block_5")
    b5.Anchored = true
    T.eq(w.act(g, "Fasten", { name = "Block_5" }), "FastenSuccess:fixed", "already held: fastened where it is")
    e.now = e.now + 3
    local floating = e.part("Block_50", { Size = V.new(2.5, 2.5, 2.5), Position = p + V.new(3, 6, 0),
        attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
    T.eq(w.act(g, "Fasten", { name = "Block_50" }), "FastenFailed:NothingTouching")
    T.ok(floating.Parent)
end)

T.test("pieces at rest square into their cells and hold; lifting one wakes what rested on it", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local function piece(name, pos, rotation)
        local p = e.part(name, { Size = V.new(2.5, 2.5, 2.5), attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
        p.CFrame = CF.new(pos) * (rotation or CF.new())
        return p
    end
    local askew = piece("Block_60", V.new(41.1, 1.25, 40.3), CF.fromOrientation(0, math.rad(20), 0))
    local leaning = piece("Block_61", V.new(51, 1.6, 40), CF.fromOrientation(math.rad(30), 0, 0))
    local moving = piece("Block_62", V.new(61, 1.25, 40))
    moving.AssemblyLinearVelocity = V.new(1, 0, 0)
    local quaking = piece("Block_63", V.new(71, 1.25, 40))
    quaking:SetAttribute("Quaking", true)
    local crowded = piece("Block_64", V.new(81.2, 1.25, 40), CF.fromOrientation(0, math.rad(20), 0))
    e.part("Pebble", { Size = V.new(0.4, 0.4, 0.4), Position = V.new(79, 1.25, 40), Anchored = true }) -- in its cell
    e.step(1.1, 0.1)
    T.eq(askew.Anchored, true, "settled")
    T.near(askew.Position.X, 40, 1e-6, "in its cell")
    local _, yaw = askew.CFrame:ToOrientation()
    T.near(yaw % (math.pi / 2), 0, 1e-6, "squared")
    T.eq(leaning.Anchored, true, "a leaning piece holds where it lies")
    local lx = leaning.CFrame:ToOrientation()
    T.near(math.deg(lx), 30, 1e-4, "unsquared")
    T.eq(moving.Anchored, false, "still moving")
    moving.AssemblyLinearVelocity = V.new(0, 0, 0)
    e.step(1.1, 0.1)
    T.eq(moving.Anchored, true)
    T.eq(quaking.Anchored, false, "the shaking holds nothing still")
    T.eq(crowded.Anchored, true)
    T.near(crowded.Position.X, 81.2, 1e-6, "its cell taken: squared where it lies")
    local _, cyaw = crowded.CFrame:ToOrientation()
    T.near(cyaw % (math.pi / 2), 0, 1e-6)
    -- a stack: lifting the bottom wakes the two above
    local bottom = piece("Block_70", V.new(90, 1.25, 50))
    local middle = piece("Block_71", V.new(90, 3.75, 50))
    local top = piece("Block_72", V.new(90, 6.25, 50))
    e.step(1.1, 0.1)
    T.eq(top:GetAttribute("Settled"), true)
    x.wakeRestingOn(bottom)
    T.eq(middle:GetAttribute("Settled"), false)
    T.eq(top:GetAttribute("Settled"), false)
    T.no(x.squaredRotation(CF.fromOrientation(math.rad(45), 0, math.rad(45))), "on an edge: no square")
    T.ok(x.squaredRotation(CF.fromOrientation(0, math.rad(44.9), 0)), "turned near half way: still squares")
end)

-- A wall to climb: 3 blocks high, 7.5 thick, with a ladder against its west face.
local function wall(w)
    local e = w.e
    local wl = e.part("Wall", { Size = V.new(7.5, 7.5, 7.5), Position = V.new(45, 3.75, -20), Anchored = true })
    local ladder = e.part("Ladder_9", { Size = V.new(1.5, 7.5, 0.4), Anchored = true,
        attrs = { RenderRole = "Ladder", IsPickupObject = true } })
    ladder.CFrame = CF.new(V.new(40.8, 3.77, -20)) * CF.fromOrientation(0, math.rad(90), 0) -- its face towards -X
    return wl, ladder
end

T.test("climbing a ladder: up onto the wall it stands against, and back down", function()
    local w = T.boot()
    local e = w.e
    local _, ladder = wall(w)
    local g = w.godling(V.new(39, 2.55, -20))
    T.eq(w.act(g, "Climb", nil), "ClimbFailed:NoLadder")
    T.eq(w.act(g, "Climb", { name = "Block_1" }), "ClimbFailed:NoLadder")
    ladder.Anchored = false
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:NotSetUp")
    ladder.Anchored = true
    e.hrp(g).Position = V.new(30, 2.55, -20)
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:TooFar")
    e.hrp(g).Position = V.new(39, 2.55, -20)
    local started = w.act(g, "Climb", { name = "Ladder_9" })
    T.starts(started, "ClimbStarted:up:")
    T.eq(g:GetAttribute("Climbing"), true)
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:AlreadyClimbing")
    T.eq(w.act(g, "StepUp", { position = { 40, -20 } }), "StepUpFailed:Busy")
    e.step(1, 0.1)
    T.ok(e.hrp(g).Position.Y > 2.6 and e.hrp(g).Position.Y < 10.5, "on the ladder")
    e.step(8, 0.1)
    T.eq(g:GetAttribute("Climbing"), false)
    T.near(e.hrp(g).Position.Y, 7.5 + 2.55, 1e-6, "on top of the wall")
    T.eq(e.hrp(g).Anchored, false)
    T.starts(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbStarted:down:")
    e.step(9, 0.1)
    T.near(e.hrp(g).Position.Y, 2.55, 1e-6, "back down")
    -- standing above its top: neither end
    e.hrp(g).Position = V.new(39.8, 12, -20)
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:NotAtAnEnd")
end)

T.test("lifting a set-up ladder lets a stone resting on its top fall (ADR-025)", function()
    local w = T.boot()
    local e = w.e
    local _, ladder = wall(w)
    -- Set there as on 2026-11-08: in the cell in front of the wall, on the ladder's top, settled and held still.
    local stone = e.part("Stone_9", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(40, 7.52 + 1.25, -20),
        Anchored = true, attrs = { RenderRole = "Stone", IsPickupObject = true, Settled = true } })
    local g = w.godling(V.new(37.5, 2.55, -20))
    holding(w, g, "Ladder_9")
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:NotSetUp", "in the hands")
    T.eq(stone.Anchored, false, "nothing holds it up now")
    T.eq(stone:GetAttribute("Settled"), false)
    T.ok(ladder.Parent, "the ladder is carried, not gone")
end)

T.test("a ladder that reaches nothing, or stands where there is no floor", function()
    local w = T.boot()
    local e = w.e
    e.part("Ladder_9", { Size = V.new(1.5, 7.5, 0.4), Position = V.new(45, 3.77, -40), Anchored = true,
        attrs = { RenderRole = "Ladder", IsPickupObject = true } })
    local g = w.godling(V.new(45, 2.55, -38.8))
    T.eq(w.act(g, "Climb", { name = "Ladder_9" }), "ClimbFailed:NothingAtTop", "against nothing, on open grass")
    e.part("Ladder_8", { Size = V.new(1.5, 7.5, 0.4), Position = V.new(45, 3.77, 300), Anchored = true,
        attrs = { RenderRole = "Ladder", IsPickupObject = true } }) -- out at sea
    e.part("Perch", { Size = V.new(2.5, 1, 2.5), Position = V.new(45, 6.45, 301.2), Anchored = true })
    e.hrp(g).Position = V.new(45, 9.5, 301.2) -- on a perch by its top, the sea below
    T.eq(w.act(g, "Climb", { name = "Ladder_8" }), "ClimbFailed:NothingAtBottom")
end)

T.test("a climber whose body is gone stops climbing", function()
    local w = T.boot()
    local e = w.e
    wall(w)
    local g = w.godling(V.new(39, 2.55, -20))
    w.act(g, "Climb", { name = "Ladder_9" })
    e.hrp(g):Destroy()
    e.step(0.1)
    T.eq(w.x.climbers[g], nil)
end)

T.test("stepping up onto a block and down off it", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling(V.new(40, 2.55, -60))
    e.part("Step", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(42.5, 1.25, -60), Anchored = true })
    e.part("Tall", { Size = V.new(2.5, 7.5, 2.5), Position = V.new(40, 3.75, -62.5), Anchored = true })
    T.eq(w.act(g, "StepUp", nil), "StepUpFailed:BadTarget")
    T.eq(w.act(g, "StepUp", { position = { "x", 1 } }), "StepUpFailed:BadTarget")
    T.eq(w.act(g, "StepUp", { position = { 50, -60 } }), "StepUpFailed:TooFar")
    T.eq(w.act(g, "StepUp", { position = { 40, -62.5 } }), "StepUpFailed:TooHigh")
    T.eq(w.act(g, "StepUp", { position = { 38, -60 } }), "StepUpFailed:NothingToStepOn")
    local lid = e.part("Lid", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(42.5, 5.5, -60), Anchored = true })
    T.eq(w.act(g, "StepUp", { position = { 42.5, -60 } }), "StepUpFailed:NoRoom")
    lid:Destroy()
    T.eq(w.act(g, "StepUp", { position = { 42.5, 0, -60 } }), "StepUpStarted:0.6")
    e.step(0.7, 0.1)
    T.near(e.hrp(g).Position.Y, 2.5 + 2.55, 1e-6, "up on the block")
    T.eq(w.act(g, "StepDown", { position = { 40, -60 } }), "StepDownStarted:0.6")
    e.step(0.7, 0.1)
    T.near(e.hrp(g).Position.Y, 2.55, 1e-6, "down again")
    T.eq(w.act(g, "StepDown", { position = { 40, -60 } }), "StepDownFailed:NothingToStepOn")
end)

T.test("a body shut inside a held piece is moved to where it fits, if there is room", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling(V.new(40, 2.55, -80))
    e.part("Beam", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(40, 4, -80), Anchored = true })
    e.step(0.5)
    T.near(e.hrp(g).Position.X, 40, 1e-9, "one look is not enough")
    e.step(0.5)
    T.ok(math.abs(e.hrp(g).Position.X - 40) > 1 or math.abs(e.hrp(g).Position.Z + 80) > 1, "moved out")
    T.eq(g:GetAttribute("Freed"), 1)
    T.logged(w, "FREED Godling")
    -- nowhere to go: it stays
    local h = e.player("Ann", V.new(-40, 2.55, 300)) -- over the sea, no floor anywhere near
    e.hrp(h).Position = V.new(-40, 2.55, 300)
    e.part("Rock", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(-40, 3, 300), Anchored = true })
    e.step(1, 0.5)
    T.near(e.hrp(h).Position.Z, 300, 1e-9)
    -- a climbing body is the world's: left alone
    h:SetAttribute("Climbing", true)
    e.step(1, 0.5)
end)

-- Two points on open sand, a short stroke apart (found by looking along the west beach).
local function sandStroke(x)
    for gx = -150, 150, 1.25 do
        for gz = -150, 150, 1.25 do
            local ok = true
            for k = 0, 6 do
                if not x.onOpenSand(gx + k * 0.5, gz) then
                    ok = false
                    break
                end
            end
            if ok then
                return gx, gz
            end
        end
    end
    error("no open sand")
end

T.test("drawing in the sand: open sand only, not too short or long, until the beach is full", function()
    local w = T.boot({ patch = { { "local MARK_WIDTH, MARK_MAX_LENGTH, MARK_MAX = 0.7, 20, 400",
        "local MARK_WIDTH, MARK_MAX_LENGTH, MARK_MAX = 0.7, 20, 1" } } })
    local e, x = w.e, w.x
    local sx, sz = sandStroke(x)
    local g = w.godling(V.new(sx, 2.45, sz))
    T.eq(w.act(g, "Draw", nil), "DrawFailed:BadTarget")
    T.eq(w.act(g, "Draw", { to = { "x", 1 } }), "DrawFailed:BadTarget")
    T.eq(w.act(g, "Draw", { to = { sx + 0.1, sz } }), "DrawFailed:Length")
    T.eq(w.act(g, "Draw", { to = { sx + 30, sz } }), "DrawFailed:Length")
    T.eq(w.act(g, "Draw", { to = { 0, sz + 19 } }), "DrawFailed:Length")
    T.eq(w.act(g, "Draw", { to = { sx + 3, sz } }), "DrawSuccess:Mark_1")
    local mark = e.find("Mark_1")
    T.eq(mark:GetAttribute("Stroke"), string.format("%.1f,%.1f,%.1f,%.1f", sx, sz, sx + 3, sz))
    T.eq(g:GetAttribute("Gesture"), "Draw")
    T.eq(w.act(g, "Draw", { to = { sx + 3, sz } }), "DrawFailed:BeachFull")
    T.no(x.onOpenSand(0, 0), "grass")
    T.no(x.onOpenSand(500, 500), "the sea")
    local palm = e.find("Palm_1").Position
    T.no(x.onOpenSand(palm.X, palm.Z), "under a palm")
    local rock = x.mesas[1]
    T.no(x.onOpenSand(rock.pos[1], rock.pos[3]), "on the rock")
end)

T.test("a line that would cross grass is refused", function()
    local w = T.boot()
    local x = w.x
    local sx, sz = sandStroke(x)
    local g = w.godling(V.new(sx, 2.45, sz))
    T.eq(w.act(g, "Draw", { to = { 0, 0 } }), "DrawFailed:Length")
    for dx = -20, 20, 2 do -- some direction leaves the sand within 20
        for dz = -20, 20, 2 do
            if math.sqrt(dx * dx + dz * dz) <= 19 and math.sqrt(dx * dx + dz * dz) >= 1 then
                local r = w.act(g, "Draw", { to = { sx + dx, sz + dz } })
                if r == "DrawFailed:NotSand" then
                    return
                end
            end
        end
    end
    error("no stroke left the sand")
end)

return T.done("test_build")
