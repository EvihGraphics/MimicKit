#!/bin/bash
set -euo pipefail

cd /root/Project/MimicKit || exit 1

# 生成新时间戳格式的root名
NEW_TS=$(date +"%Y%m%d_%H%M%S")
NEW_ROOT="ase_7case_tmux_${NEW_TS}"

# 动态查找当前旧的时间戳root名
OLD_ROOT=$(grep -oE "ase_7case_tmux_[0-9]{8}_[0-9]{6}" start_train.sh | head -n 1 || true)

if [ -z "$OLD_ROOT" ]; then
    echo "[ERROR] Cannot find previous ase_7case_tmux root in start_train.sh!"
    exit 1
fi

echo "[INFO] Found old root: $OLD_ROOT"
echo "[INFO] Replacing with new root: $NEW_ROOT"

# 一键替换所有相关启动脚本中的 root_out
sed -i "s|${OLD_ROOT}|${NEW_ROOT}|g" start_train.sh start_dashboard.sh scripts/watchdog_ase_training.sh

# 移除看门狗的可能暂停锁
rm -f /tmp/ase_watchdog.pause

# 杀掉现有的旧会话保障纯净重启
echo "[INFO] Killing old tmux sessions..."
tmux kill-session -t train_ase 2>/dev/null || true
tmux kill-session -t monitor_ase 2>/dev/null || true
tmux kill-session -t viz_ase 2>/dev/null || true

# 拉起新的一组保活和看板
echo "[INFO] Starting new training round..."
./start_train.sh
./start_dashboard.sh

echo ""
echo "[OK] Successfully started new long-cycle training!"
echo "[OK] New ROOT: ${NEW_ROOT}"
echo "[OK] You can monitor dashboard at port 8788."
