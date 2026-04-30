# ARC Raiders-like Industrial Pipeline Notes

## Why this skill exists

This workflow is for building a full production pipeline inspired by ARC Raiders' physics-based enemy locomotion. It must preserve the production lessons:

- RL locomotion alone can make a robot walk, but not necessarily walk with good style.
- Animator reference motion should become training signal through AMP/GAIL-like adversarial imitation.
- Multiple policy brains are often more production-friendly than a single overloaded network.
- Behavior Tree/GAS should remain the designer-facing layer.
- Terrain perception is part of locomotion, not a later add-on.
- Metrics, visualization, profiling, and replay capture are mandatory for iteration.

## Three-stage ownership

| Stage | Owner mindset | Output |
|---|---|---|
| MimicKit | ML training and physics controller baking | `.pt`, `.onnx`, configs, rollout videos, normalization stats |
| AI4AnimationPy | Animation engineering preview and parity tests | interactive demo, motion viewers, ONNX traces |
| UE5 | Production runtime and gameplay integration | plugin, components, Behavior Tree tasks, Chaos motor control |

## Runtime data contract

Every brain package must include:

```json
{
  "brain_name": "WalkBrain",
  "model": "WalkBrain.onnx",
  "policy_hz": 30,
  "physics_hz": 120,
  "observation_dim": 0,
  "action_dim": 0,
  "joint_order_file": "joint_order.json",
  "normalization_file": "normalization_stats.json",
  "coordinate_basis": "training_right_handed_z_up_or_documented",
  "unit_scale": "meters_to_ue_cm"
}
```

## UE5 brain-switching pattern

Behavior Tree decides intent. Neural policy decides physical execution.

```text
BTTask_SetArcBrain(Walk)
BTTask_SetArcBrain(Stop)
BTTask_SetArcBrain(Turn)
BTTask_SetArcBrain(Stomp)
BTTask_SetArcBrain(Recover)
```

In GAS terms, Walk/Stop/Turn/Stomp can be GameplayAbilities; latent vector or brain ID is payload data, not a magical AI concept.

## Minimal regression map

Create one UE5 map with:

- flat ground
- 10-degree slope
- 25-degree slope
- uneven rock field
- narrow bridge
- tunnel
- wall corner
- dynamic push impulse zone
- stop marker
- stomp target
- recovery trigger
