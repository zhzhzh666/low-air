from pathlib import Path
import json,math
R=Path(__file__).resolve().parent
cfg=json.loads((R/'config.json').read_text());orders=json.loads((R/'data/orders.json').read_text())
assert sum(o['mass_kg'] for o in orders)<=cfg['truck_capacity_kg']
assert abs(cfg['reserve_Wh']-cfg['battery_Wh']*cfg['reserve_ratio'])<1e-9
assert abs(cfg['usable_Wh']-(cfg['battery_Wh']-cfg['reserve_Wh']))<1e-9
assert cfg['wind_direction_count']==8 and cfg['normal_wind_max_mps']==8 and cfg['wind_limit_mps']==14
for case in ['truck','normal','gust','gust_milp']:
 d=json.loads((R/'results'/f'{case}.json').read_text())
 assert sorted(r[0] for r in d['orders'])==list(range(1,cfg['orders']+1))
 assert all(r[3]<=cfg['payload_kg'] for r in d['orders'] if 'drone' in r[1])
 for key in ['truck','drone','battery']:
  rows=d[key];assert all(a[0]<=b[0]+.001 for a,b in zip(rows,rows[1:])),key
 swap_times={round(s['t_s'],2) for s in d['battery_swaps']}
 for a,b in zip(d['battery'],d['battery'][1:]):
  if b[1]>a[1]+1e-6:
   assert round(b[0],2) in swap_times and abs(b[1]-cfg['battery_Wh'])<.01
 assert min(v for _,v in d['battery'])>=cfg['reserve_Wh']
 supplied=cfg['battery_Wh']+sum(cfg['battery_Wh']-s['before_Wh'] for s in d['battery_swaps'])
 assert abs(supplied-d['battery'][-1][1]-d['summary']['energy_Wh'])<.05
 assert abs(d['truck'][-1][1]-orders[0]['xy'][0])+abs(d['truck'][-1][2]-orders[0]['xy'][1])<.02
 assert all(a['forecast_issue_s']<=a['t_s']+.1 for a in d['audit'])
 assert all(0<=o['speed_mps']<=cfg['wind_limit_mps'] for o in d['weather_observations'])
 assert all(o['direction'] in ['静风','东','东北','北','西北','西','西南','南','东南'] for o in d['weather_observations'])
 assert all(a['sortie_distance_m']<=a['safe_distance_budget_m']+.2 for a in d['audit'] if a['decision']=='launch')
 for s in d['battery_swaps']:
  assert s['before_Wh']<=cfg['battery_Wh']*cfg['battery_swap_threshold_ratio']+.01
  assert abs(s['after_Wh']-cfg['battery_Wh'])<.01
 print(case,'orders, payload, eight-direction wind, distance reserve, battery swap and depot: PASS')
