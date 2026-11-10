"""Reproducible figures from executed trajectories, never schematic route claims."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap

COLORS={"truck_only":"#606975","prior":"#2563a6","random_query":"#e49b27","entropy_query":"#8e64b5","voi_query":"#0c8b75","oracle":"#ca5261"}
plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"white"})

def save(fig,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=160,bbox_inches="tight"); plt.close(fig)

def route_compare(ep,baseline,path):
    fig,axes=plt.subplots(1,2,figsize=(13,6),layout="constrained")
    for ax,e in zip(axes,[baseline,ep]):
        m=e.config["map"]; size=m["size_km"]; rows,cols=m["weather_grid_rows"],m["weather_grid_cols"]
        inst=e.instance; coords=inst.coords
        for r in range(rows):
            for c in range(cols):
                ax.add_patch(plt.Rectangle((c*size/cols,r*size/rows),size/cols,size/rows,facecolor="#f4f7fb",edgecolor="#b8c7d8",lw=.7))
                ax.text((c+.06)*size/cols,(r+.92)*size/rows,f"R{r*cols+c}",color="#98a5b3",fontsize=8)
        for edge in e.truck_edges:
            p=np.array(coords[edge["origin"]]); q=np.array(coords[edge["destination"]]); q=p+edge.get("fraction",1)*(q-p)
            ax.annotate("",xy=q,xytext=p,arrowprops=dict(arrowstyle="->",color="#2465a6",lw=1.6,alpha=.8))
        for a in e.sorties:
            p,j,k=[np.array(coords[a[v]]) for v in ("launch","customer","recover")]
            ax.plot([p[0],j[0],k[0]],[p[1],j[1],k[1]],"--",color="#dc643f",lw=1.8)
            ax.scatter(*p,marker="^",s=90,facecolors="none",edgecolors="#dc643f",zorder=5)
            ax.scatter(*k,marker="v",s=90,facecolors="none",edgecolors="#6d3ba1",zorder=5)
            ax.text(j[0],j[1]-.23,f"L{a['launch']} / R{a['recover']}",fontsize=6,color="#a54527",ha="center")
        for j,customer in inst.customers.items():
            x,y=customer.xy; ax.scatter(x,y,s=35,c="#ffc857",edgecolors="#333333",zorder=4); ax.annotate(str(j),(x,y),xytext=(5,5),textcoords="offset points",fontsize=8)
        ax.scatter(*coords[inst.start],marker="s",s=85,c="#182e45",zorder=6)
        ax.set(xlim=(-.1,size+.1),ylim=(-.1,size+.1),xlabel="x (km)",ylabel="y (km)",title=f"{e.metrics['policy']} | {e.metrics['completion_time_min']:.1f} min | cost {e.metrics['total_cost']:.1f}"); ax.set_aspect("equal")
    fig.legend(handles=[Line2D([0],[0],color="#2465a6",label="Truck (Euclidean road proxy x 1.3)"),Line2D([0],[0],color="#dc643f",ls="--",label="Drone: empty then loaded"),Line2D([0],[0],marker="^",color="#dc643f",ls="",label="Launch"),Line2D([0],[0],marker="v",color="#6d3ba1",ls="",label="Recovery")],loc="outside lower center",ncol=4,fontsize=9)
    fig.suptitle(f"Synthetic map | seed {ep.metrics['seed']} | customer numbers; start/end share depot")
    save(fig,path)

def weather_timeline(ep,path):
    step=ep.config["simulation"]["weather_step_min"]; end=ep.config["simulation"]["duration_min"]
    fig,ax=plt.subplots(figsize=(11,4.7),layout="constrained")
    n=int(end//step)+1; data=ep.truth[:n].T
    im=ax.imshow(data,aspect="auto",origin="lower",interpolation="nearest",cmap=ListedColormap(["#cce9df","#ffd77b","#d96868"]),vmin=-.5,vmax=2.5,extent=(0,n*step,-.5,len(data)-.5))
    for q in ep.queries:
        ax.plot([q["start"],q["arrival"]],[q["region"]]*2,color="#1c3154",lw=2)
        ax.plot(q["start"],q["region"],"o",color="#17345f",ms=5)
        if q["arrival"]<=ep.metrics["completion_time_min"]: ax.plot(q["arrival"],q["region"],"|",color="black",ms=12)
    ax.axvline(ep.metrics["completion_time_min"],color="#253d58",ls="--",lw=1,label="episode end")
    ax.set(xlim=(0,end),xlabel="time (min)",ylabel="weather region",yticks=range(len(data)),title=f"Synthetic hidden wind audit | {ep.metrics['policy']} | dots=query; bars=delivered report")
    cb=fig.colorbar(im,ax=ax,ticks=[0,1,2],pad=.02); cb.ax.set_yticklabels(["calm 2 m/s","moderate 6 m/s","strong 11 m/s"])
    if not ep.queries: ax.text(.01,1.02,"No query selected",transform=ax.transAxes,color="#526172")
    save(fig,path)

def vehicle_gantt(ep,path):
    fig,ax=plt.subplots(figsize=(11,3.8),layout="constrained"); end=ep.metrics["completion_time_min"]
    for e in ep.truck_edges: ax.broken_barh([(e["start"],e["end"]-e["start"])],(-.25,.5),facecolors="#3b7daf")
    starts={}
    for event in ep.events:
        typ=event["event_type"]; t=event["event_time_min"]
        if typ in ("TRUCK_SERVICE_START","TRUCK_WAIT_START"): starts[typ]=(t,event.get("reason","service"))
        match={"TRUCK_PICKUP":"TRUCK_SERVICE_START","TRUCK_WAIT_END":"TRUCK_WAIT_START"}.get(typ)
        if match and match in starts:
            s,reason=starts.pop(match); ax.broken_barh([(s,t-s)],(-.25,.5),facecolors="#263f59" if match=="TRUCK_SERVICE_START" else "#e6a94b")
    for s,reason in starts.values(): ax.broken_barh([(s,end-s)],(-.25,.5),facecolors="#e6a94b")
    for a in ep.sorties:
        finish=min(end,a["end"] if a["end"] is not None else end)
        ax.broken_barh([(a["start"],max(0,min(a["land"],end)-a["start"]))],(.75,.5),facecolors="#23977c")
        if a["land"]<finish: ax.broken_barh([(a["land"],finish-a["land"])],(.75,.5),facecolors="#98c6ad")
        ax.text(a["start"],1.35,f"{a['launch']}->{a['customer']}->{a['recover']}",fontsize=7)
    for q in ep.queries: ax.broken_barh([(q["start"],max(0,min(q["arrival"],end)-q["start"]))],(1.75,.5),facecolors="#9268b1")
    ax.set(yticks=[0,1,2],yticklabels=["Truck","Drone","Weather query"],xlabel="time (min)",xlim=(0,max(1,end)),title="Executed actions | synthetic simulation"); ax.grid(axis="x",alpha=.2)
    fig.legend(handles=[Line2D([0],[0],color=c,lw=6,label=l) for c,l in [("#3b7daf","Driving"),("#263f59","Truck service"),("#e6a94b","Truck wait"),("#23977c","Drone sortie"),("#98c6ad","Landing/recovery"),("#9268b1","Query pending")]],loc="outside lower center",ncol=3,fontsize=8)
    save(fig,path)

def episode_outputs(ep,baseline,outdir):
    import pandas as pd
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    route_compare(ep,baseline,outdir/"route_compare.png"); weather_timeline(ep,outdir/"weather_timeline.png"); vehicle_gantt(ep,outdir/"vehicle_gantt.png")
    pd.DataFrame(ep.events).to_csv(outdir/"events.csv",index=False)
    np.save(outdir/"weather_audit.npy",ep.truth)
    data={"metrics":ep.metrics,"customers":{j:vars(v) for j,v in ep.instance.customers.items()},"plans":ep.plans,"truck_edges":ep.truck_edges,"sorties":ep.sorties,"queries":ep.queries,"voi":ep.voi}
    (outdir/"episode.json").write_text(json.dumps(data,indent=2,allow_nan=False),encoding="utf-8")
    from .map_view import export_map
    export_map(ep,baseline,outdir/"map_replay.html")

def experiment_plots(raw,outdir):
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    main=raw[raw.experiment=="main"] if "main" in set(raw.experiment) else raw
    policy_order=[p for p in COLORS if p in set(main.policy)]
    fig,axes=plt.subplots(1,len(sorted(main.n_customers.unique())),figsize=(13,4.5),squeeze=False,layout="constrained")
    for ax,n in zip(axes[0],sorted(main.n_customers.unique())):
        for p in policy_order:
            d=main[(main.n_customers==n)&(main.policy==p)]; g=d.groupby("budget").total_cost
            m=g.mean(); se=g.std().fillna(0)/np.sqrt(g.count()); ax.errorbar(m.index,m,yerr=1.96*se,marker="o",ms=3,label=p,color=COLORS[p],capsize=2)
        ax.set(title=f"{n} customers",xlabel="query budget",ylabel="mean cost (synthetic units)"); ax.grid(alpha=.2)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc="outside lower center",ncol=6,fontsize=8)
    fig.suptitle("Synthetic policy comparison | 30 seeds/cell | marginal 95% normal CI; paired bootstrap in CSV")
    save(fig,outdir/"policy_cost.png")
    fig,axes=plt.subplots(1,len(sorted(main.n_customers.unique())),figsize=(13,4.5),squeeze=False,layout="constrained")
    for ax,n in zip(axes[0],sorted(main.n_customers.unique())):
        for p in policy_order:
            g=main[(main.n_customers==n)&(main.policy==p)].groupby("budget").completion_time_min; m=g.mean(); se=g.std().fillna(0)/np.sqrt(g.count())
            ax.errorbar(m.index,m,yerr=1.96*se,marker="o",ms=3,color=COLORS[p],label=p,capsize=2)
        ax.set(title=f"{n} customers",xlabel="query budget",ylabel="mean episode time (min)"); ax.grid(alpha=.2)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc="outside lower center",ncol=6,fontsize=8); fig.suptitle("Synthetic time / information trade-off | truncated runs included and flagged in CSV")
    save(fig,outdir/"time_vs_query_budget.png")
    heat=raw[(raw.experiment=="budget_delay")&(raw.policy=="voi_query")]
    if not heat.empty:
        h=heat.pivot_table(index="delay_min",columns="budget",values="total_cost",aggfunc="mean")
        fig,ax=plt.subplots(figsize=(7,4.5),layout="constrained"); im=ax.imshow(h.values,aspect="auto",origin="lower",cmap="viridis")
        ax.set_xticks(range(len(h.columns)),h.columns); ax.set_yticks(range(len(h.index)),h.index)
        for i in range(len(h.index)):
            for j in range(len(h.columns)): ax.text(j,i,f"{h.iloc[i,j]:.3f}",ha="center",va="center",color="black" if im.norm(h.iloc[i,j])>.55 else "white")
        ax.set(xlabel="query budget",ylabel="report delay (min)",title=f"Synthetic VOI cost | n={heat.n_customers.iloc[0]} | {heat.seed.nunique()} seeds/cell"); fig.colorbar(im,ax=ax,label="mean cost"); save(fig,outdir/"budget_delay_heatmap.png")
    fig,ax=plt.subplots(figsize=(8,5),layout="constrained")
    for p in policy_order:
        d=main[main.policy==p].groupby(["n_customers","budget"])[["completion_time_min","total_cost"]].mean()
        ax.scatter(d.completion_time_min,d.total_cost,color=COLORS[p],label=p,marker="x" if p=="oracle" else "o",s=35)
    ax.set(xlabel="mean episode time (min)",ylabel="mean total cost",title="Synthetic time / cost points | oracle is an unfair heuristic reference"); ax.legend(fontsize=8); ax.grid(alpha=.2); save(fig,outdir/"pareto_time_cost.png")
