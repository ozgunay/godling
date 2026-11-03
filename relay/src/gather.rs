//! The world's updates gathered between sends (ADR-017). The world sends a `spectator_delta` on every tick it reads
//! (31 a second); the relay sends viewers one every RELAY_UPDATES_PER_SECOND, doing what those did as the page would
//! have applied them one by one (Clawblox's `applySpectatorDelta`, mirrored in `island.rs`): the latest place of each
//! thing that moved, what was added and removed, the latest players, sounds and terrain, and every event once.
//! Rotations and the players' numbers are rounded to 0.001 on the way, as the replay's chunks keep rotations and
//! attributes (ADR-016); positions come from the world already rounded to 0.01.
use std::collections::HashMap;

use serde_json::{json, Map, Number, Value};

use crate::island::truthy;

/// What the deltas since the last send did.
#[derive(Default)]
pub struct Gathered {
    top: Map<String, Value>,   // the latest of everything but entities and events: tick, players, sounds, terrain…
    events: Vec<Value>,        // every delta's recent_events, in order, each once
    entries: Vec<Value>,       // entity entries, in the order they first came
    last: HashMap<u64, Last>,  // what the latest entry for an id was
    deltas: usize,
}

enum Last {
    /// An add or a move, at this index in `entries`: a later move or add for the id goes into it.
    Entry(usize),
    /// Removed: a move after it would land on nothing, as on the page.
    Removed,
}

impl Gathered {
    pub fn is_empty(&self) -> bool {
        self.deltas == 0
    }

    /// One more world delta.
    pub fn add(&mut self, delta: &Map<String, Value>) {
        self.deltas += 1;
        for (key, value) in delta {
            match (key.as_str(), value) {
                ("entities", Value::Array(entries)) => entries.iter().for_each(|entry| self.entity(entry)),
                ("recent_events", Value::Array(events)) => {
                    for event in events {
                        if !self.events.contains(event) {
                            self.events.push(event.clone());
                        }
                    }
                }
                ("entities" | "recent_events", _) => {}
                _ if fits(key, value) => {
                    self.top.insert(key.clone(), value.clone());
                }
                _ => {}
            }
        }
    }

    fn entity(&mut self, entry: &Value) {
        let Some(id) = entry.get("id").and_then(Value::as_u64) else { return };
        if entry.get("rm").is_some_and(truthy) {
            self.entries.push(json!({"id": id, "rm": true}));
            self.last.insert(id, Last::Removed);
            return;
        }
        if let Some(added @ Value::Object(_)) = entry.get("add") {
            let add = json!({"id": id, "add": added});
            match self.last.get(&id) {
                Some(Last::Entry(at)) => self.entries[*at] = add, // what was there is replaced whole, as on the page
                _ => self.push(id, add),
            }
            return;
        }
        let moved = |key: &str| entry.get(key).filter(|value| value.is_array());
        match self.last.get(&id) {
            Some(Last::Removed) => {}
            Some(Last::Entry(at)) => {
                // Into the add (where the page keeps them as position and rotation), or over the earlier move.
                let (fields, names) = place_of(&mut self.entries[*at]);
                for (key, name) in ["p", "r"].into_iter().zip(names) {
                    if let Some(value) = moved(key) {
                        fields.insert(name.into(), value.clone());
                    }
                }
            }
            None => {
                let mut fields = Map::new();
                fields.insert("id".into(), id.into());
                for key in ["p", "r"] {
                    if let Some(value) = moved(key) {
                        fields.insert(key.into(), value.clone());
                    }
                }
                self.push(id, Value::Object(fields));
            }
        }
    }

    /// Whether `delta` must start the next update instead of joining this one: it brings back an id this one removed,
    /// or removes one this one added. Gathered into one, the first would be eased on the page from where the thing
    /// vanished (it keeps a re-added id in place), and the second would never be seen at all.
    pub fn needs_split(&self, delta: &Map<String, Value>) -> bool {
        let Some(Value::Array(entries)) = delta.get("entities") else { return false };
        entries.iter().any(|entry| {
            let Some(id) = entry.get("id").and_then(Value::as_u64) else { return false };
            match self.last.get(&id) {
                Some(Last::Removed) => entry.get("add").is_some_and(Value::is_object),
                Some(Last::Entry(at)) => entry.get("rm").is_some_and(truthy) && self.entries[*at].get("add").is_some(),
                None => false,
            }
        })
    }

    fn push(&mut self, id: u64, entry: Value) {
        self.entries.push(entry);
        self.last.insert(id, Last::Entry(self.entries.len() - 1));
    }

    /// The one delta that does what all the gathered ones did, its places and players rounded.
    pub fn finish(self) -> Map<String, Value> {
        let mut out = self.top;
        if let Some(players) = out.get_mut("players") {
            rounded(players);
        }
        let mut entries = self.entries;
        for entry in &mut entries {
            let (fields, names) = place_of(entry);
            for name in names {
                if let Some(value) = fields.get_mut(name) {
                    rounded(value);
                }
            }
        }
        out.insert("entities".into(), Value::Array(entries));
        if !self.events.is_empty() {
            out.insert("recent_events".into(), Value::Array(self.events));
        }
        out
    }
}

/// Where an entry keeps its place, and the names it uses: inside an add (position, rotation), or a move's own (p, r).
fn place_of(entry: &mut Value) -> (&mut Map<String, Value>, [&'static str; 2]) {
    if entry.get("add").is_some_and(Value::is_object) {
        (entry["add"].as_object_mut().expect("checked"), ["position", "rotation"])
    } else {
        (entry.as_object_mut().expect("entries are objects"), ["p", "r"])
    }
}

/// Whether the page takes this value for this field (`applySpectatorDelta`; `Island::apply` checks the same): a later
/// delta's value of the wrong kind must not replace an earlier one's that the page would have used.
fn fits(key: &str, value: &Value) -> bool {
    match key {
        "tick" | "server_time_ms" => value.is_number(),
        "game_status" => value.is_string(),
        "players" | "sounds" => value.is_array(),
        "terrain" => value.is_object(),
        _ => true,
    }
}

/// The whole island as the world sends it, rounded as the updates are, so a viewer's island and the relay's hold the
/// same numbers and an unchanged rotation is seen to be unchanged.
pub fn round_whole(snapshot: &mut Value) {
    if let Some(players) = snapshot.get_mut("players") {
        rounded(players);
    }
    if let Some(Value::Array(entities)) = snapshot.get_mut("entities") {
        for entity in entities {
            for key in ["position", "rotation"] {
                if let Some(value) = entity.get_mut(key) {
                    rounded(value);
                }
            }
        }
    }
}

/// Every number with a fraction, to 0.001: a thousandth of a rotation's matrix, of a player's numbers.
pub fn rounded(value: &mut Value) {
    match value {
        Value::Number(number) if number.is_f64() => {
            let exact = number.as_f64().unwrap_or_default();
            if let Some(near) = Number::from_f64((exact * 1000.0).round() / 1000.0 + 0.0) {
                *number = near; // + 0.0: no -0.0
            }
        }
        Value::Array(items) => items.iter_mut().for_each(rounded),
        Value::Object(fields) => fields.values_mut().for_each(rounded),
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::island::Island;

    fn gathered(deltas: &[Value]) -> Map<String, Value> {
        let mut gathered = Gathered::default();
        for delta in deltas {
            gathered.add(delta.as_object().unwrap());
        }
        gathered.finish()
    }

    #[test]
    fn moves_keep_only_the_latest_place_of_each() {
        let out = gathered(&[
            json!({"type": "spectator_delta", "tick": 1, "entities": [{"id": 5, "p": [1.0, 0.0, 0.0], "r": [[1.0]]}]}),
            json!({"type": "spectator_delta", "tick": 2, "entities": [{"id": 5, "p": [2.0, 0.0, 0.0]}, {"id": 6, "r": [[0.5]]}]}),
            json!({"type": "spectator_delta", "tick": 3, "entities": [{"id": 6, "p": [9.0, 9.0, 9.0]}]}),
        ]);
        assert_eq!(out["tick"], 3);
        assert_eq!(out["type"], "spectator_delta");
        assert_eq!(out["entities"], json!([{"id": 5, "p": [2.0, 0.0, 0.0], "r": [[1.0]]}, {"id": 6, "r": [[0.5]], "p": [9.0, 9.0, 9.0]}]));
    }

    #[test]
    fn a_move_after_an_add_goes_into_it_and_after_a_removal_nowhere() {
        let out = gathered(&[
            json!({"entities": [{"id": 7, "add": {"id": 7, "name": "Meteor_1", "position": [0, 40, 0]}}, {"id": 8, "rm": true}]}),
            json!({"entities": [{"id": 7, "p": [0, 30, 0]}, {"id": 8, "p": [1, 1, 1]}]}),
        ]);
        assert_eq!(out["entities"], json!([
            {"id": 7, "add": {"id": 7, "name": "Meteor_1", "position": [0, 30, 0]}},
            {"id": 8, "rm": true},
        ]));
    }

    #[test]
    fn events_come_once_each_and_players_are_the_latest() {
        let out = gathered(&[
            json!({"players": [{"name": "Godling", "health": 90}], "recent_events": [{"id": 1}]}),
            json!({"players": [{"name": "Godling", "health": 80}], "recent_events": [{"id": 1}, {"id": 2}]}),
            json!({"tick": 9}),
        ]);
        assert_eq!(out["recent_events"], json!([{"id": 1}, {"id": 2}]));
        assert_eq!(out["players"], json!([{"name": "Godling", "health": 80}]));
        assert!(gathered(&[json!({"tick": 1})]).get("recent_events").is_none(), "no events: none sent");
    }

    #[test]
    fn a_later_value_of_the_wrong_kind_does_not_replace_an_earlier_one() {
        let out = gathered(&[
            json!({"tick": 5, "game_status": "playing", "players": [{"name": "Godling"}], "terrain": {"chunks": 3}}),
            json!({"tick": "six", "game_status": 2, "players": null, "terrain": null, "sounds": {}}),
        ]);
        assert_eq!((&out["tick"], &out["game_status"]), (&json!(5), &json!("playing")));
        assert_eq!((&out["players"], &out["terrain"]), (&json!([{"name": "Godling"}]), &json!({"chunks": 3})));
        assert!(out.get("sounds").is_none(), "as the page ignores them");
    }

    #[test]
    fn places_and_players_are_rounded_and_nothing_else() {
        let out = gathered(&[json!({
            "server_time_ms": 1234567,
            "players": [{"position": [1.23456, -0.0001, 2.0], "attributes": {"ViewForwardX": 0.7799999713897705, "Hunger": 96}}],
            "entities": [
                {"id": 1, "p": [-83.6712, 0.35, 159.7], "r": [[0.70710677, -0.70710677, 0.0]]},
                {"id": 2, "add": {"id": 2, "position": [1.00049, 2.0, 3.0], "size": [0.12345, 1.0, 1.0]}},
            ],
        })]);
        let text = serde_json::to_string(&out).unwrap();
        assert!(text.contains(r#""position":[1.235,0.0,2.0]"#), "{text}");
        assert!(text.contains(r#""ViewForwardX":0.78"#) && text.contains(r#""Hunger":96"#), "{text}");
        assert!(text.contains(r#""p":[-83.671,0.35,159.7]"#) && text.contains(r#""r":[[0.707,-0.707,0.0]]"#), "{text}");
        assert!(text.contains(r#""position":[1.0,2.0,3.0]"#) && text.contains(r#""size":[0.12345,1.0,1.0]"#), "{text}");
        assert!(text.contains(r#""server_time_ms":1234567"#), "{text}");
    }

    /// A small deterministic stream of random deltas: things added, moved and removed, players and events.
    fn random_deltas(count: usize, seed: u64) -> Vec<Value> {
        let mut state = seed;
        let mut next = move |below: u64| {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) % below
        };
        (0..count as u64)
            .map(|tick| {
                let entries: Vec<Value> = (0..next(6))
                    .map(|_| {
                        let id = 1 + next(12);
                        let place = json!([next(100) as f64 / 8.0, next(100) as f64 / 4.0, 0.5]);
                        match next(10) {
                            0 => json!({"id": id, "rm": true}),
                            1 => json!({"id": id, "add": {"id": id, "name": format!("Thing_{id}"), "position": place}}),
                            2 => json!({"id": id, "r": [[next(4) as f64 / 2.0, 0.0, 1.0]]}),
                            _ => json!({"id": id, "p": place}),
                        }
                    })
                    .collect();
                let mut delta = json!({"type": "spectator_delta", "tick": tick, "entities": entries,
                                       "players": [{"name": "Godling", "health": 100 - next(3)}]});
                if next(4) == 0 {
                    delta["recent_events"] = json!([{"id": tick, "name": "Event"}]);
                }
                if next(20) == 0 {
                    delta["sounds"] = json!([{"id": next(3)}]);
                }
                delta
            })
            .collect()
    }

    fn island() -> Island {
        let entities: Vec<Value> = (1..=6).map(|id| json!({"id": id, "name": format!("Thing_{id}"), "position": [0.0, 0.0, 0.0]})).collect();
        Island::from_snapshot(json!({"tick": 0, "players": [], "entities": entities})).unwrap()
    }

    fn by_id(island: &Island) -> Value {
        let mut whole: Value = serde_json::from_str(&island.to_json(0, 0)).unwrap();
        let mut entities = whole["entities"].as_array().unwrap().clone();
        entities.sort_by_key(|entity| entity["id"].as_u64());
        whole["entities"] = Value::Array(entities);
        whole
    }

    #[test]
    fn gathered_deltas_leave_the_island_as_the_deltas_one_by_one_would() {
        for seed in 1..=40 {
            let deltas = random_deltas(60, seed);
            for every in [2, 3, 5] {
                let (mut one_by_one, mut gathered_up) = (island(), island());
                for window in deltas.chunks(every) {
                    let mut gathered = Gathered::default();
                    for delta in window {
                        one_by_one.apply(delta.as_object().unwrap());
                        gathered.add(delta.as_object().unwrap());
                    }
                    gathered_up.apply(&gathered.finish());
                    let mut seen = by_id(&one_by_one);
                    let mut got = by_id(&gathered_up);
                    // The events of the last delta, against the events of the whole window.
                    seen["recent_events"] = Value::Null;
                    got["recent_events"] = Value::Null;
                    assert_eq!(got, seen, "seed {seed}, {every} at a time, at tick {}", window[0]["tick"]);
                }
            }
        }
    }
}
