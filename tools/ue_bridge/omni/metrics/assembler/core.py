"""Compatibility shim for IsaacLab on Isaac Sim 4.5 pip installs.

IsaacLab 2.3 imports ``omni.metrics.assembler.core`` while building USD
references. Some Isaac Sim 4.5 pip environments do not ship that extension
unless the large extension cache wheels are installed. Returning ``ret_val`` as
false makes IsaacLab use its plain USD reference fallback path.
"""

from __future__ import annotations


class _MetricsAssembler:
    def check_layers(self, *_args, **_kwargs):
        return {
            "ret_val": False,
            "reason": "omni.metrics compatibility shim: use direct USD reference fallback",
        }


def get_metrics_assembler_interface() -> _MetricsAssembler:
    return _MetricsAssembler()
