#!/usr/bin/env python3
"""Apply the minimal IsaacLab hotfixes required by MimicKit's native Windows mesh flow."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not find patch anchor for {label}")
    return text.replace(old, new, 1)


def patch_articulation(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    text = replace_once(
        text,
        "from isaaclab.actuators import ActuatorBase, ActuatorBaseCfg, ImplicitActuator\nfrom isaaclab.utils.types import ArticulationActions\n",
        "from isaaclab.actuators import ActuatorBase, ActuatorBaseCfg, ImplicitActuator\n"
        "from isaaclab.sim.utils.stage import get_current_stage_id\n"
        "from isaaclab.utils.types import ArticulationActions\n",
        f"{path.name}: import get_current_stage_id",
    )
    text = replace_once(
        text,
        "logger = logging.getLogger(__name__)\n\n\nclass Articulation(AssetBase):\n",
        "logger = logging.getLogger(__name__)\n\n\n"
        "def _get_or_create_physics_sim_view():\n"
        "    \"\"\"Return Isaac Sim's physics view, creating a fallback view if the global handle is missing.\"\"\"\n"
        "    physics_sim_view = SimulationManager.get_physics_sim_view()\n"
        "    if physics_sim_view is None:\n"
        "        stage_id = get_current_stage_id()\n"
        "        physics_sim_view = physx.create_simulation_view(\"torch\", stage_id)\n"
        "        physics_sim_view.set_subspace_roots(\"/\")\n"
        "        logger.warning(\"SimulationManager returned no physics sim view; created a fallback articulation view.\")\n"
        "    return physics_sim_view\n\n\n"
        "class Articulation(AssetBase):\n",
        f"{path.name}: helper insertion",
    )
    text = replace_once(
        text,
        "        self._physics_sim_view = SimulationManager.get_physics_sim_view()\n",
        "        self._physics_sim_view = _get_or_create_physics_sim_view()\n",
        f"{path.name}: use fallback sim view",
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_articulation_data(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    text = replace_once(
        text,
        "import omni.physics.tensors.impl.api as physx\nfrom isaacsim.core.simulation_manager import SimulationManager\n\nimport isaaclab.utils.math as math_utils\nfrom isaaclab.utils.buffers import TimestampedBuffer\n",
        "import omni.physics.tensors.impl.api as physx\nfrom isaacsim.core.simulation_manager import SimulationManager\n\n"
        "import isaaclab.utils.math as math_utils\n"
        "from isaaclab.sim.utils.stage import get_current_stage_id\n"
        "from isaaclab.utils.buffers import TimestampedBuffer\n",
        f"{path.name}: import get_current_stage_id",
    )
    text = replace_once(
        text,
        "logger = logging.getLogger(__name__)\n\n\nclass ArticulationData:\n",
        "logger = logging.getLogger(__name__)\n\n\n"
        "def _get_or_create_physics_sim_view():\n"
        "    \"\"\"Return Isaac Sim's physics view, creating a fallback view if the global handle is missing.\"\"\"\n"
        "    physics_sim_view = SimulationManager.get_physics_sim_view()\n"
        "    if physics_sim_view is None:\n"
        "        stage_id = get_current_stage_id()\n"
        "        physics_sim_view = physx.create_simulation_view(\"torch\", stage_id)\n"
        "        physics_sim_view.set_subspace_roots(\"/\")\n"
        "        logger.warning(\"SimulationManager returned no physics sim view; created a fallback articulation data view.\")\n"
        "    return physics_sim_view\n\n\n"
        "class ArticulationData:\n",
        f"{path.name}: helper insertion",
    )
    text = replace_once(
        text,
        "        self._physics_sim_view = SimulationManager.get_physics_sim_view()\n",
        "        self._physics_sim_view = _get_or_create_physics_sim_view()\n",
        f"{path.name}: use fallback sim view",
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_hdf5_handler(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    text = replace_once(
        text,
        "_H5PY_IMPORT_ERROR = None\nif os.environ.get(\"MIMICKIT_DISABLE_H5PY\", \"0\") == \"1\":\n    h5py = None\nelse:\n",
        "_H5PY_IMPORT_ERROR = None\n"
        "disable_h5py = os.environ.get(\"MIMICKIT_DISABLE_H5PY\", \"1\" if os.name == \"nt\" else \"0\") == \"1\"\n"
        "if disable_h5py:\n"
        "    h5py = None\n"
        "else:\n",
        f"{path.name}: disable h5py on Windows",
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply native Windows IsaacLab hotfixes for MimicKit.")
    parser.add_argument("--isaaclab-dir", required=True, help="Path to IsaacLab_full workspace root.")
    args = parser.parse_args()

    root = Path(args.isaaclab_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"isaaclab-dir does not exist: {root}")

    targets = {
        root / "source" / "isaaclab" / "isaaclab" / "assets" / "articulation" / "articulation.py": patch_articulation,
        root / "source" / "isaaclab" / "isaaclab" / "assets" / "articulation" / "articulation_data.py": patch_articulation_data,
        root / "source" / "isaaclab" / "isaaclab" / "utils" / "datasets" / "hdf5_dataset_file_handler.py": patch_hdf5_handler,
    }

    changed = 0
    for path, patch_fn in targets.items():
        if not path.exists():
            raise FileNotFoundError(f"Expected IsaacLab file is missing: {path}")
        if patch_fn(path):
            changed += 1
            print(f"[patched] {path}")
        else:
            print(f"[ok] {path}")

    print(f"[done] changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
