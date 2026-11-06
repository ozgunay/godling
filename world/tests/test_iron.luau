-- Meteoric iron (main.lua METEORIC IRON, sky.iron): a meteor's stone too hot to hold or work while it glows; cooled,
-- hammer blows knock flakes of iron off it; a flake bound onto a tool is its iron edge, and an edged tool does more.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

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

local function fastenOn(w, g, name)
    w.e.now = w.e.now + 3 -- fastening's pause
    return w.act(g, "Fasten", { name = name })
end

-- A meteor's stone, landed on open grass at `spot`, as hot as `heat`.
local function meteorite(e, n, spot, heat)
    return e.part("Meteor_" .. n, { Size = V.new(2.5, 2.5, 2.5), Position = V.new(spot.X, 1.25, spot.Z),
        attrs = { RenderRole = "Stone", IsPickupObject = true, SkyEvent = "Meteor", SkyId = n, Heat = heat,
            LandedAt = 0 } })
end

local function tool(e, name, kind, pos, size)
    return e.part(name, { Size = size or V.new(0.4, 0.4, 1.2), Position = pos,
        attrs = { RenderRole = "Tool", ToolKind = kind, IsPickupObject = true } })
end

T.test("a glowing stone is too hot to hold or work; once it no longer glows, it is a stone in the hands", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local spot = w.openSpot(6)
    local stone = meteorite(e, 3, spot, 0.35)
    e.hrp(g).Position = spot + V.new(-3, 0, 0)
    T.eq(w.act(g, "Pickup", { position = at(stone) }), "PickupFailed:TooHot")
    T.eq(x.heldBlocksByPlayer[g], nil)
    holding(w, g, "Hammer_1", spot + V.new(-3, 0, 0))
    T.eq(strikeAt(w, g, "Meteor_3"), "StrikeTooHot:Meteor_3", "the blow does nothing to it")
    T.eq(stone:GetAttribute("Blows"), nil, "and is not counted")
    T.eq(g:GetAttribute("Gesture"), "Mine")
    stone:SetAttribute("Heat", x.sky.iron.GLOWS_ABOVE) -- dark now, though not yet cold
    T.eq(strikeAt(w, g, "Meteor_3"), "StrikeChipping:1/15")
    x.releaseHeldBlock(g)
    T.eq(w.act(g, "Pickup", { position = at(stone) }), "PickupSuccess")
end)

T.test("hammer blows knock flakes of iron off a cooled stone, three in all; then it gives no more", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local iron = x.sky.iron
    local spot = w.openSpot(8)
    local stone = meteorite(e, 4, spot, 0)
    holding(w, g, "Hammer_1", spot + V.new(-3.5, 0, 0)) -- west of it
    for n = 1, iron.BLOWS_PER_FLAKE - 1 do
        T.eq(strikeAt(w, g, "Meteor_4"), "StrikeChipping:" .. n .. "/" .. iron.BLOWS_PER_FLAKE)
    end
    T.eq(strikeAt(w, g, "Meteor_4"), "StrikeChipped:Iron_1")
    local flake = e.find("Iron_1")
    T.eq(flake:GetAttribute("RenderRole"), "Iron")
    T.eq(flake:GetAttribute("IsPickupObject"), true)
    T.ok(flake.Position.X < stone.Position.X - 1.25, "it fell at the stone's foot, on the striker's side")
    T.ok(flake.Position.Y < 1, "on the ground")
    T.eq(stone:GetAttribute("Flakes"), 1)
    T.eq(stone:GetAttribute("Blows"), 0)
    for _ = 1, 2 * iron.BLOWS_PER_FLAKE do
        strikeAt(w, g, "Meteor_4")
    end
    T.ok(e.find("Iron_3"), "three flakes")
    T.eq(stone:GetAttribute("Flakes"), 3)
    T.eq(strikeAt(w, g, "Meteor_4"), "StrikeSpent:Meteor_4")
    T.eq(stone:GetAttribute("RenderRole"), "Stone", "still a building stone")
    -- a stone fastened in a wall is knocked loose first, as any fastened piece is
    local walled = meteorite(e, 5, spot + V.new(0, 0, 5), 0)
    walled:SetAttribute("Fastened", true)
    e.hrp(g).Position = walled.Position + V.new(-3.5, 1.3, 0)
    T.eq(strikeAt(w, g, "Meteor_5"), "StrikeLoosened:Meteor_5")
    T.eq(strikeAt(w, g, "Meteor_5"), "StrikeChipping:1/15")
    -- an axe or a spear does nothing to it
    x.releaseHeldBlock(g)
    holding(w, g, "Axe_1", walled.Position + V.new(-3.5, 1.3, 0))
    T.eq(strikeAt(w, g, "Meteor_5"), "StrikeNoEffect:Axe")
end)

T.test("a flake bound onto a tool is its iron edge: from the hands onto a tool set down, or the other way", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local spot = w.openSpot(8)
    local spear = tool(e, "Spear_1", "Spear", spot + V.new(2, -2.3, 0), V.new(0.3, 0.3, 4.5))
    local flake1 = e.part("Iron_1", { Size = V.new(0.5, 0.2, 1), Position = spot + V.new(-2, -2.45, 0),
        attrs = { RenderRole = "Iron", IsPickupObject = true } })
    e.part("Iron_2", { Size = V.new(0.5, 0.2, 1), Position = spot + V.new(-2, -2.45, 2),
        attrs = { RenderRole = "Iron", IsPickupObject = true } })
    e.part("Iron_3", { Size = V.new(0.5, 0.2, 1), Position = spot + V.new(-2, -2.45, -2),
        attrs = { RenderRole = "Iron", IsPickupObject = true } })
    holding(w, g, "Iron_1", spot)
    T.eq(fastenOn(w, g, "Spear_1"), "FastenEdge:Spear_1:Iron_1")
    T.eq(spear:GetAttribute("Edge"), "Iron")
    T.eq(flake1.Parent, nil, "the flake is part of the spear now")
    T.eq(x.heldBlocksByPlayer[g], nil, "the hands are empty")
    T.eq(g:GetAttribute("Gesture"), "Fasten")
    holding(w, g, "Iron_2", spot)
    T.eq(fastenOn(w, g, "Spear_1"), "FastenFailed:HasEdge:Spear_1")
    T.ok(e.find("Iron_2"), "a tool takes one edge: the flake is kept")
    T.eq(w.act(g, "Fasten", { name = "Spear_1" }), "FastenFailed:TooSoon")
    x.releaseHeldBlock(g)
    -- the other way: the axe in the hands, the flake on the ground
    local axe = holding(w, g, "Axe_1", spot)
    T.eq(fastenOn(w, g, "Iron_3"), "FastenEdge:Axe_1:Iron_3")
    T.eq(axe:GetAttribute("Edge"), "Iron")
    T.eq(x.heldBlocksByPlayer[g], axe, "the axe stays in the hands")
    T.eq(e.find("Iron_3"), nil)
    T.eq(fastenOn(w, g, "Iron_2"), "FastenFailed:HasEdge:Axe_1")
    e.hrp(g).Position = spot + V.new(20, 0, 0)
    T.eq(fastenOn(w, g, "Iron_2"), "FastenFailed:OutOfRange")
    -- a flake and anything else is no edge: an ordinary fastening, which a tool is not
    x.releaseHeldBlock(g)
    holding(w, g, "Iron_2", spot)
    T.eq(x.sky.iron.pair(x.heldBlocksByPlayer[g], e.find("Block_1")), nil)
    e.find("Hammer_1").Position = spot + V.new(2, -2.35, 2) -- set down beside it
    T.eq(fastenOn(w, g, "Hammer_1"), "FastenEdge:Hammer_1:Iron_2")
    -- a flake still moving into the hands of another is not set down
    local flake4 = e.part("Iron_4", { Size = V.new(0.5, 0.2, 1), Position = spot + V.new(1, -2.45, 1),
        attrs = { RenderRole = "Iron", IsPickupObject = true } })
    local other = e.player("Other")
    x.heldBlocksByPlayer[other] = flake4
    holding(w, g, "Spear_1", spot)
    T.eq(fastenOn(w, g, "Iron_4"), "FastenFailed:NotSetDown")
end)

T.test("an iron edge: the spear catches more, further out; the axe and the hammer need fewer blows", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling()
    local iron = x.sky.iron
    -- the spear: 0.85 misses with a wooden point (CATCH_CHANCE 0.6), not with an iron one
    local spear = tool(e, "Spear_1", "Spear", V.new(0, 0.25, 0), V.new(0.3, 0.3, 4.5))
    holding(w, g, "Spear_1")
    local fish = e.find("Fish_1")
    e.hrp(g).Position = fish.Position + V.new(-8, 2, 0)
    table.insert(e.randoms, 0.85)
    T.eq(strikeAt(w, g, "Fish_1"), "StrikeMissed:Fish_1")
    spear:SetAttribute("Edge", "Iron")
    e.hrp(g).Position = fish.Position + V.new(-8, 2, 0)
    table.insert(e.randoms, 0.85)
    T.eq(strikeAt(w, g, "Fish_1"), "StrikeCaught:Catch_1")
    local far = e.find("Fish_2")
    e.hrp(g).Position = far.Position + V.new(-(6 + 2.5 + 1), 2, 0) -- past a wooden point's reach, not an iron one's
    table.insert(e.randoms, 0.1)
    T.starts(strikeAt(w, g, "Fish_2"), "StrikeCaught:")
    spear:SetAttribute("Edge", nil)
    local farther = e.find("Fish_3")
    e.hrp(g).Position = farther.Position + V.new(-(6 + 2.5 + 1), 2, 0)
    T.eq(strikeAt(w, g, "Fish_3"), "StrikeFailed:OutOfRange")
    x.releaseHeldBlock(g)
    -- the axe: a palm in CHOPS blows, a log carved in CARVES
    local axe = e.find("Axe_1")
    axe:SetAttribute("Edge", "Iron")
    local palm = e.find("Palm_2")
    holding(w, g, "Axe_1", palm.Position + V.new(-3, -7.45, 0))
    T.eq(strikeAt(w, g, "Palm_2"), "StrikeHit:1/" .. iron.CHOPS)
    T.starts(strikeAt(w, g, "Palm_2"), "StrikeFelled:Log_")
    e.part("Log_7", { Size = V.new(7.5, 2.5, 2.5), Position = V.new(30, 1.25, 30),
        attrs = { RenderRole = "Log", IsPickupObject = true } })
    e.hrp(g).Position = V.new(25, 2.55, 30)
    T.eq(iron.CARVES, 1)
    T.starts(strikeAt(w, g, "Log_7"), "StrikeCarved:Spear_")
    x.releaseHeldBlock(g)
    -- the hammer: a quarry stone in BREAKS blows
    e.find("Hammer_1"):SetAttribute("Edge", "Iron")
    local quarry = e.find("Quarry")
    holding(w, g, "Hammer_1", quarry.Position + V.new(0, 0.05, -(3.75 + 2)))
    T.eq(strikeAt(w, g, "Quarry"), "StrikeHit:1/" .. iron.BREAKS)
    T.starts(strikeAt(w, g, "Quarry"), "StrikeBroke:Stone_")
end)

T.test("a restart keeps the flakes, the edges and the count of flakes made", function()
    local save = [[sky.saved = {["pieces"] = {
        {["name"] = "Iron_4", ["pos"] = {6.0, 0.1, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {0.5, 0.2, 1.0},
         ["color"] = {0.26, 0.25, 0.24}, ["anchored"] = false, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Iron", ["IsPickupObject"] = true}},
        {["name"] = "Spear_2", ["pos"] = {8.0, 0.2, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {0.3, 0.3, 4.5},
         ["color"] = {0.6, 0.45, 0.3}, ["anchored"] = false, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Tool", ["ToolKind"] = "Spear", ["Edge"] = "Iron", ["IsPickupObject"] = true}},
        {["name"] = "Meteor_7", ["pos"] = {12.0, 1.25, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {2.5, 2.5, 2.5},
         ["color"] = {0.25, 0.22, 0.2}, ["anchored"] = true, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Stone", ["SkyEvent"] = "Meteor", ["IsPickupObject"] = true,
                      ["LandedAt"] = 0.0, ["Heat"] = 0.0, ["Flakes"] = 1.0, ["Blows"] = 4.0}}},
      ["felled"] = {},
      ["roles"] = {"PickupObject", "Stone", "Log", "Tool", "Ladder", "Boulder", "Rock", "Coconut", "Catch", "Volleyball", "Crater", "SandMark", "Iron"},
      ["counters"] = {["Sky"] = 7.0, ["Iron"] = 4.0},
      ["clock"] = 4800.0, ["body"] = {["pos"] = {12.0, 2.55, 1.0}, ["health"] = 90.0, ["hunger"] = 80.0, ["wet"] = 0.0}} -- ISLAND SAVE]]
    local w = T.boot({ patch = { { "sky.saved = nil -- ISLAND SAVE", (save:gsub("\n%s*", " ")) } } })
    local e, x = w.e, w.x
    T.eq(e.find("Iron_4"):GetAttribute("RenderRole"), "Iron")
    T.eq(e.find("Spear_2"):GetAttribute("Edge"), "Iron")
    T.eq(x.sky.iron.made, 4)
    local g = w.godling()
    T.eq(e.find("Hammer_1"), nil, "the start's hammer was not in the save: gone")
    tool(e, "Hammer_3", "Hammer", V.new(12, 0.2, 1.5))
    holding(w, g, "Hammer_3", e.find("Meteor_7").Position + V.new(0, 1.3, -3.5))
    T.eq(strikeAt(w, g, "Meteor_7"), "StrikeChipping:5/15", "the blows already struck count")
    for _ = 1, 10 do
        strikeAt(w, g, "Meteor_7")
    end
    T.ok(e.find("Iron_5"), "numbered on from the save")
end)

return T.done("test_iron")
