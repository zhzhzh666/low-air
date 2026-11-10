"""Standalone map replay of recorded motion (audit view, never planner input)."""
import json
from pathlib import Path
from .flight import FlightModel

def export_map(ep,baseline,path):
    data=[]
    for e in [baseline,ep]:
        fm=FlightModel(e.instance,e.config); sorties=[]
        from .models import Sortie
        for a in e.sorties:
            v=fm.evaluate(Sortie(a["launch"],a["customer"],a["recover"]),e.truth[int(a["start"]//e.config["simulation"]["weather_step_min"])])
            sorties.append(dict(a,customer_arrive=a["start"]+float(v[3][0])))
        data.append(dict(metrics=e.metrics,coords=e.instance.coords,customers={j:vars(c) for j,c in e.instance.customers.items()},edges=e.truck_edges,sorties=sorties,queries=e.queries,truth=e.truth.tolist(),pickups=e.pickups))
    payload=json.dumps(dict(config=ep.config,episodes=data),ensure_ascii=False).replace("</","<\\/")
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>有限天气观测：真实轨迹地图回放</title>
<style>body{margin:0;background:#eef3f8;color:#17304d;font-family:"Microsoft YaHei",sans-serif}main{max-width:1100px;margin:25px auto;background:white;padding:24px}h1{font-size:25px}p{line-height:1.7;color:#4d6278}canvas{display:block;width:100%;height:auto;border:1px solid #dbe2eb}select,button,input{margin:8px;font-size:16px}#stats{font-size:16px;line-height:1.8}label{white-space:nowrap}.controls{display:flex;align-items:center;flex-wrap:wrap}input[type=range]{flex:1;min-width:260px}</style>
<main><h1>有限天气观测下的卡车—无人机协同取件</h1><p>合成局部地图，坐标单位 km。蓝线为卡车道路距离代理，橙色虚线为空载与载货飞行。滑动时间查看实际记录的车辆位置。隐藏天气仅供事后审计，未作为普通策略输入。</p>
<div class="controls"><select id="policy"></select><button id="play">播放</button><input id="time" type="range" min="0" max="180" step="0.05" value="0"><span id="clock"></span></div><label><input type="checkbox" id="truth">显示隐藏风况（审计）</label><canvas id="map" width="1050" height="740"></canvas><div id="stats"></div><p>模型假定每架次风场在起飞时冻结，回收点可安全落地等待。无人机落地后仍可能等待卡车，不发生悬停耗能。查询结果只有到达后才供调度使用。</p></main>
<script>const DATA=__DATA__;
const canvas=document.querySelector('#map'),g=canvas.getContext('2d'),sel=document.querySelector('#policy'),slider=document.querySelector('#time');
DATA.episodes.forEach((e,i)=>{let o=document.createElement('option');o.value=i;o.textContent=e.metrics.policy;sel.append(o)});sel.value=1;
const pos=p=>[80+p[0]/DATA.config.map.size_km*650,680-p[1]/DATA.config.map.size_km*650],mix=(a,b,f)=>[a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f];
function line(a,b,color,dash=[]){a=pos(a);b=pos(b);g.strokeStyle=color;g.lineWidth=2;g.setLineDash(dash);g.beginPath();g.moveTo(...a);g.lineTo(...b);g.stroke();g.setLineDash([])}
function dot(p,color,r=7){p=pos(p);g.fillStyle=color;g.beginPath();g.arc(...p,r,0,2*Math.PI);g.fill()}
function draw(){let e=DATA.episodes[+sel.value],t=+slider.value,c=DATA.config,m=c.map,coords=e.coords;g.clearRect(0,0,1050,740);g.font='14px Microsoft YaHei';
let slot=Math.min(e.truth.length-1,Math.floor(t/c.simulation.weather_step_min));
for(let r=0;r<m.weather_grid_rows;r++)for(let col=0;col<m.weather_grid_cols;col++){let id=r*m.weather_grid_cols+col,a=pos([col*m.size_km/m.weather_grid_cols,(r+1)*m.size_km/m.weather_grid_rows]);g.fillStyle=document.querySelector('#truth').checked?['#cce9df','#ffdb80','#dd8d88'][e.truth[slot][id]]:'#f5f8fc';g.fillRect(...a,650/m.weather_grid_cols,650/m.weather_grid_rows);g.strokeStyle='#c7d4e1';g.strokeRect(...a,650/m.weather_grid_cols,650/m.weather_grid_rows);g.fillStyle='#899cae';g.fillText('区域 '+id,a[0]+8,a[1]+20)}
e.edges.forEach(x=>{line(coords[x.origin],coords[x.destination],'#a5bfd9');if(t>=x.start)line(coords[x.origin],mix(coords[x.origin],coords[x.destination],Math.min(x.fraction??1,Math.max(0,(t-x.start)/Math.max(.001,x.end-x.start))*(x.fraction??1))),'#286aa8')});
e.sorties.forEach(a=>{line(coords[a.launch],coords[a.customer],'#e79061',[7,5]);line(coords[a.customer],coords[a.recover],'#e79061',[7,5])});
for(let [j,p] of Object.entries(e.customers)){dot(coords[j],e.pickups[j]!==undefined&&e.pickups[j]<=t?'#6ead8d':'#ffc857',6);let a=pos(coords[j]);g.fillStyle='#172c40';g.fillText(j,a[0]+8,a[1]-8)}
let truck=coords[0];for(let x of e.edges){if(t>=x.end)truck=mix(coords[x.origin],coords[x.destination],x.fraction??1);else if(t>=x.start){truck=mix(coords[x.origin],coords[x.destination],Math.min(1,(t-x.start)/Math.max(.001,x.end-x.start))*(x.fraction??1));break}}
dot(coords[0],'#182c41',10);dot(truck,'#1d62ad',9);let drone=truck,status='随车';
for(let a of e.sorties){let end=a.end??e.metrics.completion_time_min;if(t>=a.start&&t<=end){if(t<a.customer_arrive){drone=mix(coords[a.launch],coords[a.customer],(t-a.start)/(a.customer_arrive-a.start));status='空载飞行'}else if(t<a.pickup){drone=coords[a.customer];status='等待/取件'}else if(t<a.land){drone=mix(coords[a.customer],coords[a.recover],(t-a.pickup)/(a.land-a.pickup));status='载货飞行'}else{drone=coords[a.recover];status='落地等待/回收'};break}}
dot(drone,'#d75f36',5);g.fillStyle='#203a55';g.fillText('蓝点：卡车',780,80);g.fillText('橙点：无人机',780,110);g.fillText('无人机：'+status,780,150);g.fillText('已提交查询：'+e.queries.filter(q=>q.start<=t).length,780,200);g.fillText('已返回报告：'+e.queries.filter(q=>q.arrival<=t).length,780,230);g.fillText('已取件：'+Object.values(e.pickups).filter(x=>x<=t).length+' / '+m.n_customers,780,280);
e.queries.filter(q=>q.start<=t).forEach(q=>{let r=Math.floor(q.region/m.weather_grid_cols),col=q.region%m.weather_grid_cols;let p=pos([(col+.5)*m.size_km/m.weather_grid_cols,(r+.5)*m.size_km/m.weather_grid_rows]);g.strokeStyle=q.arrival<=t?'#7a4f9e':'#ad8dc4';g.lineWidth=3;g.beginPath();g.arc(...p,18,0,2*Math.PI);g.stroke()});
document.querySelector('#clock').textContent=t.toFixed(1)+' min';document.querySelector('#stats').textContent='最终结果：成本 '+e.metrics.total_cost.toFixed(3)+'，回合时间 '+e.metrics.completion_time_min.toFixed(2)+' min，查询 '+e.metrics.query_count+' 次，无人机 '+e.metrics.drone_sortie_count+' 架次。'+(e.metrics.infeasible_flag?'时限内未全部回仓。':'全部货物返回仓库。')}
let timer=null;document.querySelector('#play').onclick=()=>{if(timer){clearInterval(timer);timer=null;document.querySelector('#play').textContent='播放'}else{document.querySelector('#play').textContent='暂停';timer=setInterval(()=>{let e=DATA.episodes[+sel.value];slider.value=Math.min(e.metrics.completion_time_min,+slider.value+.3);draw();if(+slider.value>=e.metrics.completion_time_min){clearInterval(timer);timer=null;document.querySelector('#play').textContent='播放'}},40)}};sel.onchange=()=>{slider.max=DATA.episodes[+sel.value].metrics.completion_time_min;slider.value=0;draw()};slider.oninput=draw;document.querySelector('#truth').onchange=draw;sel.onchange();</script></html>'''
    Path(path).write_text(html.replace("__DATA__",payload),encoding="utf-8")
