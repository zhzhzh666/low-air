#!/usr/bin/env python3
"""Generate a standalone interactive schematic map for the logistics simulation."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUT = ROOT / "map_view.html"


def main() -> None:
    params = json.loads((RESULTS / "model_parameters.json").read_text(encoding="utf-8"))
    traces = json.loads((RESULTS / "representative_traces.json").read_text(encoding="utf-8"))
    summary = []
    for row in (RESULTS / "policy_summary.csv").read_text(encoding="utf-8-sig").splitlines()[1:]:
        cells = row.split(",")
        summary.append({"policy": cells[0], "mean_time": float(cells[2]), "drone_share": float(cells[5]), "queries": float(cells[6]), "failures": float(cells[7])})

    payload = {"params": params, "traces": traces, "summary": summary}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    title = "低空物流系统地图版仿真"
    page = f'''<div id="low-altitude-map-app" aria-label="低空物流系统地图版仿真">
  <style>
    #low-altitude-map-app {{ font-family: system-ui, -apple-system, "Microsoft YaHei", sans-serif; color:#e8f1f5; background:#081f32; padding:18px; border-radius:14px; max-width:1100px; margin:0 auto; }}
    #low-altitude-map-app .head {{ display:flex; justify-content:space-between; align-items:end; gap:16px; flex-wrap:wrap; margin-bottom:10px; }}
    #low-altitude-map-app h1 {{ font-size:24px; margin:0; font-weight:600; }}
    #low-altitude-map-app .sub {{ color:#9bb2c1; font-size:13px; margin-top:4px; }}
    #low-altitude-map-app .controls {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
    #low-altitude-map-app select {{ background:#123b54; color:#f2f7f8; border:1px solid #2e647b; border-radius:6px; padding:7px 10px; font-size:14px; }}
    #low-altitude-map-app .map-wrap {{ border-top:1px solid #244b60; padding-top:12px; }}
    #low-altitude-map-app svg {{ width:100%; height:auto; display:block; background:#0a2a40; border-radius:10px; }}
    #low-altitude-map-app .road {{ fill:none; stroke:#86a5b6; stroke-width:1.2; stroke-dasharray:2 2; opacity:.9; }}
    #low-altitude-map-app .drone {{ fill:none; stroke:#37c7d8; stroke-width:1.1; stroke-dasharray:3 2; opacity:.95; }}
    #low-altitude-map-app .zone-label {{ fill:#f4f9fb; font-size:3.6px; font-weight:600; text-anchor:middle; dominant-baseline:middle; }}
    #low-altitude-map-app .weather-label {{ fill:#b9cbd4; font-size:2.5px; text-anchor:middle; }}
    #low-altitude-map-app .hub {{ fill:#9bb2c1; opacity:.75; }}
    #low-altitude-map-app .query-ring {{ fill:none; stroke:#f4a340; stroke-width:1.1; }}
    #low-altitude-map-app .legend {{ display:flex; flex-wrap:wrap; gap:14px; padding:8px 0 0; color:#b9cbd4; font-size:13px; }}
    #low-altitude-map-app .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:-1px; }}
    #low-altitude-map-app .status {{ color:#d9e9ef; font-size:14px; margin-top:8px; }}
    #low-altitude-map-app .sr-only {{ position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }}
  </style>
  <div class="head">
    <div><h1>{html.escape(title)}</h1><div class="sub">示意坐标单位：km；用于比较调度路径，不代表真实经纬度</div></div>
    <div class="controls"><label for="policy-select">策略</label><select id="policy-select" aria-label="选择仿真策略"></select></div>
  </div>
  <div class="map-wrap"><svg id="map-svg" viewBox="0 0 100 60" role="img" aria-labelledby="map-title map-desc"><title id="map-title">低空物流车辆协同路线地图</title><desc id="map-desc">显示卡车道路路线、无人机架次、区域风况和被查询区域。</desc></svg></div>
  <div class="legend"><span><i class="dot" style="background:#42c5d6"></i>平静风</span><span><i class="dot" style="background:#f4a340"></i>中等风</span><span><i class="dot" style="background:#ee6b5f"></i>强风</span><span>实线：卡车路线</span><span>虚线：无人机架次</span><span style="color:#f4a340">圆环：天气查询</span></div>
  <div id="map-status" class="status" aria-live="polite"></div>
  <script>
  (() => {{
    const DATA = {data_json};
    const svg = document.getElementById('map-svg');
    const select = document.getElementById('policy-select');
    const status = document.getElementById('map-status');
    const zones = DATA.params.zones;
    const zoneByName = Object.fromEntries(zones.map(z => [z.name, z]));
    const route = zones.map(z => z.name);
    const depot = {{ name:'仓', x_km:6, y_km:54 }};
    const colors = {{ calm: '#42c5d6', moderate: '#f4a340', strong: '#ee6b5f' }};
    const names = {{ none: '保守不查询', blind_aggressive: '盲目飞行', random: '随机查询', active: '主动 VOI', all_query: '顺序查询', oracle: '天气全知' }};
    Object.keys(names).forEach(p => {{ const o = document.createElement('option'); o.value = p; o.textContent = names[p]; select.appendChild(o); }});
    select.value = 'active';
    const NS = 'http://www.w3.org/2000/svg';
    function el(tag, attrs) {{ const node = document.createElementNS(NS, tag); Object.entries(attrs || {{}}).forEach(([k,v]) => node.setAttribute(k, v)); return node; }}
    function render(policy) {{
      while (svg.lastChild) svg.removeChild(svg.lastChild);
      const title = el('title', {{ id:'map-title' }}); title.textContent = '低空物流车辆协同路线地图'; svg.appendChild(title);
      const desc = el('desc', {{ id:'map-desc' }}); desc.textContent = '显示卡车道路路线、无人机架次、区域风况和被查询区域。'; svg.appendChild(desc);
      const trace = DATA.traces[policy].weather_and_actions;
      const lookup = Object.fromEntries(trace.map(r => [r.zone, r]));
      const routePoints = [depot, ...route.map(n => zoneByName[n])];
      svg.appendChild(el('polyline', {{ class:'road', points:routePoints.map(z => `${{z.x_km}},${{60-z.y_km}}`).join(' ') }}));
      svg.appendChild(el('circle', {{ class:'hub', cx:depot.x_km, cy:60-depot.y_km, r:'1.5' }}));
      const depotLabel = el('text', {{ class:'weather-label', x:depot.x_km, y:60-depot.y_km-3 }}); depotLabel.textContent='仓'; svg.appendChild(depotLabel);
      routePoints.forEach((z, i) => {{
        const next = routePoints[i+1];
        const rec = lookup[z.name];
        if (rec && rec.action === 'drone' && next) {{
          const x1=z.x_km, y1=60-z.y_km, x2=(z.x_km+next.x_km)/2, y2=(60-z.y_km + 60-next.y_km)/2;
          svg.appendChild(el('path', {{ class:'drone', d:`M ${{x1}} ${{y1}} Q ${{(x1+x2)/2}} ${{(y1+y2)/2-6}} ${{x2}} ${{y2}}` }}));
          svg.appendChild(el('circle', {{ class:'hub', cx:x2, cy:y2, r:'.7' }}));
        }}
      }});
      routePoints.slice(1).forEach(z => {{
        const rec = lookup[z.name] || {{ weather_real:'calm', query:false, action:'truck' }};
        const g = el('g', {{ 'aria-label':`${{z.name}} 区域，${{rec.weather_real}}，${{rec.action}}` }});
        if (rec.query) g.appendChild(el('circle', {{ class:'query-ring', cx:z.x_km, cy:60-z.y_km, r:'4.4' }}));
        g.appendChild(el('circle', {{ cx:z.x_km, cy:60-z.y_km, r:'3.1', fill:colors[rec.weather_real] || '#9bb2c1', stroke:'#081f32', 'stroke-width':'.5' }}));
        const label = el('text', {{ class:'zone-label', x:z.x_km, y:60-z.y_km }}); label.textContent=z.name; g.appendChild(label);
        const w = el('text', {{ class:'weather-label', x:z.x_km, y:60-z.y_km+6 }}); w.textContent=rec.action === 'drone' ? '无人机' : '卡车'; g.appendChild(w);
        svg.appendChild(g);
      }});
      const selected = DATA.summary.find(x => x.policy === policy);
      status.textContent = `${{names[policy]}}：平均完成时间 ${{selected.mean_time.toFixed(1)}} 分钟，查询 ${{selected.queries}} 次，无人机占比 ${{(selected.drone_share*100).toFixed(1)}}%，平均失败 ${{selected.failures.toFixed(2)}} 架次`;
    }}
    select.addEventListener('change', () => render(select.value));
    render(select.value);
  }})();
  </script>
</div>'''
    standalone = f'''<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title></head>
<body style="margin:0;background:#061827">{page}</body>
</html>
'''
    OUT.write_text(standalone, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
