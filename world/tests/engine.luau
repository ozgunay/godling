-- A stand-in for the parts of Clawblox's engine API that world/main.lua uses, for the world's tests (TESTING.md).
-- No physics: parts stay where they are put, and a test moves time on with step(dt) (os.clock and Heartbeat), drops
-- loose pieces onto what is under them with drop(), and plays a body's walk with walk(). Randomness is the test's: a
-- queue of numbers, then a fixed sequence.

local Engine = {}

-- ---- Vector3 -----------------------------------------------------------------------------------------------------
local Vector3 = {}
local V = {}

local function vec(x, y, z)
    return setmetatable({ X = x, Y = y, Z = z }, V)
end

V.__index = function(v, key)
    if key == "Magnitude" then
        return math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
    elseif key == "Unit" then
        local m = math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z)
        return vec(v.X / m, v.Y / m, v.Z / m)
    end
    return V[key]
end
V.__add = function(a, b) return vec(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V.__sub = function(a, b) return vec(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V.__unm = function(a) return vec(-a.X, -a.Y, -a.Z) end
V.__mul = function(a, b)
    if type(a) == "number" then
        return vec(a * b.X, a * b.Y, a * b.Z)
    elseif type(b) == "number" then
        return vec(a.X * b, a.Y * b, a.Z * b)
    end
    return vec(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V.__div = function(a, b)
    if type(b) == "number" then
        return vec(a.X / b, a.Y / b, a.Z / b)
    end
    return vec(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
end
V.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
V.__tostring = function(v) return string.format("%g, %g, %g", v.X, v.Y, v.Z) end
function V.Dot(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end
function V.Cross(a, b) return vec(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X) end
function V.Lerp(a, b, t) return a + (b - a) * t end
function Vector3.new(x, y, z) return vec(x or 0, y or 0, z or 0) end
Vector3.zero = vec(0, 0, 0)

-- ---- CFrame: a position and a rotation matrix (rows) ------------------------------------------------------------
local CFrame = {}
local C = {}

local function cf(p, r)
    return setmetatable({ p = p, r = r }, C)
end

local IDENTITY = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }

local function mul(a, b)
    local out = {}
    for i = 1, 3 do
        out[i] = {}
        for j = 1, 3 do
            out[i][j] = a[i][1] * b[1][j] + a[i][2] * b[2][j] + a[i][3] * b[3][j]
        end
    end
    return out
end

local function apply(r, v)
    return vec(r[1][1] * v.X + r[1][2] * v.Y + r[1][3] * v.Z, r[2][1] * v.X + r[2][2] * v.Y + r[2][3] * v.Z,
        r[3][1] * v.X + r[3][2] * v.Y + r[3][3] * v.Z)
end

local function rx(a)
    local c, s = math.cos(a), math.sin(a)
    return { { 1, 0, 0 }, { 0, c, -s }, { 0, s, c } }
end
local function ry(a)
    local c, s = math.cos(a), math.sin(a)
    return { { c, 0, s }, { 0, 1, 0 }, { -s, 0, c } }
end
local function rz(a)
    local c, s = math.cos(a), math.sin(a)
    return { { c, -s, 0 }, { s, c, 0 }, { 0, 0, 1 } }
end

C.__index = function(c, key)
    if key == "Position" then
        return c.p
    elseif key == "X" then
        return c.p.X
    elseif key == "Y" then
        return c.p.Y
    elseif key == "Z" then
        return c.p.Z
    elseif key == "RightVector" then
        return vec(c.r[1][1], c.r[2][1], c.r[3][1])
    elseif key == "UpVector" then
        return vec(c.r[1][2], c.r[2][2], c.r[3][2])
    elseif key == "LookVector" then
        return vec(-c.r[1][3], -c.r[2][3], -c.r[3][3])
    end
    return C[key]
end
C.__mul = function(a, b)
    if getmetatable(b) == V then
        return a.p + apply(a.r, b)
    end
    return cf(a.p + apply(a.r, b.p), mul(a.r, b.r))
end
C.__add = function(a, v) return cf(a.p + v, a.r) end
C.__sub = function(a, v) return cf(a.p - v, a.r) end

-- Roblox's orientation: Y, then X, then Z (fromOrientation), as rotations about the world's axes.
function C.ToOrientation(c)
    local m = c.r
    local x = math.asin(math.clamp(-m[2][3], -1, 1))
    if math.abs(m[2][3]) < 0.9999999 then
        return x, math.atan2(m[1][3], m[3][3]), math.atan2(m[2][1], m[2][2])
    end
    return x, math.atan2(-m[3][1], m[1][1]), 0
end

local function quat(m)
    local t = m[1][1] + m[2][2] + m[3][3]
    if t > 0 then
        local s = math.sqrt(t + 1) * 2
        return { (m[3][2] - m[2][3]) / s, (m[1][3] - m[3][1]) / s, (m[2][1] - m[1][2]) / s, s / 4 }
    elseif m[1][1] > m[2][2] and m[1][1] > m[3][3] then
        local s = math.sqrt(1 + m[1][1] - m[2][2] - m[3][3]) * 2
        return { s / 4, (m[1][2] + m[2][1]) / s, (m[1][3] + m[3][1]) / s, (m[3][2] - m[2][3]) / s }
    elseif m[2][2] > m[3][3] then
        local s = math.sqrt(1 + m[2][2] - m[1][1] - m[3][3]) * 2
        return { (m[1][2] + m[2][1]) / s, s / 4, (m[2][3] + m[3][2]) / s, (m[1][3] - m[3][1]) / s }
    end
    local s = math.sqrt(1 + m[3][3] - m[1][1] - m[2][2]) * 2
    return { (m[1][3] + m[3][1]) / s, (m[2][3] + m[3][2]) / s, s / 4, (m[2][1] - m[1][2]) / s }
end

local function matrix(q)
    local x, y, z, w = q[1], q[2], q[3], q[4]
    return { { 1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w) },
        { 2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w) },
        { 2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y) } }
end

function C.Lerp(a, b, t)
    local qa, qb = quat(a.r), quat(b.r)
    local d = qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3] + qa[4] * qb[4]
    if d < 0 then
        qb = { -qb[1], -qb[2], -qb[3], -qb[4] }
    end
    local q = {}
    local n = 0
    for i = 1, 4 do
        q[i] = qa[i] + (qb[i] - qa[i]) * t
        n = n + q[i] * q[i]
    end
    n = math.sqrt(n)
    for i = 1, 4 do
        q[i] = q[i] / n
    end
    return cf(a.p:Lerp(b.p, t), matrix(q))
end

function CFrame.new(x, y, z)
    if x == nil then
        return cf(vec(0, 0, 0), IDENTITY)
    elseif type(x) == "number" then
        return cf(vec(x, y, z), IDENTITY)
    end
    return cf(x, IDENTITY)
end
function CFrame.fromOrientation(x, y, z) return cf(vec(0, 0, 0), mul(mul(ry(y), rx(x)), rz(z))) end
function CFrame.Angles(x, y, z) return cf(vec(0, 0, 0), mul(mul(rx(x), ry(y)), rz(z))) end

-- ---- small value types --------------------------------------------------------------------------------------------
local Color3 = {}
function Color3.new(r, g, b) return { R = r or 0, G = g or 0, B = b or 0 } end
function Color3.fromRGB(r, g, b) return { R = r / 255, G = g / 255, B = b / 255 } end

local PhysicalProperties = {}
function PhysicalProperties.new(density, friction, elasticity, frictionWeight, elasticityWeight)
    return { Density = density, Friction = friction, Elasticity = elasticity, FrictionWeight = frictionWeight,
        ElasticityWeight = elasticityWeight }
end

local function enumOf(kind)
    return setmetatable({}, { __index = function(t, name)
        local item = { Name = name, EnumType = kind }
        rawset(t, name, item)
        return item
    end })
end
local Enum = setmetatable({}, { __index = function(t, kind)
    local e = enumOf(kind)
    rawset(t, kind, e)
    return e
end })

-- ---- signals ------------------------------------------------------------------------------------------------------
local function signal()
    local s = { handlers = {} }
    function s:Connect(fn)
        table.insert(self.handlers, fn)
        return { Disconnect = function() end }
    end
    function s:Fire(...)
        for _, fn in ipairs(self.handlers) do
            fn(...)
        end
    end
    return s
end

Engine.Vector3, Engine.CFrame, Engine.Color3, Engine.Enum = Vector3, CFrame, Color3, Enum

-- ---- a world -----------------------------------------------------------------------------------------------------
function Engine.new(options)
    options = options or {}
    local e = { now = 0, log = {}, randoms = {}, seed = 12345, inputs = {} }

    -- Instances ----------------------------------------------------------------------------------------------------
    local I = {}
    local function newInstance(class, props)
        local inst = { ClassName = class, Name = class, _children = {}, _attrs = {}, _parent = nil, _destroyed = false }
        for k, v in pairs(props or {}) do
            inst[k] = v
        end
        return setmetatable(inst, I)
    end

    local function isPart(inst) return rawget(inst, "ClassName") == "Part" end

    I.__index = function(inst, key)
        if key == "Parent" then
            return rawget(inst, "_parent")
        elseif key == "Position" and isPart(inst) then
            return rawget(inst, "_cframe").p
        elseif key == "CFrame" and isPart(inst) then
            return rawget(inst, "_cframe")
        elseif key == "Orientation" and isPart(inst) then
            local x, y, z = rawget(inst, "_cframe"):ToOrientation()
            return vec(math.deg(x), math.deg(y), math.deg(z))
        end
        return I[key]
    end
    I.__newindex = function(inst, key, value)
        if key == "Parent" then
            local old = rawget(inst, "_parent")
            if old then
                local list = rawget(old, "_children")
                for i, child in ipairs(list) do
                    if child == inst then
                        table.remove(list, i)
                        break
                    end
                end
            end
            rawset(inst, "_parent", value)
            if value then
                table.insert(rawget(value, "_children"), inst)
            end
        elseif key == "Position" and isPart(inst) then
            rawset(inst, "_cframe", cf(value, rawget(inst, "_cframe").r))
        elseif key == "CFrame" and isPart(inst) then
            rawset(inst, "_cframe", value)
        else
            rawset(inst, key, value)
        end
    end
    I.__tostring = function(inst) return rawget(inst, "Name") end

    function I:IsA(class)
        local own = rawget(self, "ClassName")
        return class == own or class == "Instance" or (class == "BasePart" and own == "Part")
    end
    function I:FindFirstChild(name)
        for _, child in ipairs(rawget(self, "_children")) do
            if rawget(child, "Name") == name then
                return child
            end
        end
        return nil
    end
    function I:GetChildren()
        return table.clone(rawget(self, "_children"))
    end
    function I:GetDescendants()
        local out = {}
        local function walk(inst)
            for _, child in ipairs(rawget(inst, "_children")) do
                table.insert(out, child)
                walk(child)
            end
        end
        walk(self)
        return out
    end
    function I:SetAttribute(name, value)
        rawget(self, "_attrs")[name] = value
    end
    function I:GetAttribute(name)
        return rawget(self, "_attrs")[name]
    end
    function I:GetAttributes()
        return table.clone(rawget(self, "_attrs"))
    end
    function I:Destroy()
        for _, child in ipairs(self:GetChildren()) do
            child:Destroy()
        end
        self.Parent = nil
        rawset(self, "_destroyed", true)
        e.destroyed = (e.destroyed or 0) + 1
    end
    function I:GetMass()
        local s = self.Size
        local physics = self.CustomPhysicalProperties
        return (physics and physics.Density or 0.7) * s.X * s.Y * s.Z
    end
    function I:ApplyImpulseAtPosition(impulse, _)
        self.AssemblyLinearVelocity = self.AssemblyLinearVelocity + impulse / self:GetMass()
        e.impulses = (e.impulses or 0) + 1
    end
    function I:SetNetworkOwner(_) end
    -- Humanoids
    function I:MoveTo(position)
        self.WalkTarget = position
        e.moves = (e.moves or 0) + 1
    end
    function I:CancelMoveTo()
        self.WalkTarget = nil
        self.Cancels = (self.Cancels or 0) + 1
    end

    local function newPart()
        local part = newInstance("Part", {
            Size = vec(4, 1, 2), Anchored = false, CanCollide = true, CanQuery = true, CanTouch = true, Transparency = 0,
            Color = Color3.new(0.6, 0.6, 0.6), Shape = Enum.PartType.Block, Material = Enum.Material.Plastic,
            AssemblyLinearVelocity = vec(0, 0, 0), AssemblyAngularVelocity = vec(0, 0, 0),
        })
        rawset(part, "_cframe", CFrame.new())
        rawset(part, "Touched", signal())
        return part
    end

    local Instance = {}
    function Instance.new(class)
        if class == "Part" then
            return newPart()
        end
        return newInstance(class)
    end

    -- Services -----------------------------------------------------------------------------------------------------
    local Workspace = newInstance("Workspace", { Gravity = 196.2 })
    Workspace.Name = "Workspace"

    -- Half sizes as the world sees them (main.lua halfExtents).
    local function extents(part)
        local s, c = part.Size * 0.5, part.CFrame
        local r, u, l = c.RightVector, c.UpVector, c.LookVector
        return vec(math.abs(r.X) * s.X + math.abs(u.X) * s.Y + math.abs(l.X) * s.Z,
            math.abs(r.Y) * s.X + math.abs(u.Y) * s.Y + math.abs(l.Y) * s.Z,
            math.abs(r.Z) * s.X + math.abs(u.Z) * s.Y + math.abs(l.Z) * s.Z)
    end
    e.extents = extents

    local function within(inst, list)
        for _, other in ipairs(list or {}) do
            if other then
                local p = inst
                while p do
                    if p == other then
                        return true
                    end
                    p = rawget(p, "_parent")
                end
            end
        end
        return false
    end

    function Workspace:GetPartsInPart(probe, params)
        local include = params and params.FilterType == Enum.RaycastFilterType.Include
        local list = params and params.FilterDescendantsInstances or {}
        local pc, pe = probe.Position, extents(probe)
        local hits = {}
        for _, inst in ipairs(self:GetDescendants()) do
            if inst ~= probe and isPart(inst) and inst.CanQuery ~= false then
                local listed = within(inst, list)
                if (include and listed) or (not include and not listed) then
                    local c, x = inst.Position, extents(inst)
                    if math.abs(c.X - pc.X) < x.X + pe.X and math.abs(c.Y - pc.Y) < x.Y + pe.Y
                        and math.abs(c.Z - pc.Z) < x.Z + pe.Z then
                        table.insert(hits, inst)
                    end
                end
            end
        end
        return hits
    end

    local Players = newInstance("Players")
    Players.PlayerAdded, Players.PlayerRemoving = signal(), signal()
    function Players:GetPlayers()
        return self:GetChildren()
    end
    local RunService = { Heartbeat = signal() }
    local AgentInputService = options.noInputService and nil or { InputReceived = signal() }
    local services = { Players = Players, RunService = RunService, AgentInputService = AgentInputService }
    local game = { GetService = function(_, name) return services[name] end }

    -- What the script sees ----------------------------------------------------------------------------------------
    local function random(a, b)
        local r
        if #e.randoms > 0 then
            r = table.remove(e.randoms, 1)
        else
            e.seed = (e.seed * 16807) % 2147483647
            r = e.seed / 2147483647
        end
        if a == nil then
            return r
        end
        if b == nil then
            a, b = 1, a
        end
        if r >= 1 then -- a queued whole number picks that one
            return math.clamp(r, a, b)
        end
        return a + math.floor(r * (b - a + 1))
    end
    local env = setmetatable({
        game = game, Workspace = Workspace, workspace = Workspace, Instance = Instance, Vector3 = Vector3,
        CFrame = CFrame, Color3 = Color3, Enum = Enum, PhysicalProperties = PhysicalProperties,
        OverlapParams = { new = function() return { FilterType = Enum.RaycastFilterType.Exclude, FilterDescendantsInstances = {} } end },
        os = setmetatable({ clock = function() return e.now end }, { __index = os }),
        math = setmetatable({ random = random }, { __index = math }),
        print = function(...)
            local parts = {}
            for i = 1, select("#", ...) do
                parts[i] = tostring((select(i, ...)))
            end
            table.insert(e.log, table.concat(parts, "\t"))
        end,
    }, { __index = _G })
    e.env, e.Workspace, e.Players, e.RunService, e.AgentInputService = env, Workspace, Players, RunService, AgentInputService
    e.Instance = Instance

    -- What a test does --------------------------------------------------------------------------------------------
    function e.find(name)
        return Workspace:FindFirstChild(name)
    end

    function e.part(name, props)
        local part = newPart()
        part.Name = name
        for k, v in pairs(props or {}) do
            if k == "attrs" then
                for a, value in pairs(v) do
                    part:SetAttribute(a, value)
                end
            else
                part[k] = v
            end
        end
        part.Parent = Workspace
        return part
    end

    -- A player with a body: a character model holding its root part and a humanoid (the engine makes these).
    function e.player(name, position, options2)
        options2 = options2 or {}
        local player = newInstance("Player", { UserId = #Players:GetChildren() + 1 })
        player.Name = name
        local character
        if not options2.noCharacter then
            character = newInstance("Model")
            character.Name = name
            if not options2.noRoot then
                local hrp = newPart()
                hrp.Name = "HumanoidRootPart"
                hrp.Size = vec(2, 2, 1)
                hrp.Position = position or vec(0, 2.55, 0)
                hrp.CanQuery = true
                hrp.Parent = character
            end
            if not options2.noHumanoid then
                local humanoid = newInstance("Humanoid", { WalkSpeed = 16, JumpPower = 50, Health = 100, Jump = false })
                humanoid.Name = "Humanoid"
                humanoid.Parent = character
            end
            character.Parent = Workspace
        end
        player.Character = character
        player.Parent = Players
        if not options2.quiet then
            Players.PlayerAdded:Fire(player)
        end
        return player
    end

    function e.leave(player)
        Players.PlayerRemoving:Fire(player)
        player.Parent = nil
        if player.Character then
            player.Character:Destroy()
        end
    end

    function e.hrp(player)
        return player.Character and player.Character:FindFirstChild("HumanoidRootPart")
    end
    function e.humanoid(player)
        return player.Character and player.Character:FindFirstChild("Humanoid")
    end

    -- An input from a player, as the agent API sends it; the player's LastActionResult after it.
    function e.input(player, kind, data)
        table.insert(e.inputs, kind)
        AgentInputService.InputReceived:Fire(player, kind, data)
        return player:GetAttribute("LastActionResult")
    end

    -- Time moves on: os.clock, and the world's Heartbeat, in steps of at most `dt`.
    function e.step(seconds, dt)
        dt = dt or seconds
        local left = seconds
        while left > 1e-9 do
            local d = math.min(dt, left)
            e.now = e.now + d
            RunService.Heartbeat:Fire(d)
            left = left - d
        end
    end

    -- Loose pieces fall straight down onto what is under them (the engine's physics, at its plainest).
    function e.drop()
        for _, part in ipairs(Workspace:GetChildren()) do
            if isPart(part) and not part.Anchored and part.CanCollide then
                local c, x = part.Position, extents(part)
                local support = nil
                for _, other in ipairs(Workspace:GetChildren()) do
                    if other ~= part and isPart(other) and other.CanCollide then
                        local oc, ox = other.Position, extents(other)
                        local top = oc.Y + ox.Y
                        if math.abs(c.X - oc.X) < x.X + ox.X - 0.05 and math.abs(c.Z - oc.Z) < x.Z + ox.Z - 0.05
                            and top <= c.Y - x.Y + 0.05 and (support == nil or top > support) then
                            support = top
                        end
                    end
                end
                if support then
                    part.Position = vec(c.X, support + x.Y, c.Z)
                end
                part.AssemblyLinearVelocity = vec(0, 0, 0)
                part.AssemblyAngularVelocity = vec(0, 0, 0)
            end
        end
    end

    return e
end

return Engine
