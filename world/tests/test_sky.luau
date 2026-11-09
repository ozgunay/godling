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
    T.eq(w.power("Stone"), "SkyFailed:NoClearSpot")
    -- A log looks further round its aim (ADR-029: SNAP_FAR), and lands past the crowd rather than being refused.
    T.eq(w.power("Log", aim(p, 5, 5)), "SkyDone:Log:1")
    local log = e.find("Log_1")
    T.ok(math.sqrt((log.Position.X - p.X) ^ 2 + (log.Position.Z - p.Z) ^ 2) > 16, "past the crowd")
end)

T.test("unaimed, a log where a stone would fit is moved or turned till it fits", function()
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
    local moved = math.abs(log.Position.X - sx) > 0.01 or math.abs(log.Position.Z - sz) > 0.01
    local turned = math.abs(log.CFrame.RightVector.X) < 0.5 -- its length along z (ADR-029: either axis)
    T.ok(moved or turned, "moved or turned off the stone's spot")
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
    local bolt = e.find("SkyBolt_1")
    T.ok(bolt, "a bolt shows")
    T.eq(bolt:GetAttribute("SkyId"), 1, "its id shapes the bolt")
    T.eq(bolt:GetAttribute("StrikeX"), p.X, "it strikes the palm")
    T.eq(bolt:GetAttribute("StrikeZ"), p.Z)
    T.ok(math.abs(bolt:GetAttribute("StrikeY")) < 0.5, "at its foot, on the ground")
    T.eq(bolt:GetAttribute("SkyEvent"), nil, "the marker is no thing the sky left")
    e.step(1, 0.1)
    T.ok(e.find("SkyBolt_1"), "it stays a while: a viewer plays the strike when it first sees it")
    e.step(2.5, 0.1)
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
    T.eq(x.SKY_FALL_SPEED, 80, "fast: about a second from where it appears (the user's wish, 2026-11-06)")
    e.step(0.5, 0.1)
    T.ok(stone.Position.Y < 45 and stone.Position.Y > 35, "falling, 40 a half second")
    T.eq(stone.CanCollide, false)
    e.step(0.6, 0.1)
    T.eq(stone.CanCollide, true, "landed")
    T.ok(e.find("Crater_1"), "a crater")
    T.near(e.find("Crater_1").Position.Y, 0.3, 1e-9, "lying on the ground")
    T.ok(e.find("Blast_1"), "the blast shows")
    T.eq(e.find("Clock"):GetAttribute("MeteorId"), 1)
    e.step(3.1, 0.5)
    T.eq(e.find("Blast_1"), nil, "for a moment")
    T.logged(w, "SKY Meteor #1 blasted at")
end)

T.test("a meteor's stone lands glowing hot and cools over a day, its crater's scorch with it", function()
    local w = sky()
    local e, x = w.e, w.x
    local m = x.sky.meteor
    T.eq(m.COOL_SECONDS, x.DAY_SECONDS, "about a day of the island's clock")
    T.eq(w.power("Meteor", aim(w.spot, 0, 6)), "SkyDone:Meteor:1")
    e.step(40.1, 0.1)
    local stone = e.find("Meteor_1")
    T.eq(stone:GetAttribute("Heat"), 1, "white-hot as it falls")
    T.eq(stone:GetAttribute("LandedAt"), nil, "not landed yet")
    T.eq(#m.hot, 0)
    e.step(2, 0.1)
    local crater = e.find("Crater_1")
    T.eq(stone.CanCollide, true, "landed")
    local landed = stone:GetAttribute("LandedAt")
    T.ok(landed and math.abs(landed - 42) < 2.5, "on the island's clock, 40 s of warning and a short fall after it")
    T.eq(crater:GetAttribute("LandedAt"), landed, "the crater cools from the same moment")
    T.eq(stone:GetAttribute("Heat"), 1)
    T.eq(crater:GetAttribute("Heat"), 1)
    T.eq(#m.hot, 2)
    local clock = e.find("Clock")
    local function after(dayFraction) -- the clock moved on to that much of a day since it landed, and the world looked
        local now = (clock:GetAttribute("Day") - 1) * 2400 + clock:GetAttribute("TimeOfDay") * 100 - 700 -- to a second
        x.tickClock(landed + dayFraction * m.COOL_SECONDS - now)
        m.cool(m.COOL_EVERY)
    end
    after(0.3) -- fast at first: (1 - 0.3)^2 = 0.49, shown as the step above
    T.eq(stone:GetAttribute("Heat"), 0.5)
    T.eq(crater:GetAttribute("Heat"), 0.5, "the scorch fades as the stone cools")
    after(0.6)
    T.eq(stone:GetAttribute("Heat"), 0.2, "a dull glow")
    crater:Destroy() -- no longer kept (or smashed): it leaves the cooling
    after(0.99)
    T.eq(stone:GetAttribute("Heat"), 0.05, "the last of the glow: it is never 0 until it is cold")
    T.eq(#m.hot, 1)
    after(1.01)
    T.eq(stone:GetAttribute("Heat"), 0, "a plain dark stone")
    T.eq(#m.hot, 0, "and nothing is left to cool")
    T.eq(m.heat(landed - 5 * m.COOL_SECONDS), 0)
end)

T.test("the world looks at what cools every few seconds, not every beat", function()
    local w = sky()
    local e, x = w.e, w.x
    local m = x.sky.meteor
    local stone = e.part("Meteor_7", { Size = V.new(2.5, 2.5, 2.5) })
    m.landed(stone)
    x.tickClock(m.COOL_SECONDS / 2)
    m.coolBeat = 0
    e.step(m.COOL_EVERY - 0.5, 0.5)
    T.eq(stone:GetAttribute("Heat"), 1, "not looked at yet")
    e.step(0.6, 0.5)
    T.eq(stone:GetAttribute("Heat"), 0.25, "half a day: (1 - 0.5)^2")
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

T.test("a meteor falling fast through a slow beat still blasts on the wall top it passed, not the ground under it", function()
    local w = sky()
    local e, x = w.e, w.x
    local c = V.new(w.spot.X + 5, 0, w.spot.Z)
    local wall = e.part("Block_90", { Size = V.new(2.5, 7.5, 2.5), Position = c + V.new(0, 3.75, 0), Anchored = true,
        attrs = { RenderRole = "PickupObject", IsPickupObject = true, Fastened = true } })
    T.eq(w.power("Meteor", { at = { x = c.X, z = c.Z } }), "SkyDone:Meteor:1")
    e.step(40.05, 0.05)
    local fall = x.skyFalls[1]
    T.ok(fall and fall.stone, "falling")
    fall.y = 12 -- its foot at 10.75, a beat above the wall's top at 7.5
    e.step(0.25, 0.25) -- one slow beat drops it 20: its foot goes from 10.75 to -9.25, past the top
    T.eq(x.skyFalls[1], nil, "it blasted")
    T.eq(wall.Parent, nil, "on the wall it passed, which it smashed")
    T.logged(w, "SKY Meteor #1 blasted at %([^,]+, 7%.5, ", "at the wall's top, 7.5 up")
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
    x.surviving[w.g].health = 20 -- the blast kills it: no knock-down on top
    e.step(40.1, 0.1)
    e.step(2, 0.1)
    T.eq(w.g:GetAttribute("Deaths"), 1)
    T.eq(w.g:GetAttribute("DiedOf"), "Meteor")
    T.eq(x.sky.quake.knocked(w.g), false, "the dead are not knocked down")
end)

T.test("a meteor aimed at the sea, or with nowhere clear to land, and the craters that are kept", function()
    local w = sky()
    local e, x = w.e, w.x
    local spawn = V.new(x.ISLAND.raft[1] + 5, 0, x.ISLAND.raft[2] - 5) -- on the west beach, by the raft
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

T.test("no earthquake while Godling is weak, lies dead, or was born again lately, or without a body", function()
    local w = sky()
    local e, x = w.e, w.x
    e.step(0.1)
    x.surviving[w.g].health = 10
    T.eq(w.power("Earthquake"), "SkyFailed:GodlingIsWeak")
    x.death.die(w.g, x.surviving[w.g], "Hunger")
    T.eq(w.power("Earthquake"), "SkyFailed:GodlingIsWeak", "dead")
    e.step(31, 1)
    T.eq(x.surviving[w.g].health, 100, "born again, whole")
    T.eq(w.power("Earthquake"), "SkyFailed:GodlingIsWeak", "too soon after it died")
    e.now = e.now + 900
    T.ok(not x.sky.quake.weak(w.g), "fifteen minutes on, the mercy rule lets go")
    e.hrp(w.g):Destroy()
    e.now = e.now + 1000
    T.eq(w.power("Earthquake"), "SkyFailed:NobodyHere")
    T.eq(w.power("Lightning"), "SkyFailed:NoSafePalm")
end)

T.test("dying ends a brace or knock-down without releasing or getting up the corpse", function()
    local w = sky()
    local e, x = w.e, w.x
    e.step(0.1)
    for i = 1, 16 do
        piece(e, "Block_" .. (100 + i), w.spot + V.new(5 + (i % 4) * 2.5, -1.3, 5 + math.floor(i / 4) * 2.5))
    end
    T.starts(w.power("Earthquake"), "SkyDone:Earthquake:")
    T.eq(w.act(w.g, "Brace", {}), "Braced")
    x.hurt(w.g, 200, "Lightning")
    T.eq(w.g:GetAttribute("Bracing"), false, "a corpse no longer braces")
    e.step(30.1, 0.5)
    T.eq(w.g:GetAttribute("Dead"), false)
    T.eq(e.hrp(w.g).Anchored, false, "reborn before the shaking ends, it can still walk")
    x.sky.quake.knockDown(w.g, e.hrp(w.g))
    x.hurt(w.g, 200, "Meteor")
    T.eq(w.g:GetAttribute("KnockedDown"), false)
    e.step(5, 0.5)
    T.eq(e.hrp(w.g).Anchored, true, "the knock-down timer does not release a corpse")
    T.eq(w.g:GetAttribute("Gesture"), "Stagger", "it has not got up")
    e.step(25.1, 0.5)
    T.eq(e.hrp(w.g).Anchored, false, "the corpse releases at rebirth")
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

-- The storm called down (main.lua THE STORM): the order of its strikes is the world's; a test sets it.
local function strikesAt(x, order)
    for _, spot in ipairs(x.sky.storm.active().spots) do
        for _, o in ipairs(order) do
            if math.abs(spot.x - o[1]) < 1e-6 and math.abs(spot.z - o[2]) < 1e-6 then
                spot.at = o[3]
            end
        end
    end
end

T.test("a storm: a warning, three strikes where they were aimed (Godling, a palm, the ground), and it passes", function()
    local w = sky()
    local e, x = w.e, w.x
    local palm = e.find("Palm_6")
    local p = palm.Position
    local g = V.new(p.X + 20, 2.45, p.Z)
    e.hrp(w.g).Position = g
    e.step(1)
    local s = x.surviving[w.g]
    s.health = 80
    local ground = { g.X, g.Z + 15 }
    T.starts(w.power("Storm", { spots = { { x = g.X, z = g.Z }, { p.X, p.Z }, ground } }), "SkyDone:Storm:")
    strikesAt(x, { { g.X, g.Z, 40 }, { p.X, p.Z, 60 }, { ground[1], ground[2], 80 } })
    local clock = e.find("Clock")
    T.eq(clock:GetAttribute("StormPhase"), "warning")
    T.eq(#string.split(clock:GetAttribute("StormSpots"), ";"), 3)
    T.logged(w, "SKY Storm #1 called: strikes at")
    local markers = {}
    for _, part in ipairs(e.Workspace:GetChildren()) do
        if part:GetAttribute("RenderRole") == "StormSpot" then
            table.insert(markers, part)
            T.eq(part:GetAttribute("Charged"), false)
        end
    end
    T.eq(#markers, 3, "three spots crackle on the ground")
    T.eq(w.power("Storm"), "SkyFailed:AlreadyStorming")
    e.step(31, 0.5)
    T.eq(clock:GetAttribute("StormPhase"), "storm")
    T.ok(x.tickWeather.rain() >= 0.99, "heavy rain")
    e.step(7.6, 0.1) -- 1.5 s before the first bolt, its spot flares
    local flaring = 0
    for _, part in ipairs(markers) do
        flaring = flaring + (part:GetAttribute("Charged") and 1 or 0)
    end
    T.eq(flaring, 1)
    e.step(1.6, 0.1)
    T.near(s.health, 5, 0.1, "struck: half a heart (it mends a hair since)")
    T.eq(w.g:GetAttribute("Hurt"), "Storm")
    T.eq(w.g:GetAttribute("Struck"), 1)
    T.eq(w.g:GetAttribute("Scorched"), 60)
    T.eq(w.g:GetAttribute("KnockedDown"), true)
    T.eq(w.g:GetAttribute("Deaths"), nil, "never killed")
    T.logged(w, "strike 1 of 3 at")
    T.logged(w, "struck Godling, on Godling: health 5")
    local bolt
    for _, part in ipairs(e.Workspace:GetChildren()) do
        if part.Name:match("^SkyBolt_") then
            bolt = part
        end
    end
    T.near(bolt:GetAttribute("StrikeY"), e.hrp(w.g).Position.Y + 2.5, 1e-6, "the bolt ends on its head")
    e.step(20, 0.5)
    T.eq(palm:GetAttribute("RenderRole"), "Stump", "the palm is felled")
    local logs = 0
    for _, part in ipairs(e.Workspace:GetChildren()) do
        if part:GetAttribute("FromTree") == "Palm_6" then
            logs = logs + 1
            T.eq(part:GetAttribute("SkyEvent"), "Lightning", "the mind sees what lightning left")
        end
    end
    T.eq(logs, 2, "two logs")
    T.ok(s.health < 8, "far from Godling: only mending since")
    e.step(20, 0.5)
    local scorch
    for _, part in ipairs(e.Workspace:GetChildren()) do
        if part:GetAttribute("RenderRole") == "Scorch" then
            scorch = part
        end
    end
    T.ok(scorch, "open ground is scorched")
    T.near(w.g:GetAttribute("Scorched"), 20, 1, "the char fades over a minute")
    e.step(101, 0.5)
    T.eq(clock:GetAttribute("StormPhase"), "")
    T.eq(x.sky.storm.active(), nil)
    T.logged(w, "SKY Storm #1 passed")
    T.eq(w.g:GetAttribute("Scorched"), 0)
    e.step(30, 0.5)
    T.ok(x.tickWeather.rain() < 0.1, "the rain eases off")
    e.step(130, 1) -- 240 s after its strike
    T.eq(scorch.Parent, nil, "and the scorch fades")
    T.starts(w.power("Storm"), "SkyFailed:TooSoon:", "one storm every half hour")
    e.now = e.now + 1800
    T.ok(s.health < 30)
    T.eq(w.power("Storm"), "SkyFailed:GodlingIsWeak", "still weak from the strike: the mercy rule")
    s.health = 100
    T.starts(w.power("Storm"), "SkyDone:Storm:", "the sky picks all three")
    local picked = 0
    for _, spot in ipairs(x.sky.storm.active().spots) do
        picked = picked + 1
        local d = V.new(spot.x - g.X, 0, spot.z - g.Z).Magnitude
        T.ok(d >= 12 and d <= 45, "the sky picks well away from Godling")
    end
    T.eq(picked, 3)
end)

T.test("a storm's strike close by takes 35, never below half a heart; a roof takes it; the dead are left alone", function()
    local w = sky()
    local e, x = w.e, w.x
    e.step(1)
    local g = e.hrp(w.g).Position
    local s = x.surviving[w.g]
    T.eq(w.power("Storm", { spots = { { x = g.X + 100, z = g.Z } } }), "SkyFailed:TooFar")
    s.health = 20
    T.eq(w.power("Storm"), "SkyFailed:GodlingIsWeak")
    s.health = 100
    x.tickWeather.hold(1) -- a storm of the weather's own
    e.step(25, 0.5)
    T.eq(w.power("Storm"), "SkyFailed:AlreadyStorming")
    x.tickWeather.hold(nil)
    e.step(25, 0.5)
    local near, roofed, dead = { g.X + 5, g.Z }, { g.X - 5, g.Z }, { g.X, g.Z + 5 }
    T.starts(w.power("Storm", { spots = { near, roofed, dead } }), "SkyDone:Storm:")
    strikesAt(x, { { near[1], near[2], 40 }, { roofed[1], roofed[2], 50 }, { dead[1], dead[2], 60 } })
    e.step(40.1, 0.5)
    T.near(s.health, 65, 0.1, "close by: 35")
    T.eq(w.g:GetAttribute("KnockedDown"), true)
    T.eq(w.g:GetAttribute("Struck"), nil, "not struck: no char")
    T.logged(w, "close to Godling: health 65")
    e.step(3, 0.5) -- it gets up; a roof is built over it
    local roof = piece(e, "Block_90", V.new(g.X, g.Y + 5, g.Z))
    e.step(1, 0.5)
    T.eq(w.g:GetAttribute("Sheltered"), "roof")
    e.step(6.5, 0.5)
    T.ok(s.health > 64.9 and s.health < 66, "the roof takes it (a fed body mends a little meanwhile)")
    T.logged(w, "a roof over Godling took it")
    roof:Destroy()
    x.death.die(w.g, s, "Hunger")
    e.step(10, 0.5)
    T.eq(w.g:GetAttribute("Hurts"), 1, "the dead are left alone")
    T.eq(s.health, 0)
    -- close by with little left: down to half a heart, no further
    e.step(140, 1)
    s.health = 30
    e.now = e.now + 2000
    local born = e.hrp(w.g).Position -- born again at the start spot
    local again = { born.X + 5, born.Z }
    T.starts(w.power("Storm", { spots = { again } }), "SkyDone:Storm:")
    strikesAt(x, { { again[1], again[2], 31 } })
    for _, spot in ipairs(x.sky.storm.active().spots) do
        spot.at = spot.at == 31 and 31 or 200 -- the sky's two picks wait until it has passed
    end
    e.step(31.1, 0.5)
    T.near(s.health, 5, 0.1)
end)

T.test("with no palm standing in reach, the sky picks open ground well away from Godling; no body, no storm", function()
    local w = sky()
    local e, x = w.e, w.x
    e.step(1)
    for _, t in ipairs(x.trees) do
        t.part:SetAttribute("RenderRole", "Stump")
    end
    T.starts(w.power("Storm"), "SkyDone:Storm:")
    local g = e.hrp(w.g).Position
    for _, spot in ipairs(x.sky.storm.active().spots) do
        local d = V.new(spot.x - g.X, 0, spot.z - g.Z).Magnitude
        T.ok(d >= 12 and d <= 45, "open ground, 12 to 45 away")
    end
    e.step(200, 1)
    e.now = e.now + 1800
    e.hrp(w.g):Destroy()
    T.eq(w.power("Storm"), "SkyFailed:NobodyHere")
end)

T.test("a storm already called down leaves a newly reborn body under the death mercy rule", function()
    local w = sky()
    local e, x = w.e, w.x
    local spawn = x.PLAYER_SPAWN_POSITION
    e.hrp(w.g).Position = spawn
    e.step(1)
    local direct, near = { spawn.X, spawn.Z }, { spawn.X + 5, spawn.Z }
    T.starts(w.power("Storm", { spots = { direct, near, { spawn.X, spawn.Z + 15 } } }), "SkyDone:Storm:")
    strikesAt(x, { { direct[1], direct[2], 40 }, { near[1], near[2], 50 }, { spawn.X, spawn.Z + 15, 60 } })
    x.death.die(w.g, x.surviving[w.g], "Hunger")
    e.step(31, 0.5)
    T.eq(w.g:GetAttribute("Dead"), false)
    T.ok(x.sky.quake.weak(w.g), "rebirth is inside the death mercy window")
    e.step(30, 0.5)
    T.ok(x.surviving[w.g].health > 95, "neither the direct strike nor the nearby strike hurts the reborn body")
    T.eq(w.g:GetAttribute("Hurts"), nil)
    T.eq(w.g:GetAttribute("Struck"), nil)
    T.eq(w.g:GetAttribute("Scorched"), nil)
    T.eq(w.g:GetAttribute("KnockedDown"), false)
    T.eq(x.sky.storm.active().struck, 3, "all three environmental strikes still happen")
    T.ok(x.tickWeather.rain() >= 0.99, "the storm's weather continues")
    T.logged(w, "SKY Storm #1 strike 3 of 3")
end)

T.test("a meteor already called down when Godling dies still blasts, and spares the body born again under it", function()
    local w = sky()
    local e, x = w.e, w.x
    local spawn = x.PLAYER_SPAWN_POSITION
    e.hrp(w.g).Position = spawn
    e.step(1)
    T.eq(w.power("Meteor", { at = { x = spawn.X, z = spawn.Z } }), "SkyDone:Meteor:1")
    x.death.die(w.g, x.surviving[w.g], "Hunger")
    e.step(31, 0.5) -- dead 30 s, of the stone's 40 s of warning
    T.eq(w.g:GetAttribute("Dead"), false, "born again at the start spot, under the shadow")
    e.step(12, 0.1)
    T.logged(w, "SKY Meteor #1 blasted at .*hurt 0")
    T.ok(e.find("Crater_1"), "the stone still blasts and leaves its crater")
    T.ok(x.surviving[w.g].health > 95, "the reborn body is not hurt")
    T.eq(w.g:GetAttribute("Hurts"), nil)
    T.eq(x.sky.quake.knocked(w.g), false, "nor knocked down")
    T.eq(e.find("Clock"):GetAttribute("MeteorHurt"), 0)
end)

return T.done("test_sky")
