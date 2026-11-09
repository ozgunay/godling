"""Learned skills from the live run of 2026-11-08/09 (9.6 h, deepseek-flash, native memory), for ADR-032.

Each record is the skill as Godling had it when its mind asked to forget it: the steps from its `learn` entry in
mind/log.jsonl, and its counts from the runs logged after that. CUBE_STEP_AT and UPRIGHT_NAMED_LOG are copied from the
run's final memory/skills.json. Old records carry no `fails_in_a_row`; only their last five outcomes (`recent`).
"""

# Worked 71 of 81 times; forgotten at 07:08 UTC after two failed runs, both stopped by its own step log on the way in.
MEND_AT_HOME = {
    "params": [],
    "steps": [{"skill": "walk_to", "args": {"x": -80, "z": -38.5}}, {"skill": "walk_to", "args": {"x": -80, "z": -35}},
              {"skill": "walk_to", "args": {"x": -80, "z": -32.5}}, {"skill": "walk_to", "args": {"x": -80, "z": -27.5}},
              {"skill": "wait", "args": {"seconds": 30}, "repeat": 3}],
    "does": "walks the Log_24 entry route into the house and waits 90s under the roof to mend in shelter",
    "status": "proven", "uses": 81, "successes": 71, "defined_tick": 0, "version": 1,
    "recent": [False, True, True, False, False]}

# Worked 2 of 3 times; forgotten at 02:41 UTC straight after it had worked, when the mind taught itself arch_beam_z.
BEAM_Z_ON_STEP = {
    "params": ["log", "x", "z", "stand_x", "stand_z"],
    "steps": [{"skill": "pick_up", "args": {"object": "$log"}},
              {"skill": "walk_to", "args": {"x": "$stand_x", "z": "$stand_z"}},
              {"skill": "place_at", "args": {"x": "$x", "y": 8.75, "z": "$z", "turn": 90}}],
    "does": "picks the named log, walks onto the one-block step at the standing cell and sets it along z at height 8.75 "
            "centred on the target",
    "status": "proven", "uses": 3, "successes": 2, "defined_tick": 0, "version": 1, "recent": [False, True, True]}

# Worked 2 of 11 times, then failed 9 times in a row (hands full, nowhere to set the log down); forgotten at 07:25 UTC.
POST_AND_FASTEN = {
    "params": ["log", "site_x", "site_z", "stand_x", "stand_z"],
    "steps": [{"skill": "upright_named_log", "args": {"log": "$log", "site_x": "$site_x", "site_z": "$site_z",
                                                       "stand_x": "$stand_x", "stand_z": "$stand_z"}},
              {"skill": "fasten", "args": {"object": "$log"}}],
    "does": "stands the named free log upright in the site cell from the stand cell, then fastens it so it stays",
    "status": "proven", "uses": 11, "successes": 2, "defined_tick": 0, "version": 1,
    "recent": [False, False, False, False, False]}

# Still in the final library: worked 10 of 29 times, its last five runs failed.
CUBE_STEP_AT = {
    "params": ["stand_x", "stand_z"],
    "steps": [{"skill": "pick_up", "args": {"object": {"nearest_free": "cube"}}},
              {"skill": "walk_to", "args": {"x": "$stand_x", "z": "$stand_z"}},
              {"skill": "put_down", "args": {"x": "$stand_x", "z": "$stand_z"}}],
    "does": "Picks the nearest unclaimed block, walks to the standing cell and sets it down there as a one-block step",
    "status": "proven", "uses": 29, "successes": 10, "defined_tick": 312763, "version": 1,
    "recent": [False, False, False, False, False]}

# Still in the final library: worked 19 of 39 times, its last five runs failed.
UPRIGHT_NAMED_LOG = {
    "params": ["log", "site_x", "site_z", "stand_x", "stand_z"],
    "steps": [{"skill": "pick_up", "args": {"object": "$log"}},
              {"skill": "walk_to", "args": {"x": "$stand_x", "z": "$stand_z"}},
              {"skill": "put_down", "args": {"x": "$site_x", "z": "$site_z", "upright": True}}],
    "does": "picks a named free log, walks to the chosen standing cell and stands the log upright in the target cell",
    "status": "proven", "uses": 39, "successes": 19, "defined_tick": 715144, "version": 1,
    "recent": [False, False, False, False, False]}
