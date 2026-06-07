#!/usr/bin/env python3
import argparse
import json
import mimetypes
import socketserver
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

try:
    import yaml
except Exception:
    yaml = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_amp_keepalive import (  # noqa: E402
    EVIH_RESULTS_ROOT,
    ROOT,
    TRAIN_ROOT,
    build_stage_chain_rows,
    infer_samples_per_sec,
    parse_training_rows,
    read_gpu_snapshot,
    read_text,
    render_summary,
)


LIVE_GPU_HISTORY = []


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>AMP 单脑训练看板</title>
  <style>
    :root{
      --bg:#101619;
      --bg-2:#142126;
      --card:#18262dd9;
      --card-2:#1d2f37;
      --line:#2b434d;
      --ink:#edf3f1;
      --muted:#9bb1ad;
      --ok:#3fbe7e;
      --warn:#f0a23e;
      --bad:#ef6a5b;
      --accent:#7fd1b9;
      --accent-2:#60b9ff;
      --accent-3:#f59e0b;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      color:var(--ink);
      font-family:"IBM Plex Sans","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
      background:
        radial-gradient(circle at top left, #17302b 0, transparent 34%),
        radial-gradient(circle at bottom right, #2e2316 0, transparent 26%),
        linear-gradient(135deg,var(--bg),var(--bg-2));
      min-height:100vh;
    }
    .wrap{max-width:1460px;margin:0 auto;padding:18px 18px 28px}
    .head{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;justify-content:space-between;margin-bottom:16px}
    h1{margin:0;font-size:27px}
    .sub{margin-top:4px;color:var(--muted);font-size:13px}
    .toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
    input,button{
      border:1px solid var(--line);
      background:#0f171c;
      color:var(--ink);
      padding:9px 10px;
      border-radius:10px;
      font-size:13px;
    }
    input{min-width:380px}
    button{cursor:pointer;border:none;font-weight:700;background:linear-gradient(90deg,#1f5d55,#2b7d6f)}
    .grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px}
    .card{
      background:var(--card);
      border:1px solid #27404a;
      border-radius:16px;
      padding:12px;
      box-shadow:0 8px 28px rgba(0,0,0,.18);
      backdrop-filter:blur(3px);
    }
    .kpi{grid-column:span 2}
    .wide{grid-column:span 6}
    .full{grid-column:1 / -1}
    .k{color:var(--muted);font-size:12px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}
    .v{font-size:24px;font-weight:700;line-height:1.1}
    .small{font-size:12px;color:var(--muted);margin-top:6px}
    .ok{color:var(--ok)} .warn{color:var(--warn)} .bad{color:var(--bad)}
    .meter,.bar{
      height:12px;border-radius:999px;overflow:hidden;background:#0c1317;border:1px solid #35525c;
    }
    .meter{margin-top:10px}
    .fill,.bar-fill{height:100%;transition:width .25s linear}
    .fill{background:linear-gradient(90deg,#227062,var(--accent))}
    .g0{background:linear-gradient(90deg,#5dc0ff,var(--accent-2))}
    .g1{background:linear-gradient(90deg,#e38a1b,var(--accent-3))}
    .kv{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px}
    .kv-row{padding:8px 10px;border-radius:10px;background:var(--card-2);border:1px solid #243740}
    .kv-row .kk{color:var(--muted);font-size:11px;margin-bottom:4px;text-transform:uppercase}
    .kv-row .vv{font-size:13px;line-height:1.35;word-break:break-word}
    .gpu-row{display:grid;grid-template-columns:72px 1fr 122px;gap:10px;align-items:center;margin:8px 0}
    .chart-wrap{height:240px;border:1px solid #27404a;border-radius:12px;background:#0d1418;padding:8px}
    canvas{width:100%;height:100%;display:block}
    table{width:100%;border-collapse:collapse;font-size:12px}
    th,td{padding:6px 5px;text-align:left;border-bottom:1px solid #29404a;vertical-align:top}
    th{color:#c5d9d4;background:#122026;position:sticky;top:0}
    .table-wrap{max-height:340px;overflow:auto;border:1px solid #27404a;border-radius:12px;background:#0d1418}
    .mono{
      white-space:pre-wrap;font-family:"IBM Plex Mono","Menlo","Consolas",monospace;font-size:12px;line-height:1.45;
      background:#0d1418;border:1px solid #27404a;border-radius:12px;padding:10px;min-height:180px;max-height:360px;overflow:auto;
    }
    a{color:#9fd8ff;text-decoration:none}
    a:hover{text-decoration:underline}
    .pill{
      display:inline-block;padding:4px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line);
      background:#0f171c;margin:4px 6px 0 0;
    }
    .links a{display:block;margin:4px 0}
    @media (max-width:1180px){
      .kpi,.wide{grid-column:span 6}
      .kv{grid-template-columns:1fr}
    }
    @media (max-width:760px){
      .kpi,.wide{grid-column:span 12}
      input{min-width:100%}
      .gpu-row{grid-template-columns:58px 1fr 96px}
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="head">
      <div>
        <h1>AMP 单脑训练看板</h1>
        <div class="sub" id="subtitle">加载中...</div>
      </div>
      <div class="toolbar">
        <input id="rootInput" list="rootList" placeholder="AMP root-out（可空）" />
        <datalist id="rootList"></datalist>
        <button id="applyBtn">切换 Root</button>
        <button id="refreshBtn">立即刷新</button>
      </div>
    </div>

    <div class="grid">
      <div class="card kpi"><div class="k">当前 Run</div><div class="v" id="runV">-</div><div class="small" id="runSub">-</div></div>
      <div class="card kpi"><div class="k">当前 Brain</div><div class="v" id="brainV">-</div><div class="small" id="brainSub">-</div></div>
      <div class="card kpi"><div class="k">当前进度</div><div class="v" id="progressV">-</div><div class="small" id="progressSub">-</div><div class="meter"><div class="fill" id="progressFill" style="width:0%"></div></div><div class="small" id="progressHealth">-</div></div>
      <div class="card kpi"><div class="k">当前 ETA</div><div class="v" id="etaV">-</div><div class="small" id="etaSub">-</div></div>
      <div class="card kpi"><div class="k">Checkpoint 健康</div><div class="v" id="checkpointV">-</div><div class="small" id="checkpointSub">-</div></div>
      <div class="card kpi"><div class="k">Render 状态</div><div class="v" id="renderV">-</div><div class="small" id="renderSub">-</div></div>

      <div class="card wide"><div class="k">AMP 指标</div><div class="kv" id="ampKv"></div></div>
      <div class="card wide"><div class="k">运行状态</div><div class="kv" id="statusKv"></div></div>
      <div class="card wide"><div class="k">双卡实时利用率</div><div id="gpuPanel"></div></div>
      <div class="card wide"><div class="k">配置快照</div><div class="kv" id="configKv"></div></div>
      <div class="card wide"><div class="k">Auto Finish</div><div class="kv" id="autoKv"></div></div>

      <div class="card wide"><div class="k">GPU 利用率时间线</div><div class="chart-wrap"><canvas id="gpuChart" width="700" height="220"></canvas></div></div>
      <div class="card wide"><div class="k">AMP 指标时间线</div><div class="chart-wrap"><canvas id="ampChart" width="700" height="220"></canvas></div></div>

      <div class="card full"><div class="k">Render / Artifact 链接</div><div class="links" id="linksBox">-</div></div>
      <div class="card full"><div class="k">最近训练快照</div><div class="table-wrap"><table id="recentTable"></table></div></div>
      <div class="card full"><div class="k">最近事件</div><div class="mono" id="eventsBox">-</div></div>
    </div>

    <div class="small" id="foot">-</div>
  </div>

  <script>
    const refreshMs = 5000;
    const rootInput = document.getElementById("rootInput");
    const rootList = document.getElementById("rootList");
    let gpuRealtime = [];

    function q(id){ return document.getElementById(id); }
    function clsByLevel(level){ if (level === "good") return "ok"; if (level === "bad") return "bad"; return "warn"; }
    function fmtNum(v,d=2){ if (v === null || v === undefined || Number.isNaN(Number(v))) return "-"; return Number(v).toFixed(d); }
    function fmtInt(v){ if (v === null || v === undefined || Number.isNaN(Number(v))) return "-"; return Number(v).toLocaleString(); }
    function fmtPct(v,d=1){ if (v === null || v === undefined || Number.isNaN(Number(v))) return "-"; return `${Number(v).toFixed(d)}%`; }
    function clampPct(v){ if (v === null || v === undefined || Number.isNaN(Number(v))) return 0; return Math.max(0, Math.min(100, Number(v))); }
    function fmtDuration(sec){
      if (sec === null || sec === undefined || !Number.isFinite(Number(sec)) || sec < 0) return "-";
      sec = Math.round(Number(sec));
      const d = Math.floor(sec / 86400); sec -= d * 86400;
      const h = Math.floor(sec / 3600); sec -= h * 3600;
      const m = Math.floor(sec / 60);
      if (d > 0) return `${d}d ${h}h`;
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }
    function parseRootFromUrl(){ const u = new URL(window.location.href); return u.searchParams.get("root") || ""; }
    function applyRootToUrl(root){
      const u = new URL(window.location.href);
      if (root) u.searchParams.set("root", root); else u.searchParams.delete("root");
      history.replaceState({}, "", u.toString());
    }
    async function fetchStatus(){
      const root = parseRootFromUrl();
      const url = root ? `/api/status?root=${encodeURIComponent(root)}` : "/api/status";
      const r = await fetch(url, {cache:"no-store"});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    }
    function setKv(el, rows){
      const node = q(el); node.innerHTML = "";
      (rows || []).forEach((r) => {
        const div = document.createElement("div");
        div.className = "kv-row";
        div.innerHTML = `<div class="kk">${r.k}</div><div class="vv">${r.v}</div>`;
        node.appendChild(div);
      });
    }
    function setRootOptions(roots){
      rootList.innerHTML = "";
      (roots || []).forEach((r) => { const opt = document.createElement("option"); opt.value = r; rootList.appendChild(opt); });
    }
    function renderGpuPanel(gpus){
      const panel = q("gpuPanel");
      if (!gpus || !gpus.length){ panel.innerHTML = "<div class='small'>GPU 不可用</div>"; return; }
      panel.innerHTML = "";
      gpus.forEach((g, idx) => {
        const pct = clampPct(g.util);
        const row = document.createElement("div");
        row.className = "gpu-row";
        row.innerHTML = `<div><b>GPU${g.index}</b></div><div class="bar"><div class="bar-fill ${idx===0?"g0":"g1"}" style="width:${pct}%"></div></div><div>${pct}% | ${g.mem_used} MiB</div>`;
        panel.appendChild(row);
      });
    }
    function drawChart(canvasId, points, series, opts={}){
      const canvas = q(canvasId); const ctx = canvas.getContext("2d");
      const w = canvas.width; const h = canvas.height;
      ctx.clearRect(0,0,w,h); ctx.fillStyle="#0d1418"; ctx.fillRect(0,0,w,h);
      const usable = (points || []).slice(-Math.max(2, opts.limit || 120));
      if (usable.length < 2){ ctx.fillStyle="#9cb4ae"; ctx.font="12px IBM Plex Sans"; ctx.fillText("数据不足",20,24); return; }
      let minV = opts.minY, maxV = opts.maxY;
      if (minV === undefined || maxV === undefined){
        const vals = [];
        usable.forEach((p) => series.forEach((s) => {
          const v = Number(p[s.key]); if (Number.isFinite(v)) vals.push(v);
        }));
        minV = vals.length ? Math.min(...vals) : 0;
        maxV = vals.length ? Math.max(...vals) : 1;
        if (Math.abs(maxV - minV) < 1e-6) maxV = minV + 1;
        else { const pad = (maxV - minV) * 0.12; minV -= pad; maxV += pad; }
      }
      const left=36, right=w-10, top=12, bottom=h-24, plotW=right-left, plotH=bottom-top;
      ctx.strokeStyle="#21333b"; ctx.lineWidth=1;
      for (let i=0;i<=4;i++){
        const y = top + (plotH * i / 4);
        ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke();
        const v = maxV - ((maxV-minV) * i / 4);
        ctx.fillStyle="#89a39d"; ctx.font="11px IBM Plex Mono, monospace"; ctx.fillText(v.toFixed(2),2,y+3);
      }
      const mapX = (i) => left + (i / (usable.length - 1)) * plotW;
      const mapY = (v) => bottom - ((v - minV) / (maxV - minV)) * plotH;
      series.forEach((s) => {
        ctx.beginPath();
        usable.forEach((p, i) => {
          const val = Number(p[s.key]); if (!Number.isFinite(val)) return;
          const x = mapX(i), y = mapY(val);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle=s.color; ctx.lineWidth=2; ctx.stroke();
      });
      let lx = left;
      series.forEach((s) => {
        ctx.fillStyle=s.color; ctx.fillRect(lx,h-14,10,3);
        ctx.fillStyle="#dbe7e3"; ctx.font="12px IBM Plex Sans"; ctx.fillText(s.label,lx+14,h-8); lx += 130;
      });
    }
    function renderRecent(rows){
      const table = q("recentTable");
      if (!rows || !rows.length){ table.innerHTML = "<tr><td>暂无训练行</td></tr>"; return; }
      const cols = ["Iteration","Samples","Samples_Per_Sec","Train_Return","Test_Return","Disc_Reward_Mean","Disc_Agent_Acc","Disc_Demo_Acc","Value_Loss","Policy_Loss","Clip_Frac","Entropy"];
      let html = "<thead><tr>"; cols.forEach((c) => html += `<th>${c}</th>`); html += "</tr></thead><tbody>";
      rows.slice().reverse().forEach((r) => {
        html += "<tr>";
        cols.forEach((c) => html += `<td>${r[c] ?? "-"}</td>`);
        html += "</tr>";
      });
      html += "</tbody>"; table.innerHTML = html;
    }
    function renderLinks(status){
      const box = q("linksBox");
      const links = [];
      (status.autofinish_links || []).forEach((l) => links.push(l));
      (status.links || []).forEach((l) => links.push(l));
      if (!links.length){ box.innerHTML = "<div class='small'>render pending</div>"; return; }
      box.innerHTML = links.map((l) => `<a href="${l.href}" target="_blank">${l.label}</a>`).join("");
    }
    function render(status){
      setRootOptions(status.available_roots || []);
      rootInput.value = parseRootFromUrl() || status.root_name || "";
      q("subtitle").textContent = `Root: ${status.root_name || "-"} | 最近刷新: ${status.server_time || "-"} | 当前阶段: ${status.run.stage || "-"}`;
      q("runV").textContent = status.run.case_short || "-";
      q("runSub").textContent = `${status.run.case_key || "-"} | ${status.run.stage_status || "-"}`;
      q("brainV").textContent = status.run.brain || "-";
      q("brainSub").textContent = `${status.run.queue_mode || "single-brain mode"} | ${status.run.current_train_stage || "-"}`;

      const progressPct = clampPct(status.run.progress_pct);
      q("progressV").textContent = fmtPct(progressPct, 1);
      q("progressSub").textContent = `${fmtInt(status.run.progress_samples)} / ${fmtInt(status.run.progress_target_samples)} samples | phase=${status.run.progress_label || "-"}`;
      q("progressFill").style.width = `${progressPct}%`;
      q("progressHealth").innerHTML = `<span class="pill ${clsByLevel(status.health.progress.level)}">${status.health.progress.label}</span> ${status.health.progress.detail}`;

      q("etaV").textContent = status.run.completed ? "已完成" : fmtDuration(status.run.eta_sec);
      q("etaSub").textContent = `速度 ${fmtNum(status.metrics.samples_per_sec,1)} samples/s | overall ${fmtInt(status.run.overall_long_samples)} / ${fmtInt(status.run.long_target_samples)}`;

      q("checkpointV").className = `v ${clsByLevel(status.health.checkpoint.level)}`;
      q("checkpointV").textContent = status.health.checkpoint.label;
      q("checkpointSub").textContent = status.health.checkpoint.detail;

      q("renderV").className = `v ${clsByLevel(status.health.render.level)}`;
      q("renderV").textContent = status.health.render.label;
      q("renderSub").textContent = status.health.render.detail;

      setKv("ampKv", [
        {k:"Task Metric", v:`${status.metrics.task_metric_label || "-"}<div class="small">${fmtNum(status.metrics.task_metric_value,3)}</div>`},
        {k:"Disc Reward Mean", v:fmtNum(status.metrics.disc_reward_mean,3)},
        {k:"Disc Agent / Demo Acc", v:`${fmtNum(status.metrics.disc_agent_acc,3)} / ${fmtNum(status.metrics.disc_demo_acc,3)}`},
        {k:"Policy / Value Loss", v:`${fmtNum(status.metrics.policy_loss,3)} / ${fmtNum(status.metrics.value_loss,3)}`},
        {k:"Entropy / Clip Frac", v:`${fmtNum(status.metrics.entropy,3)} / ${fmtNum(status.metrics.clip_frac,3)}`},
        {k:"Samples / Sec", v:fmtNum(status.metrics.samples_per_sec,1)},
        {k:"Throughput Health", v:`<span class="${clsByLevel(status.health.throughput.level)}">${status.health.throughput.label}</span><div class="small">${status.health.throughput.detail}</div>`},
        {k:"Discriminator Health", v:`<span class="${clsByLevel(status.health.discriminator.level)}">${status.health.discriminator.label}</span><div class="small">${status.health.discriminator.detail}</div>`},
      ]);

      setKv("statusKv", [
        {k:"Current Stage", v: status.run.stage || "-"},
        {k:"Stage Status", v: status.run.stage_status || "-"},
        {k:"Current Train Dir", v: status.run.current_train_dir || "-"},
        {k:"Best Scalar", v: status.best_scalar.status_label || "warming up"},
        {k:"Best Scalar Samples", v: fmtInt(status.best_scalar.samples)},
        {k:"Queue State", v: "single-brain mode"},
        {k:"Warming Up", v: status.flags.warming_up ? "yes" : "no"},
        {k:"Render Root", v: status.render.root_path || "-"},
      ]);

      setKv("configKv", [
        {k:"Env Name", v: status.config.env_name || "-"},
        {k:"Motion File", v: status.config.motion_file || "-"},
        {k:"Char File", v: status.config.char_file || "-"},
        {k:"Task / Disc Weights", v: `${fmtNum(status.config.task_reward_weight,2)} / ${fmtNum(status.config.disc_reward_weight,2)}`},
        {k:"Agent / Engine", v: `${status.config.agent_name || "-"} / ${status.config.engine_name || "-"}`},
        {k:"Devices / Num Envs", v: `${status.config.devices || "-"} / ${fmtInt(status.config.num_envs)}`},
        {k:"Current Log", v: status.links_log ? `<a href="${status.links_log}" target="_blank">log.txt</a>` : "-"},
        {k:"Config Snapshot", v: status.links_configs.join(" | ") || "-"},
      ]);

      const auto = status.autofinish || {};
      const autoResults = (auto.stage_results || [])
        .filter((r) => ["build_best_by_case","post_train_test","post_train_visualize","post_train_render","failed","completed"].includes(r.stage))
        .map((r) => `${r.stage}: ${r.status}${r.rc === null || r.rc === undefined ? "" : ` (rc=${r.rc})`}`)
        .join("<br>");
      setKv("autoKv", [
        {k:"Watcher Status", v: auto.status || "not started"},
        {k:"Current Stage", v: auto.current_stage || "-"},
        {k:"Updated At", v: auto.updated_at || "-"},
        {k:"Summary", v: auto.summary_file ? `<a href="/artifact?path=${encodeURIComponent(auto.summary_file)}" target="_blank">post_train_summary.md</a>` : "-"},
        {k:"Watch Log", v: auto.watch_log ? `<a href="/artifact?path=${encodeURIComponent(auto.watch_log)}" target="_blank">completion_watch.log</a>` : "-"},
        {k:"Stage Logs", v: (auto.stage_logs || []).length ? auto.stage_logs.map((l) => `<a href="${l.href}" target="_blank">${l.label}</a>`).join(" | ") : "-"},
        {k:"Stage Results", v: autoResults || "-"},
      ]);

      renderGpuPanel(status.gpus || []);
      renderRecent(status.recent_rows || []);
      renderLinks(status);
      q("eventsBox").textContent = (status.events || []).join("\\n") || "-";
      q("foot").textContent = `root=${status.root_path || "-"} | runner_log=${status.runner_log || "-"} | monitor_log=${status.monitor_log || "-"} | queue_log=${status.queue_log || "-"} | history_points=${(status.monitor_samples || []).length}`;

      const gpuMerged = (status.monitor_samples || []).concat(status.gpu_realtime || []);
      drawChart("gpuChart", gpuMerged, [
        {key:"u0", label:"GPU0 util", color:"#5dc0ff"},
        {key:"u1", label:"GPU1 util", color:"#f59e0b"},
      ], {minY:0, maxY:100, limit:120});
      drawChart("ampChart", status.chart_rows || [], [
        {key:"Disc_Reward_Mean", label:"disc_reward", color:"#7fd1b9"},
        {key:"Train_Return", label:"train_return", color:"#60b9ff"},
        {key:"Test_Return", label:"test_return", color:"#f59e0b"},
      ], {limit:120});
    }
    async function tick(){
      try{
        const status = await fetchStatus();
        render(status);
      }catch(err){
        q("subtitle").textContent = `加载失败: ${err.message}`;
      }
    }
    q("applyBtn").addEventListener("click", () => { applyRootToUrl(rootInput.value.trim()); tick(); });
    q("refreshBtn").addEventListener("click", () => tick());
    tick(); setInterval(tick, refreshMs);
  </script>
</body>
</html>
"""


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8789)
    ap.add_argument("--root-out", default="", help="AMP keepalive root or direct train root; empty means auto-detect latest amp_*")
    ap.add_argument("--monitor-log", default="", help="Optional explicit monitor log path")
    ap.add_argument("--queue-log", default="", help="Optional explicit queue log path")
    ap.add_argument("--target-samples", type=int, default=1_000_000_000)
    ap.add_argument("--brain", default="", help="Optional explicit brain label")
    ap.add_argument("--series-cases", default="", help="Forward-compat only; AMP v1 shows single-brain mode")
    ap.add_argument("--render-root", default="", help="Optional output/img root or exact render root")
    ap.add_argument("--history-size", type=int, default=240)
    return ap.parse_args()


def resolve_root(root_arg: str):
    if root_arg:
        raw = Path(root_arg)
        candidates = []
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.append(TRAIN_ROOT / root_arg)
            candidates.append(ROOT / root_arg)
            candidates.append(Path(root_arg))
        for path in candidates:
            if path.exists() and path.is_dir():
                return path.resolve()
        return None
    roots = [path for path in TRAIN_ROOT.glob("amp_*") if path.is_dir()]
    if not roots:
        return None
    return sorted(roots, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def list_amp_roots(limit=40):
    roots = [path for path in TRAIN_ROOT.glob("amp_*") if path.is_dir()]
    roots = sorted(roots, key=lambda path: path.stat().st_mtime, reverse=True)
    return [path.name for path in roots[:limit]]


def read_yaml(path: Path):
    if yaml is None or not path.exists():
        return {}
    try:
        with path.open("r") as handle:
            data = yaml.safe_load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_monitor_log(root_path: Path, explicit: str):
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    candidate = root_path / "monitor.log"
    return candidate if candidate.exists() else None


def parse_monitor_samples(path: Path | None, limit: int):
    if not path or not path.exists():
        return []
    rows = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        gpus = payload.get("gpus") or []
        if len(gpus) < 2:
            continue
        try:
            rows.append(
                {
                    "t": payload.get("time", ""),
                    "u0": float(gpus[0].get("util", 0) or 0),
                    "u1": float(gpus[1].get("util", 0) or 0),
                }
            )
        except Exception:
            continue
    return rows[-limit:]


def append_live_gpu_sample(server_time: str, gpus: list, limit: int):
    if len(gpus) >= 2:
        LIVE_GPU_HISTORY.append(
            {
                "t": server_time,
                "u0": float(gpus[0].get("util", 0) or 0),
                "u1": float(gpus[1].get("util", 0) or 0),
            }
        )
    del LIVE_GPU_HISTORY[:-limit]
    return list(LIVE_GPU_HISTORY)


def artifact_href(path: str):
    return f"/artifact?path={quote(path)}"


def is_safe_artifact(path: Path):
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except Exception:
        pass
    try:
        path.resolve().relative_to(EVIH_RESULTS_ROOT.resolve())
        return True
    except Exception:
        return False


def serve_artifact(handler, path_str: str):
    path = Path(path_str)
    if not path.exists() or not is_safe_artifact(path):
        handler._send_text("not found", code=404)
        return
    if path.is_dir():
        items = []
        for child in sorted(path.iterdir()):
            href = artifact_href(str(child))
            items.append(f'<li><a href="{href}">{child.name}</a></li>')
        body = f"<html><body><h3>{path}</h3><ul>{''.join(items)}</ul></body></html>"
        handler._send_html(body)
        return
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def infer_brain(root_name: str, env_cfg: dict, explicit_brain: str):
    if explicit_brain:
        return explicit_brain
    env_name = str(env_cfg.get("env_name", "")).lower()
    probe = f"{root_name.lower()} {env_name}"
    if "stopbrain" in probe or "amp_stop" in probe:
        return "StopBrain"
    if "steering" in probe:
        return "TurnBrain"
    if "location" in probe:
        return "WalkBrain"
    return "AMPBrain"


def compute_health(latest: dict, samples_per_sec: float, throughput_floor: float, render_state: str, best_scalar: dict):
    def make(level, label, detail):
        return {"level": level, "label": label, "detail": detail}

    if not latest:
        progress = make("warning", "warming up", "log.txt 还没有有效训练行")
        throughput = make("warning", "warming up", "等待首个速度快照")
        disc = make("warning", "warming up", "等待判别器指标")
    else:
        progress = make("good", "in progress", "训练链路已写出有效训练行")
        if samples_per_sec >= throughput_floor:
            throughput = make("good", "throughput healthy", f"{samples_per_sec:.1f} >= {throughput_floor:.0f} samples/s")
        else:
            throughput = make("warning", "throughput low", f"{samples_per_sec:.1f} < {throughput_floor:.0f} samples/s")

        try:
            agent = float(latest.get("Disc_Agent_Acc"))
            demo = float(latest.get("Disc_Demo_Acc"))
        except Exception:
            agent = -1.0
            demo = -1.0
        if agent < 0 or demo < 0:
            disc = make("warning", "warming up", "等待 disc accuracy")
        elif agent > 0.95 and demo > 0.95:
            disc = make("bad", "判别器失衡", "连续高精度通常意味着 discriminator 过强")
        elif agent < 0.55 and demo < 0.55:
            disc = make("bad", "判别器塌陷", "连续低精度通常意味着 style reward 无效")
        else:
            disc = make("good", "判别器可用", f"agent={agent:.3f} demo={demo:.3f}")

    if not best_scalar:
        checkpoint = make("warning", "warming up", "还没有满足阈值的 best scalar checkpoint")
    elif best_scalar.get("eligible") and render_state == "available":
        checkpoint = make("good", "Demo-ready", "scalar 健康且已发现 render 产物")
    elif best_scalar.get("eligible"):
        checkpoint = make("warning", "scalar ready", "best scalar 已可用，但 render 仍待生成")
    else:
        checkpoint = make("warning", "warming up", "best scalar 候选尚未达到健康阈值")

    if render_state == "available":
        render = make("good", "render ready", "已发现 render_meta / mp4 / 索引文件")
    elif render_state == "failed":
        render = make("bad", "render blocked", "视觉桥接 gate 失败，查看 blocker 与 manifest")
    elif render_state == "incomplete":
        render = make("warning", "render incomplete", "已发现产物，但尚未通过视觉桥接 gate")
    else:
        render = make("warning", "render pending", "尚未发现 render-viz 产物")

    return {
        "progress": progress,
        "throughput": throughput,
        "discriminator": disc,
        "checkpoint": checkpoint,
        "render": render,
    }


def collect_autofinish(root_path: Path):
    state = read_json(root_path / "completion_watch.json")
    if not state:
        return {
            "status": "not started",
            "current_stage": "",
            "updated_at": "",
            "summary_file": "",
            "watch_log": "",
            "stage_logs": [],
            "stage_results": [],
        }

    stage_logs = []
    stage_results = []
    for stage_name, meta in (state.get("stages") or {}).items():
        log_file = str(meta.get("log_file", "")).strip()
        if log_file:
            stage_logs.append({"label": f"{stage_name}.log", "href": artifact_href(log_file)})
        if str(meta.get("status", "")).strip() != "pending":
            stage_results.append(
                {
                    "stage": stage_name,
                    "status": meta.get("status", ""),
                    "rc": meta.get("rc"),
                    "notes": meta.get("notes", ""),
                }
            )

    return {
        "status": state.get("status", "not started"),
        "current_stage": state.get("current_stage", ""),
        "updated_at": state.get("updated_at", ""),
        "summary_file": str(state.get("summary_file", "")).strip(),
        "watch_log": str(root_path / "completion_watch.log"),
        "stage_logs": stage_logs[:8],
        "stage_results": stage_results,
    }


def collect_keepalive_status(root_path: Path, config):
    supervisor_path = root_path / "keepalive_status.json"
    supervisor = json.loads(read_text(supervisor_path) or "{}")
    current_stage = str(supervisor.get("current_stage") or "")
    current_train_stage = str(supervisor.get("current_train_stage") or "")
    current_train_dir = str(supervisor.get("current_train_dir") or "")
    current_dir = Path(current_train_dir) if current_train_dir else None
    chart_rows = []
    if current_train_stage:
        _, chart_rows = build_stage_chain_rows(root_path, current_train_stage)
    recent_rows = chart_rows[-12:]
    latest = chart_rows[-1] if chart_rows else {}

    env_cfg = read_yaml(Path(supervisor.get("current_env_config", ""))) if supervisor.get("current_env_config") else {}
    agent_cfg = read_yaml(Path(supervisor.get("current_agent_config", ""))) if supervisor.get("current_agent_config") else {}
    engine_cfg = read_yaml(Path(supervisor.get("current_engine_config", ""))) if supervisor.get("current_engine_config") else {}
    brain = infer_brain(root_path.name, env_cfg, supervisor.get("brain", ""))

    samples_per_sec = infer_samples_per_sec(latest)
    progress_target = int(supervisor.get("current_target_samples") or config["target_samples"])
    progress_samples = int(supervisor.get("current_progress_samples") or 0)
    progress_pct = (100.0 * progress_samples / progress_target) if progress_target > 0 else 0.0
    eta_sec = ((progress_target - progress_samples) / samples_per_sec) if samples_per_sec > 0 and progress_samples < progress_target else None

    monitor_log = detect_monitor_log(root_path, config["monitor_log"])
    monitor_samples = parse_monitor_samples(monitor_log, limit=config["history_size"])
    gpus = read_gpu_snapshot()
    gpu_realtime = append_live_gpu_sample(supervisor.get("generated_at", ""), gpus, limit=config["history_size"])
    render = render_summary(root_path, config["render_root"])
    if not render.get("files") and supervisor.get("render"):
        render = supervisor.get("render")
    best_scalar = supervisor.get("best_scalar_checkpoint") or {}
    throughput_floor = float(supervisor.get("throughput_healthy_floor") or 0)
    health = compute_health(latest, samples_per_sec, throughput_floor, render.get("status", "pending"), best_scalar)
    autofinish = collect_autofinish(root_path)

    task_metric_value = latest.get("Test_Return")
    task_metric_label = "Test Return"
    if task_metric_value is None:
        task_metric_value = latest.get("Train_Return")
        task_metric_label = "Train Return"

    links = []
    for label, path in [
        ("infer_viz_index.tsv", render.get("infer_viz_index", "")),
        ("render_all_roots.tsv", render.get("render_all_roots", "")),
    ]:
        if path:
            links.append({"label": label, "href": artifact_href(path)})
    for path in render.get("render_meta_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("mp4_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("mesh_manifest_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("visual_result_manifest_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("comparison_sheet_files", [])[:8]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("metric_report_files", [])[:8]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("visual_review_files", [])[:4]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("full_chain_manifest_files", [])[:4]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("evih_result_files", [])[:12]:
        links.append({"label": f"evih/{Path(path).name}", "href": artifact_href(path)})
    autofinish_links = []
    if autofinish.get("summary_file"):
        autofinish_links.append({"label": "post_train_summary.md", "href": artifact_href(autofinish["summary_file"])})
    if autofinish.get("watch_log"):
        autofinish_links.append({"label": "completion_watch.log", "href": artifact_href(autofinish["watch_log"])})
    for item in autofinish.get("stage_logs", [])[:6]:
        autofinish_links.append(item)

    return {
        "server_time": supervisor.get("generated_at", ""),
        "root_name": root_path.name,
        "root_path": str(root_path),
        "available_roots": list_amp_roots(),
        "run": {
            "brain": brain,
            "case_key": supervisor.get("case_key", ""),
            "case_short": supervisor.get("case_short", brain),
            "stage": current_stage or "-",
            "stage_status": supervisor.get("current_stage_status", ""),
            "progress_label": supervisor.get("current_target_label", ""),
            "progress_samples": progress_samples,
            "progress_target_samples": progress_target,
            "progress_pct": progress_pct,
            "eta_sec": eta_sec,
            "completed": current_stage == "complete",
            "current_train_stage": current_train_stage,
            "current_train_dir": current_train_dir,
            "overall_long_samples": int(supervisor.get("overall_long_samples") or 0),
            "long_target_samples": int(supervisor.get("long_target_samples") or config["target_samples"]),
            "queue_mode": supervisor.get("queue_mode", "single-brain mode"),
        },
        "metrics": {
            "task_metric_label": task_metric_label,
            "task_metric_value": task_metric_value,
            "disc_reward_mean": latest.get("Disc_Reward_Mean"),
            "disc_agent_acc": latest.get("Disc_Agent_Acc"),
            "disc_demo_acc": latest.get("Disc_Demo_Acc"),
            "policy_loss": latest.get("Policy_Loss", latest.get("Actor_Loss")),
            "value_loss": latest.get("Value_Loss", latest.get("Critic_Loss")),
            "entropy": latest.get("Entropy", latest.get("Action_Entropy")),
            "clip_frac": latest.get("Clip_Frac"),
            "samples_per_sec": samples_per_sec,
        },
        "health": health,
        "best_scalar": best_scalar,
        "flags": {"warming_up": not bool(latest)},
        "gpus": gpus,
        "gpu_realtime": gpu_realtime,
        "monitor_samples": monitor_samples,
        "chart_rows": chart_rows[-120:],
        "recent_rows": recent_rows,
        "events": supervisor.get("events", [])[-80:],
        "runner_log": supervisor.get("runner_log", ""),
        "monitor_log": str(monitor_log) if monitor_log else "",
        "queue_log": config["queue_log"],
        "render": render,
        "autofinish": autofinish,
        "autofinish_links": autofinish_links,
        "config": {
            "env_name": env_cfg.get("env_name", ""),
            "motion_file": env_cfg.get("motion_file", ""),
            "char_file": env_cfg.get("char_file", ""),
            "task_reward_weight": agent_cfg.get("task_reward_weight"),
            "disc_reward_weight": agent_cfg.get("disc_reward_weight"),
            "agent_name": agent_cfg.get("agent_name", ""),
            "engine_name": engine_cfg.get("engine_name", engine_cfg.get("backend", "")),
            "devices": " ".join(supervisor.get("devices", []) if isinstance(supervisor.get("devices"), list) else config.get("devices", [])),
            "num_envs": supervisor.get("num_envs"),
        },
        "links": links,
        "links_log": artifact_href(str(current_dir / "log.txt")) if current_dir and (current_dir / "log.txt").exists() else "",
        "links_configs": [
            f'<a href="{artifact_href(str(Path(path)))}" target="_blank">{Path(path).name}</a>'
            for path in [supervisor.get("current_env_config", ""), supervisor.get("current_agent_config", ""), supervisor.get("current_engine_config", "")]
            if path
        ],
    }


def collect_plain_root_status(root_path: Path, config):
    rows = parse_training_rows(root_path / "log.txt")
    latest = rows[-1] if rows else {}
    env_cfg = read_yaml(root_path / "env_config.yaml")
    agent_cfg = read_yaml(root_path / "agent_config.yaml")
    engine_cfg = read_yaml(root_path / "engine_config.yaml")
    brain = infer_brain(root_path.name, env_cfg, config["brain"])
    samples_per_sec = infer_samples_per_sec(latest)
    progress_target = int(config["target_samples"])
    progress_samples = int(latest.get("Samples", 0) or 0)
    progress_pct = (100.0 * progress_samples / progress_target) if progress_target > 0 else 0.0
    eta_sec = ((progress_target - progress_samples) / samples_per_sec) if samples_per_sec > 0 and progress_samples < progress_target else None
    render = render_summary(root_path, config["render_root"])
    best_scalar = {}
    if (root_path / "model.pt").exists():
        best_scalar = {
            "status_label": "direct root",
            "model_file": str(root_path / "model.pt"),
            "out_dir": str(root_path),
            "samples": progress_samples,
            "eligible": False,
        }
    monitor_log = detect_monitor_log(root_path, config["monitor_log"])
    monitor_samples = parse_monitor_samples(monitor_log, limit=config["history_size"])
    gpus = read_gpu_snapshot()
    gpu_realtime = append_live_gpu_sample("", gpus, limit=config["history_size"])
    throughput_floor = 4550.0 if brain in {"TurnBrain", "StopBrain"} else 4800.0 if brain == "WalkBrain" else 4500.0
    health = compute_health(latest, samples_per_sec, throughput_floor, render.get("status", "pending"), best_scalar)
    autofinish = collect_autofinish(root_path)

    task_metric_value = latest.get("Test_Return")
    task_metric_label = "Test Return"
    if task_metric_value is None:
        task_metric_value = latest.get("Train_Return")
        task_metric_label = "Train Return"

    links = []
    for path in render.get("render_meta_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("mp4_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("mesh_manifest_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("visual_result_manifest_files", [])[:6]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("comparison_sheet_files", [])[:8]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("metric_report_files", [])[:8]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("visual_review_files", [])[:4]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("full_chain_manifest_files", [])[:4]:
        links.append({"label": Path(path).name, "href": artifact_href(path)})
    for path in render.get("evih_result_files", [])[:12]:
        links.append({"label": f"evih/{Path(path).name}", "href": artifact_href(path)})
    autofinish_links = []
    if autofinish.get("summary_file"):
        autofinish_links.append({"label": "post_train_summary.md", "href": artifact_href(autofinish["summary_file"])})
    if autofinish.get("watch_log"):
        autofinish_links.append({"label": "completion_watch.log", "href": artifact_href(autofinish["watch_log"])})
    for item in autofinish.get("stage_logs", [])[:6]:
        autofinish_links.append(item)

    return {
        "server_time": "",
        "root_name": root_path.name,
        "root_path": str(root_path),
        "available_roots": list_amp_roots(),
        "run": {
            "brain": brain,
            "case_key": root_path.name,
            "case_short": root_path.name,
            "stage": "direct_root",
            "stage_status": "standalone",
            "progress_label": "target_samples",
            "progress_samples": progress_samples,
            "progress_target_samples": progress_target,
            "progress_pct": progress_pct,
            "eta_sec": eta_sec,
            "completed": False,
            "current_train_stage": "direct_root",
            "current_train_dir": str(root_path),
            "overall_long_samples": progress_samples,
            "long_target_samples": progress_target,
            "queue_mode": "single-brain mode",
        },
        "metrics": {
            "task_metric_label": task_metric_label,
            "task_metric_value": task_metric_value,
            "disc_reward_mean": latest.get("Disc_Reward_Mean"),
            "disc_agent_acc": latest.get("Disc_Agent_Acc"),
            "disc_demo_acc": latest.get("Disc_Demo_Acc"),
            "policy_loss": latest.get("Policy_Loss", latest.get("Actor_Loss")),
            "value_loss": latest.get("Value_Loss", latest.get("Critic_Loss")),
            "entropy": latest.get("Entropy", latest.get("Action_Entropy")),
            "clip_frac": latest.get("Clip_Frac"),
            "samples_per_sec": samples_per_sec,
        },
        "health": health,
        "best_scalar": best_scalar,
        "flags": {"warming_up": not bool(latest)},
        "gpus": gpus,
        "gpu_realtime": gpu_realtime,
        "monitor_samples": monitor_samples,
        "chart_rows": rows[-120:],
        "recent_rows": rows[-12:],
        "events": [],
        "runner_log": "",
        "monitor_log": str(monitor_log) if monitor_log else "",
        "queue_log": config["queue_log"],
        "render": render,
        "autofinish": autofinish,
        "autofinish_links": autofinish_links,
        "config": {
            "env_name": env_cfg.get("env_name", ""),
            "motion_file": env_cfg.get("motion_file", ""),
            "char_file": env_cfg.get("char_file", ""),
            "task_reward_weight": agent_cfg.get("task_reward_weight"),
            "disc_reward_weight": agent_cfg.get("disc_reward_weight"),
            "agent_name": agent_cfg.get("agent_name", ""),
            "engine_name": engine_cfg.get("engine_name", engine_cfg.get("backend", "")),
            "devices": "",
            "num_envs": "",
        },
        "links": links,
        "links_log": artifact_href(str(root_path / "log.txt")) if (root_path / "log.txt").exists() else "",
        "links_configs": [
            f'<a href="{artifact_href(str(path))}" target="_blank">{path.name}</a>'
            for path in [root_path / "env_config.yaml", root_path / "agent_config.yaml", root_path / "engine_config.yaml"]
            if path.exists()
        ],
    }


def collect_status(config, root_override=""):
    root_path = resolve_root(root_override or config["root_out"])
    if root_path is None:
        return {
            "error": "no amp roots found",
            "available_roots": list_amp_roots(),
            "root_name": "",
            "server_time": "",
        }
    if (root_path / "keepalive_status.json").exists():
        return collect_keepalive_status(root_path, config)
    return collect_plain_root_status(root_path, config)


def make_handler(config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send_json(self, payload, code=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, text, code=200):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_text(self, text, code=200):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(HTML_PAGE)
                return
            if parsed.path == "/api/status":
                q = parse_qs(parsed.query)
                root_override = (q.get("root", [""])[0] or "").strip()
                self._send_json(collect_status(config, root_override=root_override))
                return
            if parsed.path == "/api/roots":
                self._send_json({"roots": list_amp_roots()})
                return
            if parsed.path == "/artifact":
                q = parse_qs(parsed.query)
                target = (q.get("path", [""])[0] or "").strip()
                if not target:
                    self._send_text("missing path", code=400)
                    return
                serve_artifact(self, target)
                return
            self._send_json({"error": "not found"}, code=404)

    return Handler


def main():
    args = parse_args()
    config = {
        "root_out": args.root_out.strip(),
        "monitor_log": args.monitor_log.strip(),
        "queue_log": args.queue_log.strip(),
        "target_samples": int(args.target_samples),
        "brain": args.brain.strip(),
        "series_cases": args.series_cases.strip(),
        "render_root": args.render_root.strip(),
        "history_size": max(60, int(args.history_size)),
    }
    handler = make_handler(config)

    class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True

    with ThreadingTCPServer((args.host, args.port), handler) as httpd:
        base = f"http://{args.host}:{args.port}/"
        print(f"[amp-dashboard] listen={base}")
        print(f"[amp-dashboard] root_out={config['root_out'] or '(auto)'}")
        if config["monitor_log"]:
            print(f"[amp-dashboard] monitor_log={config['monitor_log']}")
        if config["queue_log"]:
            print(f"[amp-dashboard] queue_log={config['queue_log']}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("[amp-dashboard] shutdown")


if __name__ == "__main__":
    main()
