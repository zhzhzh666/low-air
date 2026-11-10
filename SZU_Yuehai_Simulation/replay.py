"""Create an oblique, instrumented replay of the gust event from recorded XYZ telemetry."""
import json,math,bisect,subprocess,os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent
m=json.loads((R/'data/map.json').read_text());d=json.loads((R/'results/gust.json').read_text());orders=json.loads((R/'data/orders.json').read_text());cfg=json.loads((R/'config.json').read_text())
font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def F(s):return ImageFont.truetype(font,s)
f12,f15,f18,f24,f32=[F(s) for s in (13,15,18,24,32)]
W,H=1200,740;background=(237,240,232);ink='#172f35';blue='#146cb4';amber='#c2531b'
event=next(e for e in d['events'] if e[2]=='land_hold_pickup_by_truck');evtime,j,_=event
launch=next(a for a in d['audit'] if a['customer']==j and a['decision']=='launch');begin=launch['t_s'];end=next(a['t_s'] for a in d['audit'] if a['t_s']>evtime)
def at(rows,t):
 i=bisect.bisect_right([r[0] for r in rows],t)-1;i=max(0,i);a=rows[i];b=rows[min(len(rows)-1,i+1)];r=min(1,max(0,(t-a[0])/max(.00001,b[0]-a[0])))
 return [x+(y-x)*r for x,y in zip(a[1:],b[1:])]
tt=d['truck'];dd=d['drone'];bb=d['battery'];pts=[a[1:3] for a in tt+dd if begin<=a[0]<=end]+[at(tt,begin)[:2]]
def uv(x,y):return x*.9+y*.435,-(-x*.435+y*.9)*.7
us,vs=zip(*(uv(*p) for p in pts));cu=(min(us)+max(us))/2;cv=(min(vs)+max(vs))/2;s=min(730/max(600,max(us)-min(us)),465/max(400,max(vs)-min(vs)))
def proj(x,y,z=0):
 u,v=uv(x,y);return (int(445+(u-cu)*s),int(410+(v-cv-z*.72)*s))
base=Image.new('RGB',(W,H),background);g=ImageDraw.Draw(base)
for poly,typ in m['land']:g.polygon([proj(*p) for p in poly],fill='#a9d2d5' if typ=='water' else '#c0d4b6')
for ids,cl,*_ in m['roads']:
 points=[proj(*m['nodes'][n]) for n in ids];g.line(points,fill='#c3c4b9',width=max(2,int(s*(12 if cl in ['primary','trunk','motorway'] else 5))));g.line(points,fill='#faf9ef',width=max(1,int(s*(9 if cl in ['primary','trunk','motorway'] else 3))))
for p,h,src,*_ in sorted(m['buildings'],key=lambda b:sum(uv(*v)[1] for v in b[0])/len(b[0])):
 lo=[proj(*v) for v in p];hi=[proj(*v,h) for v in p]
 if max(x for x,y in lo)<0 or min(x for x,y in lo)>890:continue
 for i in range(len(p)):
  k=i-1;g.polygon([lo[k],lo[i],hi[i],hi[k]],fill=('#99aba6' if p[i][0]>p[k][0] else '#acb9b3'))
 g.polygon(hi,fill='#d4ded5' if src=='type estimate' else '#e1e5db',outline='#a5b4ae')
def mm(t):return '%02d:%02d'%(t//60,t%60)
def trail(g,rows,t,color):
 pts=[proj(*at(rows,begin))]+[proj(*a[1:]) for a in rows if begin<a[0]<t]+[proj(*at(rows,t))];g.line(pts,fill=color,width=3)
def draw(t):
 im=base.copy();g=ImageDraw.Draw(im);trail(g,tt,t,blue);trail(g,dd,t,amber)
 goal=proj(*orders[j]['xy']);g.ellipse((goal[0]-9,goal[1]-9,goal[0]+9,goal[1]+9),outline=amber,width=2)
 for rr,col,tag,dy in [(tt,blue,'卡车',20),(dd,amber,'无人机',-34)]:
  x,y=proj(*at(rr,t));g.ellipse((x-6,y-6,x+6,y+6),fill=col,outline='white',width=2);g.rounded_rectangle((x+8,y+dy,x+76,y+dy+24),5,fill=col);g.text((x+13,y+dy),tag,font=f15,fill='white')
 g.rectangle((0,0,W,83),fill='#15343a');g.text((25,9),'深圳大学粤海校区周边',font=f32,fill='white');g.text((27,52),'联合取件仿真  /  实际地图轮廓 · 合成阵风压力测试',font=f15,fill='#b4d1ca')
 g.rectangle((875,83,W,H),fill='#f9faf5');g.line((875,83,875,H),fill='#bdc7bd')
 def txt(y,v,ff=f18,c=ink):g.text((900,y),v,font=ff,fill=c)
 txt(111,'订单 %02d  /  地面接回'%j,f24);txt(162,'仿真钟',f15);txt(185,mm(t),f32)
 energy=at(bb,t)[0];txt(253,'剩余电量 · Wh',f15);txt(276,'%.1f'%energy,f32);g.rectangle((900,333,1160,341),fill='#dde4db');g.rectangle((900,333,900+260*energy/cfg['battery_Wh'],341),fill=amber);txt(357,'安全储备  %d Wh'%cfg['reserve_Wh'],f15)
 txt(414,'无人机相对地面高度',f15);txt(439,'%.0f m'%at(dd,t)[2],f24)
 status='取件与飞行' if t<evtime else ('已在客户点落地等待' if t<end-12 else '卡车接回无人机')
 txt(502,'当前状态',f15);txt(528,status,f18,amber);txt(600,'蓝色  卡车道路轨迹',f15,blue);txt(628,'橙色  无人机轨迹',f15,amber)
 g.rectangle((0,695,875,H),fill='#e5eae0');g.text((22,704),'© OpenStreetMap contributors   |   局部斜视图   ·   轨迹为叠加显示，电量为记录点间插值',font=f12,fill=ink)
 return im
fps=15;n=300
proc=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-c:v','libx264','-threads','3','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(R/'gust_recovery.mp4')],stdin=subprocess.PIPE)
for frm in range(n):proc.stdin.write(draw(begin+(end-begin)*frm/(n-1)).tobytes())
proc.stdin.close();assert proc.wait()==0
