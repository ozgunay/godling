-- The sky's powers, as the guest panel calls them: stones and logs, lightning, regrowth, the meteor and its blast,
-- the earthquake, notes from viewers; and the panel's own bodiless player.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

-- An island with Godling on open grass and the guest panel joined; power(name, data) calls a sky power.
local function sky(options)
    local w = T.boot(options)
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

local function aim(p, dx, dz)
    return { at = { x = p.X + dx, z = p.Z + dz } }
end

local function piece(e, name, pos, role, extra)
    local attrs = { RenderRole = role or "PickupObject", IsPickupObject = true }
    for k, v in pairs(extra or {}) do
        attrs[k] = v
    end
    return e.part(name, { Size = V.new(2.5, 2.5, 2.5), Position = pos, Anchored = true, attrs = attrs })
end

T.test("only the guest panel calls on the sky, and only for powers the world knows", function()
    local w = sky()
    T.eq(w.act(w.g, "Sky", { power = "Stone" }), "SkyFailed:NotTheSky")
    T.eq(w.power("Flood"), "SkyFailed:UnknownPower")
    T.eq(w.act(w.panel, "Sky", nil), "SkyFailed:UnknownPower")
    w.e.leave(w.g)
    T.eq(w.power("Stone"), "SkyFailed:NobodyHere")
end)

T.test("a stone and a log from the sky: near Godling, at its feet when aimed at it, never on what it built", function()
    local w = sky()
    local e = w.e
    T.eq(w.power("Stone"), "SkyDone:Stone:1")
    local stone = e.find("Stone_1")
    T.near(stone.Position.Y, 12, 1e-9, "dropped from on high")
    T.eq(stone:GetAttribute("SkyEvent"), "Stone")
    T.logged(w, "SKY Stone #1 dropped Stone_1")
    T.eq(w.power("Log", aim(w.spot, 1, 1)), "SkyDone:Log:2", "aimed at Godling")
    local log = e.find("Log_1")
    local d = Vector3 and 0 or 0
    local dx, dz = log.Position.X - w.spot.X, log.Position.Z - w.spot.Z
    T.near(math.sqrt(dx * dx + dz * dz), 3.5, 1e-6, "at its feet")
    T.eq(w.power("Stone", aim(w.spot, 9, 0)), "SkyDone:Stone:3", "aimed beside it")
    T.eq(w.power("Stone", aim(w.spot, 80, 0)), "SkyFailed:TooFar")
    T.eq(w.power("Stone", { at = { x = "west" } }), "SkyDone:Stone:4", "an aim it cannot read: the world chooses")
    T.ok(d == 0)
end)

T.test("a gift goes round what is built and round bodies, and finds no room in a crowd", function()
    local w = sky()
    local e, x = w.e, w.x
    local p = w.spot
    piece(e, "Block_90", p + V.new(9, -1.3, 0))
    local turned = piece(e, "Block_91", p + V.new(9, -1.3, 5))
    turned.CFrame = T.CFrame.new(turned.Position) * T.CFrame.fromOrientation(0, math.rad(30), math.rad(90))
    T.no(x.sky.aim.fits("Log", p.X + 9, p.Z, 0), "a log across the block")
    T.no(x.sky.aim.fits("Stone", p.X + 1, p.Z, 0), "on Godling")
    T.ok(x.sky.aim.fits("Stone", p.X + 9, p.Z - 6, 0))
    T.no(x.sky.aim.fits("Log", p.X + 7, p.Z + 5, math.rad(30)), "against a piece lying askew")
    w.e.player("Spirit", nil, { noCharacter = true })
    T.ok(x.sky.aim.fits("Stone", p.X - 9, p.Z - 9, 0), "a bodiless player takes no room")
    -- every spot round Godling taken: no room at its feet, nor near the aim
    for i = 1, 30 do
        local a = i / 30 * 2 * math.pi
        for r = 2, 16, 2.5 do
            piece(e, "Crowd_" .. i .. "_" .. r, p + V.new(math.cos(a) * r, -1.3, math.sin(a) * r))
        end
    end
    T.eq(w.power("Stone", aim(p, 0.1, 0)), "SkyFailed:NoClearSpot")
    T.eq(w.power("Log", aim(p, 5, 5)), "SkyFailed:NoClearSpot")
    T.eq(w.power("Stone"), "SkyFailed:NoClearSpot")
end)

T.test("unaimed, a log where a stone would fit is moved till it fits", function()
    -- The first unaimed spot (a fixed sequence) found in one world; in a second, the same, a block lies just past a
    -- stone's room from it but in a log's way.
    local first = sky()
    local spot = first.spot
    local sx, sz = first.x.skySpotNear(first.g)
    T.ok(sx, "a spot")
    local w = T.boot({ before = function(e2)
        e2.part("Block_95", { Size = V.new(2.5, 2.5, 2.5), Position = V.new(sx + 4.5, 1.25, sz), Anchored = true,
            attrs = { RenderRole = "PickupObject", IsPickupObject = true } })
    end })
    w.godling(spot)
    local panel = w.skyPlayer()
    T.eq(w.act(panel, "Sky", { power = "Log" }), "SkyDone:Log:1")
    local log = w.e.find("Log_1")
    T.ok(math.abs(log.Position.X - sx) > 0.01 or math.abs(log.Position.Z - sz) > 0.01, "moved off the stone's spot")
end)

T.test("lightning fells the palm nearest the aim, if it stands clear of Godling and its walls", function()
    local w = sky()
    local e, x = w.e, w.x
    local palm = e.find("Palm_6")
    local p = palm.Position
    T.eq(w.power("Lightning", { at = { x = p.X, z = p.Z } }), "SkyFailed:TooFar")
    e.hrp(w.g).Position = V.new(p.X + 20, 2.45, p.Z)
    T.starts(w.power("Lightning", { at = { x = p.X, z = p.Z } }), "SkyDone:Lightning:")
    T.eq(palm:GetAttribute("RenderRole"), "Stump")
    T.eq(e.find("Log_1"):GetAttribute("FromTree"), "Palm_6")
    T.eq(e.find("Log_1"):GetAttribute("SkyEvent"), "Lightning")
    T.ok(e.find("SkyBolt_1"), "a bolt shows")
    e.step(0.6, 0.1)
    T.eq(e.find("SkyBolt_1"), nil, "and is gone")
    T.starts(w.power("Lightning"), "SkyDone:Lightning:", "unaimed: the palm nearest Godling")
    for _, t in ipairs(x.trees) do
        t.part:SetAttribute("RenderRole", "Stump")
    end
    T.eq(w.power("Lightning"), "SkyFailed:NoSafePalm")
end)

T.test("a stump grows back at a word, the one nearest the aim", function()
    local w = sky()
    local e, x = w.e, w.x
    T.eq(w.power("Regrow"), "SkyFailed:NoStump")
    local palm = e.find("Palm_7")
    x.fellTree(palm, palm.Position + V.new(-3, 0, 0))
    T.starts(w.power("Regrow"), "SkyDone:Regrow:")
    T.eq(palm:GetAttribute("RenderRole"), "Tree")
    T.eq(palm:GetAttribute("SkyEvent"), "Regrow")
    x.fellTree(palm, palm.Position + V.new(0, 0, 3))
    e.hrp(w.g).Position = V.new(palm.Position.X + 10, 2.45, palm.Position.Z)
    T.starts(w.power("Regrow", { at = { x = palm.Position.X, z = palm.Position.Z } }), "SkyDone:Regrow:")
    T.eq(w.power("Regrow", { at = { x = palm.Position.X + 300, z = 0 } }), "SkyFailed:TooFar")
end)

T.test("a meteor: a shadow, a wait for a clear shadow, the fall, the blast, the crater", function()
    local w = sky()
    local e, x = w.e, w.x
    local p = w.spot
    T.eq(w.power("Meteor"), "SkyDone:Meteor:1")
    T.eq(w.power("Meteor"), "SkyFailed:TooSoon:60", "one a minute")
    local shadow = e.find("SkyShadow_1")
    T.eq(shadow:GetAttribute("LandsIn"), 40)
    local fall = x.skyFalls[1]
    e.step(10, 1)
    T.eq(shadow:GetAttribute("LandsIn"), 30)
    e.hrp(w.g).Position = V.new(fall.x, 2.55, fall.z) -- Godling under the shadow: unaimed, it waits
    e.step(31, 1)
    T.eq(shadow:GetAttribute("LandsIn"), 0)
    T.eq(e.find("Meteor_1"), nil, "waiting for a clear shadow")
    e.hrp(w.g).Position = p
    e.step(0.1)
    local stone = e.find("Meteor_1")
    T.ok(stone, "it falls")
    T.eq(stone.CanCollide, false, "carried down by the world")
    e.step(1, 0.1)
    T.ok(stone.Position.Y < 40 and stone.Position.Y > 1.25, "falling")
    e.step(1, 0.1)
    T.eq(stone.CanCollide, true, "landed")
    T.ok(e.find("Crater_1"), "a crater")
    T.near(e.find("Crater_1").Position.Y, 0.3, 1e-9, "lying on the ground")
    T.ok(e.find("Blast_1"), "the blast shows")
    T.eq(e.find("Clock"):GetAttribute("MeteorId"), 1)
    e.step(3.1, 0.5)
    T.eq(e.find("Blast_1"), nil, "for a moment")
    T.logged(w, "SKY Meteor #1 blasted at")
end)

T.test("an aimed meteor blasts what it hits: smashes, breaks fastenings, throws, fells, hurts and knocks down", function()
    local w = sky()
    local e, x = w.e, w.x
    local palm = e.find("Palm_8")
    local c = V.new(palm.Position.X + 3, 0, palm.Position.Z)
    e.hrp(w.g).Position = V.new(c.X + 4, 2.55, c.Z) -- close enough to be hurt
    local hit = piece(e, "Block_80", c + V.new(0, 1.25, 0), "PickupObject", { Settled = true })
    local mortared = piece(e, "Block_82", c + V.new(-4.5, 1.25, 0), "Stone", { Fastened = true })
    local far = piece(e, "Block_83", c + V.new(0, 1.25, -7.5), "Log", { Fastened = true })
    local loose = piece(e, "Block_84", c + V.new(5.5, 1.25, 5.5))
    local beside = piece(e, "Block_85", c + V.new(4.5, 1.25, 0)) -- beside where the stone lands: away along x
    local carried = piece(e, "Block_86", c + V.new(0, 1.25, 2))
    x.heldBlocksByPlayer[w.panel] = carried -- what someone holds is not blasted
    local before = { health = 100 }
    T.eq(w.power("Meteor", { at = { x = c.X, z = c.Z } }), "SkyDone:Meteor:1")
    e.step(41, 1)
    e.step(3, 0.1)
    T.eq(hit.Parent, nil, "smashed")
    T.eq(mortared:GetAttribute("Fastened"), false, "its fastening broke")
    T.ok(mortared.AssemblyLinearVelocity.Magnitude > 0, "and it was thrown")
    T.eq(far:GetAttribute("Fastened"), true, "too far to break")
    T.ok(loose.AssemblyLinearVelocity.Y > 0, "thrown up")
    T.ok(beside.AssemblyLinearVelocity.X > 0, "thrown out")
    T.ok(carried.Parent, "not what someone holds")
    T.eq(palm:GetAttribute("RenderRole"), "Stump", "the palm close by is felled")
    T.eq(e.find("Log_1"):GetAttribute("SkyEvent"), "Meteor")
    T.ok(w.g:GetAttribute("Health") < before.health, "Godling is hurt")
    T.eq(w.g:GetAttribute("KnockDowns"), 1, "and knocked down")
    local clock = e.find("Clock")
    T.eq(clock:GetAttribute("MeteorSmashed"), 1)
    T.eq(clock:GetAttribute("MeteorFelled") >= 1, true)
    T.eq(clock:GetAttribute("MeteorHurt"), 1)
    e.step(3, 0.5)
    T.eq(w.g:GetAttribute("KnockedDown"), false, "it gets up")
    T.eq(w.g:GetAttribute("Gesture"), "GetUp")
end)

T.test("a meteor on Godling's head, with someone standing in the crater, and one that fells it", function()
    local w = sky()
    local e, x = w.e, w.x
    local p = w.spot
    x.surviving[w.g] = { hunger = 100, health = 100, beat = 0 }
    T.eq(w.power("Meteor", aim(p, 0, 0)), "SkyDone:Meteor:1")
    e.step(40.1, 0.1)
    e.step(2, 0.1)
    local stone = e.find("Meteor_1")
    local d = (V.new(stone.Position.X, 0, stone.Position.Z) - V.new(p.X, 0, p.Z)).Magnitude
    T.ok(d >= 2.5, "the stone rests beside the body, not in it")
    -- a second, with Godling weak: the mercy rule
    x.surviving[w.g].health = 10
    x.sky.meteor.last = -math.huge
    T.eq(w.power("Meteor", aim(p, 3, 3)), "SkyFailed:GodlingIsWeak")
    x.surviving[w.g].health = 30
    T.eq(w.power("Meteor", aim(p, 3, 3)), "SkyDone:Meteor:2")
    x.surviving[w.g].health = 20 -- the blast faints it: no knock-down on top
    e.step(40.1, 0.1)
    e.step(2, 0.1)
    T.eq(w.g:GetAttribute("Faints"), 1)
end)

T.test("a meteor aimed at the sea, or with nowhere clear to land, and the craters that are kept", function()
    local w = sky()
    local e, x = w.e, w.x
    local spawn = x.PLAYER_SPAWN_POSITION
    e.hrp(w.g).Position = V.new(spawn.X, 2.45, spawn.Z)
    local seaward = nil
    for dx = -60, 60, 5 do
        for dz = -60, 60, 5 do
            if not seaward and math.sqrt(dx * dx + dz * dz) < 59 and not x.overLand(spawn.X + dx, spawn.Z + dz) then
                seaward = { x = spawn.X + dx, z = spawn.Z + dz }
            end
        end
    end
    T.eq(w.power("Meteor", { at = seaward }), "SkyFailed:NotOnLand")
    e.hrp(w.g).Position = V.new(500, 2.55, 500) -- out at sea: no clear spot near
    T.eq(w.power("Meteor"), "SkyFailed:NoClearSpot")
    T.eq(w.power("Note", { text = "hello" }), "SkyFailed:NoClearSpot")
    T.eq(w.power("Stone"), "SkyFailed:NoClearSpot")
    -- nine blasts: the oldest crater goes
    for n = 1, 9 do
        local stone = e.part("Meteor_x" .. n, { Size = V.new(2.5, 2.5, 2.5) })
        local shadow = e.part("Shadow_x" .. n)
        x.sky.meteor.blast({ n = 100 + n, x = 30 + n * 10, z = 300, stone = stone, shadow = shadow }, 0)
    end
    T.eq(#x.sky.meteor.craters, 8)
    T.eq(e.find("Crater_101"), nil)
    T.eq(x.sky.meteor.groundAt(500, 500), 0, "the sea's surface is 0 too")
end)

T.test("the earthquake: a rumble, Godling braces, the shaking wakes loose pieces, and it dies away", function()
    local w = sky()
    local e, x = w.e, w.x
    local p = w.spot
    T.eq(w.act(w.g, "Brace", {}), "BraceFailed:StillGround")
    T.eq(w.power("Earthquake"), "SkyFailed:NothingBuiltYet")
    local pieces = {}
    for i = 1, 16 do
        pieces[i] = piece(e, "Block_" .. (100 + i), p + V.new(5 + (i % 4) * 2.5, -1.3, 5 + math.floor(i / 4) * 2.5))
    end
    pieces[16]:SetAttribute("Fastened", true)
    -- Godling stands on a block: that one, and the one under it, hold
    local plinth = piece(e, "Block_200", p + V.new(-5, -1.3, -5))
    local step = piece(e, "Block_201", p + V.new(-5, 1.2, -5))
    e.hrp(w.g).Position = p + V.new(-5, 2.5 + 2.5, -5)
    local ann = e.player("Ann", p + V.new(-8, 0, 8)) -- caught unbraced
    local climber = e.player("Climber", p + V.new(-9, 0, -9))
    x.climbers[climber] = { path = { e.hrp(climber).Position, e.hrp(climber).Position }, times = { 1000 }, leg = 1, t = 0 }
    T.eq(w.act(climber, "Brace", {}), "BraceFailed:StillGround")
    T.starts(w.power("Earthquake"), "SkyDone:Earthquake:")
    T.eq(w.power("Earthquake"), "SkyFailed:AlreadyShaking")
    T.eq(w.g:GetAttribute("Gesture"), "LookAround")
    T.eq(w.act(climber, "Brace", {}), "BraceFailed:Climbing")
    local clock = e.find("Clock")
    e.step(2, 0.5)
    T.eq(clock:GetAttribute("QuakePhase"), "rumble")
    T.eq(w.act(w.g, "Brace", {}), "Braced")
    T.eq(e.hrp(w.g).Anchored, true)
    e.step(6.5, 0.5)
    T.eq(clock:GetAttribute("QuakePhase"), "shaking")
    T.eq(pieces[1].Anchored, false, "loose pieces woken")
    T.eq(pieces[16].Anchored, true, "a fastened one holds")
    T.eq(plinth.Anchored, true, "what holds Godling up stays")
    T.eq(step.Anchored, true)
    T.eq(ann:GetAttribute("KnockedDown"), true, "caught unbraced")
    T.eq(w.g:GetAttribute("KnockedDown"), nil, "braced: not knocked down")
    T.ok(e.impulses > 0, "the ground's motion pushes what is loose")
    pieces[1].Position = pieces[1].Position + V.new(0, -2, 0) -- fell
    pieces[2].Position = pieces[2].Position + V.new(0.5, 0, 0) -- moved a little
    pieces[3]:Destroy() -- into the sea
    e.step(20, 0.5)
    T.eq(clock:GetAttribute("QuakePhase"), "fade")
    e.step(5, 0.5)
    T.eq(clock:GetAttribute("QuakePhase"), "")
    T.eq(pieces[4]:GetAttribute("Quaking"), false)
    e.step(2, 0.5)
    T.eq(w.g:GetAttribute("Bracing"), false, "lets go once it is still")
    e.step(8, 0.5)
    T.eq(clock:GetAttribute("QuakeFell"), 2)
    T.logged(w, "SKY Earthquake #%d+ over: woke %d+, moved 1, fell 2")
    T.starts(w.power("Earthquake"), "SkyFailed:TooSoon:")
end)

T.test("no earthquake while Godling is weak, or just after it fainted, or without a body", function()
    local w = sky()
    local e, x = w.e, w.x
    e.step(0.1)
    x.surviving[w.g].health = 10
    T.eq(w.power("Earthquake"), "SkyFailed:GodlingIsWeak")
    x.surviving[w.g].health = 100
    w.g:SetAttribute("Faints", 1)
    e.step(0.1)
    T.eq(w.power("Earthquake"), "SkyFailed:GodlingIsWeak", "too soon after a faint")
    e.hrp(w.g):Destroy()
    e.now = e.now + 1000
    T.eq(w.power("Earthquake"), "SkyFailed:NobodyHere")
    T.eq(w.power("Lightning"), "SkyFailed:NoSafePalm")
end)

T.test("notes from viewers: cleaned, capped by characters, drifting down, and gone after a while", function()
    local w = sky()
    local e, x = w.e, w.x
    T.eq(w.power("Note", { text = "  \t " }), "SkyFailed:EmptyNote")
    T.eq(w.power("Note"), "SkyFailed:EmptyNote")
    T.eq(w.power("Note", { text = "hello\nthere   Godling " }), "SkyDone:Note:1")
    local clock = e.find("Clock")
    T.eq(clock:GetAttribute("NoteText"), "hello there Godling")
    T.eq(clock:GetAttribute("NoteId"), 1)
    local note = e.find("SkyNote_1")
    T.near(note.Position.Y, 9, 1e-9)
    e.step(2, 0.5)
    T.ok(note.Position.Y < 9 and note.Position.Y > 0.12, "drifting down")
    e.step(240, 10)
    T.near(note.Position.Y, 0.12, 1e-9, "lying on the ground")
    e.step(3, 1)
    T.eq(note.Parent, nil, "gone")
    T.eq(x.sky.notes.cut("ab", 5), "ab")
    T.eq(x.sky.notes.cut("aé🙂b", 3), "aé🙂", "never half a character")
    T.eq(x.sky.notes.cut("ab", 0), "")
    local long = "a" .. string.rep("🙂", 200)
    w.power("Note", { text = long })
    T.eq(utf8.len(clock:GetAttribute("NoteText")), 160)
end)

T.test("the guest panel's body is kept on its pedestal, and viewers see how Godling is", function()
    local w = sky()
    local e, x = w.e, w.x
    local hrp = e.hrp(w.panel)
    hrp.Position = V.new(0, 5, 0) -- it drifted onto the island
    e.step(0.5)
    T.near(hrp.Position.Y, -40, 1e-9, "put back under the island")
    w.g:SetAttribute("Bracing", true)
    e.step(0.5)
    T.eq(e.find("Clock"):GetAttribute("GodlingBracing"), true)
    e.leave(w.g)
    x.sky.mirrorGodling() -- nobody to mirror
    T.eq(x.godlingPlayer(), nil)
end)

T.test("the sky test timer drops a stone near Godling now and then", function()
    local w = T.boot({ patch = { { "local SKY_TEST_EVERY = 0", "local SKY_TEST_EVERY = 30" } } })
    local e = w.e
    e.step(31, 1) -- nobody on the island yet
    T.eq(e.find("SkyShadow_1"), nil)
    local g = w.godling(V.new(500, 2.55, 500)) -- out at sea: no spot near
    e.step(30, 1)
    T.eq(e.find("SkyShadow_1"), nil)
    e.hrp(g).Position = w.openSpot(14)
    e.step(30, 1)
    T.ok(e.find("SkyShadow_1"), "a shadow near Godling")
end)

T.test("trees nearest a point, by kind", function()
    local w = sky()
    local x = w.x
    local t = x.nearestTree("Tree", V.new(0, 0, 0))
    T.ok(t and t.part, "a standing palm")
    T.eq(x.nearestTree("Stump", V.new(0, 0, 0)), nil, "no stump yet")
end)

return T.done("test_sky")
