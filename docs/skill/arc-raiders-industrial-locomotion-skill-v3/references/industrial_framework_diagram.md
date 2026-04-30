# ARC Raiders-like Industrial Framework Diagram

## Canonical diagram

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

## Engineering interpretation

### 1. Reference animation
Source material may come from GLB, FBX, BVH, or hand-keyed animation. It is not only “visual inspiration”; it is a training asset that will be cleaned, retargeted, segmented, and turned into motion/style supervision.

### 2. AI4AnimationPy
Use AI4AnimationPy as the Python-side animation engineering workbench:
- import
- cleanup
- retarget
- segmentation
- motion-loop validation
- contact inspection
- quick rollout playback

Do not position AI4AnimationPy as the main large-scale RL trainer.

### 3. Dataset
The dataset layer should explicitly separate motion categories and metadata:
- looping walk/run
- turning clips
- hit reactions / stumble / recover
- foot-contact labels
- brain/task labels
- versioning and manifest files

### 4. MimicKit AMP
This is the RL/AMP core:
- policy
- critic
- discriminator
- observation builder
- reward terms
- motion library access

If multi-task interference is observed, split into task-specific brains instead of overloading a single policy.

### 5. Isaac Lab
This is the scalable simulator baking layer:
- thousands of environments in parallel
- curriculum progression
- perturbation training
- domain randomization
- throughput monitoring

### 6. Export
Every export package must contain at least:
- model file (`.onnx` preferred for UE5 runtime)
- observation/action specification
- normalization statistics
- joint order
- physics/control frequency
- coordinate basis notes

### 7. UE5 runtime
UE5 runtime must be treated as a native runtime system:
- C++ inference path
- state packaging
- cache reuse
- profiling
- deterministic debug tools

### 8. Physics execution
Map policy outputs to a physically meaningful execution layer:
- Chaos joint drive
- Physics Control
- Physical Animation
- PD target mapping

### 9. Behavior Tree / Blackboard
This is where design intent lives:
- choose WalkBrain / StopBrain / TurnBrain / RecoverBrain
- set target direction
- switch behavior by combat state

### 10. Final enemy behavior
The final target is not “walks in sim.”
The target is production enemy behavior:
- walk
- run
- stumble
- recover
- integrate with combat and gameplay logic
