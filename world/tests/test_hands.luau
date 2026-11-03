-- The body's hands and legs: picking up, setting down, throwing, eating, turning, and the other plain inputs.
local T = load_plain(readfile("world/tests/lib.luau"), "world/tests/lib.luau")()
local V = T.Vector3

local function at(part) -- an input's position: where a part is
    local p = part.Position
    return { p.X, p.Y, p.Z }
end

-- Godling standing beside Block_1 (the starting pile runs east and north from it), a block's width to its west.
local function beside(name)
    local w = T.boot()
    local block = w.e.find(name or "Block_1")
    local g = w.godling(block.Position + V.new(-2.5, 1.3, 0))
    return w, g, block
end

T.test("picking up: the reasons it fails", function()
    local w, g, block = beside()
    T.eq(w.act(g, "Pickup", nil), "PickupFailed:MissingPosition")
    T.eq(w.act(g, "Pickup", {}), "PickupFailed:MissingPosition")
    T.eq(w.act(g, "Pickup", { position = "here" }), "PickupFailed:InvalidPosition")
    T.eq(w.act(g, "Pickup", { position = { 1, "y", 3 } }), "PickupFailed:InvalidPosition")
    T.eq(w.act(g, "Pickup", { position = { 0 / 0, 0, 0 } }), "PickupFailed:InvalidPosition")
    T.eq(w.act(g, "Pickup", { position = { 500, 1, 500 } }), "PickupFailed:OutOfRange")
    local p = block.Position
    T.eq(w.act(g, "Pickup", { position = { p.X, p.Y + 3.5, p.Z } }), "PickupFailed:NoBlock")
    block:SetAttribute("Fastened", true)
    T.eq(w.act(g, "Pickup", { position = at(block) }), "PickupFailed:Fastened")
    block:SetAttribute("Fastened", false)
    block:SetAttribute("Burning", true)
    T.eq(w.act(g, "Pickup", { position = at(block) }), "PickupFailed:Burning")
end)

T.test("a picked-up block rises into the hands, and the hands are then full", function()
    local w, g, block = beside()
    local e = w.e
    T.eq(w.act(g, "Pickup", { position = at(block) }), "PickupSuccess")
    T.eq(g:GetAttribute("Gesture"), "PickUp")
    T.eq(g:GetAttribute("Reaches"), 1)
    T.eq(block.CanCollide, false)
    T.eq(block:GetAttribute("HeldBy"), "Godling", "it names its holder, for the renderer's hand")
    e.step(0.5)
    T.ok(block.Position.Y < e.hrp(g).Position.Y + 4 - 0.1, "half way up")
    e.step(0.6)
    e.step(0.1)
    T.near(block.Position.Y, e.hrp(g).Position.Y + 4, 1e-6, "held over the head")
    T.eq(w.act(g, "Pickup", { position = at(block) }), "PickupFailed:AlreadyHolding")
    e.hrp(g).Position = e.hrp(g).Position + V.new(3, 0, 0) -- it follows the body
    e.step(0.1)
    T.near(block.Position.X, e.hrp(g).Position.X, 1e-6)
end)

T.test("a heavy boulder halves the walk; set down, the pace comes back", function()
    local w, g, boulder = beside("Boulder_1")
    local e = w.e
    e.hrp(g).Position = boulder.Position + V.new(2.5, 1.25, 0)
    T.eq(w.act(g, "Pickup", { position = at(boulder) }), "PickupSuccess")
    T.eq(e.humanoid(g).WalkSpeed, 8)
    T.eq(g:GetAttribute("WalkSpeed"), 8)
    e.step(1.5)
    local p = e.hrp(g).Position
    T.eq(w.act(g, "Place", { position = { p.X + 4, 1.3, p.Z } }), "PlaceSuccess")
    T.eq(e.humanoid(g).WalkSpeed, 16)
end)

T.test("setting down: the reasons it fails", function()
    local w, g, block = beside()
    local e = w.e
    T.eq(w.act(g, "Place", { position = { 0, 0, 0 } }), "PlaceFailed:EmptyHands")
    w.act(g, "Pickup", { position = at(block) })
    e.step(1.2)
    local p = e.hrp(g).Position
    T.eq(w.act(g, "Place", nil), "PlaceFailed:MissingPosition")
    T.eq(w.act(g, "Place", { rotation = 0 }), "PlaceFailed:MissingPosition")
    T.eq(w.act(g, "Place", { position = { "a", 1, 1 } }), "PlaceFailed:InvalidPosition")
    T.eq(w.act(g, "Place", { position = { 300, 1, 300 } }), "PlaceFailed:OutOfRange")
    local spot = { p.X + 2.5, 1.25, p.Z }
    T.eq(w.act(g, "Place", { position = spot, rotation = "sideways" }), "PlaceFailed:InvalidRotation")
    T.eq(w.act(g, "Place", { position = spot, rotation = 0 / 0 }), "PlaceFailed:InvalidRotation")
    T.eq(w.act(g, "Place", { position = spot, rotation = { pitch = "x" } }), "PlaceFailed:InvalidRotation")
    T.eq(w.act(g, "Place", { position = spot, rotation = { 0 / 0, 0, 0 } }), "PlaceFailed:InvalidRotation")
    local other = e.find("Block_12").Position -- the far corner of the pile
    T.eq(w.act(g, "Place", { position = { other.X, other.Y, other.Z } }), "PlaceFailed:OutOfRange")
    local near = e.find("Block_5").Position
    e.hrp(g).Position = near + V.new(0, 1.3, 2.5)
    T.eq(w.act(g, "Place", { position = { near.X, near.Y, near.Z } }), "PlaceFailed:Occupied")
end)

T.test("a block set down is lowered into its grid cell, turned as asked", function()
    local w, g, block = beside()
    local e = w.e
    w.act(g, "Pickup", { position = at(block) })
    e.step(1.2)
    local p = e.hrp(g).Position
    T.eq(w.act(g, "Place", { position = { p.X + 3.1, 1.3, p.Z + 0.4 }, rotation = 90 }), "PlaceSuccess")
    T.eq(g:GetAttribute("Gesture"), "PutDown")
    T.eq(block:GetAttribute("HeldBy"), nil, "no longer in a hand")
    T.eq(block.Anchored, true, "carried down by the world")
    e.step(0.6)
    T.ok(math.abs(block.Position.X % 2.5) > 0.01 or block.Position.Y > 1.4, "still on its way")
    e.step(0.7)
    T.near(block.Position.X % 2.5, 0, 1e-6, "in its cell")
    T.near(block.Position.Y, 1.3, 1e-6)
    T.eq(block.Anchored, false, "loose, to settle")
    T.eq(block.CanCollide, true)
    local _, yaw = block.CFrame:ToOrientation()
    T.near(math.deg(yaw), 90, 1e-4, "turned a quarter round")
end)

T.test("a ladder stands upright whatever it is told, and is carried lying flat", function()
    local w = T.boot()
    local e = w.e
    local ladder = e.find("Ladder_1")
    local g = w.godling(ladder.Position + V.new(2, 2.4, 0))
    T.eq(w.act(g, "Pickup", { position = at(ladder) }), "PickupSuccess")
    e.step(1.2)
    e.step(0.1)
    local pitch = ladder.CFrame:ToOrientation()
    T.near(math.abs(math.deg(pitch)), 90, 1e-4, "lying flat while carried")
    local p = e.hrp(g).Position
    T.eq(w.act(g, "Place", { position = { p.X + 3, 3.77, p.Z }, rotation = { pitch = 45, yaw = 90, roll = 30 } }), "PlaceSuccess")
    e.step(1.3)
    T.eq(ladder.Anchored, true, "it stands by itself")
    local px, py, pz = ladder.CFrame:ToOrientation()
    T.near(px, 0, 1e-6, "upright")
    T.near(math.deg(py), 90, 1e-4, "only its facing turned")
    T.near(pz, 0, 1e-6)
    T.eq(w.act(g, "Pickup", { position = at(ladder) }), "PickupSuccess")
    e.step(1.2)
    T.eq(w.act(g, "Place", { position = { p.X + 3, 3.77, p.Z } }), "PlaceSuccess") -- no rotation at all
end)

T.test("throwing: the reasons it fails, and a throw", function()
    local w, g, block = beside()
    local e = w.e
    T.eq(w.act(g, "Throw", { direction = { 1, 0, 0 } }), "ThrowFailed:EmptyHands")
    w.act(g, "Pickup", { position = at(block) })
    e.step(1.2)
    T.eq(w.act(g, "Throw", nil), "ThrowFailed:MissingDirection")
    T.eq(w.act(g, "Throw", { direction = "north" }), "ThrowFailed:InvalidDirection")
    T.eq(w.act(g, "Throw", { direction = { 0, 0, 0 } }), "ThrowFailed:InvalidDirection")
    T.eq(w.act(g, "Throw", { direction = { 1, 1, 0 }, speed = 99 }), "ThrowSuccess")
    T.eq(g:GetAttribute("Gesture"), "Throw")
    T.near(block.AssemblyLinearVelocity.Magnitude > 0 and 1 or 0, 1, 0)
    T.eq(block.CanCollide, false, "not straight into the thrower")
    e.step(0.2)
    T.eq(block.CanCollide, true, "after a moment it collides")
    -- default and unreadable speeds
    for _, speed in ipairs({ "fast", nil }) do
        local b2 = e.find("Block_3")
        e.hrp(g).Position = b2.Position + V.new(0, 1.3, -2.5)
        T.eq(w.act(g, "Pickup", { position = at(b2) }), "PickupSuccess")
        e.step(1.2)
        T.eq(w.act(g, "Throw", { direction = { 0, 1, 0 }, speed = speed }), "ThrowSuccess")
        T.near(b2.AssemblyLinearVelocity.Y, 10 + 6, 1e-6, "at most 10, plus the upward toss")
        b2:Destroy() -- gone in flight: the world lets go of it
        e.step(0.05)
    end
end)

T.test("a body without a root part throws nothing", function()
    local w = T.boot()
    local g = w.e.player("Godling", nil, { noCharacter = true })
    -- a bodiless player has no humanoid either: the world ignores its inputs
    T.eq(g:GetAttribute("LastActionResult"), "Ready")
end)

T.test("the rock: picked up and thrown, its impacts would break off blocks (none at block scale)", function()
    local w = T.boot()
    local e, x = w.e, w.x
    local rock = e.find("Rock_1")
    local g = w.godling(rock.Position + V.new(2.8, 1.45, 0))
    T.eq(w.act(g, "Pickup", { position = at(rock) }), "PickupSuccess")
    e.step(1.2)
    T.eq(w.act(g, "Throw", { direction = { 1, 0, 0 } }), "ThrowSuccess")
    local state = x.rockImpactStates[rock]
    T.ok(state, "the rock watches its impacts")
    local ground = e.find("Ground_1")
    rock.Touched:Fire(nil)
    rock.Touched:Fire(e.Players) -- not a part
    rock.Touched:Fire(rock)
    rock.Touched:Fire(ground) -- too soon after the throw
    e.now = e.now + 5
    rock.AssemblyLinearVelocity = V.new(1, 0, 0)
    rock.Touched:Fire(ground) -- too slow
    rock.AssemblyLinearVelocity = V.new(6.1, 0, 0)
    rock.CustomPhysicalProperties = { Density = 1 }
    rock.Touched:Fire(ground) -- too light to matter
    rock.CustomPhysicalProperties = { Density = 8 }
    rock.AssemblyLinearVelocity = V.new(12, 0, 0)
    rock.Touched:Fire(ground)
    T.eq(e.find("ImpactBlock_13"), nil, "no blocks break off at block scale")
    rock.Touched:Fire(ground) -- within the cooldown
    x.rockImpactStates[rock] = nil
    rock.Touched:Fire(ground) -- no longer watched
end)

T.test("with impact blocks switched on, a hard landing breaks blocks off", function()
    local w = T.boot({ patch = { { "local ROCK_MAX_IMPACT_CUBES = 0", "local ROCK_MAX_IMPACT_CUBES = 8" } } })
    local e = w.e
    local rock = e.find("Rock_1")
    e.now = 5
    rock.AssemblyLinearVelocity = V.new(12, 0, 0)
    rock.Touched:Fire(e.find("Ground_1"))
    T.ok(e.find("ImpactBlock_13"), "a block broke off")
end)

T.test("eating: what can and cannot be eaten", function()
    local w, g, block = beside()
    local e = w.e
    T.eq(w.act(g, "Eat", {}), "EatFailed:EmptyHands")
    w.act(g, "Pickup", { position = at(block) })
    T.eq(w.act(g, "Eat", {}), "EatFailed:NotFood")
    w.act(g, "Throw", { direction = { 1, 0, 0 } })
    local p = e.hrp(g).Position
    local function food(name, role, cooked)
        local f = e.part(name, { Size = V.new(0.9, 0.9, 0.9), Position = p + V.new(1.5, -2, 0),
            attrs = { RenderRole = role, IsPickupObject = true, Cooked = cooked } })
        T.eq(w.act(g, "Pickup", { position = at(f) }), "PickupSuccess")
        return f
    end
    w.x.surviving[g] = nil -- not yet counted: a meal starts the count
    food("Coconut_9", "Coconut")
    T.eq(w.act(g, "Eat", {}), "EatSuccess:100")
    T.eq(g:GetAttribute("Gesture"), "Eat")
    w.x.surviving[g].hunger = 10
    food("Catch_9", "Catch")
    T.eq(w.act(g, "Eat", {}), "EatSuccess:30")
    food("Catch_8", "Catch", true)
    T.eq(w.act(g, "Eat", {}), "EatSuccess:80")
end)

T.test("a thought for the bubble: only things and feelings the renderer knows", function()
    local w = T.boot()
    local g = w.godling()
    g:SetAttribute("LastActionResult", "before")
    w.act(g, "Think", { thing = "fish", feeling = "hungry" })
    T.eq(g:GetAttribute("Thought"), "fish")
    T.eq(g:GetAttribute("Thoughts"), 1)
    w.act(g, "Think", { thing = "spaceship", feeling = "happy" })
    w.act(g, "Think", nil)
    T.eq(g:GetAttribute("Thoughts"), 1)
    T.eq(g:GetAttribute("LastActionResult"), "before", "a thought is not an action")
end)

T.test("talking along, walking, stopping, jumping, and what the world does not know", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling()
    T.eq(w.act(g, "Talk", {}), "TalkSuccess")
    T.eq(g:GetAttribute("Gesture"), "Talk")
    w.act(g, "MoveTo", { position = { 10, 2.55, 10 } })
    T.eq(e.humanoid(g).WalkTarget.X, 10)
    T.eq(w.act(g, "MoveTo", { position = { "x" } }), "MoveToFailed:InvalidPosition")
    T.eq(w.act(g, "MoveTo", {}), "InvalidAction")
    w.act(g, "Stop", {})
    T.eq(e.humanoid(g).WalkTarget, nil)
    w.act(g, "Jump", {})
    T.eq(e.humanoid(g).Jump, true)
    T.eq(w.act(g, "Fly", {}), "InvalidAction")
end)

T.test("Face turns the body on the spot, at its own pace", function()
    local w = T.boot()
    local e = w.e
    local g = w.godling(V.new(0, 2.55, 0))
    local hrp = e.hrp(g)
    T.eq(w.act(g, "Face", nil), "FaceFailed:InvalidPosition")
    T.eq(w.act(g, "Face", { position = { 0.01, 2.55, 0 } }), "FaceFailed:TooClose")
    T.eq(w.act(g, "Face", { position = { 0, 2.55, 20 } }), "FaceStarted") -- behind: half a turn
    e.step(0.1)
    local _, yaw = hrp.CFrame:ToOrientation()
    T.near(math.abs(yaw), 0.6, 1e-6, "a tenth of a second's turn")
    e.step(1, 0.1)
    _, yaw = hrp.CFrame:ToOrientation()
    T.near(math.abs(yaw), math.pi, 1e-6, "facing it")
    T.eq(w.x.sky.turners[g], nil, "done turning")
    w.act(g, "Face", { position = { 20, 2.55, 0 } })
    w.act(g, "MoveTo", { position = { 5, 2.55, 5 } })
    T.eq(w.x.sky.turners[g], nil, "a walk turns the body itself")
    w.act(g, "Face", { position = { 20, 2.55, 0 } })
    local here = e.hrp(g).Position
    w.x.climbers[g] = { path = { here, here }, times = { 100 }, leg = 1, t = 0 }
    T.eq(w.act(g, "Face", { position = { -20, 2.55, 0 } }), "FaceFailed:Climbing")
    e.step(0.1)
    T.eq(w.x.sky.turners[g], nil, "a climb takes over")
    w.x.climbers[g] = nil
    w.act(g, "Face", { position = { -20, 2.55, 0 } })
    e.hrp(g):Destroy()
    e.step(0.1)
    T.eq(w.x.sky.turners[g], nil, "a body gone stops turning")
end)

T.test("a piece lost below the world is let go of, wherever it was", function()
    local w, g, block = beside()
    local e = w.e
    w.act(g, "Pickup", { position = at(block) })
    w.x.destroyBlock(block) -- lost while held
    T.eq(block.Parent, nil)
    T.eq(g:GetAttribute("LastActionResult"), "ResetAfterFall")
    local fallen = e.find("Block_7")
    fallen.Position = V.new(0, -300, 0) -- lying loose below the world
    e.step(0.1)
    T.eq(fallen.Parent, nil, "a piece below the world is gone")
    local b2 = e.find("Block_2")
    e.hrp(g).Position = b2.Position + V.new(0, 1.3, -2.5)
    w.act(g, "Pickup", { position = at(b2) })
    e.step(1.2)
    local p = e.hrp(g).Position
    w.act(g, "Place", { position = { p.X + 3, 1.3, p.Z } })
    w.x.destroyBlock(b2) -- while it is being set down
    T.eq(#w.x.placingBlocks, 0)
    w.x.destroyBlock(b2) -- already gone
    local b3 = e.find("Block_3")
    e.hrp(g).Position = b3.Position + V.new(0, 1.3, -2.5)
    w.act(g, "Pickup", { position = at(b3) })
    w.act(g, "Throw", { direction = { 1, 0, 0 } })
    local b4 = e.find("Block_4")
    w.x.thrownBlocks[2] = { block = b4, elapsed = 0, duration = 1 }
    w.x.destroyBlock(b3) -- while it flies
    T.eq(#w.x.thrownBlocks, 1)
    local lost = e.find("Block_6")
    lost:Destroy()
    e.step(0.1) -- a tracked block gone: forgotten
    T.eq(w.x.trackedBlocks[lost], nil)
end)

T.test("the golden ring of upstream's world, when switched on", function()
    local w = T.boot({ patch = { { "local ENABLE_LARGE_RING = false", "local ENABLE_LARGE_RING = true" } } })
    local ring = w.e.find("Ring_1")
    T.eq(ring:GetAttribute("RenderRole"), "Ring")
    local again = T.boot({
        patch = { { "local ENABLE_LARGE_RING = false", "local ENABLE_LARGE_RING = true" } },
        before = function(e)
            e.part("Ring_1", { AssemblyLinearVelocity = V.new(5, 0, 0) })
        end,
    })
    T.eq(again.e.find("Ring_1").AssemblyLinearVelocity.Magnitude, 0, "an old ring is put back still")
    T.eq(again.x.createRing("Ring_2", V.new(0, 1, 0), "Yellow", nil, V.new(1, 1, 1)).Name, "Ring_2")
end)

return T.done("test_hands")
