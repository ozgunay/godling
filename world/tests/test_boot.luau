-- The island as the world script builds it, and who comes and goes.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

T.test("the island is built: sea, sand and grass, rock, trees, the raft, the quarry and the starting pieces", function()
    local w = T.boot()
    local e, x = w.e, w.x
    T.eq(e.Workspace.Gravity, 10, "gravity")
    T.eq(e.find("Ocean"):GetAttribute("RenderRole"), "Ocean")
    T.eq(e.find("Beach_1"):GetAttribute("Surface"), "Sand")
    T.eq(e.find("Ground_1"):GetAttribute("Surface"), "Grass")
    T.eq(e.find("Peak_1"):GetAttribute("Feature"), "Peak")
    T.eq(e.find("Tree_1"), nil, "the island has no inland trees, only palms")
    T.eq(e.find("Palm_1"):GetAttribute("ModelUrl"), "asset://palm.glb")
    T.eq(e.find("Raft"):GetAttribute("RenderRole"), "Wreck")
    T.eq(e.find("Quarry"):GetAttribute("ModelUrl"), "asset://quarry.glb")
    for _, name in ipairs({ "Hammer_1", "Axe_1", "Ladder_1", "Boulder_1", "Boulder_2", "Block_12", "Rock_1", "Volleyball",
        "Clock", "SkyPedestal", "BoundaryNorth" }) do
        T.ok(e.find(name), name .. " is there")
    end
    T.eq(e.find("Boulder_1").Anchored, true, "a boulder holds where it lies")
    T.eq(e.find("Hammer_1"):GetAttribute("ToolKind"), "Hammer")
    T.eq(#x.trees > 20, true, "palms all round")
    local fish = 0
    for _, inst in ipairs(e.Workspace:GetChildren()) do
        if inst:GetAttribute("RenderRole") == "Fish" then
            fish = fish + 1
        end
    end
    T.eq(fish, 12, "fish in the shallows")
    T.logged(w, "=== Mesa World ===")
end)

T.test("a world that was there before keeps its parts and loses what it no longer has", function()
    local w = T.boot({
        before = function(e)
            e.part("Ground", { Size = V.new(10, 1, 10) }) -- an earlier layout's ground
            e.part("GroundNE", { Size = V.new(10, 1, 10) })
            e.part("Ocean")
            e.part("Block_1", { Position = V.new(3, 1.25, 3) })
            e.part("Rock_1", { Position = V.new(9, 1, 9) })
            e.part("Clock")
            e.part("SkyPedestal")
            e.part("Volleyball")
            e.part("Hammer_1")
            e.player("Ann", V.new(5, 2.55, 5), { quiet = true }) -- already in the world when it starts
        end,
    })
    local e = w.e
    T.eq(e.find("Ground"), nil, "the old ground is gone")
    T.eq(e.find("GroundNE"), nil)
    T.eq(e.find("Block_1"):GetAttribute("RenderRole"), "PickupObject", "the old block is a block again")
    T.eq(e.find("Block_1").Position.X, 3, "and stays where it was")
    T.eq(e.find("Rock_1"):GetAttribute("RenderRole"), "Rock")
    local ann = e.Players:GetPlayers()[1]
    T.eq(ann:GetAttribute("LastActionResult"), "Ready", "a player already there is set up")
    T.eq(e.hrp(ann).Position.X, 5, "and left where it stands")
end)

T.test("players join, and leave with what they held", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    T.eq(g:GetAttribute("LastActionResult"), "Ready")
    T.eq(g:GetAttribute("BaseWalkSpeed"), 16)
    T.eq(e.humanoid(g).JumpPower, 15, "a person's hop")
    T.eq(e.hrp(g):GetAttribute("ModelUrl"), "asset://godling.glb")
    T.near(e.hrp(g).Position.X, w.x.PLAYER_SPAWN_POSITION.X, 1e-9, "at the spawn by the raft")
    local sky = w.skyPlayer()
    T.near(e.hrp(sky).Position.Y, -40, 1e-9, "the guest panel's body is parked under the island")
    local plain = e.player("Ghost", nil, { noHumanoid = true })
    T.eq(plain:GetAttribute("LastActionResult"), "Ready")
    local bodiless = e.player("Spirit", nil, { noCharacter = true })
    T.eq(bodiless:GetAttribute("LastActionResult"), "Ready")
    e.player("Sky", nil, { noCharacter = true }) -- a guest panel without a body yet
    -- Godling picks up a block and leaves: the block goes with it
    local block = e.find("Block_1")
    e.hrp(g).Position = block.Position + V.new(2, 1.3, 0)
    T.eq(w.act(g, "Pickup", { position = { block.Position.X, block.Position.Y, block.Position.Z } }), "PickupSuccess")
    e.leave(g)
    T.eq(block.Parent, nil, "what it held is gone with it")
    e.leave(sky) -- leaving with empty hands
end)

T.test("a player without a humanoid sends nothing the world acts on", function()
    local w = T.boot()
    local p = w.e.player("Ghost", nil, { noHumanoid = true })
    p:SetAttribute("LastActionResult", "untouched")
    w.act(p, "Jump", {})
    T.eq(p:GetAttribute("LastActionResult"), "untouched")
end)

T.test("a world without the agent input service still starts", function()
    local w = T.boot({ engine = { noInputService = true } })
    T.ok(w.e.find("Clock"))
end)

T.test("the clock turns: hours, days and the start at seven", function()
    local w = T.boot()
    local clock = w.e.find("Clock")
    T.eq(clock:GetAttribute("TimeOfDay"), 7)
    w.e.step(1)
    T.near(clock:GetAttribute("TimeOfDay"), 7.01, 1e-9)
    T.eq(clock:GetAttribute("Day"), 1)
    w.e.step(2400, 100)
    T.eq(clock:GetAttribute("Day"), 2, "a 40-minute day")
end)

T.test("a body that falls out of the world is put back at the spawn", function()
    local w = T.boot()
    local g = w.godling()
    w.e.hrp(g).Position = V.new(0, -500, 0)
    w.e.step(0.1)
    T.near(w.e.hrp(g).Position.Y, 5, 1e-9)
    T.ok(w.e.humanoid(g).Cancels > 0, "and its walk is called off")
end)

T.test("the island is put back as a run left it (sky.restore)", function()
    local save = [[sky.saved = {["pieces"] = {
        {["name"] = "Crater_3", ["pos"] = {10.0, 0.3, 10.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {8.0, 0.6, 8.0},
         ["color"] = {0.2, 0.2, 0.2}, ["anchored"] = true, ["collide"] = false,
         ["attrs"] = {["RenderRole"] = "Crater", ["SkyId"] = 3.0}},
        {["name"] = "Block_1", ["pos"] = {2.5, 1.25, 5.0}, ["turn"] = {0.0, 1.5708, 0.0}, ["size"] = {2.5, 2.5, 2.5},
         ["color"] = {0.5, 0.5, 0.5}, ["anchored"] = true, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "PickupObject", ["Fastened"] = true}},
        {["name"] = "Stone_7", ["pos"] = {5.0, 1.25, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {2.5, 2.5, 2.5},
         ["color"] = {0.5, 0.5, 0.5}, ["anchored"] = true, ["collide"] = true, ["attrs"] = {["RenderRole"] = "Stone"}},
        {["name"] = "Coconut_4", ["pos"] = {6.0, 0.5, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {0.9, 0.9, 0.9},
         ["color"] = {0.5, 0.3, 0.2}, ["anchored"] = false, ["collide"] = true, ["attrs"] = {["RenderRole"] = "Coconut"}},
        {["name"] = "Mark_2", ["pos"] = {7.0, 0.0, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {3.0, 0.06, 0.7},
         ["color"] = {0.6, 0.5, 0.4}, ["anchored"] = true, ["collide"] = false, ["attrs"] = {["RenderRole"] = "SandMark"}},
        {["name"] = "Meteor_5", ["pos"] = {12.0, 1.25, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {2.5, 2.5, 2.5},
         ["color"] = {0.25, 0.22, 0.2}, ["anchored"] = true, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Stone", ["SkyEvent"] = "Meteor", ["SkyId"] = 5.0, ["ModelUrl"] = "asset://meteor.glb",
                      ["LandedAt"] = 1200.0, ["Heat"] = 0.3}},
        {["name"] = "Hammer_1", ["pos"] = {8.0, 0.2, 5.0}, ["turn"] = {0.0, 0.0, 0.0}, ["size"] = {0.4, 0.4, 1.2},
         ["color"] = {0.5, 0.4, 0.2}, ["anchored"] = false, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Tool", ["ToolKind"] = "Hammer"}}},
      ["felled"] = {{["name"] = "Palm_1", ["pos"] = {0.0, 0.625, 0.0}, ["turn"] = {0.0, 0.0, 0.0},
         ["size"] = {2.5, 1.25, 2.5}, ["color"] = {0.4, 0.3, 0.2}, ["anchored"] = true, ["collide"] = true,
         ["attrs"] = {["RenderRole"] = "Stump", ["ModelUrl"] = "asset://stump.glb"}}},
      ["roles"] = {"PickupObject", "Stone", "Log", "Tool", "Ladder", "Boulder", "Rock", "Coconut", "Catch", "Volleyball", "Crater", "SandMark"},
      ["counters"] = {["Sky"] = 9.0, ["Block"] = 12.0, ["Stone"] = 7.0, ["Log"] = 3.0, ["Mark"] = 2.0, ["Coconut"] = 4.0},
      ["clock"] = 2400.0, ["body"] = {["pos"] = {1.0, 2.55, 2.0}, ["health"] = 60.0, ["hunger"] = 40.0, ["wet"] = 10.0}} -- ISLAND SAVE]]
    local w = T.boot({ patch = { { "sky.saved = nil -- ISLAND SAVE", (save:gsub("\n%s*", " ")) } } })
    local e, x = w.e, w.x
    T.eq(e.find("Block_1"):GetAttribute("Fastened"), true, "the fastened block is back, fastened")
    T.near(e.find("Block_1").Position.Z, 5, 1e-9)
    T.ok(e.find("Stone_7"), "the quarried stone is back")
    T.ok(e.find("Crater_3"), "the crater too")
    T.eq(e.find("Block_2"), nil, "a starting block that was gone stays gone")
    T.eq(e.find("Rock_1"), nil)
    T.eq(e.find("Palm_1"):GetAttribute("RenderRole"), "Stump", "the felled palm is a stump again")
    T.eq(#x.sky.meteor.craters, 1)
    T.logged(w, "ISLAND restored: 7 pieces, 1 felled trees, day 2")
    -- A meteor's stone cools on where it was: it landed at 1200 s, half a day before the save's clock (2400 s).
    T.eq(e.find("Meteor_5"):GetAttribute("ModelUrl"), "asset://meteor.glb")
    T.eq(e.find("Crater_3"):GetAttribute("Heat"), 0, "a crater from before stones cooled is long cold")
    T.eq(#x.sky.meteor.hot, 1)
    e.step(x.sky.meteor.COOL_EVERY + 0.1, 0.5)
    T.eq(e.find("Meteor_5"):GetAttribute("Heat"), 0.25, "(1 - 0.5)^2: a dull glow, as it was when the run stopped")
    local g = w.godling()
    T.near(e.hrp(g).Position.X, 1, 1e-9, "Godling stands where it stood")
    T.eq(g:GetAttribute("Health"), 60)
    local again = e.player("Godling2")
    T.near(e.hrp(again).Position.X, x.PLAYER_SPAWN_POSITION.X, 1e-9, "only once")
    w.skyPlayer() -- the guest panel never takes Godling's body
end)

return T.done("test_boot")
