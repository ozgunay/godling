"""tools/make_island.py: the generator gives the island the world runs (a golden test), and its pieces hold up."""
import runpy
import shutil
import struct
import sys
import zlib
from pathlib import Path

import pytest

import make_island as mi

REPO = Path(mi.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    """The whole generator run once, into a copy of the repository's world and research folders."""
    root = tmp_path_factory.mktemp("repo")
    (root / "world").mkdir()
    (root / "research").mkdir()
    shutil.copy(REPO / "world" / "main.lua", root / "world" / "main.lua")
    saved = mi.ROOT
    mi.ROOT = root
    try:
        mi.main()
    finally:
        mi.ROOT = saved
    return root


def test_the_generator_gives_the_committed_island(generated):
    assert (generated / "world/island.lua").read_text(encoding="utf-8") == \
        (REPO / "world/island.lua").read_text(encoding="utf-8")
    # main.lua carries the same block between its markers, and nothing else changed
    assert (generated / "world/main.lua").read_text(encoding="utf-8") == \
        (REPO / "world/main.lua").read_text(encoding="utf-8")


def test_the_preview_is_a_valid_png(generated):
    png = (generated / "research/island-preview.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    length, tag = struct.unpack(">I4s", png[8:16])
    width, height = struct.unpack(">II", png[16:24])
    assert tag == b"IHDR" and width == height == (2 * mi.HALF + 1) * 4
    crc = struct.unpack(">I", png[16 + length:20 + length])[0]
    assert crc == zlib.crc32(png[12:16 + length]) & 0xFFFFFFFF


def test_noise_is_smooth_and_bounded():
    assert 0 <= mi.hash01(1, 2, 3) <= 1 and mi.hash01(1, 2, 3) == mi.hash01(1, 2, 3)
    assert mi.value_noise(5, 5, 1) == pytest.approx(mi.hash01(5, 5, 1))  # at a lattice point
    assert all(0 <= mi.fbm(x / 7, x / 3, 4) <= 1 for x in range(50))


def test_rectangles_cover_exactly():
    cells = {(0, 0), (1, 0), (0, 1), (1, 1), (3, 0), (-2, -2)}
    rects = mi.rectangles(cells)
    covered = {(i, j) for i0, j0, i1, j1 in rects for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
    assert covered == cells and len(rects) == 3
    assert mi.rect_box((0, 0, 1, 0)) == (1.25, 0.0, 5.0, 2.5)
    assert mi.lua_number(2.50) == "2.5" and mi.lua_number(3.0) == "3" and mi.lua_number(-0.125) == "-0.12"


def test_features_and_neighbours():
    assert mi.feature_of((round(mi.MOUNTAIN[0] / mi.CELL), round(mi.MOUNTAIN[1] / mi.CELL)), {}) == "Peak"
    assert mi.feature_of((round(mi.HILLS[1][0] / mi.CELL), round(mi.HILLS[1][1] / mi.CELL)), {}) == "SouthHill"
    assert set(mi.neighbours4(0, 0)) == {(1, 0), (-1, 0), (0, 1), (0, -1)}


def test_write_lua_without_markers(tmp_path, monkeypatch, generated):
    """A world script without the ISLAND markers is left as it is; island.lua is still written."""
    (tmp_path / "world").mkdir()
    (tmp_path / "world/main.lua").write_text("print('no island here')\n")
    monkeypatch.setattr(mi, "ROOT", tmp_path)
    spots = {"trees": [(0, 0)], "palms": [((1, 1), 90, True), ((2, 2), 0, False)], "raft": (3, 3), "spawn": (4, 4),
             "pile": (5, 5), "ladder": (6, 6), "axe": (7, 7), "hammer": (8, 8), "rock": (9, 9), "quarry": (10, 10),
             "boulders": [(11, 11)], "at": lambda i, j: (i * mi.CELL, j * mi.CELL)}
    land = {(i, j) for i in range(-3, 4) for j in range(-3, 4)}
    count = mi.write_lua(land, {(-3, -3)}, {(0, 0): 2, (0, 1): 4}, spots)
    assert sum(count.values()) == 2
    text = (tmp_path / "world/island.lua").read_text()
    assert "trees = {{0, 0}}," in text and "{2.5, 2.5, 90, true}," in text and "{5, 5, 0, false}," in text
    assert (tmp_path / "world/main.lua").read_text() == "print('no island here')\n"
    mi.write_png(tmp_path / "p.png", land, {(-3, -3)}, {(0, 0): 2}, spots)
    assert (tmp_path / "p.png").read_bytes()[:4] == b"\x89PNG"


def test_run_as_a_script(monkeypatch, tmp_path, capsys):
    """`python tools/make_island.py` runs main(); here with the work faked, to check the wiring only."""
    called = []
    monkeypatch.setattr(sys, "argv", ["make_island.py"])
    source = (REPO / "tools/make_island.py").read_text(encoding="utf-8")
    code = compile(source.replace("\nif __name__ == \"__main__\":\n    main()", "\nif __name__ == \"__main__\":\n    called.append(main)"),
                   str(REPO / "tools/make_island.py"), "exec")
    exec(code, {"__name__": "__main__", "called": called, "__file__": str(REPO / "tools/make_island.py")})
    assert called and called[0].__name__ == "main"


def test_a_lone_raised_cell_is_dropped():
    peak = (round(mi.MOUNTAIN[0] / mi.CELL), round(mi.MOUNTAIN[1] / mi.CELL))
    assert mi.make_heights({peak}, {peak: 50}) == {}  # the mountain's top alone, with nothing round it: noise
