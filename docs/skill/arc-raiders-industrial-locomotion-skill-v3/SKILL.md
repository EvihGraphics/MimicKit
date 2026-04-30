---
name: arc-raiders-industrial-locomotion
description: Use this skill when building, reviewing, or extending an ARC Raiders-like physics-based enemy locomotion pipeline across MimicKit training, AI4AnimationPy demo validation, and UE5 industrial deployment. Trigger on requests involving MimicKit, AMP/GAIL/ASE/CASE, AI4AnimationPy, UE5 active ragdoll, Chaos physics, ONNX Runtime inference, Behavior Tree brain switching, point-cloud terrain perception, or productionizing physics-based neural enemy locomotion.
---

# ARC Raiders-like Physics-Based Enemy Locomotion Skill

## 0. Mission

The goal is to help the user build an **industrial production pipeline** for ARC Raiders-like enemy locomotion, not a paper-only reproduction.

The final system must look like a game-engine feature:

```text
Animator reference motion
        ↓
MimicKit / AMP-style training
        ↓
multiple policy brains: Walk / Stop / Turn / Stomp / Recover
        ↓
AI4AnimationPy demo and visualization layer
        ↓
ONNX export + deterministic data contract
        ↓
UE5 C++ runtime inference
        ↓
Chaos / FBodyInstance / Physical Animation / Joint Drive execution
        ↓
Behavior Tree / GAS / gameplay-controlled enemy locomotion
        ↓
profiling, QA, regression clips, model registry
```

Treat the trained policy as a **runtime controller**, like a compiled `UCharacterMovementComponent::PhysCustom()` or physics-driven animation component. It takes a fixed observation struct every physics tick and outputs motor targets.


## 0.1 Canonical reference framework diagram

Use the following diagram as the **default production pipeline reference** when planning tasks, reviewing architecture, or splitting work across stages:

```mermaid
flowchart LR
    A[参考动画\nGLB/FBX/BVH/手K] --> B[AI4AnimationPy\n导入/清洗/重定向/可视化]
    B --> C[训练数据集\n循环步态/转向/受击恢复/标签]
    C --> D[MimicKit AMP\nPolicy + Critic + Discriminator]
    D --> E[Isaac Lab 并行训练\n课程学习/随机化/扰动]
    E --> F[导出模型\nONNX 或 TorchScript]
    F --> G[UE5 Runtime Plugin\n推理/状态组包/缓存]
    G --> H[Physics Control / Physical Animation\nPD目标映射]
    H --> I[Behavior Tree / Blackboard\n多brain切换]
    I --> J[敌人最终表现\n走/跑/绊/恢复/战斗接入]
```

Interpretation rules:

- **AI4AnimationPy lives before MimicKit and before UE5.** It is the data-conditioning, retargeting, inspection, and demo-validation layer.
- **MimicKit AMP is the training core.** It owns the low-level policy, critic, and discriminator training logic.
- **Isaac Lab is the scalable parallel baking environment.** Curriculum learning, domain randomization, perturbation pushes, and bulk rollout collection happen here.
- **UE5 Runtime Plugin is the production boundary.** Everything after model export must be framed as a game runtime system, not a notebook demo.
- **Physics Control / Physical Animation is the execution layer.** The neural output is not the final animation clip; it is a control signal that must be mapped to PD targets / motors.
- **Behavior Tree / Blackboard is the designer-facing orchestration layer.** High-level intent selects which brain runs, while the neural controller executes locomotion physically.

Stage ownership implied by the diagram:

- `A -> C` belongs primarily to **AI4AnimationPy Demo搭建阶段**.
- `D -> F` belongs primarily to **MimicKit 学习阶段**.
- `G -> J` belongs primarily to **UE5 工业化部署阶段**.

This diagram should appear in planning notes, milestone reviews, and handoff documents unless the user explicitly asks for a different architecture.

## 1. Non-negotiable principles

1. **Do not reduce the work to an AMP paper demo.**
   - A paper demo ends at "the agent walks in simulation."
   - This skill targets "the enemy runs in UE5 production with designer controls, debug tooling, profiling, rollback, and iteration workflows."

2. **Separate training, demo, and production.**
   - Python is the baking/training side.
   - UE5 C++ is the runtime/inference side.
   - AI4AnimationPy is a demo, inspection, and visualization bridge, not the main RL simulator.

3. **Preserve ARC-like production structure.**
   - Use multiple task-specific brains when tasks interfere.
   - Use Behavior Tree or GAS to switch high-level behavior.
   - Keep animator reference motion in the loop through adversarial imitation / AMP-style style reward.
   - Use point-cloud or ray-based perception for complex geometry; heightmaps are only acceptable for the first flat-terrain MVP.

4. **Never deploy the discriminator at runtime unless explicitly requested.**
   - In AMP/GAIL-style workflows, the discriminator is a training-time style reward module.
   - Runtime should usually load only the policy brain or low-level skill policy.

5. **Always treat UE5 migration as Sim-to-Sim Gap.**
   - Isaac / PhysX / GPU simulation and UE5 Chaos do not match by default.
   - Fixed timestep, mass, friction, damping, torque limits, coordinate conversion, and joint limits must be audited.

6. **Use ONNX Runtime C++ Native as the default production inference path.**
   - NNE can be used for prototypes, but production guidance should prefer ONNX Runtime unless the user explicitly targets NNE.
   - Avoid Python in UE5 runtime.

7. **Fixed physics timestep is mandatory.**
   - Training normally assumes fixed policy/control frequency.
   - UE5 must enable Physics Sub-stepping and should use `FBodyInstance::AddCustomPhysics` or an equivalent substep hook for stable torque/joint control.

8. **Coordinate conversion is mandatory.**
   - Isaac/OpenGL-like systems are commonly right-handed; UE5 is left-handed, Z-up, X-forward, Y-right.
   - Position conversion may be as simple as `(x, y, z) -> (x, -y, z)` depending on source axes, but do not blindly transform quaternions by sign hacking.
   - Recalculate rotations through a basis transform and validate with Debug Draw.

## 2. Required mental model for explanations

Always translate ML/RL terms into UE/game-engine terms first:

| RL / ML term | UE5 / engine analogy |
|---|---|
| Policy Network | Runtime Controller / Tick Logic |
| Observation | `FBodyInstance` state + socket transforms + terrain samples |
| Action | Joint motor target / PD target / torque command |
| Reward | Fitness function / automated debug score |
| Episode | One BeginPlay-to-fall-or-timeout session |
| PPO training | Massive automated parameter tuning |
| AMP discriminator | Animation-style judge used during baking |
| Latent skill vector | Gameplay Tag payload / skill handle |
| Sim-to-Sim Gap | PhysX-vs-Chaos solver discrepancy |
| Motion prior | Style constraint from animator reference motion |

Use these analogies before deep RL jargon.

## 3. Source-grounded architectural target

Use the ARC Raiders report as the production inspiration:

- Traditional hand-keyed animation, mocap, and procedural animation were considered insufficient for giant multi-legged physical robots because dynamic physical interaction and maintainability become difficult.
- Initial RL could make robots walk, but gait style lacked weight and appeal.
- Production solution used adversarial imitation / AMP-like style learning from animator-authored references.
- Multiple task-specific brains were used instead of one monolithic network when forward/stop/stomp/turn tasks interfered.
- Designers controlled behavior through familiar Behavior Tree abstractions.
- Terrain perception evolved from top-down heightmap to robot-centered point cloud/raycast perception for tunnels and interiors.
- Engineering interface design, metrics, iteration tools, and cross-discipline workflow are part of the core technical solution, not optional polish.

## 4. Stage A — MimicKit [学习阶段 / Training Foundation]

### 4.1 Objective

Use MimicKit to understand and reproduce the **training-side runtime controller**:

```text
Reference motion + robot physics model + task reward
        ↓
AMP / ASE / PPO training
        ↓
policy brain .pt
        ↓
ONNX export + normalization stats + observation/action contract
```

This stage is successful only when the user can explain and modify the training pipeline, not merely run a command.

### 4.2 Required deliverables

Create or maintain these artifacts:

```text
training/
  assets/
    arc_robot.xml or equivalent asset definition
    arc_robot_skeleton.json
    physics_params.yaml
  motions/
    walk_ref.pkl or npz
    stop_ref.pkl or npz
    turn_ref.pkl or npz
    stomp_ref.pkl or npz
  configs/
    arc_walk_env.yaml
    arc_stop_env.yaml
    arc_turn_env.yaml
    arc_stomp_env.yaml
    arc_amp_agent.yaml
  exports/
    WalkBrain.onnx
    StopBrain.onnx
    TurnBrain.onnx
    StompBrain.onnx
    RecoverBrain.onnx
    obs_action_spec.yaml
    normalization_stats.json
    brain_manifest.json
  reports/
    tensorboard_snapshot/
    rollout_videos/
    training_log.md
```

### 4.3 Learning tasks

When Codex is asked to help with this stage, prioritize these tasks:

1. **Run the existing MimicKit example first.**
   - Confirm Python environment.
   - Confirm simulator backend.
   - Confirm policy rollout works.
   - Confirm TensorBoard logging.
   - Confirm model checkpoint loading.

2. **Map the codebase by responsibility.**
   - `Environment`: builds observations and rewards.
   - `Agent`: PPO/AMP/ASE training loop.
   - `Model`: policy/value/discriminator networks.
   - `MotionLib`: reference motion loading and sampling.
   - `Engine backend`: Isaac Gym / Isaac Lab / other simulator interface.

3. **Extract the observation/action schema.**
   - Root height.
   - Root local rotation.
   - Root local linear/angular velocity.
   - Local joint rotations.
   - Local joint velocities.
   - Foot/end-effector positions.
   - Target direction/distance.
   - Previous action.
   - Terrain rays or height samples.
   - Optional latent vector if using ASE/CASE.

4. **Build a first robot controller.**
   - Start with simplified quadruped or hexapod.
   - Do not begin with the full ARC robot scale/complexity.
   - First train WalkBrain with task reward only.
   - Then add AMP style reward.
   - Then split StopBrain / TurnBrain / StompBrain.

5. **Export deterministic runtime assets.**
   - ONNX model.
   - Normalization stats.
   - Joint order.
   - Action scale.
   - PD gains.
   - Physics units.
   - Coordinate basis metadata.
   - Control frequency.

### 4.4 Stage A acceptance criteria

MimicKit learning stage is complete when:

- WalkBrain can move toward a target without falling in simulator.
- StopBrain can decelerate and settle without sliding forever.
- TurnBrain can rotate toward a target heading without violent jitter.
- AMP-style training visibly improves gait weight/style compared with pure task reward.
- Every ONNX export has a matching `obs_action_spec.yaml`.
- A fresh script can replay a trained checkpoint and regenerate rollout videos.
- Training and runtime frequencies are written down explicitly.

### 4.5 Common failure modes

| Failure | Likely cause | Codex response |
|---|---|---|
| Walks but looks weightless | Task reward dominates style reward | Increase AMP/style reward, improve reference motion, penalize excessive energy |
| Walks but cannot stop | One policy learned conflicting tasks | Split into WalkBrain and StopBrain |
| Explodes in simulation | PD gain / force limit / timestep issue | Reduce gains, cap torque, increase substeps |
| Looks good in Isaac but bad in UE | Sim-to-Sim gap | Audit units, joint axes, friction, damping, timestep |
| ONNX output mismatches Python | Export wrapper changed normalization/order | Create parity test: PyTorch vs ONNX same input |


### 4.6 Mandatory repository skill addition — AMP Dashboard Skill

When working inside the MimicKit repository, the MimicKit learning stage has one extra non-negotiable deliverable:

```text
docs/skill/mimickit-amp-dashboard-skill/SKILL.md
```

Build it as a parallel sibling of the existing GitHub-accessible skills:

```text
docs/skill/mimickit-ase-dashboard-skill/SKILL.md
docs/skill/mimickit-render-viz-sequence-skill/SKILL.md
docs/skill/mimickit-amp-dashboard-skill/SKILL.md   # new required skill
```

Use the branch/path supplied by the user as the source of truth:

```text
https://github.com/EvihGraphics/MimicKit/tree/feat/ase-prework/docs/skill
```

Codex must first read the existing `mimickit-ase-dashboard-skill` and `mimickit-render-viz-sequence-skill` from GitHub or the local checkout, then create the AMP dashboard skill in the same style. Do not destructively rewrite the ASE dashboard skill.

#### Why this exists

ASE and AMP are related but not identical:

- ASE dashboard tracks latent-space health, encoder reward, diversity loss, and serial ASE pretraining stages.
- AMP dashboard should track adversarial style imitation health for task-specific policy brains.
- AMP does not have ASE's latent encoder/diversity objective unless the codebase explicitly adds one, so do not copy ASE latent-specific cards blindly.

Think of the AMP dashboard as the UE equivalent of a dedicated Gameplay Debugger page for one locomotion controller: it tells whether the runtime controller is learning the intended gait style, whether task reward is improving, and whether the checkpoint is worth sending to AI4AnimationPy/UE5.

#### AMP Dashboard expected focus

The new `mimickit-amp-dashboard-skill` must focus on:

```text
- AMP run progress to a target sample budget
- task reward vs AMP/style reward
- discriminator reward / discriminator accuracy
- policy loss, value loss, entropy, clip_frac when available
- samples/s and ETA
- dual RTX 4090 utilization / memory / temperature
- current brain name: WalkBrain / StopBrain / TurnBrain / StompBrain / RecoverBrain
- queue state for multi-brain AMP series
- checkpoint health and best-model selection
- links to render-viz output for rollout inspection
```

#### Suggested entry scripts

If the repository already has a generalized dashboard runner, adapt it. Otherwise create AMP-specific scripts that mirror the ASE naming convention:

```text
scripts/run_amp_dashboard.py
scripts/watchdog_amp_training.sh
scripts/run_amp_series_queue.py              # optional if no generic queue exists
```

The dashboard must be read-only and based on parsing existing training outputs/logs. It should not mutate checkpoints or restart training unless the user explicitly asks for watchdog/keepalive behavior.

#### Required relationship with render-viz sequence skill

The AMP dashboard skill must explicitly pair with:

```text
docs/skill/mimickit-render-viz-sequence-skill/SKILL.md
```

Minimum integration requirement:

```text
1. Dashboard shows whether render-viz outputs exist for current/best checkpoints.
2. Dashboard links to `output/img/.../render_meta.json`, PNG frame folders, and MP4s if generated.
3. Codex uses render-viz before declaring a checkpoint visually good or collapsed.
4. For AMP/ASE policy cases, render via the agent test loop whenever available; do not judge quality from a static actor wrapper.
```

#### AMP Dashboard acceptance criteria

The new AMP dashboard skill is complete when:

```text
[ ] `docs/skill/mimickit-amp-dashboard-skill/SKILL.md` exists.
[ ] Its metadata `name` is `mimickit-amp-dashboard`.
[ ] It references `scripts/run_amp_dashboard.py` or the actual implemented dashboard entry script.
[ ] It explains differences from the ASE dashboard.
[ ] It removes or guards ASE-only latent metrics such as `enc_reward_mean` and `diversity_loss`.
[ ] It tracks AMP/style/discriminator/task/throughput metrics.
[ ] It includes Quick Start commands.
[ ] It states how to pair with `mimickit-render-viz-sequence-skill`.
[ ] It defines visual acceptance through rollout renders, not just scalar rewards.
[ ] It supports multi-brain ARC-like runs: Walk / Stop / Turn / Stomp / Recover.
```

#### Do not do these

```text
- Do not name the new skill `ase` or leave ASE-only descriptions in it.
- Do not claim AMP has latent-space health unless this repository implements latent variables for that run.
- Do not use the dashboard as proof of production readiness; UE5 parity and physical deployment are still required.
- Do not skip render-viz inspection before exporting a model to the UE5 stage.
```


## 5. Stage B — AI4AnimationPy [Demo搭建阶段 / Interactive Demo Bridge]

### 5.1 Objective

Use AI4AnimationPy as the **animation engineering and demo bridge**:

```text
MimicKit rollout / exported ONNX
        ↓
motion inspection + skeleton viewer + interactive brain switch
        ↓
debug curves + contact visualization + action inspection
        ↓
validated data contract for UE5
```

AI4AnimationPy is not the main RL training environment. It is the "Animation Blueprint preview scene" of the Python side.

### 5.2 Required deliverables

```text
demo_ai4animationpy/
  importers/
    import_mimickit_motion.py
    import_rollout_npz.py
  viewers/
    brain_switch_demo.py
    rollout_viewer.py
    contact_debug_viewer.py
  inference/
    onnx_policy_runner.py
    obs_builder_stub.py
    parity_test.py
  exports/
    ue_test_clip_walk.npz
    ue_test_clip_stop.npz
    ue_debug_trajectory.json
  docs/
    demo_controls.md
    schema_notes.md
```

### 5.3 Demo responsibilities

1. **Motion data inspection**
   - Load BVH/FBX/GLB/NPZ where possible.
   - Convert reference animation into MimicKit-compatible motion format or a shared intermediate.
   - Display root trajectory, foot contacts, joint curves, and action curves.

2. **Policy inference sanity check**
   - Load ONNX policy.
   - Load `normalization_stats.json`.
   - Feed scripted observations.
   - Verify outputs are stable and within joint limits.

3. **Interactive brain switching**
   - Keyboard or UI switches:
     - `W`: WalkBrain.
     - `S`: StopBrain.
     - `A/D`: TurnBrain.
     - `Space`: StompBrain.
     - `R`: RecoverBrain.
   - This can be a kinematic or simplified physical preview; do not pretend it is UE5 production physics.

4. **Debug artifact generation**
   - Save replayable clips.
   - Save observation logs.
   - Save ONNX input/output traces.
   - Export one deterministic frame-by-frame trace for UE5 parity tests.

### 5.4 Stage B acceptance criteria

AI4AnimationPy demo stage is complete when:

- A non-ML user can switch brains and inspect what changes.
- The same ONNX model returns the same output as PyTorch within tolerance.
- Joint order and coordinate basis are visibly validated.
- Foot contact and root motion are easy to inspect.
- At least one exported trace can be loaded by UE5 tests.

### 5.5 Common failure modes

| Failure | Likely cause | Codex response |
|---|---|---|
| Demo looks good but UE fails | Demo skipped physical execution | Make it clear this is preview only; add UE parity trace |
| Joint order mismatch | Different skeleton traversal order | Generate `joint_order.json` and assert it everywhere |
| ONNX output unstable | Missing normalization | Load and apply training stats |
| Reference animation cannot import | Format mismatch | Add a conversion script and document axis/unit assumptions |

## 6. Stage C — UE5 [工业化部署阶段 / Production Runtime]

### 6.1 Objective

Build a UE5 runtime system that treats the trained brain as a **native C++ physics controller**, not a Python demo.

Target architecture:

```text
BT_ArcEnemy / GAS Ability
        ↓
UArcBrainSelectorComponent
        ↓
UArcObservationBuilderComponent
        ↓
UArcOnnxPolicyRunner
        ↓
UArcJointMotorComponent
        ↓
Chaos Physics / FBodyInstance / PhysicalAnimation / PhysicsConstraint
        ↓
UArcNeuralLocomotionDebugComponent
```

### 6.2 Required UE5 modules/classes

```text
Plugins/ArcNeuralLocomotion/
  Source/ArcNeuralLocomotionRuntime/
    Public/
      ArcBrainTypes.h
      ArcObservationSpec.h
      ArcBrainSelectorComponent.h
      ArcObservationBuilderComponent.h
      ArcOnnxPolicyRunner.h
      ArcJointMotorComponent.h
      ArcTerrainPerceptionComponent.h
      ArcNeuralLocomotionComponent.h
      ArcLocomotionDebugComponent.h
    Private/
      ArcBrainSelectorComponent.cpp
      ArcObservationBuilderComponent.cpp
      ArcOnnxPolicyRunner.cpp
      ArcJointMotorComponent.cpp
      ArcTerrainPerceptionComponent.cpp
      ArcNeuralLocomotionComponent.cpp
      ArcLocomotionDebugComponent.cpp
  Content/
    Models/
      WalkBrain.onnx
      StopBrain.onnx
      TurnBrain.onnx
      StompBrain.onnx
      RecoverBrain.onnx
    Data/
      obs_action_spec.yaml
      normalization_stats.json
      brain_manifest.json
```

### 6.3 UE5 runtime responsibilities

1. **Brain selection**
   - Behavior Tree sets desired locomotion intent.
   - GAS can represent skills as GameplayAbilities.
   - A latent vector or brain ID can be passed through GameplayEvent payload.
   - Runtime chooses the model or latent skill, not the animator.

2. **Observation building**
   - Read root body transform, velocities, joint local rotations, angular velocities, contacts, target direction, previous action, and terrain perception.
   - Convert UE units from cm to training meters.
   - Convert UE coordinate basis to training coordinate basis.
   - Normalize using training stats.
   - Assert exact dimension and joint order.

3. **Inference**
   - Default: ONNX Runtime C++ CPU.
   - Batch only if controlling many enemies and profiling proves benefit.
   - Keep inference off the render path.
   - Avoid GPU inference unless data already lives on GPU and latency is proven acceptable.

4. **Physics execution**
   - Use Physics Sub-stepping.
   - Use `FBodyInstance::AddCustomPhysics` or an equivalent substep path for stable control.
   - Game thread can run inference at policy frequency.
   - Physics substep applies PD or motor targets at solver frequency.
   - Never depend on variable `DeltaTime` for motor stability.

5. **Perception**
   - MVP: local height samples.
   - Production target: robot-centered ray/point-cloud perception.
   - Cache static-world hits in world space when possible.
   - Transform cached hits into robot local space for observation.
   - Treat tunnels/interiors as required test cases.

6. **Debug and QA**
   - Draw current skeleton vs target/motor skeleton.
   - Draw terrain rays and point-cloud samples.
   - Draw root heading, target heading, foot contacts, torque usage.
   - Log ONNX input/output trace.
   - Provide replay capture for deterministic bug reports.
   - Add Unreal Insights markers for observation, inference, and motor application.

### 6.4 Stage C acceptance criteria

UE5 production stage is complete when:

- The enemy can run in PIE and packaged build without Python.
- Behavior Tree can switch Walk/Stop/Turn/Stomp/Recover brains.
- Designer-facing controls exist without touching ML code.
- Animator-facing reference iteration is documented.
- The robot can be pushed, collide, recover, or fail gracefully.
- Physics runs at fixed substep frequency.
- ONNX inference time is measured and budgeted.
- Terrain perception works in tunnels and interiors.
- A regression map contains flat terrain, slope, uneven rocks, bridge, tunnel, and obstacle cases.
- Model version, normalization stats, and observation spec are locked together.

## 7. Industrial workflow checklist

For any implementation request, Codex should check:

```text
[ ] Is this training-side, demo-side, or UE5 runtime-side?
[ ] Does the requested change affect observation dimensions?
[ ] Does it affect action dimensions or joint order?
[ ] Does it affect normalization stats?
[ ] Does it affect coordinate conversion?
[ ] Does it affect control frequency?
[ ] Does it affect Physics Asset / joint limits / PD gains?
[ ] Does it need a new ONNX export?
[ ] Does UE5 need a matching schema update?
[ ] Does the AI4AnimationPy demo need a matching validation trace?
```

If any schema changes, update all dependent artifacts:

```text
obs_action_spec.yaml
normalization_stats.json
brain_manifest.json
joint_order.json
UE5 C++ constants / data asset
AI4AnimationPy parity tests
MimicKit env config
```

## 8. Recommended output format when responding to the user

When asked to plan, implement, or review code, answer in this order:

```text
1. 执行结论
2. 当前阶段：MimicKit / AI4AnimationPy / UE5
3. 本次要改的文件
4. 数据流是否变化
5. 具体实现步骤
6. 验收标准
7. 风险与下一步
```

For code changes, produce file-level patches and explicitly mention any assumptions.

## 9. Industrial definition of done

The feature is not done when the policy walks in a simulator. It is done when:

- Training can be reproduced from versioned configs.
- Demo can visualize and validate the trained brain.
- UE5 can run the brain without Python.
- Designers can switch behavior through Behavior Tree/GAS.
- Animators can update reference motion without rewriting the RL code.
- QA can replay locomotion bugs.
- Engineers can profile inference, observation building, and physics control independently.
- Sim-to-Sim differences are measured, not guessed.
- The system degrades gracefully under failed inference or bad terrain perception.

## 10. Default implementation strategy

Prefer this order:

1. MimicKit existing AMP example.
2. Simplified quadruped or hexapod WalkBrain.
3. AMP-style reference gait.
4. StopBrain and TurnBrain split.
5. AI4AnimationPy ONNX parity viewer.
6. UE5 ONNX Runtime component.
7. UE5 fixed-step physical motor control.
8. Behavior Tree brain switching.
9. Point-cloud perception.
10. Recovery brain and production QA suite.

Do not start with full ARC-scale enemy complexity.
Do not merge all skills into one network until the simple split-brain system is stable.
Do not remove debug instrumentation to make demos look cleaner.
