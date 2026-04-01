#!/usr/bin/env python3
import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import socketserver
import subprocess
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import yaml
except Exception:
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "output" / "train"
OFFICIAL_LLC_TARGET_SAMPLES = 13_107_200_000
OFFICIAL_HLC_TARGET_SAMPLES = 1_310_720_000
CASE_META = {
    "ase_humanoid": {
        "args": "ase_humanoid_args.txt",
        "short": "ASE Humanoid",
        "out_name": "ase_humanoid_l2",
        "family": "llc",
    },
    "ase_humanoid_sword_shield": {
        "args": "ase_humanoid_sword_shield_args.txt",
        "short": "ASE SwordShield",
        "out_name": "ase_humanoid_sword_shield_l2",
        "family": "llc",
    },
    "ase_getup_humanoid_sword_shield": {
        "args": "ase_getup_humanoid_sword_shield_args.txt",
        "short": "ASE Getup",
        "out_name": "ase_getup_humanoid_sword_shield_l2",
        "family": "llc",
    },
    "ase_heading_humanoid_sword_shield": {
        "args": "ase_heading_humanoid_sword_shield_args.txt",
        "short": "ASE Heading",
        "out_name": "ase_heading_humanoid_sword_shield_l2",
        "family": "hlc",
    },
    "ase_location_humanoid_sword_shield": {
        "args": "ase_location_humanoid_sword_shield_args.txt",
        "short": "ASE Location",
        "out_name": "ase_location_humanoid_sword_shield_l2",
        "family": "hlc",
    },
    "ase_reach_humanoid_sword_shield": {
        "args": "ase_reach_humanoid_sword_shield_args.txt",
        "short": "ASE Reach",
        "out_name": "ase_reach_humanoid_sword_shield_l2",
        "family": "hlc",
    },
    "ase_strike_humanoid_sword_shield": {
        "args": "ase_strike_humanoid_sword_shield_args.txt",
        "short": "ASE Strike",
        "out_name": "ase_strike_humanoid_sword_shield_l2",
        "family": "hlc",
    },
    "ase_perturb_humanoid_sword_shield": {
        "args": "ase_perturb_humanoid_sword_shield_args.txt",
        "short": "ASE Perturb",
        "out_name": "",
        "family": "tooling",
    },
    "view_motion_humanoid_sword_shield": {
        "args": "view_motion_humanoid_sword_shield_args.txt",
        "short": "View Motion",
        "out_name": "",
        "family": "tooling",
    },
}
CASE_ARGS_TO_KEY = {meta["args"]: key for key, meta in CASE_META.items()}


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>ASE 专用训练看板</title>
  <style>
    :root{
      --bg:#0f1418;
      --bg-2:#131d22;
      --card:#18232ad9;
      --card-2:#1d2a31;
      --line:#2d434d;
      --ink:#e8f0ed;
      --muted:#9cb4ae;
      --ok:#3fbf7f;
      --warn:#f0a93e;
      --bad:#ef6a5b;
      --accent:#7fd1b9;
      --accent-2:#f59e0b;
      --accent-3:#5dc0ff;
      --accent-4:#d97706;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      color:var(--ink);
      font-family:"IBM Plex Sans","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
      background:
        radial-gradient(circle at top left, #1a2d28 0, transparent 32%),
        radial-gradient(circle at bottom right, #2a2418 0, transparent 28%),
        linear-gradient(135deg,var(--bg),var(--bg-2));
      min-height:100vh;
    }
    .wrap{
      max-width:1400px;
      margin:0 auto;
      padding:18px 18px 28px;
    }
    .head{
      display:flex;
      flex-wrap:wrap;
      align-items:flex-start;
      justify-content:space-between;
      gap:14px;
      margin-bottom:16px;
    }
    h1{
      margin:0;
      font-size:26px;
      letter-spacing:.2px;
    }
    .sub{
      color:var(--muted);
      font-size:13px;
      margin-top:4px;
    }
    .toolbar{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      align-items:center;
    }
    input,button{
      border:1px solid var(--line);
      background:#0f171c;
      color:var(--ink);
      padding:9px 10px;
      border-radius:10px;
      font-size:13px;
    }
    input{
      min-width:360px;
    }
    button{
      cursor:pointer;
      background:linear-gradient(90deg,#1f5d55,#2b7d6f);
      border:none;
      font-weight:700;
    }
    .grid{
      display:grid;
      grid-template-columns:repeat(12,minmax(0,1fr));
      gap:12px;
    }
    .card{
      background:var(--card);
      border:1px solid #27404a;
      border-radius:16px;
      padding:12px;
      box-shadow:0 8px 28px rgba(0,0,0,.18);
      backdrop-filter:blur(3px);
    }
    .kpi{grid-column:span 3}
    .wide{grid-column:span 6}
    .full{grid-column:1 / -1}
    .k{
      color:var(--muted);
      font-size:12px;
      margin-bottom:6px;
      text-transform:uppercase;
      letter-spacing:.4px;
    }
    .v{
      font-size:26px;
      font-weight:700;
      line-height:1.1;
    }
    .small{
      font-size:12px;
      color:var(--muted);
      margin-top:6px;
    }
    .ok{color:var(--ok)}
    .warn{color:var(--warn)}
    .bad{color:var(--bad)}
    .meter{
      height:14px;
      border-radius:999px;
      overflow:hidden;
      background:#0c1317;
      border:1px solid #35525c;
      margin-top:10px;
    }
    .fill{
      height:100%;
      transition:width .25s linear;
      background:linear-gradient(90deg,#227062,var(--accent));
    }
    .gpu-row{
      display:grid;
      grid-template-columns:72px 1fr 122px;
      gap:10px;
      align-items:center;
      margin:8px 0;
    }
    .bar{
      height:12px;
      border-radius:999px;
      overflow:hidden;
      background:#0c1317;
      border:1px solid #35525c;
    }
    .bar-fill{
      height:100%;
      transition:width .25s linear;
    }
    .g0{background:linear-gradient(90deg,#5dc0ff,var(--accent-3))}
    .g1{background:linear-gradient(90deg,#e38a1b,var(--accent-4))}
    .pill{
      display:inline-block;
      padding:4px 8px;
      border-radius:999px;
      font-size:12px;
      border:1px solid var(--line);
      background:#0f171c;
      margin:4px 6px 0 0;
    }
    .chart-wrap{
      height:240px;
      border:1px solid #27404a;
      border-radius:12px;
      background:#0d1418;
      padding:8px;
    }
    canvas{
      width:100%;
      height:100%;
      display:block;
    }
    .kv{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:8px 12px;
    }
    .kv-row{
      padding:8px 10px;
      border-radius:10px;
      background:var(--card-2);
      border:1px solid #243740;
    }
    .kv-row .kk{
      color:var(--muted);
      font-size:11px;
      margin-bottom:4px;
      text-transform:uppercase;
    }
    .kv-row .vv{
      font-size:13px;
      line-height:1.35;
      word-break:break-word;
    }
    table{
      width:100%;
      border-collapse:collapse;
      font-size:12px;
    }
    th,td{
      padding:6px 5px;
      text-align:left;
      border-bottom:1px solid #29404a;
      vertical-align:top;
    }
    th{
      color:#c5d9d4;
      background:#122026;
      position:sticky;
      top:0;
    }
    .table-wrap{
      max-height:320px;
      overflow:auto;
      border:1px solid #27404a;
      border-radius:12px;
      background:#0d1418;
    }
    .mono{
      white-space:pre-wrap;
      font-family:"IBM Plex Mono","Menlo","Consolas",monospace;
      font-size:12px;
      line-height:1.45;
      background:#0d1418;
      border:1px solid #27404a;
      border-radius:12px;
      padding:10px;
      min-height:180px;
      max-height:360px;
      overflow:auto;
    }
    .foot{
      margin-top:12px;
      color:var(--muted);
      font-size:12px;
    }
    @media (max-width:1100px){
      .kpi,.wide{grid-column:span 6}
      .kv{grid-template-columns:1fr}
      input{min-width:280px}
    }
    @media (max-width:760px){
      .kpi,.wide{grid-column:span 12}
      .gpu-row{grid-template-columns:58px 1fr 96px}
      input{min-width:100%}
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="head">
      <div>
        <h1>ASE 专用训练看板</h1>
        <div class="sub" id="subtitle">加载中...</div>
      </div>
      <div class="toolbar">
        <input id="rootInput" list="rootList" placeholder="ASE root-out（可空）" />
        <datalist id="rootList"></datalist>
        <button id="applyBtn">切换 Root</button>
        <button id="refreshBtn">立即刷新</button>
      </div>
    </div>

    <div class="grid">
      <div class="card kpi">
        <div class="k">当前 Run</div>
        <div class="v" id="runV">-</div>
        <div class="small" id="runSub">-</div>
      </div>
      <div class="card kpi">
        <div class="k">当前进度</div>
        <div class="v" id="progressV">-</div>
        <div class="small" id="progressSub">-</div>
        <div class="meter"><div class="fill" id="progressFill" style="width:0%"></div></div>
        <div class="small" id="progressHealth">-</div>
      </div>
      <div class="card kpi">
        <div class="k">当前 ETA</div>
        <div class="v" id="etaV">-</div>
        <div class="small" id="etaSub">-</div>
      </div>
      <div class="card kpi">
        <div class="k">ASE 健康</div>
        <div class="v" id="healthV">-</div>
        <div class="small" id="healthSub">-</div>
      </div>

      <div class="card wide">
        <div class="k">ASE 专用指标</div>
        <div class="kv" id="aseKv"></div>
      </div>
      <div class="card wide">
        <div class="k">SOP / Queue 状态</div>
        <div class="kv" id="queueKv"></div>
      </div>

      <div class="card wide">
        <div class="k">双卡实时利用率</div>
        <div id="gpuPanel"></div>
      </div>
      <div class="card wide">
        <div class="k">配置快照</div>
        <div class="kv" id="configKv"></div>
      </div>

      <div class="card wide">
        <div class="k">GPU 利用率时间线</div>
        <div class="chart-wrap"><canvas id="gpuChart" width="700" height="220"></canvas></div>
      </div>
      <div class="card wide">
        <div class="k">ASE 指标时间线</div>
        <div class="chart-wrap"><canvas id="aseChart" width="700" height="220"></canvas></div>
      </div>

      <div class="card full">
        <div class="k">最近训练快照</div>
        <div class="table-wrap"><table id="recentTable"></table></div>
      </div>

      <div class="card full">
        <div class="k">最近事件</div>
        <div class="mono" id="eventsBox">-</div>
      </div>
    </div>

    <div class="foot" id="foot">-</div>
  </div>

  <script>
    const refreshMs = 5000;
    const rootInput = document.getElementById("rootInput");
    const rootList = document.getElementById("rootList");
    const subtitle = document.getElementById("subtitle");
    const foot = document.getElementById("foot");
    let activeRoot = "";
    let gpuRealtime = [];

    function q(id){ return document.getElementById(id); }

    function clsByLevel(level){
      if (level === "good") return "ok";
      if (level === "warning") return "warn";
      return "bad";
    }

    function parseRootFromUrl(){
      const u = new URL(window.location.href);
      return u.searchParams.get("root") || "";
    }

    function applyRootToUrl(root){
      const u = new URL(window.location.href);
      if (root) u.searchParams.set("root", root);
      else u.searchParams.delete("root");
      history.replaceState({}, "", u.toString());
    }

    function fmtNum(v, digits=2){
      if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
      return Number(v).toFixed(digits);
    }

    function fmtInt(v){
      if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
      return Number(v).toLocaleString();
    }

    function fmtPct(v, digits=1){
      if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
      return `${Number(v).toFixed(digits)}%`;
    }

    function clampPct(v){
      if (v === null || v === undefined || Number.isNaN(Number(v))) return null;
      return Math.max(0, Math.min(100, Number(v)));
    }

    function fmtDuration(sec){
      if (sec === null || sec === undefined || !Number.isFinite(Number(sec)) || sec < 0) return "-";
      sec = Math.round(Number(sec));
      const d = Math.floor(sec / 86400);
      sec -= d * 86400;
      const h = Math.floor(sec / 3600);
      sec -= h * 3600;
      const m = Math.floor(sec / 60);
      if (d > 0) return `${d}d ${h}h`;
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }

    async function fetchStatus(){
      const root = parseRootFromUrl();
      const url = root ? `/api/status?root=${encodeURIComponent(root)}` : "/api/status";
      const r = await fetch(url, {cache:"no-store"});
      if (!r.ok){
        throw new Error(`HTTP ${r.status}`);
      }
      return await r.json();
    }

    function setKv(el, rows){
      const node = q(el);
      node.innerHTML = "";
      (rows || []).forEach((r) => {
        const div = document.createElement("div");
        div.className = "kv-row";
        div.innerHTML = `<div class="kk">${r.k}</div><div class="vv">${r.v}</div>`;
        node.appendChild(div);
      });
    }

    function setRootOptions(roots){
      rootList.innerHTML = "";
      (roots || []).forEach((r) => {
        const opt = document.createElement("option");
        opt.value = r;
        rootList.appendChild(opt);
      });
    }

    function renderGpuPanel(gpus){
      const panel = q("gpuPanel");
      if (!gpus || !gpus.length){
        panel.innerHTML = "<div class='small'>GPU 不可用</div>";
        return;
      }
      panel.innerHTML = "";
      gpus.forEach((g, idx) => {
        const row = document.createElement("div");
        row.className = "gpu-row";
        const pct = Math.max(0, Math.min(100, Number(g.util || 0)));
        row.innerHTML = `
          <div><b>GPU${g.index}</b></div>
          <div class="bar"><div class="bar-fill ${idx===0 ? "g0" : "g1"}" style="width:${pct}%"></div></div>
          <div>${pct}% | ${g.mem_used} MiB</div>
        `;
        panel.appendChild(row);
      });
    }

    function appendRealtimeGpu(status){
      const g = status.gpus || [];
      if (g.length >= 2){
        gpuRealtime.push({
          t: status.server_time || "",
          u0: Number(g[0].util || 0),
          u1: Number(g[1].util || 0),
        });
      }
      gpuRealtime = gpuRealtime.slice(-240);
    }

    function drawChart(canvasId, points, series, opts={}){
      const canvas = q(canvasId);
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#0d1418";
      ctx.fillRect(0, 0, w, h);

      const usable = (points || []).slice(-Math.max(2, opts.limit || 120));
      if (usable.length < 2){
        ctx.fillStyle = "#9cb4ae";
        ctx.font = "12px IBM Plex Sans";
        ctx.fillText("数据不足", 20, 24);
        return;
      }

      let minV = opts.minY;
      let maxV = opts.maxY;
      if (minV === undefined || maxV === undefined){
        let vals = [];
        usable.forEach((p) => {
          series.forEach((s) => {
            const v = Number(p[s.key]);
            if (Number.isFinite(v)) vals.push(v);
          });
        });
        minV = vals.length ? Math.min(...vals) : 0;
        maxV = vals.length ? Math.max(...vals) : 1;
        if (Math.abs(maxV - minV) < 1e-6){
          maxV = minV + 1;
        } else {
          const pad = (maxV - minV) * 0.12;
          minV -= pad;
          maxV += pad;
        }
      }

      const left = 36;
      const right = w - 10;
      const top = 12;
      const bottom = h - 24;
      const plotW = right - left;
      const plotH = bottom - top;

      ctx.strokeStyle = "#21333b";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++){
        const y = top + (plotH * i / 4);
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();

        const v = maxV - ((maxV - minV) * i / 4);
        ctx.fillStyle = "#89a39d";
        ctx.font = "11px IBM Plex Mono, monospace";
        ctx.fillText(v.toFixed(2), 2, y + 3);
      }

      const mapX = (i) => left + (i / (usable.length - 1)) * plotW;
      const mapY = (v) => bottom - ((v - minV) / (maxV - minV)) * plotH;

      series.forEach((s) => {
        ctx.beginPath();
        usable.forEach((p, i) => {
          const val = Number(p[s.key]);
          if (!Number.isFinite(val)) return;
          const x = mapX(i);
          const y = mapY(val);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      let lx = left;
      series.forEach((s) => {
        ctx.fillStyle = s.color;
        ctx.fillRect(lx, h - 14, 10, 3);
        ctx.fillStyle = "#dbe7e3";
        ctx.font = "12px IBM Plex Sans";
        ctx.fillText(s.label, lx + 14, h - 8);
        lx += 120;
      });
    }

    function renderRecent(rows){
      const table = q("recentTable");
      if (!rows || !rows.length){
        table.innerHTML = "<tr><td>暂无训练行</td></tr>";
        return;
      }
      const cols = [
        "Iteration","Samples","Samples_Per_Sec","Disc_Reward_Mean",
        "Enc_Reward_Mean","Diversity_Loss","Clip_Frac","Disc_Agent_Acc","Disc_Demo_Acc"
      ];
      let html = "<thead><tr>";
      cols.forEach((c) => html += `<th>${c}</th>`);
      html += "</tr></thead><tbody>";
      rows.slice().reverse().forEach((r) => {
        html += "<tr>";
        cols.forEach((c) => {
          const v = r[c];
          html += `<td>${v ?? "-"}</td>`;
        });
        html += "</tr>";
      });
      html += "</tbody>";
      table.innerHTML = html;
    }

    function render(status){
      const run = status.run || {};
      activeRoot = status.root_name || "";
      setRootOptions(status.available_roots || []);
      rootInput.value = parseRootFromUrl() || activeRoot;
      subtitle.textContent = `Root: ${activeRoot || "-"} | 最近刷新: ${status.server_time || "-"} | 当前 Case: ${run.case_name || "-"}`;

      q("runV").textContent = run.case_short || "-";
      q("runSub").textContent = `iter=${fmtInt(run.iteration)} | num_envs=${fmtInt(run.num_envs)} | backend=${status.config?.engine_name || "-"}`;

      const progressPct = clampPct(run.display_target_pct ?? run.target_pct);
      const overflowSamples = Number(run.overflow_samples || 0);
      const progressBaseSamples = run.display_progress_base_samples ?? run.target_samples;
      let progressSub = `${fmtInt(run.samples)} / ${fmtInt(progressBaseSamples)} samples`;
      if (progressBaseSamples !== run.target_samples && Number(run.target_samples || 0) > 0){
        progressSub += ` | ${run.target_label || "预算线"} ${fmtInt(run.target_samples)}`;
      } else if (Number(run.target_samples || 0) > 0) {
        progressSub += ` | ${run.target_label || "当前预算"}`;
      }
      if (run.completed){
        progressSub += overflowSamples > 0 ? ` | 已超目标 ${fmtInt(overflowSamples)}` : " | 已达目标";
      }
      q("progressV").textContent = fmtPct(progressPct, 1);
      q("progressSub").textContent = progressSub;
      q("progressFill").style.width = `${progressPct ?? 0}%`;
      const progressHealth = status.health?.progress || {};
      const progressHealthLevel = clsByLevel(progressHealth.level || "warning");
      q("progressHealth").innerHTML = `<span class="pill ${progressHealthLevel}">${progressHealth.label || "-"}</span> ${progressHealth.detail || "-"}`;

      const etaSpeed = `速度 ${fmtNum(run.samples_per_sec, 1)} samples/s | 约 ${fmtNum(run.samples_per_hour_m, 2)}M/h`;
      q("etaV").textContent = run.completed ? "已完成" : fmtDuration(run.eta_current_sec);
      q("etaSub").textContent = run.completed ? `${etaSpeed} | 当前目标已达成` : etaSpeed;

      const hv = q("healthV");
      hv.className = `v ${clsByLevel(status.health?.overall?.level || "warning")}`;
      hv.textContent = status.health?.overall?.label || "-";
      q("healthSub").textContent = status.health?.overall?.detail || "-";

      setKv("aseKv", [
        {k:"Disc Reward Mean", v: fmtNum(status.metrics?.disc_reward_mean, 3)},
        {k:"Enc Reward Mean", v: fmtNum(status.metrics?.enc_reward_mean, 3)},
        {k:"Diversity Loss", v: fmtNum(status.metrics?.diversity_loss, 3)},
        {k:"Clip Frac", v: fmtNum(status.metrics?.clip_frac, 3)},
        {k:"Disc Agent / Demo Acc", v: `${fmtNum(status.metrics?.disc_agent_acc, 3)} / ${fmtNum(status.metrics?.disc_demo_acc, 3)}`},
        {k:"Train Episode Length", v: fmtNum(status.metrics?.train_episode_length, 2)},
        {k:"Style Health", v: `<span class="${clsByLevel(status.health?.style?.level || "warning")}">${status.health?.style?.label || "-"}</span><div class="small">${status.health?.style?.detail || "-"}</div>`},
        {k:"Latent Health", v: `<span class="${clsByLevel(status.health?.latent?.level || "warning")}">${status.health?.latent?.label || "-"}</span><div class="small">${status.health?.latent?.detail || "-"}</div>`},
      ]);

      setKv("queueKv", [
        {k:"SOP Stage", v: status.run?.sop_stage || "-"},
        {k:"Series Cases", v: fmtInt(status.series?.total_cases)},
        {k:"Series Progress", v: `${fmtPct(status.series?.progress_pct, 1)}<div class="small">${status.series?.active_case || "-"} | next=${status.series?.next_case || "-"}</div>`},
        {k:"Series ETA", v: fmtDuration(status.series?.eta_series_sec)},
        {k:"Resume Chain", v: (status.series?.resume_chain || []).join(" -> ") || "-"},
        {k:"Queue State", v: `${status.queue?.state_label || "-"}<div class="small">${status.queue?.detail || "-"}</div>`},
        {k:"Queue Last Update", v: status.queue?.last_update || "-"},
      ]);

      renderGpuPanel(status.gpus || []);
      setKv("configKv", [
        {k:"Motion File", v: status.config?.motion_file || "-"},
        {k:"Latent Dim", v: fmtInt(status.config?.latent_dim)},
        {k:"Disc / Enc Reward Weight", v: `${fmtNum(status.config?.disc_reward_weight, 2)} / ${fmtNum(status.config?.enc_reward_weight, 2)}`},
        {k:"Diversity Weight", v: fmtNum(status.config?.diversity_weight, 4)},
        {k:"Latent Time", v: `${fmtNum(status.config?.latent_time_min, 2)} - ${fmtNum(status.config?.latent_time_max, 2)} s`},
        {k:"Task Reward Weight", v: fmtNum(status.config?.task_reward_weight, 2)},
        {k:"Control / Sim Freq", v: `${fmtInt(status.config?.control_freq)} / ${fmtInt(status.config?.sim_freq)} Hz`},
        {k:"Num Envs / Port", v: `${fmtInt(status.run?.num_envs)} | ${fmtInt(status.run?.master_port)}`},
      ]);

      appendRealtimeGpu(status);
      const gpuMerged = (status.monitor_samples || []).concat(gpuRealtime);
      drawChart("gpuChart", gpuMerged, [
        {key:"u0", label:"GPU0", color:"#5dc0ff"},
        {key:"u1", label:"GPU1", color:"#d97706"},
      ], {minY:0, maxY:100, limit:160});

      drawChart("aseChart", status.metric_history || [], [
        {key:"Disc_Reward_Mean", label:"Disc", color:"#7fd1b9"},
        {key:"Enc_Reward_Mean", label:"Enc", color:"#f59e0b"},
        {key:"Diversity_Loss", label:"Diversity", color:"#5dc0ff"},
      ], {limit:180});

      renderRecent(status.recent_rows || []);
      q("eventsBox").textContent = (status.events || []).join("\\n");
      foot.textContent = `root=${status.root_path || "-"} | runner_log=${status.runner_log || "-"} | monitor_log=${status.monitor_log || "-"} | queue_log=${status.queue_log || "-"} | history_points=${(status.monitor_samples || []).length}`;
    }

    async function tick(){
      try{
        const status = await fetchStatus();
        render(status);
      }catch(err){
        subtitle.textContent = `刷新失败: ${err.message}`;
      }
    }

    q("refreshBtn").addEventListener("click", tick);
    q("applyBtn").addEventListener("click", () => {
      const v = rootInput.value.trim();
      applyRootToUrl(v);
      tick();
    });

    setInterval(tick, refreshMs);
    tick();
  </script>
</body>
</html>
"""


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--root-out", default="", help="ASE run root name or path; empty means auto-detect latest")
    ap.add_argument("--monitor-log", default="", help="optional monitor log path")
    ap.add_argument("--queue-log", default="", help="optional queue controller log path")
    ap.add_argument("--history-size", type=int, default=240, help="max monitor history points")
    ap.add_argument("--target-samples", type=int, default=1_000_000_000, help="fallback target for unknown/tooling cases")
    ap.add_argument("--llc-target-samples", type=int, default=OFFICIAL_LLC_TARGET_SAMPLES)
    ap.add_argument("--hlc-target-samples", type=int, default=OFFICIAL_HLC_TARGET_SAMPLES)
    ap.add_argument(
        "--series-cases",
        default="ase_humanoid_args.txt,ase_humanoid_sword_shield_args.txt,ase_getup_humanoid_sword_shield_args.txt,ase_heading_humanoid_sword_shield_args.txt,ase_location_humanoid_sword_shield_args.txt,ase_reach_humanoid_sword_shield_args.txt,ase_strike_humanoid_sword_shield_args.txt",
        help="comma-separated ASE series order",
    )
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

        for p in candidates:
            if p.exists() and p.is_dir():
                return p.resolve()
        return None

    roots = list(TRAIN_ROOT.glob("ase_*"))
    roots = [x for x in roots if x.is_dir()]
    if not roots:
        return None
    return sorted(roots, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def list_ase_roots(limit=30):
    roots = list(TRAIN_ROOT.glob("ase_*"))
    roots = [x for x in roots if x.is_dir()]
    roots = sorted(roots, key=lambda p: p.stat().st_mtime, reverse=True)
    return [x.name for x in roots[:limit]]


def read_text(path: Path):
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def read_yaml(path: Path):
    if yaml is None or not path.exists():
        return {}
    try:
        with path.open("r") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def tail_lines(path: Path, n=20):
    text = read_text(path)
    if not text:
        return []
    return text.splitlines()[-n:]


def read_gpu_snapshot():
    base_args = [
        "--query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw",
        "--format=csv,noheader,nounits",
    ]
    candidates = []
    override = os.environ.get("MIMICKIT_NVIDIA_SMI")
    if override:
        candidates.append(override)
    candidates.extend(
        [
            "nvidia-smi",
            "/mnt/c/Windows/System32/nvidia-smi.exe",
            "/mnt/c/WINDOWS/System32/nvidia-smi.exe",
        ]
    )

    out = ""
    for exe in candidates:
        try:
            out = subprocess.check_output([exe, *base_args], text=True).strip()
            if out:
                break
        except Exception:
            continue
    if not out:
        return []

    rows = []
    for line in out.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 5:
            continue
        rows.append(
            {
                "index": int(float(parts[0])),
                "util": int(float(parts[1])),
                "mem_used": int(float(parts[2])),
                "mem_total": int(float(parts[3])),
                "power": float(parts[4]),
            }
        )
    return rows


def detect_monitor_log(root_path: Path, explicit: str):
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        return p if p.exists() else None

    if root_path is not None:
        name = root_path.name
        ts_match = re.search(r"(20\d{6}_\d{6})", name)
        if ts_match:
            ts = ts_match.group(1)
            hits = sorted(glob.glob(f"/tmp/*{ts}*.log"), key=os.path.getmtime, reverse=True)
            if hits:
                return Path(hits[0])

    hits = sorted(glob.glob("/tmp/mk_dualgpu_follow_until_high_*.log"), key=os.path.getmtime, reverse=True)
    if hits:
        return Path(hits[0])
    return None


def detect_queue_log(root_path: Path, explicit: str):
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        return p if p.exists() else None

    if root_path is not None:
        if (root_path / "keepalive_status.json").exists() or (root_path / "current_case.txt").exists():
            return None

    hits = sorted((TRAIN_ROOT.glob("ase_series_queue_controller_*.log")), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def parse_monitor_samples(path: Path, limit: int):
    text = read_text(path)
    if not text:
        return []
    samples = []
    rx = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| .*?GPU0=(?P<u0>\d+)%.*?GPU1=(?P<u1>\d+)%",
        re.M,
    )
    for m in rx.finditer(text):
        samples.append({"t": m.group("ts"), "u0": int(m.group("u0")), "u1": int(m.group("u1"))})
    return samples[-limit:]


def parse_launch_info(path: Path):
    text = read_text(path)
    info = {"num_envs": None, "master_port": None}
    if not text:
        return info

    m = re.search(r"Using master port:\s*(\d+)", text)
    if m:
        info["master_port"] = int(m.group(1))
    m = re.search(r"Building\s+(\d+)/(\d+)\s+envs", text)
    if m:
        info["num_envs"] = int(m.group(1))
    return info


def split_columns(line: str):
    return re.split(r"\s{2,}", line.strip())


def to_number(text: str):
    try:
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text)
        return float(text)
    except Exception:
        return text


def parse_training_rows(log_path: Path):
    raw = read_text(log_path)
    if not raw:
        return []

    lines = [x.strip() for x in raw.replace("\r", "\n").split("\n") if x.strip()]
    header = None
    rows = []
    for line in lines:
        if header is None and "Iteration" in line and "Samples" in line:
            header = split_columns(line)
            continue
        if header is None:
            continue
        parts = split_columns(line)
        if len(parts) != len(header):
            continue
        if not re.fullmatch(r"\d+", parts[0]):
            continue
        rows.append({k: to_number(v) for k, v in zip(header, parts)})

    dedup = {}
    for row in rows:
        dedup[int(row["Iteration"])] = row
    return [dedup[k] for k in sorted(dedup)]


def enrich_training_rows(rows):
    if not rows:
        return rows
    out = []
    prev = None
    for row in rows:
        new_row = dict(row)
        sps = None
        if prev is not None:
            ds = float(row["Samples"]) - float(prev["Samples"])
            dt_hours = float(row["Wall_Time"]) - float(prev["Wall_Time"])
            if dt_hours > 0:
                sps = ds / (dt_hours * 3600.0)
        new_row["Samples_Per_Sec"] = sps
        out.append(new_row)
        prev = row
    return out


def parse_kv_tsv(path: Path):
    text = read_text(path)
    if not text:
        return {}

    rows = {}
    for idx, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        val = parts[1].strip()
        if idx == 0 and key == "key" and val == "value":
            continue
        if key:
            rows[key] = val
    return rows


def parse_resume_context(root_path: Path):
    return parse_kv_tsv(root_path / "resume_context.tsv")


def to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def find_resume_successor(root_path: Path):
    candidate_ctx_paths = []
    sibling_parent = root_path.resolve().parent
    if sibling_parent.exists():
        candidate_ctx_paths.extend(sorted(sibling_parent.glob("*/resume_context.tsv")))

    train_root_resolved = TRAIN_ROOT.resolve()
    if sibling_parent != train_root_resolved and train_root_resolved.exists():
        candidate_ctx_paths.extend(sorted(TRAIN_ROOT.glob("*/resume_context.tsv")))

    seen_ctx = set()
    hits = []
    root_resolved = root_path.resolve()
    for ctx_path in candidate_ctx_paths:
        ctx_path = ctx_path.resolve()
        if ctx_path in seen_ctx:
            continue
        seen_ctx.add(ctx_path)
        run_dir = ctx_path.parent.resolve()
        if run_dir == root_resolved:
            continue

        ctx = parse_kv_tsv(ctx_path)
        if not ctx:
            continue

        source_run = str(ctx.get("source_run", "")).strip()
        source_model_file = str(ctx.get("source_model_file", "")).strip()
        matched = source_run == root_path.name

        if (not matched) and source_model_file:
            try:
                matched = Path(source_model_file).resolve().parent == root_resolved
            except Exception:
                matched = False

        if matched:
            hits.append(run_dir)

    if not hits:
        return None
    hits = sorted(hits, key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0]


def build_resume_chain(root_path: Path, limit=32):
    chain = [root_path.resolve()]
    seen = {chain[0]}
    curr = chain[0]

    while len(chain) < limit:
        nxt = find_resume_successor(curr)
        if nxt is None:
            break
        nxt = nxt.resolve()
        if nxt in seen:
            break
        seen.add(nxt)
        chain.append(nxt)
        curr = nxt

    return chain


def build_chain_rows(root_path: Path):
    chain = build_resume_chain(root_path)
    all_rows = []
    segments = []

    for seg_root in chain:
        resume_ctx = parse_resume_context(seg_root)
        base_samples = to_int(resume_ctx.get("source_last_samples", ""), 0)
        seg_rows = enrich_training_rows(parse_training_rows(seg_root / "log.txt"))
        latest_seg = seg_rows[-1] if seg_rows else {}
        wall_time_h = latest_seg.get("Wall_Time") if latest_seg else None

        segments.append(
            {
                "root_name": seg_root.name,
                "root_path": str(seg_root),
                "base_samples": base_samples,
                "segment_samples": int(latest_seg.get("Samples", 0) or 0),
                "total_samples": base_samples + int(latest_seg.get("Samples", 0) or 0),
                "wall_time_h": float(wall_time_h) if wall_time_h is not None else None,
                "source_run": str(resume_ctx.get("source_run", "")).strip(),
            }
        )

        for row in seg_rows:
            new_row = dict(row)
            segment_samples = int(row.get("Samples", 0) or 0)
            new_row["Segment_Samples"] = segment_samples
            new_row["Samples"] = base_samples + segment_samples
            all_rows.append(new_row)

    all_rows = sorted(
        all_rows,
        key=lambda r: (
            float(r.get("Samples", 0) or 0),
            float(r.get("Wall_Time", 0) or 0),
            int(r.get("Iteration", 0) or 0),
        ),
    )
    return chain, segments, all_rows


def resolve_supervisor_active_root(root_path: Path):
    current_case_path = root_path / "current_case.txt"
    if not current_case_path.exists():
        return root_path, ""

    current_key = read_text(current_case_path).strip()
    if not current_key or current_key == "COMPLETE":
        return root_path, current_key

    meta = CASE_META.get(current_key)
    if not meta or not meta.get("out_name"):
        return root_path, current_key

    case_root = root_path / meta["out_name"]
    if case_root.exists() and case_root.is_dir():
        return case_root.resolve(), current_key

    resume_hits = sorted(root_path.glob(f"{meta['out_name']}_resume*"))
    if resume_hits:
        return resume_hits[0].resolve(), current_key

    return root_path, current_key


def infer_case_name(root_path: Path, env_cfg: dict, current_case_key: str = ""):
    if current_case_key in CASE_META:
        return CASE_META[current_case_key]["args"]

    motion = str(env_cfg.get("motion_file", "")).lower()
    env_name = str(env_cfg.get("env_name", "")).lower()
    name = (root_path.name if root_path else "").lower()
    probe = " ".join([name, motion, env_name])

    ordered = [
        ("view_motion", "view_motion_humanoid_sword_shield_args.txt"),
        ("perturb", "ase_perturb_humanoid_sword_shield_args.txt"),
        ("getup", "ase_getup_humanoid_sword_shield_args.txt"),
        ("heading", "ase_heading_humanoid_sword_shield_args.txt"),
        ("location", "ase_location_humanoid_sword_shield_args.txt"),
        ("reach", "ase_reach_humanoid_sword_shield_args.txt"),
        ("strike", "ase_strike_humanoid_sword_shield_args.txt"),
    ]
    for token, case_name in ordered:
        if token in probe:
            return case_name
    if "sword_shield" in probe:
        return "ase_humanoid_sword_shield_args.txt"
    return "ase_humanoid_args.txt"


def short_case_name(case_name: str):
    key = CASE_ARGS_TO_KEY.get(case_name, "")
    if key in CASE_META:
        return CASE_META[key]["short"]
    return case_name.replace("_args.txt", "")


def target_samples_for_case(case_name: str, config: dict):
    key = CASE_ARGS_TO_KEY.get(case_name, "")
    family = CASE_META.get(key, {}).get("family", "")
    if family == "llc":
        return int(config["llc_target_samples"])
    if family == "hlc":
        return int(config["hlc_target_samples"])
    return int(config["target_samples"])


def target_label_for_case(case_name: str):
    key = CASE_ARGS_TO_KEY.get(case_name, "")
    family = CASE_META.get(key, {}).get("family", "")
    if family == "llc":
        return "官方 LLC 预算"
    if family == "hlc":
        return "官方 HLC 预算"
    return "当前预算"


def severity_rank(level: str):
    return {"good": 0, "warning": 1, "critical": 2}.get(level, 1)


def make_status(level, label, detail):
    return {"level": level, "label": label, "detail": detail}


def detect_training_runtime(root_path: Path):
    result = {
        "has_keepalive": False,
        "has_runner": False,
        "detail": "",
    }
    try:
        out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True, errors="ignore")
    except Exception:
        return result

    root_markers = {
        str(root_path),
        root_path.name,
    }
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not any(marker and marker in line for marker in root_markers):
            continue
        if "run_ase_7case_keepalive.py" in line:
            result["has_keepalive"] = True
        if "mimickit/run.py" in line:
            result["has_runner"] = True

    if result["has_keepalive"] and result["has_runner"]:
        result["detail"] = "keepalive + run.py 活跃"
    elif result["has_keepalive"]:
        result["detail"] = "仅 keepalive 活跃"
    elif result["has_runner"]:
        result["detail"] = "仅 run.py 活跃"
    else:
        result["detail"] = "未发现训练进程"
    return result


def compute_health(latest: dict, gpus: list, samples_per_sec: float, completed=False):
    if not latest:
        empty = make_status("warning", "等待首个快照", "log.txt 还没有有效训练行")
        return {"overall": empty, "style": empty, "latent": empty, "throughput": empty, "gpu": empty}

    disc = float(latest.get("Disc_Reward_Mean", 0.0))
    enc = float(latest.get("Enc_Reward_Mean", 0.0))
    div = float(latest.get("Diversity_Loss", 0.0))
    clip = float(latest.get("Clip_Frac", 0.0))
    imp = float(latest.get("Imp_Ratio", 1.0))

    if disc >= 0.25:
        style = make_status("good", "风格奖励健康", f"Disc_Reward_Mean={disc:.3f}")
    elif disc >= 0.12:
        style = make_status("warning", "风格奖励偏低", f"Disc_Reward_Mean={disc:.3f}")
    else:
        style = make_status("critical", "风格分支偏弱", f"Disc_Reward_Mean={disc:.3f}")

    if enc >= 0.15 and div <= 1.1:
        latent = make_status("good", "潜空间稳定", f"Enc={enc:.3f} | Diversity={div:.3f}")
    elif enc < 0.08 or div > 1.4:
        latent = make_status("critical", "疑似 latent 风险", f"Enc={enc:.3f} | Diversity={div:.3f}")
    else:
        latent = make_status("warning", "潜空间需观察", f"Enc={enc:.3f} | Diversity={div:.3f}")

    if samples_per_sec is None:
        throughput = make_status("warning", "吞吐未就绪", "缺少足够历史点")
    elif samples_per_sec >= 6000:
        throughput = make_status("good", "吞吐正常", f"{samples_per_sec:.1f} samples/s")
    elif samples_per_sec >= 3500:
        throughput = make_status("warning", "吞吐偏低", f"{samples_per_sec:.1f} samples/s")
    else:
        throughput = make_status("critical", "吞吐异常偏低", f"{samples_per_sec:.1f} samples/s")

    if len(gpus) >= 2:
        u0 = int(gpus[0].get("util", 0))
        u1 = int(gpus[1].get("util", 0))
        if u0 >= 60 and u1 >= 60:
            gpu = make_status("good", "双卡高利用率", f"GPU0={u0}% GPU1={u1}%")
        elif abs(u0 - u1) > 35:
            gpu = make_status("warning", "双卡负载不均", f"GPU0={u0}% GPU1={u1}%")
        else:
            gpu = make_status("warning", "GPU 利用率一般", f"GPU0={u0}% GPU1={u1}%")
    else:
        gpu = make_status("critical", "GPU 不可用", "nvidia-smi 无双卡数据")

    extra = None
    if clip > 0.85 or imp < 0.85 or imp > 1.2:
        extra = make_status("warning", "PPO 更新较激进", f"Clip={clip:.3f} | Imp={imp:.3f}")

    checks = [style, latent, throughput, gpu] + ([extra] if extra else [])
    if all(severity_rank(x["level"]) == 0 for x in checks):
        overall = make_status("good", "ASE 训练健康", f"{style['label']} | {latent['label']} | {gpu['label']}")
    else:
        overall = max(checks, key=lambda x: severity_rank(x["level"]))
    if overall is latent:
        overall = make_status(overall["level"], overall["label"], f"{overall['detail']} | style={disc:.3f}")
    elif overall is style:
        overall = make_status(overall["level"], overall["label"], f"{overall['detail']} | enc={enc:.3f}")
    elif overall is throughput:
        overall = make_status(overall["level"], overall["label"], f"{overall['detail']} | clip={clip:.3f}")
    elif overall is gpu:
        overall = make_status(overall["level"], overall["label"], f"{overall['detail']} | disc={disc:.3f} enc={enc:.3f}")

    if completed:
        overall = make_status("good", "ASE 训练完成", f"已达到目标 samples | disc={disc:.3f} enc={enc:.3f}")
    return {"overall": overall, "style": style, "latent": latent, "throughput": throughput, "gpu": gpu}


def compute_progress_health(case_name: str, latest: dict, samples_per_sec: float, train_log: Path, runtime=None):
    runtime = runtime or {}
    has_keepalive = bool(runtime.get("has_keepalive"))
    has_runner = bool(runtime.get("has_runner"))
    runtime_detail = str(runtime.get("detail", "")).strip()

    if not has_runner:
        detail = runtime_detail or "未发现活跃训练 worker"
        if train_log and train_log.exists():
            try:
                age_sec = max(0.0, dt.datetime.now().timestamp() - train_log.stat().st_mtime)
                detail += f" | 日志已 {int(age_sec // 60)} 分钟未更新"
            except Exception:
                pass
        if has_keepalive:
            return make_status("warning", "keepalive 重试中", detail)
        return make_status("critical", "当前无训练进程", detail)

    if not latest:
        return make_status("warning", "等待首个快照", "训练日志还没有有效样本")

    age_sec = None
    if train_log and train_log.exists():
        try:
            age_sec = max(0.0, dt.datetime.now().timestamp() - train_log.stat().st_mtime)
        except Exception:
            age_sec = None

    key = CASE_ARGS_TO_KEY.get(case_name, "")
    family = CASE_META.get(key, {}).get("family", "")
    good_floor = 15_000.0 if family == "llc" else 3_000.0
    warn_floor = 7_000.0 if family == "llc" else 1_000.0

    if age_sec is not None and age_sec > 15 * 60:
        return make_status("critical", "进度停滞", f"日志已 {int(age_sec // 60)} 分钟未更新")
    if samples_per_sec is None:
        detail = "历史点不足，等待测速稳定"
        if age_sec is not None:
            detail += f" | 日志 {int(age_sec // 60)} 分钟前更新"
        return make_status("warning", "进度待观察", detail)

    age_text = f"日志 {max(0, int((age_sec or 0) // 60))} 分钟前更新"
    detail = f"{samples_per_sec:.1f} samples/s | {age_text}"
    if samples_per_sec >= good_floor:
        return make_status("good", "进度正常", detail)
    if samples_per_sec >= warn_floor:
        return make_status("warning", "进度偏慢", detail)
    return make_status("critical", "进度异常偏慢", detail)


def parse_queue_log(path: Path):
    text = read_text(path)
    result = {
        "state_label": "未配置",
        "detail": "无 queue controller",
        "last_update": "",
        "target_samples": None,
        "last_samples": None,
        "next_run": "",
    }
    if not text:
        return result

    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not lines:
        return result

    target = None
    last_samples = None
    last_update = ""
    next_run = ""
    for line in lines:
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| .*until samples >= (\d+)", line)
        if m:
            last_update = m.group(1)
            target = int(m.group(2))
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| current_samples=(\d+)", line)
        if m:
            last_update = m.group(1)
            last_samples = int(m.group(2))
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| starting sword_shield run: (\S+)", line)
        if m:
            last_update = m.group(1)
            next_run = m.group(2)

    result["last_update"] = last_update
    result["target_samples"] = target
    result["last_samples"] = last_samples
    result["next_run"] = next_run

    if next_run:
        result["state_label"] = "已切到下一条"
        result["detail"] = next_run
    elif last_samples is not None and target is not None:
        pct = 100.0 * last_samples / max(target, 1)
        result["state_label"] = "串行队列已挂载"
        result["detail"] = f"等待当前 case 达到 {target:,} samples（{pct:.1f}%）"
    else:
        result["state_label"] = "queue 已发现"
        result["detail"] = "已读取 controller log，但尚未解析到完整状态"
    return result


def collect_status(config, root_arg_override=""):
    root_path = resolve_root(root_arg_override or config["root_out"])
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if root_path is None:
        return {
            "server_time": now,
            "root_name": "",
            "root_path": "",
            "available_roots": list_ase_roots(),
            "run": {},
            "metrics": {},
            "config": {},
            "series": {},
            "queue": {},
            "health": {"overall": make_status("critical", "未发现 ASE 运行目录", "请指定 --root-out 或等待目录创建")},
            "gpus": read_gpu_snapshot(),
            "monitor_samples": [],
            "metric_history": [],
            "recent_rows": [],
            "events": [],
            "runner_log": "",
            "monitor_log": "",
            "queue_log": "",
        }

    requested_root = root_path.resolve()
    case_root, current_case_key = resolve_supervisor_active_root(requested_root)
    chain_roots, chain_segments, rows = build_chain_rows(case_root)
    active_root = chain_roots[-1] if chain_roots else case_root

    launch_log = active_root / "launch.log"
    train_log = active_root / "log.txt"
    env_cfg = read_yaml(active_root / "env_config.yaml")
    agent_cfg = read_yaml(active_root / "agent_config.yaml")
    engine_cfg = read_yaml(active_root / "engine_config.yaml")
    launch_info = parse_launch_info(launch_log)
    latest = rows[-1] if rows else {}
    prev_rows = [r for r in rows if r.get("Samples_Per_Sec") is not None]
    samples_per_sec = None
    if prev_rows:
        tail = prev_rows[-4:]
        vals = [float(r["Samples_Per_Sec"]) for r in tail if r.get("Samples_Per_Sec") is not None]
        if vals:
            samples_per_sec = sum(vals) / len(vals)

    case_name = infer_case_name(case_root, env_cfg, current_case_key=current_case_key)
    target_samples = target_samples_for_case(case_name, config)
    target_label = target_label_for_case(case_name)
    samples = int(latest.get("Samples", 0) or 0)
    observed_max_samples = max((int(r.get("Samples", 0) or 0) for r in rows), default=samples)
    display_progress_base_samples = max(target_samples, observed_max_samples, samples)
    target_pct = (100.0 * samples / target_samples) if target_samples > 0 else 0.0
    display_target_pct = (100.0 * samples / display_progress_base_samples) if display_progress_base_samples > 0 else 0.0
    completed = target_samples > 0 and samples >= target_samples
    overflow_samples = max(samples - target_samples, 0) if target_samples > 0 else 0
    eta_current_sec = None
    if samples_per_sec and target_samples > samples:
        eta_current_sec = (target_samples - samples) / samples_per_sec

    series_cases = config["series_cases"]
    active_idx = series_cases.index(case_name) if case_name in series_cases else 0
    next_case = series_cases[active_idx + 1] if active_idx + 1 < len(series_cases) else ""
    series_targets = [target_samples_for_case(x, config) for x in series_cases]
    series_total_samples = sum(series_targets)
    completed_series_samples = sum(series_targets[:active_idx]) + min(samples, target_samples)
    progress_pct = (
        100.0 * completed_series_samples / series_total_samples
        if series_total_samples > 0
        else 0.0
    )
    eta_series_sec = None
    if samples_per_sec:
        remaining = max(target_samples - samples, 0)
        remaining += sum(series_targets[active_idx + 1 :])
        eta_series_sec = remaining / samples_per_sec

    monitor_log = detect_monitor_log(active_root, config["monitor_log"])
    queue_log = detect_queue_log(requested_root, config["queue_log"])
    monitor_samples = parse_monitor_samples(monitor_log, limit=config["history_size"])
    queue = parse_queue_log(queue_log)
    if completed:
        queue = dict(queue)
        queue["state_label"] = "当前 case 已完成"
        queue["detail"] = f"{short_case_name(case_name)} 已达到 {samples:,} samples"
    gpus = read_gpu_snapshot()
    health = compute_health(latest, gpus, samples_per_sec, completed=completed)
    runtime = detect_training_runtime(requested_root)
    health["progress"] = compute_progress_health(case_name, latest, samples_per_sec, train_log, runtime=runtime)

    total_wall_time_h = None
    wall_vals = [float(x["wall_time_h"]) for x in chain_segments if x.get("wall_time_h") is not None]
    if wall_vals:
        total_wall_time_h = sum(wall_vals)

    metrics = {
        "disc_reward_mean": latest.get("Disc_Reward_Mean"),
        "enc_reward_mean": latest.get("Enc_Reward_Mean"),
        "diversity_loss": latest.get("Diversity_Loss"),
        "clip_frac": latest.get("Clip_Frac"),
        "imp_ratio": latest.get("Imp_Ratio"),
        "disc_agent_acc": latest.get("Disc_Agent_Acc"),
        "disc_demo_acc": latest.get("Disc_Demo_Acc"),
        "train_episode_length": latest.get("Train_Episode_Length"),
    }

    run = {
        "case_name": case_name,
        "case_short": short_case_name(case_name),
        "iteration": latest.get("Iteration"),
        "samples": samples,
        "target_samples": target_samples,
        "target_label": target_label,
        "observed_max_samples": observed_max_samples,
        "display_progress_base_samples": display_progress_base_samples,
        "target_pct": target_pct,
        "display_target_pct": display_target_pct,
        "overflow_samples": overflow_samples,
        "completed": completed,
        "wall_time_h": total_wall_time_h if total_wall_time_h is not None else latest.get("Wall_Time"),
        "samples_per_sec": samples_per_sec,
        "samples_per_hour_m": (samples_per_sec * 3600.0 / 1_000_000.0) if samples_per_sec else None,
        "eta_current_sec": eta_current_sec,
        "num_envs": launch_info.get("num_envs"),
        "master_port": launch_info.get("master_port"),
        "sop_stage": ("Stage 1-2 预训练完成" if completed else "Stage 1-2 预训练（style + latent）"),
    }

    cfg = {
        "motion_file": env_cfg.get("motion_file", ""),
        "engine_name": engine_cfg.get("engine_name", ""),
        "control_freq": engine_cfg.get("control_freq"),
        "sim_freq": engine_cfg.get("sim_freq"),
        "latent_dim": (((agent_cfg.get("model") or {}).get("latent_dim")) if isinstance(agent_cfg.get("model"), dict) else None),
        "disc_reward_weight": agent_cfg.get("disc_reward_weight"),
        "enc_reward_weight": agent_cfg.get("enc_reward_weight"),
        "diversity_weight": agent_cfg.get("diversity_weight"),
        "latent_time_min": agent_cfg.get("latent_time_min"),
        "latent_time_max": agent_cfg.get("latent_time_max"),
        "task_reward_weight": agent_cfg.get("task_reward_weight"),
    }

    recent_rows = []
    for row in rows[-12:]:
        recent_rows.append(
            {
                "Iteration": int(row.get("Iteration", 0)),
                "Samples": int(row.get("Samples", 0)),
                "Samples_Per_Sec": f"{float(row['Samples_Per_Sec']):.1f}" if row.get("Samples_Per_Sec") is not None else "-",
                "Disc_Reward_Mean": f"{float(row.get('Disc_Reward_Mean', 0.0)):.3f}",
                "Enc_Reward_Mean": f"{float(row.get('Enc_Reward_Mean', 0.0)):.3f}",
                "Diversity_Loss": f"{float(row.get('Diversity_Loss', 0.0)):.3f}",
                "Clip_Frac": f"{float(row.get('Clip_Frac', 0.0)):.3f}",
                "Disc_Agent_Acc": f"{float(row.get('Disc_Agent_Acc', 0.0)):.3f}",
                "Disc_Demo_Acc": f"{float(row.get('Disc_Demo_Acc', 0.0)):.3f}",
            }
        )

    events = []
    if len(chain_segments) > 1:
        chain_names = " -> ".join(x["root_name"] for x in chain_segments)
        events.append(f"[CHAIN] merged resume chain: {chain_names}")
    events.extend([f"[RUNNER] {x}" for x in tail_lines(launch_log, n=10)])
    events.extend([f"[QUEUE] {x}" for x in tail_lines(queue_log, n=8)])
    events.extend([f"[MONITOR] {x}" for x in tail_lines(monitor_log, n=8)])
    events = events[-26:]

    return {
        "server_time": now,
        "root_name": requested_root.name,
        "root_path": str(requested_root),
        "available_roots": list_ase_roots(),
        "run": run,
        "metrics": metrics,
        "config": cfg,
        "series": {
            "total_cases": len(series_cases),
            "active_case": case_name,
            "next_case": next_case,
            "progress_pct": progress_pct,
            "eta_series_sec": eta_series_sec,
            "series_total_samples": series_total_samples,
            "series_completed_samples": completed_series_samples,
            "resume_chain": [x["root_name"] for x in chain_segments],
        },
        "queue": queue,
        "health": health,
        "gpus": gpus,
        "monitor_samples": monitor_samples,
        "metric_history": rows[-180:],
        "recent_rows": recent_rows,
        "events": events,
        "runner_log": str(launch_log) if launch_log.exists() else "",
        "monitor_log": str(monitor_log) if monitor_log else "",
        "queue_log": str(queue_log) if queue_log else "",
    }


def make_handler(config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

        def _send_json(self, obj, code=200):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, text, code=200):
            raw = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self._send_html(HTML_PAGE)
                return
            if u.path == "/api/status":
                q = parse_qs(u.query)
                root_override = (q.get("root", [""])[0] or "").strip()
                status = collect_status(config, root_arg_override=root_override)
                self._send_json(status)
                return
            self._send_json({"error": "not found"}, code=404)

    return Handler


def main():
    args = parse_args()
    config = {
        "root_out": args.root_out.strip(),
        "monitor_log": args.monitor_log.strip(),
        "queue_log": args.queue_log.strip(),
        "history_size": max(60, int(args.history_size)),
        "target_samples": int(args.target_samples),
        "llc_target_samples": int(args.llc_target_samples),
        "hlc_target_samples": int(args.hlc_target_samples),
        "series_cases": [x.strip() for x in args.series_cases.split(",") if x.strip()],
    }
    handler = make_handler(config)

    class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True

    with ThreadingTCPServer((args.host, args.port), handler) as httpd:
        base = f"http://{args.host}:{args.port}/"
        print(f"[ase-dashboard] listen={base}")
        print(f"[ase-dashboard] root_out={config['root_out'] or '(auto)'}")
        if config["monitor_log"]:
            print(f"[ase-dashboard] monitor_log={config['monitor_log']}")
        if config["queue_log"]:
            print(f"[ase-dashboard] queue_log={config['queue_log']}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
