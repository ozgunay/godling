"""Observations as Clawblox sends them, built by hand for the mind's tests."""
from godling.world import BODY_CENTRE_Y, Snapshot


def ent(name, pos=(0, 1.25, 0), size=(2.5, 2.5, 2.5), role="", attrs=None, rot=None, eid=None):
    attributes = dict(attrs or {})
    if role:
        attributes.setdefault("RenderRole", role)
    raw = {"id": eid if eid is not None else abs(hash(name)) % 100000, "name": name, "position": list(pos),
           "size": list(size), "attributes": attributes}
    if rot is not None:
        raw["rotation"] = rot
    return raw


def ground(name="Ground", pos=(0, -0.5, 0), size=(400, 1, 400), **kw):
    return ent(name, pos, size, role=kw.pop("role", "Ground"), **kw)


def raw_obs(entities=(), me=(0, BODY_CENTRE_Y, 0), attrs=None, clock=None, others=(), events=(), tick=0):
    ents = list(entities)
    if clock is not None:
        ents.append(ent("Clock", (0, -50, 0), (1, 1, 1), attrs=clock))
    return {"tick": tick, "player": {"position": list(me), "attributes": dict(attrs or {})},
            "other_players": [{"name": n, "position": list(p)} for n, p in others],
            "world": {"entities": ents}, "events": list(events)}


def snap(entities=(), **kw):
    return Snapshot(raw_obs(entities, **kw))


def block(name, x, y, z, **kw):
    """A cube resting with its centre at (x, y, z)."""
    return ent(name, (x, y, z), (2.5, 2.5, 2.5), **kw)
