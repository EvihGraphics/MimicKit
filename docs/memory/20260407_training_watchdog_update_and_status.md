# 2026-04-07 Training Status and Watchdog Upgrade

## 1. 状态更新 (Current Status)
- **当前运行实例**: ASE Dual-GPU Training (`train_ase` + `monitor_ase` in tmux).
- **当前案例**: `ase_heading_humanoid_sword_shield_args.txt`.
- **目前进度**: 刚刚经历一次 Watchdog 级别的环境重启，目前位于 `ase_heading_humanoid_sword_shield_l2_resume426`。
- **看板延迟原因**: 监控看板（Dashboard）暂时显示进度为 0.0% 且等待首个快照。这是因为模型进程正在利用 `cuda:0` 和 `cuda:1` 重新编译和装载 `mujoco_warp` 及 `newton_engine` 的大量多重物理 JIT Kernel，耗时约 5-10 分钟（此期间 GPU 1 必定显示 0% 利用率）。待 CUDA 缓存装载完毕，首个 Step 跑完后将正常释出第一笔 Reward 和 Epoch 训练快照，看板即可自行恢复推演。

## 2. 异常修复纪要 (Zombie Deadlock Fix)
- **现象**: 之前训练期间发生死锁，残留的僵尸进程导致 GPU 0 满载运算（100%），而 GPU 1 空载（0%）。由于原版的守护死机脚本仅仅判断“双卡平均/总和利用率是否等于 0”，导致这种单边死锁的僵尸状态无法被自动清理。
- **解决措施**: 
  - 对 `scripts/watchdog_ase_training.sh` 脚本进行了监控逻辑重构，引入分别判定的显卡容错体系。
  - 目前当运行双卡训练时，分别监听 GPU 0 和 GPU 1。如果**任意一张卡**在容错阈值内利用率降为 0%，即判定为单点死锁并执行 `pkill -9` 环境清盘。
  - 为了兼容 JIT 内核长达 10 分钟以上的静态编译期，将容忍上限由原来的 3 minutes 并发扩宽至 **15 minutes（15 ticks）**，彻底避免 Watchdog 杀掉自身正常加载流水的乌龙。

## 3. 全自动推理渲染管线 (Automated Visualization Handoff)
- 现行代码加入了全自动论文级测试流水：一旦 Watchdog 读取到 `output/train/.../current_case.txt` 中的 `COMPLETE`。
- 脚本便会自动跳出无限重跑的监测循环，并立即通过隔离建立 `viz_ase` Tmux Session，无缝衔接推理脚本：`tools/ue_bridge/build_mimickit_render_sequences.py`。
- 由训练期直至生成验证序列再无断点，完成端到端的 Paper-level Standard（论文级全复现有序架构）。