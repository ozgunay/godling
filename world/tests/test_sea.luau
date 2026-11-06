-- The sea (2026-11-05): a body hanging on the beach's edge is put back on the sand; a body in the sea drowns slowly
-- and wakes at the start spot. The places are the live run's: the south end of the west beach, where a "stepping
-- away" reflex walked Godling off the sand at (-119.8, -44.8) and it later slipped in at (-117.3, -50.2).
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

T.test("hanging on the beach's edge: after three seconds the world puts the body back on the sand", function()
    local w = T.boot()
    local e, x = w.e, w.x
    -- Its capsule caught on the end of a sand strip, its middle over the water: 0.8 lower than standing on the sand.
    local g = w.godling(V.new(-119.76, 1.68, -44.8))
    T.eq(x.surfaceTopAt(-119.76, -44.8, -20, 20), nil, "nothing under its middle")
    e.step(2, 0.5)
    T.near(e.hrp(g).Position.X, -119.76, 1e-9, "not yet")
    T.no(g:GetAttribute("Drowning"), "on the edge it does not drown")
    e.step(1.5, 0.5)
    local p = e.hrp(g).Position
    T.eq(g:GetAttribute("Ashore"), 1)
    T.logged(w, "ASHORE Godling hung on the edge of the sand: %(%-119.8, %-44.8%) to")
    local floor = x.surfaceTopAt(p.X, p.Z, -1, 1)
    T.ok(floor, "on the sand now")
    T.near(p.Y, floor + x.BODY_ABOVE_FEET, 1e-9, "standing on it")
    for c = 0, 7 do -- all of it, not hanging on the lip again
        local a = c * math.pi / 4
        T.ok(x.surfaceTopAt(p.X + math.cos(a), p.Z + math.sin(a), floor - 0.3, floor + 0.3), "ground under its rim")
    end
    T.ok((p - V.new(-119.76, p.Y, -44.8)).Magnitude < 4, "the nearest sand, not the start spot")
    e.step(5, 0.5)
    T.eq(g:GetAttribute("Ashore"), 1, "once")
end)

T.test("standing on the sand by the water's edge, or on the grass, the sea leaves the body alone", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling(V.new(-117.0, 2.45, -47.5)) -- on the sand, a step from the edge
    e.step(10, 0.5)
    T.eq(g:GetAttribute("Ashore"), nil)
    T.no(g:GetAttribute("Drowning"))
    T.near(e.hrp(g).Position.X, -117.0, 1e-9)
    e.hrp(g).Position = V.new(-117.0, 4.5, -47.5) -- hopping: in the air over the sand
    e.step(1, 0.5)
    T.no(g:GetAttribute("Drowning"))
end)

T.test("in the sea the body drowns over a minute and a half, dies, and is born again at the start spot", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local g = w.godling(V.new(-117.3, -1.85, -50.2)) -- slipped off the lip, in the water beside the sand
    e.step(0.5, 0.5)
    local s = x.surviving[g]
    s.health, s.hunger = 66.7, 17.8
    e.step(10, 0.5)
    T.eq(g:GetAttribute("Drowning"), true)
    T.near(s.health, 66.7 - 10 * 100 / 90, 0.6, "about 1.1 a second")
    T.eq(x.clockPart:GetAttribute("GodlingDrowning"), true, "viewers see it too")
    T.eq(g:GetAttribute("Ashore"), nil, "too far below the sand to be put back on it")
    e.step(60, 0.5)
    T.eq(g:GetAttribute("Drowned"), 1)
    T.eq(g:GetAttribute("Deaths"), 1, "it died of the sea (DEATH, ADR-022)")
    T.eq(g:GetAttribute("DiedOf"), "Sea")
    T.eq(g:GetAttribute("Dead"), true)
    T.eq(g:GetAttribute("Drowning"), false, "the dead drown no further")
    T.logged(w, "DROWNED Godling at %(%-117.3, %-50.2%): born again at the start spot")
    e.step(30, 0.5) -- it lies dead, then is born again
    local p = e.hrp(g).Position
    T.near(p.X, x.PLAYER_SPAWN_POSITION.X, 1e-9, "at the start spot")
    T.near(p.Z, x.PLAYER_SPAWN_POSITION.Z, 1e-9)
    T.near(s.health, 100, 0.5, "whole again, as after any death")
    T.near(s.hunger, 50, 0.5, "and half fed")
    e.hrp(g).Position = V.new(p.X, 2.55, p.Z) -- landed (no physics here)
    e.step(1, 0.5)
    T.eq(g:GetAttribute("Drowning"), false)
    T.eq(x.clockPart:GetAttribute("GodlingDrowning"), false)
end)

T.test("a body far under the water drowns too, the guest panel never does, and a climber is left alone", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local sky = w.skyPlayer() -- parked under the island, out of sight
    local g = w.godling(V.new(-140, -6, -40)) -- open sea, well off the beach
    e.step(1, 0.5)
    T.eq(g:GetAttribute("Drowning"), true)
    T.eq(sky:GetAttribute("Drowning"), nil)
    T.eq(sky:GetAttribute("Drowned"), nil)
    g:SetAttribute("Climbing", true) -- the world moves a climbing body itself
    local before = x.surviving[g].health
    e.step(2, 0.5)
    T.ok(x.surviving[g].health >= before, "not while the world moves it")
    T.eq(g:GetAttribute("Drowning"), false)
end)

T.test("hanging on an edge with nowhere safe ashore: the sea still drowns the body", function()
    local w = T.boot({
        before = function(e) -- a lone post standing in the sea, too narrow for a body to stand on its top
            e.part("SeaPost", { Anchored = true, Size = V.new(2, 10, 2), Position = V.new(-160, -5.1, -40) })
        end,
    })
    local e, x = w.e, w.x
    local g = w.godling(V.new(-158.3, 1.68, -40)) -- hanging on its edge
    e.step(4, 0.5)
    T.eq(g:GetAttribute("Ashore"), nil, "nowhere to put it")
    T.near(e.hrp(g).Position.X, -158.3, 1e-9)
    T.eq(g:GetAttribute("Drowning"), true, "the lip cannot keep it safe after rescue fails")
    local s = x.surviving[g]
    s.hunger = 0 -- no healing obscures the sea's pace
    local before = s.health
    e.step(6, 0.5)
    T.near(s.health, before - 6 * (100 / 90 + 100 / x.STARVE_SECONDS), 0.01,
        "drowning continues between attempts to find a safe landing")
    s.health = 0.1
    e.step(0.5, 0.5)
    T.eq(g:GetAttribute("Drowned"), 1)
    T.eq(g:GetAttribute("Deaths"), 1)
    e.step(30.5, 0.5) -- dead a while, then born again
    T.near(e.hrp(g).Position.X, x.PLAYER_SPAWN_POSITION.X, 1e-9)
    T.near(e.hrp(g).Position.Z, x.PLAYER_SPAWN_POSITION.Z, 1e-9)
    T.eq(g:GetAttribute("Drowning"), false)
end)

T.test("a failed lip rescue retries when a safe landing appears and stops the drowning", function()
    local w = T.boot({
        before = function(e)
            e.part("SeaPost", { Anchored = true, Size = V.new(2, 10, 2), Position = V.new(-160, -5.1, -40) })
        end,
    })
    local e, x = w.e, w.x
    local g = w.godling(V.new(-158.3, 1.68, -40))
    e.step(4, 0.5)
    T.eq(g:GetAttribute("Drowning"), true)
    e.part("SeaLanding", { Anchored = true, Size = V.new(8, 1, 8), Position = V.new(-160, -0.6, -40) })
    e.step(2.5, 0.5) -- the next attempt, three seconds after the failed rescue
    T.eq(g:GetAttribute("Ashore"), 1)
    T.eq(g:GetAttribute("Drowning"), false)
    T.eq(x.clockPart:GetAttribute("GodlingDrowning"), false)
    T.near(e.hrp(g).Position.Y, -0.1 + x.BODY_ABOVE_FEET, 1e-9)
    local s = x.surviving[g]
    s.hunger = 20 -- neither starving nor healing
    local ashoreHealth = s.health
    e.step(2, 0.5)
    T.near(s.health, ashoreHealth, 1e-9, "the failed-rescue state is cleared ashore")
    T.eq(g:GetAttribute("Drowned"), nil)
    T.eq(g:GetAttribute("Ashore"), 1)
end)

return T.done("test_sea")
