"""Directed-road truck/UAV experiments with node-wise weather observations and battery swaps."""
from rolling import choose
from pathlib import Path
import json,math,csv,random,heapq,functools
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components,dijkstra
from osgeo import ogr
from collections import defaultdict,Counter
R=Path(__file__).resolve().parent
M=json.loads((R/'data/map.json').read_text()); cfg=json.loads((R/'config.json').read_text())
nodes=list(M['nodes']); idx={n:i for i,n in enumerate(nodes)}; xy=np.array([M['nodes'][n] for n in nodes])
def dist(a,b):return float(np.linalg.norm(np.array(a)-b))
speed={'primary':9,'secondary':8,'tertiary':7,'service':3.5,'residential':5,'trunk':12,'motorway':16}
edges={}; candid=set()
for ns,cl,one,name,osm in M['roads']:
 if cl in ['service','residential','living_street','unclassified']:candid.update(idx[n] for n in ns)
 for a,b in zip(ns,ns[1:]):
  i,j=idx[a],idx[b]; sec=max(.01,dist(xy[i],xy[j])/speed.get(cl,6.0))
  for arc in ([(i,j)] if one in ['yes','true','1'] else [(j,i)] if one=='-1' else [(i,j),(j,i)]):
   edges[arc]=min(sec,edges.get(arc,float('inf')))
ij=list(edges); G=csr_matrix(([edges[a] for a in ij],tuple(zip(*ij))),shape=(len(xy),len(xy)))
_,labels=connected_components(G,directed=True,connection='strong'); main=Counter(labels).most_common(1)[0][0]
# Buffered building geometries and a spatial index in local metres.
bins=defaultdict(list);obs=[]
def cells(lo,hi):
 for x in range(math.floor(lo[0]/100),math.floor(hi[0]/100)+1):
  for y in range(math.floor(lo[1]/100),math.floor(hi[1]/100)+1):yield x,y
for polygon,h,*_ in M['buildings']:
 ring=ogr.Geometry(ogr.wkbLinearRing)
 for x,y in polygon+[polygon[0]]:ring.AddPoint_2D(x,y)
 poly=ogr.Geometry(ogr.wkbPolygon);poly.AddGeometry(ring);poly=poly.Buffer(5);x,X,y,Y=poly.GetEnvelope();i=len(obs);obs.append((poly,h))
 for key in cells([x,y],[X,Y]):bins[key].append(i)
def maxheight(a,b):
 a=np.array(a);b=np.array(b);l=ogr.Geometry(ogr.wkbLineString);l.AddPoint_2D(*a);l.AddPoint_2D(*b)
 ids=set(v for k in cells(np.minimum(a,b),np.maximum(a,b)) for v in bins[k])
 return max([0]+[obs[i][1] for i in ids if obs[i][0].Intersects(l)])
rng=random.Random(cfg['seed']);pool=sorted(i for i in candid if labels[i]==main)
rng.shuffle(pool);valid=[]
for i in pool:
 if maxheight(xy[i],xy[i])==0 and all(dist(xy[i],xy[j])>155 for j in valid):valid.append(i)
 if len(valid)>=cfg['orders']+1:break
assert len(valid)==cfg['orders']+1
origin=min(valid,key=lambda i:dist(xy[i],[-430,0]));valid.remove(origin);stops=[origin]+valid
T,pred=dijkstra(G,indices=stops,return_predecessors=True)
@functools.lru_cache(None)
def road(a,b):
 n=stops[b];route=[n]
 while n!=stops[a]:
  n=int(pred[a,n]);assert n>=0;route.append(n)
 return tuple(reversed(route))
def pos(i):return xy[stops[i]]
order=[];left=set(range(1,len(stops)));a=0
while left:
 b=min(left,key=lambda j:T[a,stops[j]]);order.append(b);left.remove(b);a=b
order.append(0)
weights={j:round(rng.uniform(.25,cfg['payload_kg']),2) for j in order if j}
deadlines={};estimate=0;a=0
for j in order:
 estimate+=T[a,stops[j]]+cfg['service_s'];deadlines[j]=estimate*.95+rng.uniform(-120,300);a=j
WIND_SOURCES=(
 ('东',np.array([1.0,0.0])),('东北',np.array([1.0,1.0])),
 ('北',np.array([0.0,1.0])),('西北',np.array([-1.0,1.0])),
 ('西',np.array([-1.0,0.0])),('西南',np.array([-1.0,-1.0])),
 ('南',np.array([0.0,-1.0])),('东南',np.array([1.0,-1.0])),
)
WIND_SOURCES=tuple((name,vec/np.linalg.norm(vec)) for name,vec in WIND_SOURCES)
def wind(case,t,p,issue=None,noise=0):
 # The source direction is snapped to eight compass directions. Forecasts are re-issued at every truck node.
 q=t if issue is None else issue
 direction_index=int(abs(math.floor(q/240+p[0]/700-p[1]/930)))%len(WIND_SOURCES)
 _,source=WIND_SOURCES[direction_index]
 base=3.8+2.2*math.sin(q/610+p[0]/1200)+1.1*math.cos(q/430+p[1]/880)
 if case=='truck':speed=cfg['wind_limit_mps']
 elif case=='normal':speed=min(cfg['normal_wind_max_mps'],max(0,base))
 else:
  speed=max(0,base)
  phase=(t-420)/1700
  if 0<phase<1 and (issue is None or q>=540):speed+=8.2*math.sin(math.pi*phase)**.7
  if 610<t<760 and issue is None:speed=max(speed,13.8)
 speed=float(np.clip(speed+.55*noise,0,cfg['wind_limit_mps']))
 # A wind "from" a compass direction moves in the opposite vector direction.
 return -source*speed
def observe_weather(case,t,p):
 w=wind(case,t,p);speed=float(np.linalg.norm(w))
 if case=='truck' or speed>=cfg['wind_limit_mps']-1e-9:weather_class='truck_only'
 elif speed<=cfg['normal_wind_max_mps']:weather_class='normal'
 else:weather_class='gust'
 if speed<1e-9:name='静风'
 else:
  source=-w/speed;name=max(WIND_SOURCES,key=lambda item:float(item[1]@source))[0]
 return dict(speed_mps=round(speed,2),direction=name,weather_class=weather_class)
@functools.lru_cache(None)
def clearance(a,b):return max(cfg['altitude_m'],maxheight(pos(a),pos(b))+cfg['clearance_m'])
def flight(a,b,load,t,case,issue=None,noise=0):
 p,q=pos(a),pos(b);h=clearance(a,b);dr=q-p;d=float(np.linalg.norm(dr));direction=dr/d
 w=wind(case,t,(p+q)/2,issue,noise);along=float(w@direction);cross2=float(w@w)-along**2;va=cfg['airspeed_mps']
 if cross2>=va**2:return None
 vg=math.sqrt(max(0,va**2-cross2))+along
 if vg<2 or h>cfg['altitude_limit_m'] or np.linalg.norm(w)>cfg['wind_limit_mps']:return None
 durations=[h/3.5,d/vg,h/2.8]
 load_ratio=min(1,max(0,load/cfg['payload_kg']))
 rate=cfg['empty_Wh_per_km']+(cfg['full_Wh_per_km']-cfg['empty_Wh_per_km'])*load_ratio
 energy=d/1000*rate*(va/vg)
 return durations,energy,h
def safe_distance_budget(B):
 # d <= (v_air-w_max)*t, with t converted from usable energy by the full-load power rate.
 safe_ground=max(.1,cfg['airspeed_mps']-cfg['wind_limit_mps'])
 loaded_power=cfg['full_Wh_per_km']*cfg['airspeed_mps']*3.6
 usable=max(0,B-cfg['reserve_Wh'])
 return safe_ground*(usable/loaded_power)*3600
def run(case):
 truck=[];drone=[];events=[];tasks=[];charges=[];audit=[];weather_observations=[];battery_swaps=[]
 B=cfg['battery_Wh'];t=0;a=0;km=0;late=0;Bmin=B;energy_used=0;done=set();pend=order.copy()
 def add(track,t,p,z=0):track.append([round(t,3),round(float(p[0]),2),round(float(p[1]),2),round(z,2)])
 def truck_move(a,b,t):
  nonlocal km
  ns=road(a,b);add(truck,t,xy[ns[0]])
  for i,j in zip(ns,ns[1:]):
   t+=edges[i,j];km+=dist(xy[i],xy[j])/1000;add(truck,t,xy[j])
  return t
 def serve(j,time,mode):
  nonlocal late
  if j:assert j not in done;done.add(j);late+=max(0,time-deadlines[j]);tasks.append([j,mode,round(time,1),weights[j],round(max(0,time-deadlines[j]),1)])
 def legtrack(a,b,t,f):
  ds,e,h=f;add(drone,t,pos(a),2);add(drone,t+ds[0],pos(a),h);add(drone,t+sum(ds[:2]),pos(b),h);add(drone,t+sum(ds),pos(b),2)
 def debit(t,e):
  nonlocal B,Bmin,energy_used
  B-=e;energy_used+=e;Bmin=min(Bmin,B);charges.append([round(t,2),round(B,3)])
 def maybe_swap(node):
  nonlocal B,t
  threshold=cfg['battery_Wh']*cfg['battery_swap_threshold_ratio']
  if B>threshold+1e-6:return False
  before=B;t+=cfg['battery_swap_time_s'];B=cfg['battery_Wh'];charges.append([round(t,2),round(B,3)])
  battery_swaps.append(dict(t_s=round(t,1),node=node,before_Wh=round(before,2),after_Wh=round(B,2)))
  events.append([round(t,1),node,'battery_swap']);add(truck,t,pos(node));add(drone,t,pos(node),2)
  return True
 charges.append([0,B]);add(truck,0,pos(a));add(drone,0,pos(a),2)
 while pend:
  swapped=maybe_swap(a);obs=observe_weather(case,t,pos(a));obs.update(t_s=round(t,1),node=a,battery_Wh=round(B,2));weather_observations.append(obs)
  j=pend[0];k=pend[1] if len(pend)>1 else None;use=False;preds=[];reason='ground';issue=t
  sortie_distance=dist(pos(a),pos(j))+dist(pos(j),pos(k)) if k is not None else None
  distance_budget=safe_distance_budget(B)
  if case!='truck' and obs['weather_class']!='truck_only' and k is not None and weights[j]<=cfg['payload_kg']:
   if sortie_distance>distance_budget:reason='distance_reserve'
   else:
    for n in [-2,-1,0,1,2]:
     out=flight(a,j,0,t,case,issue,n);back=flight(j,k,weights[j],t+sum(out[0])+cfg['service_s'],case,issue,n) if out else None
     if out and back:preds.append((out[1]+back[1]+cfg['handling_Wh'],sum(out[0])+sum(back[0])+cfg['service_s']))
    if len(preds)<5:reason='weather_or_clearance'
    elif max(e for e,s in preds)>B-cfg['reserve_Wh']:reason='return_energy'
    elif 15+max(T[a,stops[k]],max(s for e,s in preds))+12 < T[a,stops[j]]+cfg['service_s']+T[j,stops[k]]:use=True
    else:reason='truck_faster'
  elif obs['weather_class']=='truck_only':reason='wind_threshold_truck'
  if case=='gust_milp' and j and k is not None and len(preds)==5 and max(e for e,s in preds)<=B-cfg['reserve_Wh'] and sortie_distance<=distance_budget:
   use=choose([a]+pend,t,B,issue,T,stops,road,pos,flight,case,weights,deadlines,cfg,dist,xy)
   if not use:reason='milp_ground'
  if use:
   start=t+15;out=flight(a,j,0,start,case);back=flight(j,k,weights[j],start+sum(out[0])+cfg['service_s'],case) if out else None
   # Ground check uses only departure-local wind and sensor battery, never future return truth.
   if out is None:use=False;reason='launch_unavailable'
  audit.append(dict(t_s=round(t,1),customer=j,rendezvous=k,forecast_issue_s=round(issue,1),available_Wh=round(B-cfg['reserve_Wh'],2),battery_pct=round(B/cfg['battery_Wh']*100,1),observed_wind_mps=obs['speed_mps'],observed_wind_direction=obs['direction'],weather_class=obs['weather_class'],battery_swapped=swapped,safe_distance_budget_m=round(distance_budget,1),sortie_distance_m=round(sortie_distance,1) if sortie_distance is not None else None,n_feasible=len(preds),max_forecast_Wh=round(max(e for e,s in preds),2) if preds else None,decision='launch' if use else reason))
  if use:
   legtrack(a,j,start,out);atj=start+sum(out[0]);debit(atj,out[1]);finish=atj+cfg['service_s'];add(drone,finish,pos(j),2)
   tk=truck_move(a,k,start);serve(k,tk+cfg['service_s'],'truck') if k else None
   # At customer, measured return-leg conditions in this segment-constant execution model.
   if back is None or back[1]+cfg['handling_Wh']>B-cfg['reserve_Wh']:
    debit(finish,cfg['handling_Wh']);serve(j,finish,'drone_ground_recovery');events.append([round(finish,1),j,'land_hold_pickup_by_truck'])
    t=truck_move(k,j,max(tk+(cfg['service_s'] if k else 0),finish));a=j;t+=12
    add(drone,t,pos(j),2);add(truck,t,pos(j))
   else:
    serve(j,finish,'drone');legtrack(j,k,finish,back);td=finish+sum(back[0]);debit(td,back[1]+cfg['handling_Wh'])
    t=max(tk+(cfg['service_s'] if k else 0),td)+12;a=k;add(truck,t,pos(k));add(drone,t,pos(k),2);events.append([round(start,1),j,'sortie'])
   pend=pend[2:]
  else:
   events.append([round(t,1),j,reason]);startidx=len(truck);t=truck_move(a,j,t)
   for tt,x,y,z in truck[startidx:]:add(drone,tt,[x,y],2)
   if j:t+=cfg['service_s'];serve(j,t,'truck')
   add(truck,t,pos(j));add(drone,t,pos(j),2);a=j;pend.pop(0)
 if a!=0:
  n=len(truck);t=truck_move(a,0,t)
  for tt,x,y,z in truck[n:]:add(drone,tt,[x,y],2)
  depot_obs=observe_weather(case,t,pos(0));depot_obs.update(t_s=round(t,1),node=0,battery_Wh=round(B,2));weather_observations.append(depot_obs)
 assert len(done)==cfg['orders'] and Bmin>=cfg['reserve_Wh']-1e-6
 classes=Counter(o['weather_class'] for o in weather_observations)
 return dict(config_snapshot=dict(battery_Wh=cfg['battery_Wh'],reserve_Wh=cfg['reserve_Wh'],reserve_ratio=cfg['reserve_ratio'],payload_kg=cfg['payload_kg'],airspeed_mps=cfg['airspeed_mps'],wind_limit_mps=cfg['wind_limit_mps'],normal_wind_max_mps=cfg['normal_wind_max_mps'],empty_Wh_per_km=cfg['empty_Wh_per_km'],full_Wh_per_km=cfg['full_Wh_per_km'],service_s=cfg['service_s']),audit=audit,weather_observations=weather_observations,battery_swaps=battery_swaps,summary=dict(case=case,served=len(done),drone_collections=sum(s[1].startswith('drone') for s in tasks),ground_recoveries=sum(s[1]=='drone_ground_recovery' for s in tasks),battery_swaps=len(battery_swaps),normal_observations=classes['normal'],gust_observations=classes['gust'],truck_only_observations=classes['truck_only'],distance_rejections=sum(e[2]=='distance_reserve' for e in events),energy_rejections=sum(e[2]=='return_energy' for e in events),weather_or_clearance_rejections=sum(e[2]=='weather_or_clearance' for e in events),truck_km=round(km,2),minutes=round(t/60,2),energy_Wh=round(energy_used,2),final_Wh=round(B,2),late_minutes=round(late/60,2)),truck=truck,drone=drone,events=events,orders=tasks,battery=charges)
results={c:run(c) for c in ['truck','normal','gust','gust_milp']}
for c,d in results.items():
 (R/'results'/f'{c}.json').write_text(json.dumps(d,separators=(',',':')))
 print(d['summary'])
with (R/'results/summary.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=results['truck']['summary']);w.writeheader();w.writerows(d['summary'] for d in results.values())
(R/'data/orders.json').write_text(json.dumps([dict(id=j,node=nodes[n],xy=xy[n].tolist(),mass_kg=weights.get(j,0),deadline_s=round(deadlines.get(j,0),1)) for j,n in enumerate(stops)]))
