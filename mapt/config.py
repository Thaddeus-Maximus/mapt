"""Settings from an optional ``mapt.yaml`` at the data root."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

CONFIG_NAME = "mapt.yaml"

DEFAULTS = {
    "title": "mapt",
    "home": None,                 # the place whose map opens first; default: the only top-level map
    "places_dir": "places",
    "things_dir": "things",
    "attachments_dir": "attachments",
}


@dataclass
class Config:
    raw: dict

    def __getitem__(self, key):
        return self.raw[key]

    def kind_for_folder(self, folder: str) -> str | None:
        f = folder.casefold()
        if f == str(self.raw["places_dir"]).casefold():
            return "place"
        if f == str(self.raw["things_dir"]).casefold():
            return "thing"
        return None

    def folder(self, kind: str) -> str:
        return self.raw["places_dir"] if kind == "place" else self.raw["things_dir"]


def load(root: Path) -> Config:
    path = root / CONFIG_NAME
    data: dict = {}
    if path.exists():
        loaded = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    return Config({**DEFAULTS, **data})
