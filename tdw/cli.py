import argparse
import json
from pathlib import Path
from .models import load_config
from .simulator import Simulator

def seeds_from_string(value):
    if ":" in value:
        a,b=map(int,value.split(":")); return list(range(a,b+1))
    return [int(x) for x in value.split(",")]

def main():
    parser=argparse.ArgumentParser(description="Synthetic truck-drone pickup under limited weather observations")
    parser.add_argument("command",choices=["run","compare","sweep"])
    parser.add_argument("--config",default="configs/base.yaml")
    parser.add_argument("--policy",default="prior")
    parser.add_argument("--policies",default="truck_only,prior,random_query,entropy_query,voi_query,oracle")
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--seeds",default="0:9")
    parser.add_argument("--output",default=None)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--quick",action="store_true",help="Small main matrix; labels itself a smoke run")
    args=parser.parse_args(); cfg=load_config(args.config)
    if args.command=="run":
        from .plots import episode_outputs
        out=Path(args.output or "outputs/single"); ep=Simulator(cfg,args.policy,args.seed).run()
        base=ep if args.policy=="truck_only" else Simulator(cfg,"truck_only",args.seed).run()
        episode_outputs(ep,base,out)
        (out/"resolved_config.json").write_text(json.dumps(cfg,indent=2),encoding="utf-8")
        print(json.dumps(ep.metrics,indent=2,allow_nan=False))
    elif args.command=="compare":
        from .experiments import compare,summarize
        out=Path(args.output or "outputs/sanity"); raw,episodes=compare(cfg,seeds_from_string(args.seeds),args.policies.split(","),out)
        summarize(raw,out); print(raw.groupby("policy")[["total_cost","completion_time_min","query_count","drone_sortie_count","infeasible_flag"]].mean().to_string())
    else:
        from .experiments import sweep
        raw,summary=sweep(cfg,seeds_from_string(args.seeds),Path(args.output or "outputs/experiments"),args.policies.split(","),quick=args.quick,workers=args.workers)
        print(f"Completed {len(raw)} episodes; {int(raw.infeasible_flag.sum())} flagged incomplete. Outputs: {args.output or 'outputs/experiments'}")

if __name__=="__main__": main()
