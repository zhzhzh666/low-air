"""Restricted rolling MILP: directed arcs over a fixed customer sequence, optional paired sorties."""
import numpy as np
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import lil_matrix
def choose(seq,t,B,issue,T,stops,road,pos,flight,case,weights,deadlines,cfg,dist,xy):
 seq=seq[:15];n=len(seq);sv=cfg['service_s'];big=100000
 safe_ground=max(.1,cfg['airspeed_mps']-cfg['wind_limit_mps'])
 loaded_power=cfg['full_Wh_per_km']*cfg['airspeed_mps']*3.6
 safe_distance=safe_ground*(max(0,B-cfg['reserve_Wh'])/loaded_power)*3600
 ref=[t]
 for a,k in zip(seq,seq[1:]):ref.append(ref[-1]+T[a,stops[k]]+(sv if k else 0))
 arcs=[]
 for u in range(n-1):
  a,k=seq[u:u+2]
  def km(a,k):
   ns=road(a,k);return sum(dist(xy[i],xy[j]) for i,j in zip(ns,ns[1:]))/1000
  drive=T[a,stops[k]]
  arcs.append((u,u+1,drive+(sv if k else 0),km(a,k),0,[(u+1,drive+sv)] if k else []))
  if u+2>=n:continue
  j,k=seq[u+1:u+3]
  if not j or weights[j]>cfg['payload_kg']:continue
  if dist(pos(a),pos(j))+dist(pos(j),pos(k))>safe_distance:continue
  samples=[]
  for noise in [-2,-1,0,1,2]:
   o=flight(a,j,0,ref[u]+15,case,issue,noise)
   if not o:break
   b=flight(j,k,weights[j],ref[u]+15+sum(o[0])+sv,case,issue,noise)
   if not b:break
   samples.append((o[1]+b[1]+cfg['handling_Wh'],sum(o[0])+sv+sum(b[0]),sum(o[0])+sv))
  if len(samples)!=5:continue
  E,fly,pick=map(max,zip(*samples));drive=T[a,stops[k]]
  if E>B-cfg['reserve_Wh']:continue
  tasks=[(u+1,15+pick)]+([(u+2,15+drive+sv)] if k else [])
  arcs.append((u,u+2,15+max(fly,drive+(sv if k else 0))+12,km(a,k),E,tasks))
 m=len(arcs);N=m+2*n;cost=np.zeros(N);cost[m+n-1]=cfg['yuan_per_min']/60
 for u in range(1,n):cost[m+n+u]=cfg['late_yuan_per_min']/60
 rows=[];lb=[];ub=[]
 def row(coeff,l,h):rows.append(coeff);lb.append(l);ub.append(h)
 for u in range(n):
  flow={i:(1 if a[0]==u else -1) for i,a in enumerate(arcs) if u in a[:2]}
  value=1 if u==0 else -1 if u==n-1 else 0;row(flow,value,value)
 row({i:a[4] for i,a in enumerate(arcs)},0,B-cfg['reserve_Wh'])
 for i,(u,v,dt,d,e,tasks) in enumerate(arcs):
  cost[i]=cfg['yuan_per_km']*d+cfg['yuan_per_Wh']*e
  row({m+v:1,m+u:-1,i:-big},dt-big,np.inf)
  for j,offset in tasks:row({m+n+j:1,m+u:-1,i:-big},offset-deadlines[seq[j]]-big,np.inf)
 A=lil_matrix((len(rows),N))
 for r,co in enumerate(rows):
  for k,v in co.items():A[r,k]=v
 lo=np.zeros(N);hi=np.full(N,big,dtype=float);hi[:m]=1;lo[m]=hi[m]=t
 ans=milp(cost,integrality=np.r_[np.ones(m),np.zeros(2*n)],bounds=Bounds(lo,hi),constraints=LinearConstraint(A.tocsr(),lb,ub),options={'time_limit':1.5,'mip_rel_gap':.03})
 if ans.x is None:raise RuntimeError(ans.message)
 return any(u==0 and v==2 and ans.x[i]>.5 for i,(u,v,*_) in enumerate(arcs))
