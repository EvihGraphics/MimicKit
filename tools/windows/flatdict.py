"""Minimal flatdict compatibility shim for Isaac Lab on native Windows.

This environment only needs ``FlatDict`` for flattening nested dictionaries
into delimiter-separated key/value pairs while bootstrapping Isaac Lab
extensions.
"""

from __future__ import annotations


class FlatDict(dict):
    def __init__(self, value=None, delimiter=":"):
        self.delimiter = delimiter
        super().__init__()
        if value is not None:
            self._flatten("", value)

    def _flatten(self, prefix, value):
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                next_prefix = key_text if not prefix else f"{prefix}{self.delimiter}{key_text}"
                self._flatten(next_prefix, child)
            return

        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                key_text = str(index)
                next_prefix = key_text if not prefix else f"{prefix}{self.delimiter}{key_text}"
                self._flatten(next_prefix, child)
            return

        self[prefix] = value
