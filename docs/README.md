# Docs 分类索引

为了避免 `README_XXX.md` 平铺，文档已按类别整理如下：

## 1. `docs/methods/`（方法文档）

- `docs/methods/README_DeepMimic.md`
- `docs/methods/README_AMP.md`
- `docs/methods/README_ASE.md`
- `docs/methods/README_ADD.md`

适合查：方法原理、参数含义、案例与训练/推理/可视化说明。

## 2. `docs/guides/`（学习与上手）

- `docs/guides/README_ASE_Dual4090_SOP.md`
- `docs/guides/README_ASE_FullChain_TrainInferVisual_SOP.md`
- `docs/guides/README_Newbie_TrainInferVisual_PaperCases.md`
- `docs/guides/README_LearningPlan.md`
- `docs/guides/README_VisualReproductionAcceptance.md`
- `docs/guides/README_Paper_ConfigCaseCatalog.md`

适合查：零基础学习路径、全量案例总览、统一使用流程。
若当前主目标是双 RTX 4090 上的 ASE 大规模训练，优先读：`docs/guides/README_ASE_Dual4090_SOP.md`。
若当前目标是把 upstream `ASE` 的 LLC -> HLC -> perturb / view_motion 全链路在本仓库跑通，优先读：`docs/guides/README_ASE_FullChain_TrainInferVisual_SOP.md`，再读 `docs/methods/README_ASE.md`。
推荐先读：`docs/guides/README_VisualReproductionAcceptance.md` 中的 `8h -> 24h` 预算策略，再开始全案例长周期运行。

## 3. `docs/guide/`（面向小白的综合手册）

- `docs/guide/README_Newbie_ConfigAudit_and_Onboarding.md`

适合查：从 0 到 1 的上手流程、配置问题排查、线上论文与资料核对、可直接复制的安全命令模板。

## 4. `docs/benchmarks/`（案例与性能评测）

- `docs/benchmarks/README_MimicKit_CaseCatalog.md`
- `docs/benchmarks/README_MimicKit_GPUCaseBenchmark.md`
- `docs/benchmarks/README_MimicKit_GPUUtilizationPatterns.md`
- `docs/benchmarks/README_MimicKit_AllCaseLongcycle.md`
- `docs/benchmarks/README_GPU_AgentProfiles.md`

适合查：case 清单、GPU 利用率、性能配置对比。

## 5. `docs/paper/`（论文中文翻译详解）

- `docs/paper/README.md`
- `docs/paper/README_DeepMimic_CN.md`
- `docs/paper/README_AMP_CN.md`
- `docs/paper/README_ASE_CN.md`
- `docs/paper/README_ADD_CN.md`
- `docs/paper/README_MimicKit_CN.md`

适合查：论文中文导读式翻译、公式直觉、与仓库实现关系。

## 6. `docs/paper_code/`（论文到代码映射）

- `docs/paper_code/README.md`
- `docs/paper_code/README_DeepMimic_TheoryCode.md`
- `docs/paper_code/README_AMP_TheoryCode.md`
- `docs/paper_code/README_ASE_TheoryCode.md`
- `docs/paper_code/README_ADD_TheoryCode.md`

适合查：函数级定位、参数级映射、实现差异说明。

## 7. `docs/ops/`（运维与长任务）

- `docs/ops/tmux-keepalive-guide.md`

适合查：tmux 保活和长时训练会话管理。

## 8. `docs/skill/`（自动化技能）

- `docs/skill/mimickit-deepmimic-training-skill/SKILL.md`
- `docs/skill/mimickit-allcase-e2e-skill/SKILL.md`
- `docs/skill/mimickit-allcase-longcycle-skill/SKILL.md`
- `docs/skill/mimickit-framework-usage-from-git-history/SKILL.md`
- `docs/skill/mimickit-multicase-gpu-util-skill/SKILL.md`
- `docs/skill/mimickit-gpu-efficiency-optimization-skill/SKILL.md`
- `docs/skill/mimickit-ase-dashboard-skill/SKILL.md`
- `docs/skill/mimickit-progress-dashboard-skill/SKILL.md`
- `docs/skill/mimickit-render-viz-sequence-skill/SKILL.md`
- `docs/skill/mimickit-piplus-dualgpu-training-skill/SKILL.md`
- `docs/skill/mimickit-wsl-multi-backend-setup-skill/SKILL.md`
- `docs/skill/mimickit-wsl-newton-setup-skill/SKILL.md`

适合查：自动化运行流程、批量 case 测试、长周期训练脚本化操作。
