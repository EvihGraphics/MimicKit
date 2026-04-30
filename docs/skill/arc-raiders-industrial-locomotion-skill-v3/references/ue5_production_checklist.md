# UE5 Production Checklist

## Runtime classes

- `UArcNeuralLocomotionComponent`
- `UArcBrainSelectorComponent`
- `UArcObservationBuilderComponent`
- `UArcOnnxPolicyRunner`
- `UArcJointMotorComponent`
- `UArcTerrainPerceptionComponent`
- `UArcLocomotionDebugComponent`

## Hard requirements

- No Python dependency in packaged build.
- ONNX Runtime C++ or an explicitly accepted alternative.
- Physics substepping enabled.
- Substep-safe motor application.
- Observation schema checked at startup.
- Joint order checked at startup.
- Model, normalization, and spec version locked.
- Debug draw can be toggled at runtime.
- Inference time profiled with Unreal Insights.
- Fallback behavior when inference fails.

## Fixed-timestep policy

Recommended structure:

```text
Game Thread:
  accumulate policy timer
  when policy tick fires:
    build observation snapshot
    run ONNX inference
    store latest action / joint target

Physics Substep:
  read latest action
  apply PD / joint motor targets
```

Use substep for motor stability. Run ONNX inference in the physics thread only after profiling proves it is safe.

## Coordinate conversion policy

- Convert positions and velocities from UE5 cm to training meters.
- Convert UE5 left-handed coordinate data into training basis.
- Recompute quaternions through basis matrices.
- Validate with:
  - root forward arrow
  - up vector arrow
  - foot socket positions
  - joint axis debug lines
