-- Mesa World - A simple mesa world with a player and ground

local RunService = game:GetService("RunService")
local Players = game:GetService("Players")
local AgentInputService = game:GetService("AgentInputService")

-- Workspace.Gravity = 196.2
Workspace.Gravity = 10

-- Godling (ADR-005): blocks at Minecraft scale. The body is 2 wide and 5 tall, so a 2.5 block is half its height
-- and a one-block doorway fits it. Upstream: 0.75.
local BLOCK_SIZE = 2.5
local GRID = BLOCK_SIZE -- placed blocks and logs settle into cells this wide (x and z)
local ENABLE_LARGE_RING = true
local PICKUP_RANGE = 6
local PLACE_RANGE = 7
local HOLD_OFFSET = Vector3.new(0, 4.0, 0) -- upstream 3.5: a held block clears the 5-tall body
local THROW_SPAWN_OFFSET_Y = 2.5
local THROW_FORWARD_OFFSET = 1.75
local THROW_SPEED = 16
local THROW_UPWARD_SPEED = 6
local THROW_CARRY_VELOCITY_FACTOR = 0.35
local THROW_COLLISION_GRACE_PERIOD = 0.18
local MIN_THROW_SPEED = 0
local MAX_THROW_SPEED = 10
local PLAYER_SPAWN_POSITION = Vector3.new(0, 5, 0)
local OUT_OF_BOUNDS_Y = -200
local WORLD_BOUNDARY_HALF_EXTENT = 80
local WORLD_BOUNDARY_HEIGHT = 80
local WORLD_BOUNDARY_THICKNESS = 6
local GROUND_HEIGHT = 10
local GROUND_Y = -(GROUND_HEIGHT * 0.5)
local OCEAN_COLOR = Color3.fromRGB(52, 128, 168)
local OCEAN_SIZE = 600
local OCEAN_THICKNESS = 0.45
local OCEAN_TOP_Y = -0.5
local OCEAN_Y = OCEAN_TOP_Y - (OCEAN_THICKNESS * 0.5)
local ROCK_COLOR = Color3.fromRGB(52, 49, 44)
local ROCK_SPAWN_POSITION = Vector3.new(-31.4, 3.05, 26.9)
local ROCK_SIZE = Vector3.new(3.2, 2.1, 2.8)
local ROCK_IMPACT_ARM_DELAY = 1.0
local ROCK_IMPACT_COOLDOWN = 0.35
local ROCK_MIN_IMPACT_SPEED = 6
local ROCK_MIN_IMPACT_ENERGY = 3000
local ROCK_ENERGY_PER_CUBE = 3000
local ROCK_MAX_IMPACT_CUBES = 0 -- upstream 8: at block scale they would be free blocks piling into each other;
                                 -- material comes from the quarry and the trees

-- Godling changes to Mesa Island (see README.md in this folder).
-- Human-paced hands (ADR-003 O2): a block rises into the hands and is lowered into place, as by a person.
local LIFT_SECONDS = 1.0
local PLACE_SECONDS = 1.2 -- upstream: 0.3
-- A steady supply of cubes (ADR-003 O7): while few cubes lie loose on open ground, one drops from the sky
-- at a clear, reachable spot. The spots follow a fixed random sequence, the same in every run.
local SUPPLY_INTERVAL = 120 -- seconds between deliveries
local SUPPLY_WHEN_FEWER_THAN = 6 -- loose cubes lying on open ground
local SUPPLY_SEED = 20261101
local SUPPLY_DROP_HEIGHT = 14
local SUPPLY_FROM_SKY = false -- superseded by the quarry (ADR-004); kept for viewer drops
-- Quarrying (ADR-004): a hammer and a rocky outcrop. Strikes with the hammer in hand break stone blocks off it,
-- heavy and grippy. It never runs out; every block costs work. (Long bricks were dropped at block scale, ADR-005.)
local QUARRY = { name = "Quarry", size = {10, 6, 8}, pos = {28, 3, -40} }
local HAMMER_HOME = Vector3.new(20, 0.2, -34)
local HAMMER_SIZE = Vector3.new(0.4, 0.4, 1.2)
local STRIKE_RANGE = 6 -- from the body centre to the target's nearest surface, like PICKUP_RANGE
local STRIKES_PER_STONE = 3
local STRIKE_COOLDOWN = 0.8 -- seconds between swings
-- Felling (ADR-004): with the axe in hand, a few strikes fell a tree into two logs. A stump is left, and it grows
-- back into the tree after TREE_REGROW_SECONDS.
local AXE_HOME = Vector3.new(-6, 0.2, 7)
local AXE_SIZE = Vector3.new(0.4, 0.4, 1.0)
local CHOPS_PER_TREE = 4
local TREE_REGROW_SECONDS = 600
local LOG_SIZE = Vector3.new(3 * BLOCK_SIZE, BLOCK_SIZE / 2, BLOCK_SIZE / 2) -- a beam three blocks long, along X
-- Ladder (ADR-004): carried like anything else. Set down, it stands upright and stays put; Climb takes the body
-- up to the surface its top reaches, or back down. The world moves the body: the engine has no climbing.
local LADDER_HOME = Vector3.new(4, 0.25, 6)
local LADDER_SIZE = Vector3.new(1.5, 3 * BLOCK_SIZE, 0.4) -- three blocks tall
local CLIMB_SPEED = 1.5 -- units per second
local BODY_ABOVE_FEET = 2.55 -- the body centre when standing (ground top is y=0)
-- Fastening (ADR-004): joins a placed piece to everything it touches, like pegs or mortar. A hammer strike on a
-- fastened piece knocks it loose again.
local FASTEN_COOLDOWN = 2.5
local FASTEN_MAX_JOINS = 6
-- Boulders: very heavy. Carrying one halves the walking pace.
local BOULDERS = { { name = "Boulder_1", pos = {14, 1.3, -42} }, { name = "Boulder_2", pos = {38, 1.3, -28} } }
local BOULDER_DIAMETER = 2.6
-- A person's hop (about 0.6 up) instead of upstream's 6-unit leap: the way up is ladders and building.
local JUMP_POWER = 15
-- Face: the body turns on the spot towards a point (the glance reflex), without stepping anywhere.
local TURN_RATE = 6 -- radians per second
-- Sky events (research report "God games lessons for Godling", batch 1): a stone falls from the sky, announced
-- by a dark shadow on the ground SKY_WARN_SECONDS before it lands, so the landing can be watched and met. It lands
-- as a stone block, building material. Viewers will buy these; until they can send them in, SKY_TEST_EVERY drops
-- one near the player on a timer (seconds, 0 = off; run_godling.py --sky-test-minutes sets it).
local SKY_TEST_EVERY = 0
local SKY_WARN_SECONDS = 40
local SKY_DROP_HEIGHT = 40
local SKY_FALL_SPEED = 25 -- already falling fast when it appears: about 1.3 s to the ground
local SKY_SPOT_NEAR, SKY_SPOT_FAR = 8, 16 -- from the player: close enough to see, clear of its feet
local SKY_SPOT_CLEARANCE = 4 -- no building piece this close, so a test drop never hits what was built
local SKY_SHADOW_CLEARANCE = 3 -- a stone lands only while nobody stands this close to its shadow's centre
-- The guest panel (tools/guest_panel.py) joins under this name to send sky powers. It has no body in the world: it
-- is parked out of sight under the island, and the mind leaves it out of what it sees.
local SKY_PLAYER = "Sky"
local SKY_PARKING = Vector3.new(0, -40, 0)
local SKY_GIFT_HEIGHT = 12 -- dropped stones and logs fall from here
local SKY_FLASH_SECONDS = 0.5 -- how long a lightning bolt shows
-- Models from the art pipeline (asset://name.glb); nil draws a plain coloured part.
local ART = { Hammer = "asset://hammer.glb", Quarry = "asset://quarry.glb", Stone = "asset://stone.glb",
    Axe = "asset://axe.glb", Log = "asset://log.glb", Ladder = "asset://ladder.glb", Boulder = "asset://boulder.glb",
    Stump = "asset://stump.glb" }
-- What settles into the grid when placed: building blocks and logs (not tools, ladders, rings or boulders).
local SNAPPED_ROLES = { PickupObject = true, Stone = true, Log = true }

local heldBlocksByPlayer = {}
local liftingBlocks = {} -- player -> { block, from, elapsed }
local placingBlocks = {} -- { block, startCFrame, targetCFrame, elapsed, duration }
local thrownBlocks = {} -- { block, elapsed, duration }
local trackedBlocks = {}
local impactBlockCounter = 0
local rockImpactStates = {}

local function findWorkspaceChild(name)
    return Workspace:FindFirstChild(name)
end

local blockColors = {
    Sand = Color3.fromRGB(214, 186, 128),
    Slate = Color3.fromRGB(148, 136, 124),
    Yellow = Color3.fromRGB(232, 192, 74),
    Gold = Color3.fromRGB(232, 192, 74),
}

local blockPhysics = PhysicalProperties.new(
    0.7, -- density
    0.9, -- friction
    0.03, -- elasticity
    1.0, -- friction weight
    1.0 -- elasticity weight
)
-- Quarried stone: much heavier than the play blocks and grippier, so it stays where it is set.
local stonePhysics = PhysicalProperties.new(2.6, 1.0, 0.02, 1.0, 1.0)
-- Wood: light, and grips a little less than stone.
local woodPhysics = PhysicalProperties.new(0.6, 0.8, 0.05, 1.0, 1.0)

local terrainPhysics = PhysicalProperties.new(
    2.0, -- density
    1.4, -- friction
    0.0, -- elasticity
    1.0, -- friction weight
    1.0 -- elasticity weight
)

--------------------------------------------------------------------------------
-- GROUND
--------------------------------------------------------------------------------

-- Ocean: large flat plane surrounding the island
local ocean = findWorkspaceChild("Ocean") or Instance.new("Part")
ocean.Name = "Ocean"
ocean.Size = Vector3.new(OCEAN_SIZE, OCEAN_THICKNESS, OCEAN_SIZE)
ocean.Position = Vector3.new(0, OCEAN_Y, 0)
ocean.Anchored = true
ocean.CanCollide = false
ocean.Color = OCEAN_COLOR
ocean.Material = Enum.Material.Glass
ocean.Transparency = 0.18
ocean:SetAttribute("RenderRole", "Ocean")
ocean.Parent = Workspace

-- Island ground: roughly circular outline built from 5 overlapping parts.
-- Each lobe is offset from true cardinal so the silhouette reads as organic, not a plus-sign.
local groundParts = {
    { name = "GroundCenter", size = {96, GROUND_HEIGHT, 100}, pos = {-2, GROUND_Y, 0} },
    { name = "GroundN",      size = {42, GROUND_HEIGHT, 14},  pos = {10, GROUND_Y, 56} },
    { name = "GroundS",      size = {36, GROUND_HEIGHT, 14},  pos = {-12, GROUND_Y, -55} },
    { name = "GroundW",      size = {14, GROUND_HEIGHT, 40},  pos = {-56, GROUND_Y, -3} },
    { name = "GroundE",      size = {10, GROUND_HEIGHT, 58},  pos = {48, GROUND_Y, 5} },
}

for _, g in ipairs(groundParts) do
    local part = findWorkspaceChild(g.name) or Instance.new("Part")
    part.Name = g.name
    part.Size = Vector3.new(g.size[1], g.size[2], g.size[3])
    part.Position = Vector3.new(g.pos[1], g.pos[2], g.pos[3])
    part.Anchored = true
    part.Color = Color3.fromRGB(85, 239, 196)
    part.Material = Enum.Material.SmoothPlastic
    part.CustomPhysicalProperties = terrainPhysics
    part:SetAttribute("RenderRole", "Ground")
    part.Parent = Workspace
end

-- Remove ground parts from earlier layouts that aren't in the current groundParts list.
local currentGroundNames = {}
for _, g in ipairs(groundParts) do
    currentGroundNames[g.name] = true
end
for _, legacyName in ipairs({ "Ground", "GroundNE", "GroundNW", "GroundSW", "GroundSE", "GroundE" }) do
    if not currentGroundNames[legacyName] then
        local stale = findWorkspaceChild(legacyName)
        if stale then
            stale:Destroy()
        end
    end
end

local invisibleWalls = {
    {
        name = "BoundaryNorth",
        size = Vector3.new(WORLD_BOUNDARY_HALF_EXTENT * 2, WORLD_BOUNDARY_HEIGHT, WORLD_BOUNDARY_THICKNESS),
        pos = Vector3.new(0, WORLD_BOUNDARY_HEIGHT / 2, WORLD_BOUNDARY_HALF_EXTENT + WORLD_BOUNDARY_THICKNESS / 2),
    },
    {
        name = "BoundarySouth",
        size = Vector3.new(WORLD_BOUNDARY_HALF_EXTENT * 2, WORLD_BOUNDARY_HEIGHT, WORLD_BOUNDARY_THICKNESS),
        pos = Vector3.new(0, WORLD_BOUNDARY_HEIGHT / 2, -WORLD_BOUNDARY_HALF_EXTENT - WORLD_BOUNDARY_THICKNESS / 2),
    },
    {
        name = "BoundaryEast",
        size = Vector3.new(WORLD_BOUNDARY_THICKNESS, WORLD_BOUNDARY_HEIGHT, WORLD_BOUNDARY_HALF_EXTENT * 2),
        pos = Vector3.new(WORLD_BOUNDARY_HALF_EXTENT + WORLD_BOUNDARY_THICKNESS / 2, WORLD_BOUNDARY_HEIGHT / 2, 0),
    },
    {
        name = "BoundaryWest",
        size = Vector3.new(WORLD_BOUNDARY_THICKNESS, WORLD_BOUNDARY_HEIGHT, WORLD_BOUNDARY_HALF_EXTENT * 2),
        pos = Vector3.new(-WORLD_BOUNDARY_HALF_EXTENT - WORLD_BOUNDARY_THICKNESS / 2, WORLD_BOUNDARY_HEIGHT / 2, 0),
    },
}

for _, wallDef in ipairs(invisibleWalls) do
    local wall = findWorkspaceChild(wallDef.name) or Instance.new("Part")
    wall.Name = wallDef.name
    wall.Size = wallDef.size
    wall.Position = wallDef.pos
    wall.Anchored = true
    wall.Transparency = 1
    wall.CanCollide = true
    wall.CanQuery = false
    wall.CanTouch = false
    wall.CustomPhysicalProperties = terrainPhysics
    wall.Parent = Workspace
end

local mesas = {
    -- Ground-level formations
    { name = "LowStep",       size = {8, 2, 10},     pos = {8, 1, 18} },
    { name = "LargeMesa",     size = {20, 4, 16},    pos = {20, 2, 20} },
    { name = "SmallPlateau",  size = {10, 2, 8},     pos = {-30, 1, 28} },
    { name = "SteppingStone", size = {8, 2.5, 8},    pos = {-18, 1.25, -12} },
    { name = "Ridge",         size = {6, 3, 25},     pos = {35, 1.5, -10} },
    { name = "TallMesa",      size = {12, 6, 10},    pos = {-25, 3, -20} },
    -- NE climbing path: large mesa (4) -> high shelf (7) -> peak (11)
    { name = "HighShelf",     size = {10, 7, 8},     pos = {25, 3.5, 28} },
    { name = "Peak",          size = {5, 11, 5},     pos = {28, 5.5, 32} },
    -- SW climbing path: tall mesa (6) -> tower base (7) -> summit (10) -> spire (20)
    { name = "TowerBase",     size = {8, 7, 8},      pos = {-28, 3.5, -26} },
    { name = "Summit",        size = {6, 10, 6},     pos = {-28, 5, -30} },
    { name = "Spire",         size = {4, 20, 4},     pos = {-30, 10, -33} },
}

for _, m in ipairs(mesas) do
    local mesa = findWorkspaceChild(m.name) or Instance.new("Part")
    mesa.Name = m.name
    mesa.Size = Vector3.new(m.size[1], m.size[2], m.size[3])
    mesa.Position = Vector3.new(m.pos[1], m.pos[2], m.pos[3])
    mesa.Anchored = true
    mesa.Color = Color3.fromRGB(200, 160, 100)
    mesa.CustomPhysicalProperties = terrainPhysics
    mesa:SetAttribute("RenderRole", "Mesa")
    mesa.Parent = Workspace
end

-- Trees (Godling): two groves and a few loners on open ground. Each collides as its trunk only; the renderer
-- draws art/build_props.py's tree, fitted to the part's height. Later they are to be felled into logs.
local trees = {
    { name = "Tree_1", size = {1.4, 8, 1.4},   pos = {-10, 4, 9} },
    { name = "Tree_2", size = {1.4, 9, 1.4},   pos = {-15, 4.5, 4} },
    { name = "Tree_3", size = {1.4, 7, 1.4},   pos = {-12, 3.5, 15} },
    { name = "Tree_4", size = {1.4, 8.5, 1.4}, pos = {12, 4.25, -25} },
    { name = "Tree_5", size = {1.4, 7.5, 1.4}, pos = {17, 3.75, -30} },
    { name = "Tree_6", size = {1.4, 9, 1.4},   pos = {8, 4.5, -33} },
    { name = "Tree_7", size = {1.4, 8, 1.4},   pos = {-40, 4, 8} },
    { name = "Tree_8", size = {1.4, 7, 1.4},   pos = {-2, 3.5, 30} },
}

for _, t in ipairs(trees) do
    local tree = findWorkspaceChild(t.name) or Instance.new("Part")
    tree.Name = t.name
    tree.Size = Vector3.new(t.size[1], t.size[2], t.size[3])
    tree.Position = Vector3.new(t.pos[1], t.pos[2], t.pos[3])
    tree.Anchored = true
    tree.Color = Color3.fromRGB(120, 80, 50)
    tree.CustomPhysicalProperties = terrainPhysics
    tree:SetAttribute("RenderRole", "Tree")
    tree:SetAttribute("ModelUrl", "asset://tree.glb")
    tree.Parent = Workspace
    t.part = tree -- felling turns it into a stump and regrowing restores it from this definition
end

do -- the quarry: an outcrop on open ground, terrain like a mesa (too high to climb)
    local quarry = findWorkspaceChild(QUARRY.name) or Instance.new("Part")
    quarry.Name = QUARRY.name
    quarry.Size = Vector3.new(QUARRY.size[1], QUARRY.size[2], QUARRY.size[3])
    quarry.Position = Vector3.new(QUARRY.pos[1], QUARRY.pos[2], QUARRY.pos[3])
    quarry.Anchored = true
    quarry.Material = Enum.Material.Slate
    quarry.Color = Color3.fromRGB(128, 124, 118)
    quarry.CustomPhysicalProperties = terrainPhysics
    quarry:SetAttribute("RenderRole", "Quarry")
    if ART.Quarry then
        quarry:SetAttribute("ModelUrl", ART.Quarry)
    end
    quarry.Parent = Workspace
end

--------------------------------------------------------------------------------
-- BLOCKS
--------------------------------------------------------------------------------

local function setPickupMetadata(block, colorName, renderRole)
    block:SetAttribute("RenderRole", renderRole or "PickupObject")
    block:SetAttribute("ItemColorName", colorName)
    block:SetAttribute("IsPickupObject", true)
    block:SetAttribute("IsCarryable", true)
    block:SetAttribute("CarryKind", renderRole or "Carryable")
end

local function createBlock(name, position, colorName)
    local existing = findWorkspaceChild(name)
    if existing then
        setPickupMetadata(existing, colorName, "PickupObject")
        trackedBlocks[existing] = true
        return existing
    end
    local block = Instance.new("Part")
    block.Name = name
    block.Size = Vector3.new(BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
    block.Position = position
    block.Anchored = false
    block.Material = Enum.Material.Slate
    block.Color = blockColors[colorName]
    block.CustomPhysicalProperties = stonePhysics -- upstream: the light blockPhysics; at block scale the body shoved them
    setPickupMetadata(block, colorName, "PickupObject")
    block.Parent = Workspace
    trackedBlocks[block] = true
    return block
end

-- A carryable piece other than the play blocks: quarried stones, logs, boulders, tools and the ladder.
local function createPiece(name, cframe, size, color, renderRole, physics, modelUrl, shape)
    local piece = Instance.new("Part")
    piece.Name = name
    piece.Size = size
    if shape then
        piece.Shape = shape
    end
    piece.CFrame = cframe
    piece.Anchored = false
    piece.Material = renderRole == "Log" and Enum.Material.Wood or Enum.Material.Slate
    piece.Color = color
    piece.CustomPhysicalProperties = physics
    setPickupMetadata(piece, "Slate", renderRole)
    if modelUrl then
        piece:SetAttribute("ModelUrl", modelUrl)
    end
    piece.Parent = Workspace
    trackedBlocks[piece] = true
    return piece
end

-- Things that belong to the island and turn up again at home if lost (in the sea).
local KEEPSAKES = {
    Hammer_1 = function()
        local p = createPiece("Hammer_1", CFrame.new(HAMMER_HOME), HAMMER_SIZE, Color3.fromRGB(140, 96, 60), "Tool",
            blockPhysics, ART.Hammer)
        p:SetAttribute("ToolKind", "Hammer")
    end,
    Axe_1 = function()
        local p = createPiece("Axe_1", CFrame.new(AXE_HOME), AXE_SIZE, Color3.fromRGB(150, 110, 70), "Tool",
            blockPhysics, ART.Axe)
        p:SetAttribute("ToolKind", "Axe")
    end,
    Ladder_1 = function() -- lying flat until someone sets it up
        createPiece("Ladder_1", CFrame.new(LADDER_HOME) * CFrame.fromOrientation(math.rad(90), 0, 0), LADDER_SIZE,
            Color3.fromRGB(176, 132, 84), "Ladder", woodPhysics, ART.Ladder)
    end,
}
for _, b in ipairs(BOULDERS) do
    KEEPSAKES[b.name] = function()
        local p = createPiece(b.name, CFrame.new(b.pos[1], b.pos[2], b.pos[3]),
            Vector3.new(BOULDER_DIAMETER, BOULDER_DIAMETER, BOULDER_DIAMETER), Color3.fromRGB(112, 108, 102), "Boulder",
            stonePhysics, ART.Boulder, Enum.PartType.Ball)
        p:SetAttribute("Heavy", true)
    end
end
local function restoreKeepsakes()
    for name, make in pairs(KEEPSAKES) do
        if not findWorkspaceChild(name) then
            make()
        end
    end
end
restoreKeepsakes()

local function createRock(name, position, size)
    local existing = findWorkspaceChild(name)
    if existing then
        setPickupMetadata(existing, "Slate", "Rock")
        existing.Color = ROCK_COLOR
        trackedBlocks[existing] = true
        return existing
    end

    local rock = Instance.new("Part")
    rock.Name = name
    rock.Size = size
    rock.Position = position
    rock.Anchored = false
    rock.Material = Enum.Material.Slate
    rock.Color = ROCK_COLOR
    rock.CustomPhysicalProperties = PhysicalProperties.new(
        8.0,
        0.9,
        0.0,
        1.0,
        1.0
    )
    setPickupMetadata(rock, "Slate", "Rock")
    rock.Parent = Workspace
    trackedBlocks[rock] = true
    return rock
end

local function createRing(name, position, colorName, rotationDegrees, size)
    local pitch = 0
    local yaw = 0
    local roll = 0
    if rotationDegrees then
        pitch = rotationDegrees[1] or pitch
        yaw = rotationDegrees[2] or yaw
        roll = rotationDegrees[3] or roll
    end
    local spawnCFrame = CFrame.new(position) * CFrame.Angles(math.rad(pitch), math.rad(yaw), math.rad(roll))

    local existing = findWorkspaceChild(name)
    if existing then
        setPickupMetadata(existing, colorName, "Ring")
        -- Snap ring to canonical spawn on script load so layout edits take effect without a db wipe.
        existing.Anchored = false
        existing.CFrame = spawnCFrame
        existing.AssemblyLinearVelocity = Vector3.new(0, 0, 0)
        existing.AssemblyAngularVelocity = Vector3.new(0, 0, 0)
        trackedBlocks[existing] = true
        return existing
    end
    local ring = Instance.new("Part")
    ring.Name = name
    ring.Size = size
    ring.Shape = Enum.PartType.Ring
    ring.CFrame = spawnCFrame
    ring.Anchored = false
    ring.Material = Enum.Material.Plastic
    ring.Color = blockColors[colorName]
    ring.CustomPhysicalProperties = PhysicalProperties.new(
        0.45,
        0.35,
        0.18,
        1.0,
        1.0
    )
    setPickupMetadata(ring, colorName, "Ring")
    ring.Parent = Workspace
    trackedBlocks[ring] = true
    return ring
end

-- Godling (ADR-005): the 12 starting blocks lie side by side on grid cells, one layer (4 x 3), instead of
-- upstream's tumble from the sky: at block scale they would land on each other, and a pile two layers high
-- would already count as a wall Godling never built.
local baseBlockPile = {}
for i = 0, 11 do
    baseBlockPile[i + 1] = { color = "Slate", pos = Vector3.new(12.5 + (i % 4) * BLOCK_SIZE, BLOCK_SIZE / 2,
        math.floor(i / 4) * BLOCK_SIZE) }
end

for index, blockDef in ipairs(baseBlockPile) do
    createBlock("Block_" .. index, blockDef.pos, blockDef.color)
end
impactBlockCounter = #baseBlockPile

local rock = createRock("Rock_1", ROCK_SPAWN_POSITION, ROCK_SIZE)

if ENABLE_LARGE_RING then
    createRing("Ring_1", Vector3.new(40, 0.28, -42), "Yellow", { 0, 32, 0 }, Vector3.new(3.6, 0.56, 3.6))
end

--------------------------------------------------------------------------------
-- PLAYER
--------------------------------------------------------------------------------

local function getHumanoidRootPart(player)
    local character = player.Character
    if character then
        return character:FindFirstChild("HumanoidRootPart")
    end
    return nil
end

local function setPlayerBlockState(player, block)
    -- Intentionally keep pickup/held state implicit in observations.
    -- Agents can infer state from world changes and LastActionResult.
end

local function setupPlayer(player, shouldSpawnAtStart)
    local humanoid = nil
    local character = player.Character
    if character then
        humanoid = character:FindFirstChild("Humanoid")
    end

    if player.Name == SKY_PLAYER then -- the guest panel: no body on the island
        local hrp = character and character:FindFirstChild("HumanoidRootPart")
        if hrp then
            hrp.Anchored = true
            hrp.CanCollide = false
            hrp.Position = SKY_PARKING
        end
        player:SetAttribute("LastActionResult", "Ready")
        return
    end

    if humanoid then
        humanoid.WalkSpeed = 16
        humanoid.JumpPower = JUMP_POWER -- upstream: 50
        player:SetAttribute("BaseWalkSpeed", humanoid.WalkSpeed) -- carrying a boulder halves it
    end

    if character then
        character:SetAttribute("ModelUrl", "asset://godling.glb")

        local hrp = character:FindFirstChild("HumanoidRootPart")
        if hrp then
            hrp:SetAttribute("ModelUrl", "asset://godling.glb") -- the renderer reads the model from the root part
            hrp:SetAttribute("ModelYawOffsetDeg", 180)
            if shouldSpawnAtStart ~= false then
                hrp.Position = PLAYER_SPAWN_POSITION
            end
        end
    end

    player:SetAttribute("LastActionResult", "Ready")
end

local function cleanupPlayer(player)
    local heldBlock = heldBlocksByPlayer[player]
    if heldBlock then
        heldBlocksByPlayer[player] = nil
        trackedBlocks[heldBlock] = nil
        rockImpactStates[heldBlock] = nil
        if heldBlock.Parent then
            heldBlock:Destroy()
        end
    end
end

local function resetPlayerToSpawn(player)
    local character = player.Character
    if not character then
        return
    end

    local hrp = character:FindFirstChild("HumanoidRootPart")
    local humanoid = character:FindFirstChild("Humanoid")
    if hrp then
        hrp.Position = PLAYER_SPAWN_POSITION
        hrp.AssemblyLinearVelocity = Vector3.new(0, 0, 0)
        hrp.AssemblyAngularVelocity = Vector3.new(0, 0, 0)
    end
    if humanoid then
        humanoid:CancelMoveTo()
    end
end

local function releaseBlockReferences(block)
    for player, heldBlock in pairs(heldBlocksByPlayer) do
        if heldBlock == block then
            heldBlocksByPlayer[player] = nil
            setPlayerBlockState(player, nil)
            player:SetAttribute("LastActionResult", "ResetAfterFall")
        end
    end

    local i = 1
    while i <= #placingBlocks do
        if placingBlocks[i].block == block then
            table.remove(placingBlocks, i)
        else
            i = i + 1
        end
    end

    local thrownIndex = 1
    while thrownIndex <= #thrownBlocks do
        if thrownBlocks[thrownIndex].block == block then
            table.remove(thrownBlocks, thrownIndex)
        else
            thrownIndex = thrownIndex + 1
        end
    end
end

local function destroyBlock(block)
    if not block.Parent then
        return
    end
    releaseBlockReferences(block)
    rockImpactStates[block] = nil
    trackedBlocks[block] = nil
    block:Destroy()
end

local function spawnImpactCubes(origin, count)
    for i = 1, count do
        impactBlockCounter = impactBlockCounter + 1
        local angle = (i / count) * math.pi * 2
        local radius = 1.1 + 0.35 * ((i - 1) % 3)
        local spawnOffset = Vector3.new(math.cos(angle) * radius, 0.9 + 0.15 * ((i - 1) % 2), math.sin(angle) * radius)
        local cube = createBlock("ImpactBlock_" .. impactBlockCounter, origin + spawnOffset, "Slate")
        cube.AssemblyLinearVelocity = Vector3.new(
            math.cos(angle) * (2.5 + i * 0.2),
            4.5 + i * 0.25,
            math.sin(angle) * (2.5 + i * 0.2)
        )
        cube.AssemblyAngularVelocity = Vector3.new(0, 6 + i, 0)
    end
end

local function armRockImpact(rockPart)
    rockImpactStates[rockPart] = {
        ignoreUntil = os.clock() + ROCK_IMPACT_ARM_DELAY,
        lastImpactAt = -math.huge,
    }

    rockPart.Touched:Connect(function(otherPart)
        if not otherPart or not otherPart:IsA("BasePart") or otherPart == rockPart then
            return
        end

        local state = rockImpactStates[rockPart]
        if not state then
            return
        end

        local now = os.clock()
        if now < state.ignoreUntil or now - state.lastImpactAt < ROCK_IMPACT_COOLDOWN then
            return
        end

        local speed = rockPart.AssemblyLinearVelocity.Magnitude
        if speed < ROCK_MIN_IMPACT_SPEED then
            return
        end

        local impactEnergy = 0.5 * rockPart:GetMass() * speed * speed
        if impactEnergy < ROCK_MIN_IMPACT_ENERGY then
            return
        end

        state.lastImpactAt = now
        local cubeCount = math.clamp(
            math.floor(impactEnergy / ROCK_ENERGY_PER_CUBE),
            1,
            ROCK_MAX_IMPACT_CUBES
        )
        spawnImpactCubes(rockPart.Position, cubeCount)
    end)
end

armRockImpact(rock)

--------------------------------------------------------------------------------
-- INPUT HANDLING
--------------------------------------------------------------------------------

local function getHumanoid(player)
    local character = player.Character
    if character then
        return character:FindFirstChild("Humanoid")
    end
    return nil
end

local function findNearestBlock(targetPosition, maxDistance)
    local closestBlock = nil
    local closestDistance = maxDistance

    for _, inst in ipairs(Workspace:GetDescendants()) do
        if inst:IsA("Part") and inst:GetAttribute("IsPickupObject") then
            local distance = (inst.Position - targetPosition).Magnitude
            if distance <= closestDistance then
                closestBlock = inst
                closestDistance = distance
            end
        end
    end

    return closestBlock
end

local function normalizeOrNil(vector)
    local magnitude = vector.Magnitude
    if magnitude <= 0.001 then
        return nil
    end
    return vector / magnitude
end

local function canReach(player, worldPosition, maxDistance)
    local hrp = getHumanoidRootPart(player)
    if not hrp then
        return false
    end
    return (hrp.Position - worldPosition).Magnitude <= maxDistance
end

local function setCarryPace(player, block)
    local humanoid = getHumanoid(player)
    local base = player:GetAttribute("BaseWalkSpeed")
    if humanoid and base then
        humanoid.WalkSpeed = (block and block:GetAttribute("Heavy")) and base / 2 or base
    end
end

local function releaseHeldBlock(player)
    local block = heldBlocksByPlayer[player]
    if not block then
        return nil
    end

    heldBlocksByPlayer[player] = nil
    setPlayerBlockState(player, nil)
    setCarryPace(player, nil)
    return block
end

local function parsePosition(pos)
    if type(pos) ~= "table" then return nil end
    local x = tonumber(pos[1])
    local y = tonumber(pos[2])
    local z = tonumber(pos[3])
    if not x or not y or not z then return nil end
    if x ~= x or y ~= y or z ~= z then return nil end
    return Vector3.new(x, y, z)
end

local function noteReach(player)
    -- Counts pick-ups and places, so the renderer can play the character's reach animation (Godling).
    player:SetAttribute("Reaches", (player:GetAttribute("Reaches") or 0) + 1)
end

local function pickupBlock(player, inputData)
    if heldBlocksByPlayer[player] then
        player:SetAttribute("LastActionResult", "PickupFailed:AlreadyHolding")
        return
    end

    if not inputData or not inputData.position then
        player:SetAttribute("LastActionResult", "PickupFailed:MissingPosition")
        return
    end

    local targetPosition = parsePosition(inputData.position)
    if not targetPosition then
        player:SetAttribute("LastActionResult", "PickupFailed:InvalidPosition")
        return
    end
    if not canReach(player, targetPosition, PICKUP_RANGE) then
        player:SetAttribute("LastActionResult", "PickupFailed:OutOfRange")
        return
    end

    local block = findNearestBlock(targetPosition, 1.5)
    if not block then
        player:SetAttribute("LastActionResult", "PickupFailed:NoBlock")
        return
    end
    if block:GetAttribute("Fastened") then -- joined to what it touches; a hammer strike knocks it loose
        player:SetAttribute("LastActionResult", "PickupFailed:Fastened")
        return
    end

    heldBlocksByPlayer[player] = block
    setCarryPace(player, block)
    block.Anchored = false
    block.AssemblyLinearVelocity = Vector3.new(0, 0, 0)
    block.AssemblyAngularVelocity = Vector3.new(0, 0, 0)
    block.CanCollide = false
    setPlayerBlockState(player, block)
    liftingBlocks[player] = { block = block, from = block.Position, elapsed = 0 }

    local impactState = rockImpactStates[block]
    if impactState then
        impactState.ignoreUntil = os.clock() + 0.25
    end

    player:SetAttribute("LastActionResult", "PickupSuccess")
    noteReach(player)
end

local function parseRotationDegrees(rotation)
    if rotation == nil then
        return nil
    end
    if type(rotation) == "number" then
        if rotation ~= rotation then
            return nil
        end
        return 0, tonumber(rotation), 0
    end
    if type(rotation) ~= "table" then
        return nil
    end

    local pitch = tonumber(rotation.pitch or rotation.x or rotation[1] or 0)
    local yaw = tonumber(rotation.yaw or rotation.y or rotation[2] or 0)
    local roll = tonumber(rotation.roll or rotation.z or rotation[3] or 0)
    if not pitch or not yaw or not roll then
        return nil
    end
    if pitch ~= pitch or yaw ~= yaw or roll ~= roll then
        return nil
    end
    return pitch, yaw, roll
end

local function getCurrentRotationCFrame(object)
    local pitch, yaw, roll = object.CFrame:ToOrientation()
    return CFrame.fromOrientation(pitch, yaw, roll)
end

local function getTargetPlacementCFrame(object, targetPosition, rotation)
    local rotationCFrame = getCurrentRotationCFrame(object)
    if rotation ~= nil then
        local pitch, yaw, roll = parseRotationDegrees(rotation)
        if pitch == nil then
            return nil
        end
        rotationCFrame = CFrame.fromOrientation(math.rad(pitch), math.rad(yaw), math.rad(roll))
    end
    return CFrame.new(targetPosition) * rotationCFrame
end

local function positionOccupied(player, targetCFrame, object)
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { heldBlocksByPlayer[player] }

    local probe = Instance.new("Part")
    probe.Size = object.Size
    probe.CFrame = targetCFrame
    probe.Shape = object.Shape

    local hits = Workspace:GetPartsInPart(probe, params)
    probe:Destroy()

    for _, hit in ipairs(hits) do
        if hit:IsA("Part") and hit:GetAttribute("RenderRole") ~= "SkyShadow" then -- a shadow takes no room
            return true
        end
    end

    return false
end

local function placeBlock(player, inputData)
    local block = heldBlocksByPlayer[player]
    if not block then
        player:SetAttribute("LastActionResult", "PlaceFailed:EmptyHands")
        return
    end

    if not inputData or not inputData.position then
        player:SetAttribute("LastActionResult", "PlaceFailed:MissingPosition")
        return
    end

    local targetPosition = parsePosition(inputData.position)
    if not targetPosition then
        player:SetAttribute("LastActionResult", "PlaceFailed:InvalidPosition")
        return
    end
    if not canReach(player, targetPosition, PLACE_RANGE) then
        player:SetAttribute("LastActionResult", "PlaceFailed:OutOfRange")
        return
    end

    local rotation = inputData.rotation
    if block:GetAttribute("RenderRole") == "Ladder" then -- a ladder always stands upright; only its facing turns
        local _, yaw = parseRotationDegrees(rotation or {})
        rotation = { pitch = 0, yaw = yaw or 0, roll = 0 }
    end
    if SNAPPED_ROLES[block:GetAttribute("RenderRole")] then -- blocks and logs settle into the grid (ADR-005)
        targetPosition = Vector3.new(math.floor(targetPosition.X / GRID + 0.5) * GRID, targetPosition.Y,
            math.floor(targetPosition.Z / GRID + 0.5) * GRID)
    end
    local targetCFrame = getTargetPlacementCFrame(block, targetPosition, rotation)
    if not targetCFrame then
        player:SetAttribute("LastActionResult", "PlaceFailed:InvalidRotation")
        return
    end

    if positionOccupied(player, targetCFrame, block) then
        player:SetAttribute("LastActionResult", "PlaceFailed:Occupied")
        return
    end

    local startCFrame = block.CFrame
    block.Anchored = true
    block.CanCollide = false
    releaseHeldBlock(player)

    table.insert(placingBlocks, {
        block = block,
        startCFrame = startCFrame,
        targetCFrame = targetCFrame,
        elapsed = 0,
        duration = PLACE_SECONDS,
    })

    player:SetAttribute("LastActionResult", "PlaceSuccess")
    noteReach(player)
end

local function clamp(value, minValue, maxValue)
    return math.max(minValue, math.min(maxValue, value))
end

local function getThrowDirection(inputData)
    if not inputData or not inputData.direction then
        return nil
    end

    local direction = parsePosition(inputData.direction)
    if not direction then
        return nil
    end
    return normalizeOrNil(direction)
end

local function getThrowSpeed(inputData)
    if not inputData or inputData.speed == nil then
        return clamp(THROW_SPEED, MIN_THROW_SPEED, MAX_THROW_SPEED)
    end

    return clamp(tonumber(inputData.speed) or THROW_SPEED, MIN_THROW_SPEED, MAX_THROW_SPEED)
end

local function throwBlock(player, inputData)
    local hrp = getHumanoidRootPart(player)
    local block = heldBlocksByPlayer[player]
    if not hrp or not block then
        player:SetAttribute("LastActionResult", "ThrowFailed:EmptyHands")
        return
    end

    if not inputData or not inputData.direction then
        player:SetAttribute("LastActionResult", "ThrowFailed:MissingDirection")
        return
    end

    local throwDirection = getThrowDirection(inputData)
    if not throwDirection then
        player:SetAttribute("LastActionResult", "ThrowFailed:InvalidDirection")
        return
    end

    local throwSpeed = getThrowSpeed(inputData)

    local blockToThrow = releaseHeldBlock(player)
    if not blockToThrow then
        player:SetAttribute("LastActionResult", "ThrowFailed:EmptyHands")
        return
    end

    blockToThrow.Anchored = false
    blockToThrow.CanCollide = false
    blockToThrow.Position = hrp.Position
        + Vector3.new(0, THROW_SPAWN_OFFSET_Y, 0)
        + throwDirection * THROW_FORWARD_OFFSET
    blockToThrow.AssemblyLinearVelocity = throwDirection * throwSpeed
        + Vector3.new(0, THROW_UPWARD_SPEED, 0)
        + hrp.AssemblyLinearVelocity * THROW_CARRY_VELOCITY_FACTOR
    blockToThrow.AssemblyAngularVelocity = Vector3.new(0, 8, 0)
    blockToThrow:SetNetworkOwner(nil)

    local impactState = rockImpactStates[blockToThrow]
    if impactState then
        impactState.ignoreUntil = os.clock() + THROW_COLLISION_GRACE_PERIOD
    end

    table.insert(thrownBlocks, {
        block = blockToThrow,
        elapsed = 0,
        duration = THROW_COLLISION_GRACE_PERIOD,
    })

    player:SetAttribute("LastActionResult", "ThrowSuccess")
end

--------------------------------------------------------------------------------
-- BUILDING: STRIKING, FASTENING, CLIMBING (Godling, ADR-004)
--------------------------------------------------------------------------------

local function isCarried(part)
    for _, held in pairs(heldBlocksByPlayer) do
        if held == part then
            return true
        end
    end
    return false
end

local function halfExtents(part) -- the part's axis-aligned half size in the world, whatever its rotation
    local s, cf = part.Size * 0.5, part.CFrame
    local r, u, l = cf.RightVector, cf.UpVector, cf.LookVector
    return Vector3.new(math.abs(r.X) * s.X + math.abs(u.X) * s.Y + math.abs(l.X) * s.Z,
        math.abs(r.Y) * s.X + math.abs(u.Y) * s.Y + math.abs(l.Y) * s.Z,
        math.abs(r.Z) * s.X + math.abs(u.Z) * s.Y + math.abs(l.Z) * s.Z)
end

local function nearestPoint(part, point)
    local c, e = part.Position, halfExtents(part)
    return Vector3.new(clamp(point.X, c.X - e.X, c.X + e.X), clamp(point.Y, c.Y - e.Y, c.Y + e.Y),
        clamp(point.Z, c.Z - e.Z, c.Z + e.Z))
end

local function isSolid(inst)
    if not inst:IsA("BasePart") or not inst.CanCollide then
        return false
    end
    local role = inst:GetAttribute("RenderRole")
    return role ~= "Ocean" and string.sub(inst.Name, 1, 8) ~= "Boundary"
end

-- The highest solid top over (x, z) between minTop and maxTop, ignoring `except`; nil if there is none.
local function surfaceTopAt(x, z, minTop, maxTop, except)
    local best = nil
    for _, inst in ipairs(Workspace:GetChildren()) do
        if inst ~= except and isSolid(inst) then
            local c, e = inst.Position, halfExtents(inst)
            if math.abs(x - c.X) <= e.X and math.abs(z - c.Z) <= e.Z then
                local top = c.Y + e.Y
                if top >= minTop and top <= maxTop and (best == nil or top > best) then
                    best = top
                end
            end
        end
    end
    return best
end

local quarryWork = { count = 0, made = 0 }
local lastStrikeAt = {}

-- Over a long run stones and logs pile up where they are made. A new piece must not appear inside one already
-- there (the physics would fling both): try spots along the given side, then higher up, so it drops onto the pile.
local function freeSpawn(cframe, size, side)
    local s = size * 0.5
    local r, u, l = cframe.RightVector, cframe.UpVector, cframe.LookVector
    local e = Vector3.new(math.abs(r.X) * s.X + math.abs(u.X) * s.Y + math.abs(l.X) * s.Z,
        math.abs(r.Y) * s.X + math.abs(u.Y) * s.Y + math.abs(l.Y) * s.Z,
        math.abs(r.Z) * s.X + math.abs(u.Z) * s.Y + math.abs(l.Z) * s.Z)
    local across, up = 2 * math.max(e.X, e.Z) + 0.1, 2 * e.Y + 0.05 -- one piece's width aside, its height up
    for lift = 0, 5 do
        for _, offset in ipairs({ 0, 1, -1, 2, -2 }) do
            local candidate = cframe + side * (offset * across) + Vector3.new(0, lift * up, 0)
            local c, clear = candidate.Position, true
            for _, inst in ipairs(Workspace:GetChildren()) do
                if isSolid(inst) then
                    local oc, oe = inst.Position, halfExtents(inst)
                    if math.abs(c.X - oc.X) < e.X + oe.X and math.abs(c.Y - oc.Y) < e.Y + oe.Y
                        and math.abs(c.Z - oc.Z) < e.Z + oe.Z then
                        clear = false
                        break
                    end
                end
            end
            if clear then
                return candidate
            end
        end
    end
    return cframe + Vector3.new(0, 5, 0)
end

local function breakStone(body, nearest)
    quarryWork.count = quarryWork.count + 1
    if quarryWork.count < STRIKES_PER_STONE then
        return "StrikeHit:" .. quarryWork.count .. "/" .. STRIKES_PER_STONE
    end
    quarryWork.count = 0
    quarryWork.made = quarryWork.made + 1
    -- A stone block breaks off the face towards the striker and drops at the quarry's foot.
    local out = Vector3.new(body.X - nearest.X, 0, body.Z - nearest.Z)
    out = out.Magnitude > 0.01 and out.Unit or Vector3.new(0, 0, 1)
    local spot = Vector3.new(nearest.X, BLOCK_SIZE / 2 + 0.05, nearest.Z) + out * (BLOCK_SIZE / 2 + 0.3)
    local name = "Stone_" .. quarryWork.made
    local size = Vector3.new(BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
    createPiece(name, freeSpawn(CFrame.new(spot), size, Vector3.new(-out.Z, 0, out.X)), size,
        Color3.fromRGB(150, 146, 140), "Stone", stonePhysics, ART.Stone)
    return "StrikeBroke:" .. name
end

local logCounter = 0

local fellTree -- below: chopping and lightning both fell trees

local function chopTree(tree, body)
    local chops = (tree:GetAttribute("Chops") or 0) + 1
    if chops < CHOPS_PER_TREE then
        tree:SetAttribute("Chops", chops)
        return "StrikeHit:" .. chops .. "/" .. CHOPS_PER_TREE
    end
    tree:SetAttribute("Chops", 0)
    return "StrikeFelled:" .. table.concat(fellTree(tree, body), ",")
end

-- A tree falls away from `body` into two logs lying along the fall; a stump stays behind. `mark` (optional) is
-- applied to each log. Returns the logs' names.
function fellTree(tree, body, mark)
    local base = Vector3.new(tree.Position.X, 0, tree.Position.Z)
    local away = Vector3.new(base.X - body.X, 0, base.Z - body.Z)
    away = away.Magnitude > 0.01 and away.Unit or Vector3.new(1, 0, 0)
    local side = Vector3.new(-away.Z, 0, away.X)
    local yaw = math.atan2(-away.Z, away.X) -- turns the log's length (X) along the fall
    local names = {}
    for i = 1, 2 do
        logCounter = logCounter + 1
        local spot = base + away * (1.0 + LOG_SIZE.X / 2) + side * ((i == 1 and -1 or 1) * (LOG_SIZE.Y / 2 + 0.1))
            + Vector3.new(0, LOG_SIZE.Y / 2 + 0.05, 0)
        local name = "Log_" .. logCounter
        local log = createPiece(name, freeSpawn(CFrame.new(spot) * CFrame.fromOrientation(0, yaw, 0), LOG_SIZE, side),
            LOG_SIZE, Color3.fromRGB(140, 98, 62), "Log", woodPhysics, ART.Log) -- a square beam: a round one rolled away
        if mark then
            mark(log)
        end
        names[i] = name
    end
    tree.Size = Vector3.new(tree.Size.X, 0.6, tree.Size.Z)
    tree.Position = Vector3.new(base.X, 0.3, base.Z)
    tree:SetAttribute("RenderRole", "Stump")
    tree:SetAttribute("ModelUrl", ART.Stump)
    tree:SetAttribute("FelledAt", os.clock())
    return names
end

local function regrowStump(t)
    local stump = t.part
    stump.Size = Vector3.new(t.size[1], t.size[2], t.size[3])
    stump.Position = Vector3.new(t.pos[1], t.pos[2], t.pos[3])
    stump:SetAttribute("RenderRole", "Tree")
    stump:SetAttribute("ModelUrl", "asset://tree.glb")
    stump:SetAttribute("SkyEvent", "") -- grown back by itself; a sky regrowth marks it again
end

local function regrowTrees()
    for _, t in ipairs(trees) do
        local stump = t.part
        if stump and stump.Parent and stump:GetAttribute("RenderRole") == "Stump"
            and os.clock() - (stump:GetAttribute("FelledAt") or 0) >= TREE_REGROW_SECONDS then
            regrowStump(t)
        end
    end
end

local function unfasten(piece)
    for _, child in ipairs(piece:GetChildren()) do
        if child:IsA("WeldConstraint") then
            child:Destroy()
        end
    end
    if piece:GetAttribute("RenderRole") ~= "Ladder" then -- a set-up ladder stays standing
        piece.Anchored = false
    end
    piece:SetAttribute("Fastened", false)
    return "StrikeLoosened:" .. piece.Name
end

local function strike(player, inputData)
    local hrp = getHumanoidRootPart(player)
    local held = heldBlocksByPlayer[player]
    local tool = held and held:GetAttribute("ToolKind")
    if not hrp or not tool then
        player:SetAttribute("LastActionResult", "StrikeFailed:NoTool")
        return
    end
    local target = inputData and inputData.name and findWorkspaceChild(tostring(inputData.name))
    if not target or not target:IsA("BasePart") then
        player:SetAttribute("LastActionResult", "StrikeFailed:NoTarget")
        return
    end
    local body = hrp.Position
    local nearest = nearestPoint(target, body)
    if (nearest - body).Magnitude > STRIKE_RANGE then
        player:SetAttribute("LastActionResult", "StrikeFailed:OutOfRange")
        return
    end
    if os.clock() - (lastStrikeAt[player] or -math.huge) < STRIKE_COOLDOWN then
        player:SetAttribute("LastActionResult", "StrikeFailed:TooSoon")
        return
    end
    lastStrikeAt[player] = os.clock()
    player:SetAttribute("Strikes", (player:GetAttribute("Strikes") or 0) + 1) -- the renderer plays the swing
    local role = target:GetAttribute("RenderRole")
    local result
    if target.Name == QUARRY.name and tool == "Hammer" then
        result = breakStone(body, nearest)
    elseif role == "Tree" and tool == "Axe" then
        result = chopTree(target, body)
    elseif target:GetAttribute("Fastened") and tool == "Hammer" then
        result = unfasten(target)
    else
        result = "StrikeNoEffect:" .. tool
    end
    player:SetAttribute("LastActionResult", result)
end

local lastFastenAt = {}

local function isPlacing(piece)
    for _, p in ipairs(placingBlocks) do
        if p.block == piece then
            return true
        end
    end
    return false
end

local function fasten(player, inputData)
    local hrp = getHumanoidRootPart(player)
    local piece = inputData and inputData.name and findWorkspaceChild(tostring(inputData.name))
    if not hrp or not piece or not piece:IsA("BasePart") or not piece:GetAttribute("IsPickupObject")
        or piece:GetAttribute("ToolKind") then
        player:SetAttribute("LastActionResult", "FastenFailed:NotAPiece")
        return
    end
    if isCarried(piece) or isPlacing(piece) then
        player:SetAttribute("LastActionResult", "FastenFailed:NotSetDown")
        return
    end
    if (nearestPoint(piece, hrp.Position) - hrp.Position).Magnitude > PLACE_RANGE then
        player:SetAttribute("LastActionResult", "FastenFailed:OutOfRange")
        return
    end
    if os.clock() - (lastFastenAt[player] or -math.huge) < FASTEN_COOLDOWN then
        player:SetAttribute("LastActionResult", "FastenFailed:TooSoon")
        return
    end
    lastFastenAt[player] = os.clock()
    -- Never weld to anything fixed: a weld to the anchored island ground made the engine move the ground with the
    -- piece, and the island sank. Resting on something fixed (ground, mesa, a piece already fastened in place),
    -- the piece is pinned in place itself, like mortar; touching only loose pieces, it is welded to them.
    local c, e = piece.Position, halfExtents(piece)
    local loose, onFixed = {}, false
    for _, other in ipairs(Workspace:GetChildren()) do
        if other ~= piece and isSolid(other) and not isCarried(other) then
            local oc, oe = other.Position, halfExtents(other)
            if math.abs(c.X - oc.X) <= e.X + oe.X + 0.08 and math.abs(c.Y - oc.Y) <= e.Y + oe.Y + 0.08
                and math.abs(c.Z - oc.Z) <= e.Z + oe.Z + 0.08 then
                if other.Anchored then
                    onFixed = true
                elseif #loose < FASTEN_MAX_JOINS then
                    table.insert(loose, other)
                end
            end
        end
    end
    if not onFixed and #loose == 0 then
        player:SetAttribute("LastActionResult", "FastenFailed:NothingTouching")
        return
    end
    if onFixed then
        piece.Anchored = true
    else
        for _, other in ipairs(loose) do
            local weld = Instance.new("WeldConstraint")
            weld.Part0 = piece
            weld.Part1 = other
            weld.Parent = piece
        end
    end
    piece:SetAttribute("Fastened", true)
    player:SetAttribute("Reaches", (player:GetAttribute("Reaches") or 0) + 1)
    player:SetAttribute("LastActionResult", "FastenSuccess:" .. (onFixed and "fixed" or #loose))
end

local climbers = {} -- player -> { path = {Vector3...}, times = {seconds per leg}, leg, t }

local function climb(player, inputData)
    local hrp = getHumanoidRootPart(player)
    local ladder = inputData and inputData.name and findWorkspaceChild(tostring(inputData.name))
    if not hrp or not ladder or ladder:GetAttribute("RenderRole") ~= "Ladder" then
        player:SetAttribute("LastActionResult", "ClimbFailed:NoLadder")
        return
    end
    if not ladder.Anchored or isCarried(ladder) then
        player:SetAttribute("LastActionResult", "ClimbFailed:NotSetUp")
        return
    end
    if climbers[player] then
        player:SetAttribute("LastActionResult", "ClimbFailed:AlreadyClimbing")
        return
    end
    local body = hrp.Position
    local feet = body.Y - BODY_ABOVE_FEET
    local lp = ladder.Position
    if Vector3.new(body.X - lp.X, 0, body.Z - lp.Z).Magnitude > 2.8 then
        player:SetAttribute("LastActionResult", "ClimbFailed:TooFar")
        return
    end
    local bottom, top = lp.Y - LADDER_SIZE.Y / 2, lp.Y + LADDER_SIZE.Y / 2
    local face = ladder.CFrame.LookVector
    face = Vector3.new(face.X, 0, face.Z).Unit
    -- At its foot: up. Standing on something higher, anywhere along its height (a ladder may be taller than the
    -- wall it stands against): down.
    local up = math.abs(feet - bottom) < 1.2
    if not up and (feet < bottom + 0.9 or feet > top + 0.6) then
        player:SetAttribute("LastActionResult", "ClimbFailed:NotAtAnEnd")
        return
    end
    -- Step off on whichever side of the ladder has a surface at the far end: going up, the highest surface the
    -- ladder reaches (at least a body's step above its foot); going down, the ground or floor at its foot.
    local best, bestTop = nil, nil
    for _, sign in ipairs({ 1, -1 }) do
        local spot = Vector3.new(lp.X, 0, lp.Z) + face * (sign * 1.5) -- clear of the ladder for a 2-wide body
        local found = up and surfaceTopAt(spot.X, spot.Z, bottom + 0.9, top + 0.5, ladder)
            or surfaceTopAt(spot.X, spot.Z, bottom - 1.2, bottom + 0.6, ladder)
        if found and (bestTop == nil or (up and found > bestTop) or (not up and found < bestTop)) then
            best, bestTop = spot, found
        end
    end
    if not best then
        player:SetAttribute("LastActionResult", up and "ClimbFailed:NothingAtTop" or "ClimbFailed:NothingAtBottom")
        return
    end
    local toBody = Vector3.new(body.X - lp.X, 0, body.Z - lp.Z)
    local onLadder = Vector3.new(lp.X, 0, lp.Z) + (toBody.Magnitude > 0.01 and toBody.Unit or face) * 1.2
    local endY = bestTop + BODY_ABOVE_FEET
    local path = { body, Vector3.new(onLadder.X, body.Y, onLadder.Z), Vector3.new(onLadder.X, endY + 0.3, onLadder.Z),
        Vector3.new(best.X, endY, best.Z) }
    local times = { 0.3, math.abs(endY + 0.3 - body.Y) / CLIMB_SPEED, 0.5 }
    local humanoid = getHumanoid(player)
    if humanoid then
        humanoid:CancelMoveTo()
    end
    hrp.Anchored = true
    climbers[player] = { path = path, times = times, leg = 1, t = 0 }
    player:SetAttribute("Climbing", true)
    player:SetAttribute("LastActionResult", string.format("ClimbStarted:%s:%.1f", up and "up" or "down",
        times[1] + times[2] + times[3]))
end

local function advanceClimbers(dt)
    for player, c in pairs(climbers) do
        local hrp = getHumanoidRootPart(player)
        if not hrp then
            climbers[player] = nil
        else
            c.t = c.t + dt
            while c.leg <= #c.times and c.t >= c.times[c.leg] do
                c.t = c.t - c.times[c.leg]
                c.leg = c.leg + 1
            end
            if c.leg > #c.times then
                hrp.CFrame = CFrame.new(c.path[#c.path]) * (hrp.CFrame - hrp.CFrame.Position)
                hrp.Anchored = false
                hrp.AssemblyLinearVelocity = Vector3.new(0, 0, 0)
                climbers[player] = nil
                player:SetAttribute("Climbing", false)
            else
                local a, b = c.path[c.leg], c.path[c.leg + 1]
                local alpha = c.times[c.leg] > 0 and c.t / c.times[c.leg] or 1
                hrp.CFrame = CFrame.new(a + (b - a) * alpha) * (hrp.CFrame - hrp.CFrame.Position)
            end
        end
    end
end

local turners = {} -- player -> the yaw Face is turning the body to
local skyPower -- with the sky events below: the guest panel's powers

local function yawOf(cframe) -- the way a part faces, as the yaw the engine gives a walking body (forward is -Z)
    local look = cframe.LookVector
    return math.atan2(-look.X, -look.Z)
end

local function face(player, inputData)
    local hrp = getHumanoidRootPart(player)
    local target = inputData and inputData.position and parsePosition(inputData.position)
    if not hrp or not target then
        player:SetAttribute("LastActionResult", "FaceFailed:InvalidPosition")
        return
    end
    if climbers[player] then
        player:SetAttribute("LastActionResult", "FaceFailed:Climbing")
        return
    end
    local dx, dz = target.X - hrp.Position.X, target.Z - hrp.Position.Z
    if dx * dx + dz * dz < 0.01 then
        player:SetAttribute("LastActionResult", "FaceFailed:TooClose")
        return
    end
    local humanoid = getHumanoid(player)
    if humanoid then
        humanoid:CancelMoveTo()
    end
    turners[player] = math.atan2(-dx, -dz)
    player:SetAttribute("LastActionResult", "FaceStarted")
end

local function advanceTurners(dt)
    for player, target in pairs(turners) do
        local hrp = getHumanoidRootPart(player)
        if not hrp or climbers[player] then
            turners[player] = nil
        else
            local now = yawOf(hrp.CFrame)
            local delta = (target - now + math.pi) % (2 * math.pi) - math.pi
            local step = math.clamp(delta, -TURN_RATE * dt, TURN_RATE * dt)
            hrp.CFrame = CFrame.new(hrp.Position) * CFrame.fromOrientation(0, now + step, 0)
            if math.abs(delta) <= TURN_RATE * dt then
                turners[player] = nil
            end
        end
    end
end

if AgentInputService then
    AgentInputService.InputReceived:Connect(function(player, inputType, inputData)
        local humanoid = getHumanoid(player)
        if not humanoid then return end

        if inputType == "MoveTo" and inputData and inputData.position then
            local targetPosition = parsePosition(inputData.position)
            if not targetPosition then
                player:SetAttribute("LastActionResult", "MoveToFailed:InvalidPosition")
                return
            end
            turners[player] = nil -- walking turns the body itself
            humanoid:MoveTo(targetPosition)
        elseif inputType == "Face" then
            face(player, inputData)
        elseif inputType == "Sky" then
            skyPower(player, inputData)
        elseif inputType == "Stop" then
            humanoid:CancelMoveTo()
        elseif inputType == "Jump" then
            humanoid.Jump = true
        elseif inputType == "Pickup" then
            pickupBlock(player, inputData)
        elseif inputType == "Place" then
            placeBlock(player, inputData)
        elseif inputType == "Throw" then
            throwBlock(player, inputData)
        elseif inputType == "Strike" then
            strike(player, inputData)
        elseif inputType == "Fasten" then
            fasten(player, inputData)
        elseif inputType == "Climb" then
            climb(player, inputData)
        else
            player:SetAttribute("LastActionResult", "InvalidAction")
        end
    end)
end

--------------------------------------------------------------------------------
-- SUPPLY (Godling, ADR-003 O7)
--------------------------------------------------------------------------------

local supplyState = SUPPLY_SEED
local supplyCounter = 0
local supplyTimer = 0
local keepsakeTimer = 0

local function supplyRandom()
    -- Park-Miller: small enough to stay exact in doubles, so every run gets the same sequence.
    supplyState = (supplyState * 16807) % 2147483647
    return supplyState / 2147483647
end

local function within(x, z, def, margin)
    return math.abs(x - def.pos[1]) < def.size[1] / 2 + margin and math.abs(z - def.pos[3]) < def.size[3] / 2 + margin
end

local function isHeld(part)
    for _, held in pairs(heldBlocksByPlayer) do
        if held == part then
            return true
        end
    end
    return false
end

local function looseGroundCubes()
    local count = 0
    for _, inst in ipairs(Workspace:GetChildren()) do
        if inst:IsA("Part") and inst:GetAttribute("RenderRole") == "PickupObject" and not isHeld(inst)
            and math.abs(inst.Position.Y - BLOCK_SIZE / 2) < 0.15 then
            count = count + 1
        end
    end
    return count
end

local function clearSupplySpot(x, z)
    local onGround = false
    for _, g in ipairs(groundParts) do
        if within(x, z, g, -3) then -- well inside the island, away from the shore
            onGround = true
        end
    end
    if not onGround then
        return false
    end
    for _, m in ipairs(mesas) do
        if within(x, z, m, 2.5) then -- not on a mesa and not against its foot
            return false
        end
    end
    for _, t in ipairs(trees) do
        if within(x, z, t, 2.5) then -- not into a tree's crown
            return false
        end
    end
    if within(x, z, QUARRY, 2.5) then
        return false
    end
    for _, inst in ipairs(Workspace:GetChildren()) do
        if inst:IsA("Part") and inst:GetAttribute("IsPickupObject") then
            local dx, dz = inst.Position.X - x, inst.Position.Z - z
            if dx * dx + dz * dz < 4 then
                return false
            end
        end
    end
    for _, player in ipairs(Players:GetPlayers()) do
        local hrp = getHumanoidRootPart(player)
        if hrp then
            local dx, dz = hrp.Position.X - x, hrp.Position.Z - z
            if dx * dx + dz * dz < 9 then
                return false
            end
        end
    end
    return true
end

local function deliverCube()
    for _ = 1, 40 do
        local x = -60 + supplyRandom() * 115
        local z = -62 + supplyRandom() * 124
        if clearSupplySpot(x, z) then
            supplyCounter = supplyCounter + 1
            createBlock("SupplyBlock_" .. supplyCounter, Vector3.new(x, SUPPLY_DROP_HEIGHT, z), "Sand")
            return
        end
    end
end

--------------------------------------------------------------------------------
-- SKY EVENTS (Godling: a stone falls from the sky, announced by its shadow)
--------------------------------------------------------------------------------

local skyState = SUPPLY_SEED + 1 -- its own fixed sequence, so the supply drops stay as they were
local skyCounter = 0
local skyTimer = 0
local skyFalls = {} -- { n, x, z, shadow, landsAt }

local function skyRandom()
    skyState = (skyState * 16807) % 2147483647
    return skyState / 2147483647
end

local function clearOfPieces(x, z, clearance)
    for _, inst in ipairs(Workspace:GetChildren()) do
        if inst:IsA("Part") and inst:GetAttribute("IsPickupObject") then
            local dx, dz = inst.Position.X - x, inst.Position.Z - z
            if dx * dx + dz * dz < clearance * clearance then
                return false
            end
        end
    end
    return true
end

local function skySpotNear(player)
    local hrp = getHumanoidRootPart(player)
    if not hrp then
        return nil
    end
    for _ = 1, 40 do
        local angle = skyRandom() * 2 * math.pi
        local dist = SKY_SPOT_NEAR + skyRandom() * (SKY_SPOT_FAR - SKY_SPOT_NEAR)
        local x, z = hrp.Position.X + math.cos(angle) * dist, hrp.Position.Z + math.sin(angle) * dist
        if clearSupplySpot(x, z) and clearOfPieces(x, z, SKY_SPOT_CLEARANCE) then
            return x, z
        end
    end
    return nil
end

local skyFlashes = {} -- { part, gone }

local function skyMark(kind, id)
    return function(part)
        part:SetAttribute("SkyEvent", kind)
        part:SetAttribute("SkyId", id)
    end
end

local function skyMarker(name, size, position, color, role) -- a shadow or a bolt: seen, never touched
    local part = Instance.new("Part")
    part.Name = name
    part.Size = size
    part.Position = position
    part.Anchored = true
    part.CanCollide = false
    part.Color = color
    part:SetAttribute("RenderRole", role)
    part.Parent = Workspace
    return part
end

local function godlingPlayer() -- the one the sky aims for: the first player that is not the guest panel
    for _, player in ipairs(Players:GetPlayers()) do
        if player.Name ~= SKY_PLAYER then
            return player
        end
    end
    return nil
end

local function shadowOccupied(fall) -- the sky never drops a stone on someone: it waits until the shadow is clear
    for _, player in ipairs(Players:GetPlayers()) do
        local hrp = player.Name ~= SKY_PLAYER and getHumanoidRootPart(player)
        if hrp then
            local dx, dz = hrp.Position.X - fall.x, hrp.Position.Z - fall.z
            if dx * dx + dz * dz < SKY_SHADOW_CLEARANCE * SKY_SHADOW_CLEARANCE then
                return true
            end
        end
    end
    return false
end

local function announceSkyFall(x, z)
    skyCounter = skyCounter + 1
    local shadow = skyMarker("SkyShadow_" .. skyCounter, Vector3.new(3.2, 0.06, 3.2), Vector3.new(x, 0.04, z),
        Color3.fromRGB(24, 22, 20), "SkyShadow")
    skyMark("Meteor", skyCounter)(shadow)
    shadow:SetAttribute("LandsIn", SKY_WARN_SECONDS)
    table.insert(skyFalls, { n = skyCounter, x = x, z = z, shadow = shadow, landsAt = os.clock() + SKY_WARN_SECONDS })
    print(string.format("SKY Meteor #%d warned at (%.1f, %.1f), lands in %ds", skyCounter, x, z, SKY_WARN_SECONDS))
    return skyCounter
end

local function advanceSkyFalls()
    local now = os.clock()
    local i = 1
    while i <= #skyFalls do
        local fall = skyFalls[i]
        if now >= fall.landsAt and not shadowOccupied(fall) then
            fall.shadow:Destroy()
            local size = Vector3.new(BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
            local stone = createPiece("Meteor_" .. fall.n, CFrame.new(fall.x, SKY_DROP_HEIGHT, fall.z), size,
                Color3.fromRGB(64, 56, 52), "Stone", stonePhysics) -- dark and bare: not a quarried stone
            skyMark("Meteor", fall.n)(stone)
            stone.AssemblyLinearVelocity = Vector3.new(0, -SKY_FALL_SPEED, 0)
            print(string.format("SKY Meteor #%d landed at (%.1f, %.1f)", fall.n, fall.x, fall.z))
            table.remove(skyFalls, i)
        else
            local left = math.max(0, math.ceil(fall.landsAt - now)) -- 0 while it waits for a clear shadow
            if fall.shadow:GetAttribute("LandsIn") ~= left then
                fall.shadow:SetAttribute("LandsIn", left)
            end
            i = i + 1
        end
    end
    i = 1
    while i <= #skyFlashes do
        if now >= skyFlashes[i].gone then
            skyFlashes[i].part:Destroy()
            table.remove(skyFlashes, i)
        else
            i = i + 1
        end
    end
end

local function nearestTree(role, to)
    local best, bestDist = nil, math.huge
    for _, t in ipairs(trees) do
        local part = t.part
        if part and part.Parent and part:GetAttribute("RenderRole") == role then
            local d = (Vector3.new(part.Position.X, 0, part.Position.Z) - Vector3.new(to.X, 0, to.Z)).Magnitude
            if d < bestDist then
                best, bestDist = t, d
            end
        end
    end
    return best
end

local function dropGift(kind, x, z)
    skyCounter = skyCounter + 1
    local piece
    if kind == "Stone" then
        quarryWork.made = quarryWork.made + 1 -- stones share one numbering, wherever they come from
        local size = Vector3.new(BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
        piece = createPiece("Stone_" .. quarryWork.made, CFrame.new(x, SKY_GIFT_HEIGHT, z), size,
            Color3.fromRGB(150, 146, 140), "Stone", stonePhysics, ART.Stone)
    else
        logCounter = logCounter + 1
        piece = createPiece("Log_" .. logCounter, CFrame.new(x, SKY_GIFT_HEIGHT, z), LOG_SIZE,
            Color3.fromRGB(140, 98, 62), "Log", woodPhysics, ART.Log)
    end
    skyMark(kind, skyCounter)(piece)
    print(string.format("SKY %s #%d dropped %s at (%.1f, %.1f)", kind, skyCounter, piece.Name, x, z))
    return skyCounter
end

-- What the guest panel can do. Viewers choose what; the world chooses where: near Godling, in view, clear of what
-- it built. Each returns the event's number, or nil and why not.
local SKY_POWERS = {
    Meteor = function(godling)
        local x, z = skySpotNear(godling)
        if not x then
            return nil, "NoClearSpot"
        end
        return announceSkyFall(x, z)
    end,
    Stone = function(godling)
        local x, z = skySpotNear(godling)
        if not x then
            return nil, "NoClearSpot"
        end
        return dropGift("Stone", x, z)
    end,
    Log = function(godling)
        local x, z = skySpotNear(godling)
        if not x then
            return nil, "NoClearSpot"
        end
        return dropGift("Log", x, z)
    end,
    Lightning = function(godling)
        local hrp = getHumanoidRootPart(godling)
        local t = hrp and nearestTree("Tree", hrp.Position)
        if not t then
            return nil, "NoStandingTree"
        end
        skyCounter = skyCounter + 1
        local p = t.part.Position
        local bolt = skyMarker("SkyBolt_" .. skyCounter, Vector3.new(0.35, 30, 0.35), Vector3.new(p.X, 15, p.Z),
            Color3.fromRGB(255, 244, 170), "SkyFlash")
        table.insert(skyFlashes, { part = bolt, gone = os.clock() + SKY_FLASH_SECONDS })
        local mark = skyMark("Lightning", skyCounter)
        local names = fellTree(t.part, hrp.Position, function(log)
            mark(log)
            log:SetAttribute("FromTree", t.name)
        end)
        print(string.format("SKY Lightning #%d felled %s into %s", skyCounter, t.name, table.concat(names, ",")))
        return skyCounter
    end,
    Regrow = function(godling)
        local hrp = getHumanoidRootPart(godling)
        local t = hrp and nearestTree("Stump", hrp.Position)
        if not t then
            return nil, "NoStump"
        end
        skyCounter = skyCounter + 1
        regrowStump(t)
        skyMark("Regrow", skyCounter)(t.part)
        print(string.format("SKY Regrow #%d grew %s back", skyCounter, t.name))
        return skyCounter
    end,
}

function skyPower(player, inputData)
    if player.Name ~= SKY_PLAYER then -- only the guest panel calls on the sky; Godling cannot
        player:SetAttribute("LastActionResult", "SkyFailed:NotTheSky")
        return
    end
    local name = inputData and tostring(inputData.power or "")
    local power = SKY_POWERS[name]
    local godling = godlingPlayer()
    if not power or not godling then
        player:SetAttribute("LastActionResult", "SkyFailed:" .. (power and "NobodyHere" or "UnknownPower"))
        return
    end
    local id, why = power(godling)
    player:SetAttribute("LastActionResult", id and ("SkyDone:" .. name .. ":" .. id) or ("SkyFailed:" .. why))
end

--------------------------------------------------------------------------------
-- MAIN LOOP
--------------------------------------------------------------------------------

RunService.Heartbeat:Connect(function(dt)
    for _, player in ipairs(Players:GetPlayers()) do
        local hrp = getHumanoidRootPart(player)
        if hrp and hrp.Position.Y < OUT_OF_BOUNDS_Y then
            resetPlayerToSpawn(player)
        end
    end

    -- Update held blocks (a block just picked up rises into the hands over LIFT_SECONDS)
    for player, heldBlock in pairs(heldBlocksByPlayer) do
        local hrp = getHumanoidRootPart(player)
        if hrp and heldBlock then
            local target = hrp.Position + HOLD_OFFSET
            local lift = liftingBlocks[player]
            if lift and lift.block == heldBlock and lift.elapsed < LIFT_SECONDS then
                lift.elapsed = lift.elapsed + dt
                local alpha = math.min(lift.elapsed / LIFT_SECONDS, 1)
                local t = 1 - (1 - alpha) * (1 - alpha)
                heldBlock.Position = lift.from + (target - lift.from) * t
            else
                liftingBlocks[player] = nil
                if heldBlock:GetAttribute("RenderRole") == "Ladder" then
                    -- Carried lying flat along the way the body faces; set down, it stands up again.
                    heldBlock.CFrame = CFrame.new(target) * (hrp.CFrame - hrp.CFrame.Position)
                        * CFrame.fromOrientation(math.rad(90), 0, 0)
                else
                    heldBlock.Position = target
                end
            end
            heldBlock.AssemblyLinearVelocity = Vector3.new(0, 0, 0)
            heldBlock.AssemblyAngularVelocity = Vector3.new(0, 0, 0)
        end
    end

    supplyTimer = supplyTimer + dt
    if supplyTimer >= SUPPLY_INTERVAL then
        supplyTimer = 0
        if SUPPLY_FROM_SKY and looseGroundCubes() < SUPPLY_WHEN_FEWER_THAN then
            deliverCube()
        end
    end

    advanceClimbers(dt)
    advanceTurners(dt)
    if SKY_TEST_EVERY > 0 then
        skyTimer = skyTimer + dt
        if skyTimer >= SKY_TEST_EVERY then
            skyTimer = 0
            local player = godlingPlayer()
            if player then
                local x, z = skySpotNear(player)
                if x then
                    announceSkyFall(x, z)
                end
            end
        end
    end
    advanceSkyFalls()
    keepsakeTimer = keepsakeTimer + dt
    if keepsakeTimer >= 10 then
        keepsakeTimer = 0
        restoreKeepsakes() -- tools, the ladder and boulders lost in the sea turn up again at home
        regrowTrees()
    end

    -- Animate placing blocks
    local i = 1
    while i <= #placingBlocks do
        local p = placingBlocks[i]
        p.elapsed = p.elapsed + dt
        local alpha = math.min(p.elapsed / p.duration, 1)
        -- Smooth ease-out
        local t = 1 - (1 - alpha) * (1 - alpha)
        p.block.CFrame = p.startCFrame:Lerp(p.targetCFrame, t)

        if alpha >= 1 then
            p.block.Anchored = p.block:GetAttribute("RenderRole") == "Ladder" -- a set-up ladder stands by itself
            p.block.CanCollide = true
            setPickupMetadata(
                p.block,
                p.block:GetAttribute("ItemColorName"),
                p.block:GetAttribute("RenderRole")
            )
            local impactState = rockImpactStates[p.block]
            if impactState then
                impactState.ignoreUntil = os.clock() + 0.15
            end
            table.remove(placingBlocks, i)
        else
            i = i + 1
        end
    end

    local thrownIndex = 1
    while thrownIndex <= #thrownBlocks do
        local thrown = thrownBlocks[thrownIndex]
        if not thrown.block.Parent then
            table.remove(thrownBlocks, thrownIndex)
        else
            thrown.elapsed = thrown.elapsed + dt
            if thrown.elapsed >= thrown.duration then
                thrown.block.CanCollide = true
                table.remove(thrownBlocks, thrownIndex)
            else
                thrownIndex = thrownIndex + 1
            end
        end
    end

    for block, _ in pairs(trackedBlocks) do
        if not block.Parent then
            trackedBlocks[block] = nil
            rockImpactStates[block] = nil
        elseif block.Position.Y < OUT_OF_BOUNDS_Y then
            destroyBlock(block)
        end
    end
end)

--------------------------------------------------------------------------------
-- INITIALIZATION
--------------------------------------------------------------------------------

Players.PlayerAdded:Connect(function(player)
    setupPlayer(player, true)
end)
Players.PlayerRemoving:Connect(cleanupPlayer)

for _, player in ipairs(Players:GetPlayers()) do
    setupPlayer(player, false)
end

print("=== Mesa World ===")
