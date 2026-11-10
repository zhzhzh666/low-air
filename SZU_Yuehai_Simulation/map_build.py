"""Convert OSM API XML tiles to local metre coordinates. Run with Python 3."""
import xml.etree.ElementTree as ET
import glob,math,json,os,re,sys,hashlib
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cx,cy=113.933,22.532
def local(lon,lat):return [round((lon-cx)*111320*math.cos(math.radians(cy)),2),round((lat-cy)*110780,2)]
nodes={}; ways={}; versions=set()
for file in sorted(glob.glob(sys.argv[1]+'/*.osm')):
 root=ET.parse(file).getroot()
 for e in root.findall('node'):nodes[e.get('id')]=local(float(e.get('lon')),float(e.get('lat')))
 for e in root.findall('way'):
  ways[e.get('id')]=([n.get('ref') for n in e.findall('nd')],{t.get('k'):t.get('v') for t in e.findall('tag')})
roads=[];buildings=[];land=[];used=set()
allowed={'primary','secondary','tertiary','residential','service','unclassified','living_street','trunk','primary_link','secondary_link','tertiary_link','trunk_link','motorway','motorway_link'}
for id,(ids,t) in ways.items():
 if not all(i in nodes for i in ids) or len(ids)<2:continue
 pts=[nodes[i] for i in ids]
 inside=lambda p:abs(p[0])<=2058 and abs(p[1])<=1994
 if t.get('highway') in allowed and t.get('access') not in ['private','no'] and t.get('motor_vehicle') not in ['private','no']:
  part=[]
  for n in ids+[None]:
   if n and inside(nodes[n]):part.append(n);continue
   if len(part)>1:
    roads.append([part,t['highway'],t.get('oneway','yes' if t.get('junction')=='roundabout' or t['highway']=='motorway' else 'no'),t.get('name',''),id]);used.update(part)
   part=[]
 if ids[0]!=ids[-1] or len(ids)<4 or not all(map(inside,pts)):continue
 if 'building' in t and t['building']!='no':
  h=None
  for tag,mult in [('height',1),('building:levels',3.2)]:
   m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:m)?',t.get(tag,'').strip())
   if m and float(m[1])>0:h=float(m[1])*mult;src=tag;break
  if h is None:
   h={'apartments':29,'residential':19,'office':35,'industrial':12,'university':18,'dormitory':22,'commercial':24,'roof':4}.get(t['building'],16);src='type estimate'
  buildings.append([pts[:-1],round(h,1),src,id,t.get('name','')])
 elif t.get('natural')=='water' or t.get('leisure') in ['park','pitch','garden'] or t.get('landuse') in ['grass','forest','meadow'] or t.get('natural')=='wood':
  land.append([pts[:-1],'water' if t.get('natural')=='water' else 'green'])
result=dict(center=[cx,cy],nodes={n:nodes[n] for n in used},roads=roads,buildings=buildings,land=land)
(ROOT/'data/map.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
print(len(roads),len(used),len(buildings),len(land),Counter(b[2] for b in buildings))
