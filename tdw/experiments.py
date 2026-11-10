"""Batch experiment runner with common instances/weather and paired bootstrap."""
from pathlib import Path
import copy, json, hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from .models import load_config
from .simulator import Simulator
from .plots import experiment_plots

POLICIES=["truck_only","prior","random_query","entropy_query","voi_query","oracle"]
METRICS=["total_cost","completion_time_min","truck_km","drone_km","drone_energy_Wh","query_count","query_cost","query_wait_min","drone_sortie_count","truck_wait_min","on_time_rate","total_lateness_min","incident_count","canceled_sortie_count","tasks_completed","infeasible_flag","planning_cpu_sec","total_wall_sec"]

def _episode(cfg,policy,seed,experiment,condition):
    ep=Simulator(cfg,policy,seed).run(); d=dict(ep.metrics); d.update(experiment=experiment,condition=condition,budget=cfg["observation"]["max_queries"],delay_min=cfg["observation"]["delay_min"],accuracy=cfg["observation"]["correct_classification_probability"],strong_prior=cfg["weather"]["initial_prob"][2],epsilon=cfg["planning"]["unsafe_probability_tolerance"],order_hash=ep.metrics["order_hash"],weather_hash=ep.metrics["weather_hash"])
    return d,ep

def _paired_ci(raw,outdir,draws=2000,seed=90210):
    rows=[]; rng=np.random.default_rng(seed)
    if raw.empty: return pd.DataFrame()
    for keys,g in raw.groupby(["experiment","condition","n_customers","budget"],dropna=False):
        if "prior" not in set(g.policy) or "voi_query" not in set(g.policy): continue
        a=g[g.policy=="voi_query"].set_index("seed"); b=g[g.policy=="prior"].set_index("seed"); common=sorted(set(a.index)&set(b.index));
        if not common: continue
        for metric in ["total_cost","completion_time_min","query_count","drone_sortie_count","incident_count"]:
            x=(a.loc[common,metric].to_numpy(float)-b.loc[common,metric].to_numpy(float)); n=len(x); idx=rng.integers(0,n,size=(draws,n)); boots=x[idx].mean(axis=1)
            rows.append(dict(experiment=keys[0],condition=keys[1],n_customers=keys[2],budget=keys[3],metric=metric,policy_a="voi_query",policy_b="prior",n=n,mean_change=float(x.mean()),relative_change=float(x.mean()/max(abs(b.loc[common,metric].mean()),1e-9)),ci_low=float(np.quantile(boots,.025)),ci_high=float(np.quantile(boots,.975)),bootstrap_seed=seed,bootstrap_draws=draws))
    out=pd.DataFrame(rows); out.to_csv(Path(outdir)/"paired_ci.csv",index=False); return out

def run_experiment(config,policies,seeds,outdir,experiment="main",condition="base",extra=None):
    cfg=copy.deepcopy(config); extra=extra or {}
    for section,vals in extra.items(): cfg.setdefault(section,{}).update(vals)
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    rows=[]; episodes={}
    for seed in seeds:
        # Each policy receives an independent simulator wrapper but the keyed instance/weather are identical.
        for p in policies:
            d,ep=_episode(cfg,p,int(seed),experiment,condition); rows.append(d); episodes[(p,int(seed))]=ep
    return pd.DataFrame(rows),episodes

def compare(config,seeds,policies,outdir):
    raw,eps=run_experiment(config,policies,seeds,outdir,"compare","base")
    raw.to_csv(Path(outdir)/"compare_raw.csv",index=False)
    return raw,eps

def summarize(raw,outdir):
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    cols=[c for c in ["total_cost","completion_time_min","query_count","drone_sortie_count","infeasible_flag"] if c in raw]
    out=raw.groupby("policy")[cols].agg(["mean","std","count"]).reset_index()
    out.columns=["_".join(x).rstrip("_") if isinstance(x,tuple) else x for x in out.columns]
    out.to_csv(outdir/"summary.csv",index=False)
    return out

def _worker(job):
    key,cfg,policy,seed=job
    return key,Simulator(cfg,policy,seed).run().metrics

def _key(cfg,policy,seed):
    # Pure policies ignore all observation parameters; zero budget query policies
    # execute exactly the prior policy. Reuse identical simulations transparently.
    cfg=copy.deepcopy(cfg)
    if policy in ["random_query","entropy_query","voi_query"] and cfg["observation"]["max_queries"]==0: policy="prior"
    if policy in ["truck_only","prior","oracle"]: cfg["observation"]={}
    return hashlib.sha256(json.dumps([cfg,policy,seed],sort_keys=True).encode()).hexdigest()

def sweep(config,seeds,outdir,policies=None,quick=False,workers=1):
    policies=policies or POLICIES; all_rows=[]; first={}; conditions=[]
    ns=[8,15,25] if not quick else [8]; budgets=[0,2,4,8] if not quick else [0,4]
    for n in ns:
        for b in budgets:
            cfg=copy.deepcopy(config); cfg["map"]["n_customers"]=n; cfg["observation"]["max_queries"]=b
            conditions.append(("main",f"n{n}_b{b}",cfg))
    # One-factor sensitivity cells, reusing requested seed count.
    for acc in [.70,.85,.95]:
        cfg=copy.deepcopy(config); cfg["observation"]["correct_classification_probability"]=acc; cfg["map"]["n_customers"]=8; cfg["observation"]["max_queries"]=4
        conditions.append(("accuracy",f"accuracy_{acc:.2f}",cfg))
    for delay in [0,3,8]:
        cfg=copy.deepcopy(config); cfg["observation"]["delay_min"]=delay; cfg["map"]["n_customers"]=8; cfg["observation"]["max_queries"]=4
        conditions.append(("delay",f"delay_{delay:g}",cfg))
    for strong in [.10,.25,.40]:
        cfg=copy.deepcopy(config); cfg["weather"]["initial_prob"]=[1-strong-.25,.25,strong]; cfg["map"]["n_customers"]=8; cfg["observation"]["max_queries"]=4
        conditions.append(("strong_prior",f"strong_{strong:.2f}",cfg))
    for eps in [.05,.10,.20]:
        cfg=copy.deepcopy(config); cfg["planning"]["unsafe_probability_tolerance"]=eps; cfg["map"]["n_customers"]=8; cfg["observation"]["max_queries"]=4
        conditions.append(("epsilon",f"epsilon_{eps:.2f}",cfg))
    # Explicit budget x delay grid required by the specification.
    for b in [0,2,4,8]:
        for delay in [0,3,8]:
            cfg=copy.deepcopy(config); cfg["map"]["n_customers"]=8; cfg["observation"]["max_queries"]=b; cfg["observation"]["delay_min"]=delay
            conditions.append(("budget_delay",f"b{b}_d{delay}",cfg))
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    jobs={}; manifest=[]
    for ex,condition,cfg in conditions:
        for seed in seeds:
            for policy in policies:
                key=_key(cfg,policy,int(seed)); reused=key in jobs
                jobs.setdefault(key,(key,cfg,policy,int(seed)))
                manifest.append(dict(key=key,experiment=ex,condition=condition,policy=policy,seed=int(seed),n_customers=cfg["map"]["n_customers"],budget=cfg["observation"]["max_queries"],delay_min=cfg["observation"]["delay_min"],accuracy=cfg["observation"]["correct_classification_probability"],strong_prior=cfg["weather"]["initial_prob"][2],epsilon=cfg["planning"]["unsafe_probability_tolerance"],reused_episode=int(reused)))
    (outdir/"condition_configs.json").write_text(json.dumps([{ "experiment":ex,"condition":cn,"config":cf} for ex,cn,cf in conditions],indent=2),encoding="utf-8")
    (outdir/"protocol.json").write_text(json.dumps(dict(seeds=list(seeds),policies=policies,unique_simulations=len(jobs),design_rows=len(manifest),quick=quick,workers=workers,bootstrap_draws=2000,bootstrap_seed=90210,reuse="Identical stochastic simulations reused across conditions; pure policies ignore observation settings; budget-zero query policies equal prior",completion="All horizon-truncated episodes remain in tables with infeasible_flag=1; metrics describe executed partial trajectory"),indent=2),encoding="utf-8")
    cache={}; cachepath=outdir/"episode_cache.jsonl"
    if cachepath.exists():
        for line in cachepath.read_text(encoding="utf-8").splitlines():
            try:
                item=json.loads(line); cache[item["key"]]=item["metrics"]
            except json.JSONDecodeError: pass
    pending=[job for key,job in jobs.items() if key not in cache]
    print(f"Design {len(manifest)} rows; {len(jobs)} unique episodes; {len(pending)} remaining; workers={workers}",flush=True)
    with cachepath.open("a",encoding="utf-8") as f, ProcessPoolExecutor(max_workers=max(1,workers)) as pool:
        futures=[pool.submit(_worker,job) for job in pending]
        for i,future in enumerate(as_completed(futures),1):
            key,metrics=future.result(); cache[key]=metrics; f.write(json.dumps(dict(key=key,metrics=metrics),allow_nan=False)+"\n"); f.flush()
            if i%50==0 or i==len(pending): print(f"Computed {i}/{len(pending)}",flush=True)
    for row in manifest:
        d=dict(cache[row["key"]]); d.update(row); all_rows.append(d)
    raw=pd.DataFrame(all_rows); raw.to_csv(outdir/"raw_results.csv",index=False)
    summary=raw.groupby(["experiment","condition","policy","n_customers","budget"],dropna=False)[METRICS].agg(["mean","std","count"]).reset_index(); summary.columns=["_".join(x).rstrip("_") if isinstance(x,tuple) else x for x in summary.columns]; summary.to_csv(Path(outdir)/"summary.csv",index=False)
    _paired_ci(raw,outdir)
    experiment_plots(raw,outdir)
    (Path(outdir)/"resolved_config.json").write_text(json.dumps(config,indent=2,ensure_ascii=False),encoding="utf-8")
    return raw,summary
