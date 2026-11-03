//! The island as the relay keeps it: the world's first spectator message (the whole island), with every
//! `spectator_delta` after it applied the way Clawblox's page applies them (`frontend_runtime/dist/main.js`
//! `applySpectatorDelta`, with patches/v1's terrain). A viewer who joins late is handed this, so it holds the same island
//! as one who watched from the start.
use indexmap::IndexMap;
use serde::ser::{SerializeMap, Serializer};
use serde::Serialize;
use serde_json::{Map, Value};

pub struct Island {
    top: Map<String, Value>, // everything but the entities: tick, players, sounds, terrain…
    entities: IndexMap<u64, Value>, // by id, in the order the world listed them
}

impl Island {
    /// The world's whole island, as its first message gives it; None if that is not an object.
    pub fn from_snapshot(snapshot: Value) -> Option<Island> {
        let Value::Object(mut top) = snapshot else { return None };
        let listed = match top.remove("entities") {
            Some(Value::Array(listed)) => listed,
            _ => Vec::new(),
        };
        let mut entities = IndexMap::with_capacity(listed.len());
        for entity in listed {
            if let Some(id) = entity.get("id").and_then(Value::as_u64) {
                entities.insert(id, entity);
            }
        }
        Some(Island { top, entities })
    }

    /// One `spectator_delta`, applied as the page applies it.
    pub fn apply(&mut self, delta: &Map<String, Value>) {
        for key in ["tick", "server_time_ms"] {
            if let Some(value @ Value::Number(_)) = delta.get(key) {
                self.top.insert(key.into(), value.clone());
            }
        }
        if let Some(value @ Value::String(_)) = delta.get("game_status") {
            self.top.insert("game_status".into(), value.clone());
        }
        for key in ["players", "sounds"] {
            if let Some(value @ Value::Array(_)) = delta.get(key) {
                self.top.insert(key.into(), value.clone());
            }
        }
        // Events belong to the update that carried them: an update without any clears them.
        let events = match delta.get("recent_events") {
            Some(value @ Value::Array(_)) => value.clone(),
            _ => Value::Array(Vec::new()),
        };
        self.top.insert("recent_events".into(), events);
        if let Some(value @ Value::Object(_)) = delta.get("terrain") {
            self.top.insert("terrain".into(), value.clone());
        }
        let Some(Value::Array(entries)) = delta.get("entities") else { return };
        for entry in entries {
            let Some(id) = entry.get("id").and_then(Value::as_u64) else { continue };
            if entry.get("rm").is_some_and(truthy) {
                self.entities.shift_remove(&id);
                continue;
            }
            if let Some(added @ Value::Object(_)) = entry.get("add") {
                self.entities.insert(id, added.clone()); // a known id keeps its place, a new one goes last
                continue;
            }
            if let Some(Value::Object(entity)) = self.entities.get_mut(&id) {
                if let Some(position @ Value::Array(_)) = entry.get("p") {
                    entity.insert("position".into(), position.clone());
                }
                if let Some(rotation @ Value::Array(_)) = entry.get("r") {
                    entity.insert("rotation".into(), rotation.clone());
                }
            }
        }
    }

    /// The island as one message, in the world's own shape, with where it stands in the relay's stream.
    pub fn to_json(&self, epoch: u64, seq: u64) -> String {
        serde_json::to_string(&Whole { island: self, epoch, seq }).expect("an island always serializes")
    }

    pub fn entity_count(&self) -> usize {
        self.entities.len()
    }

    pub fn tick(&self) -> Option<u64> {
        self.top.get("tick").and_then(Value::as_u64)
    }
}

fn truthy(value: &Value) -> bool {
    !matches!(value, Value::Null | Value::Bool(false)) && value.as_f64() != Some(0.0) && value.as_str() != Some("")
}

struct Whole<'a> {
    island: &'a Island,
    epoch: u64,
    seq: u64,
}

impl Serialize for Whole<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.island.top.len() + 3))?;
        for (key, value) in &self.island.top {
            map.serialize_entry(key, value)?;
        }
        map.serialize_entry("entities", &Entities(&self.island.entities))?;
        map.serialize_entry("relay_epoch", &self.epoch)?;
        map.serialize_entry("relay_seq", &self.seq)?;
        map.end()
    }
}

struct Entities<'a>(&'a IndexMap<u64, Value>);

impl Serialize for Entities<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_seq(self.0.values())
    }
}

/// A world message with its place in the relay's stream added (`"relay_seq":n` first), without parsing it again.
/// The page ignores fields it does not know; a reconnecting page sends the last one back to resume. None when the
/// message is not a JSON object.
pub fn with_seq(message: &str, seq: u64) -> Option<String> {
    let body = message.trim_start().strip_prefix('{')?;
    let rest = body.trim_start();
    let separator = if rest.starts_with('}') { "" } else { "," };
    Some(format!("{{\"relay_seq\":{seq}{separator}{body}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn island() -> Island {
        Island::from_snapshot(json!({
            "tick": 10, "server_time_ms": 1000, "game_status": "playing",
            "players": [{"name": "Godling"}], "sounds": [], "recent_events": [{"kind": "speech"}],
            "entities": [
                {"id": 1, "name": "Ground", "position": [0, 0, 0], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
                {"id": 2, "name": "Stone_1", "position": [5, 1, 5], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
                {"id": 3, "name": "Log_1", "position": [9, 1, 9], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            ],
        }))
        .unwrap()
    }

    fn delta(value: Value) -> Map<String, Value> {
        value.as_object().unwrap().clone()
    }

    fn parsed(island: &Island) -> Value {
        serde_json::from_str(&island.to_json(7, 42)).unwrap()
    }

    #[test]
    fn moves_adds_and_removes_as_the_page_does() {
        let mut island = island();
        island.apply(&delta(json!({
            "type": "spectator_delta", "tick": 11, "server_time_ms": 1033,
            "entities": [
                {"id": 2, "p": [6, 1, 5], "r": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]},
                {"id": 3, "rm": true},
                {"id": 4, "add": {"id": 4, "name": "Meteor_1", "position": [0, 40, 0]}},
                {"id": 99, "p": [1, 2, 3]},
            ],
        })));
        let whole = parsed(&island);
        assert_eq!(whole["tick"], 11);
        assert_eq!(whole["server_time_ms"], 1033);
        let ids: Vec<u64> = whole["entities"].as_array().unwrap().iter().map(|e| e["id"].as_u64().unwrap()).collect();
        assert_eq!(ids, vec![1, 2, 4], "Log_1 removed, Meteor_1 last, an unknown id ignored");
        assert_eq!(whole["entities"][1]["position"], json!([6, 1, 5]));
        assert_eq!(whole["entities"][1]["rotation"], json!([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]));
        assert_eq!(whole["entities"][1]["name"], "Stone_1", "a move keeps everything else");
    }

    #[test]
    fn keeps_what_a_delta_leaves_out_but_clears_events() {
        let mut island = island();
        island.apply(&delta(json!({"type": "spectator_delta", "tick": 11})));
        let whole = parsed(&island);
        assert_eq!(whole["players"], json!([{"name": "Godling"}]));
        assert_eq!(whole["game_status"], "playing");
        assert_eq!(whole["recent_events"], json!([]));
        island.apply(&delta(json!({"players": [], "terrain": {"chunks": 3}, "recent_events": [{"kind": "x"}]})));
        let whole = parsed(&island);
        assert_eq!(whole["players"], json!([]));
        assert_eq!(whole["terrain"], json!({"chunks": 3}));
        assert_eq!(whole["recent_events"], json!([{"kind": "x"}]));
    }

    #[test]
    fn an_add_for_a_known_id_replaces_it_in_place() {
        let mut island = island();
        island.apply(&delta(json!({"entities": [{"id": 2, "add": {"id": 2, "name": "Stone_1", "Fastened": true}}]})));
        let whole = parsed(&island);
        assert_eq!(whole["entities"][1], json!({"id": 2, "name": "Stone_1", "Fastened": true}));
        assert_eq!(island.entity_count(), 3);
    }

    #[test]
    fn only_an_object_is_an_island_and_its_game_status_follows_the_deltas() {
        assert!(Island::from_snapshot(json!([1, 2, 3])).is_none());
        assert_eq!(Island::from_snapshot(json!({"tick": 1, "entities": "none"})).unwrap().entity_count(), 0);
        let mut island = island();
        island.apply(&delta(json!({"type": "spectator_delta", "game_status": "ended", "entities": []})));
        assert_eq!(parsed(&island)["game_status"], "ended");
        island.apply(&delta(json!({"type": "spectator_delta", "game_status": 3})));
        assert_eq!(parsed(&island)["game_status"], "ended", "only a word is a status");
    }

    #[test]
    fn the_whole_island_says_where_it_stands() {
        let whole = parsed(&island());
        assert_eq!(whole["relay_epoch"], 7);
        assert_eq!(whole["relay_seq"], 42);
        assert_eq!(whole["entities"].as_array().unwrap().len(), 3);
    }

    #[test]
    fn with_seq_adds_the_place_without_touching_the_rest() {
        let message = r#"{"type":"spectator_delta","tick":5,"entities":[{"id":1,"p":[1.5,2,3]}]}"#;
        let out = with_seq(message, 9).unwrap();
        assert_eq!(out, r#"{"relay_seq":9,"type":"spectator_delta","tick":5,"entities":[{"id":1,"p":[1.5,2,3]}]}"#);
        let back: Value = serde_json::from_str(&out).unwrap();
        assert_eq!(back["relay_seq"], 9);
        assert_eq!(with_seq("  { }", 3).unwrap(), "{\"relay_seq\":3 }");
        assert!(with_seq("[1,2]", 1).is_none());
    }
}
