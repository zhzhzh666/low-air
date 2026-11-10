"""Audit saved experiments and generate a concise, data-derived research note."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .experiments import METRICS

def audit(outdir="outputs/experiments"):
    outdir=Path(outdir); r=pd.read_csv(outdir/"raw_results.csv"); ci=pd.read_csv(outdir/"paired_ci.csv")
    assert len(r)>0 and np.isfinite(r[METRICS].to_numpy()).all(),"Nonfinite required metric"
    assert not r.duplicated(["experiment","condition","seed","policy"]).any()
    assert (r.query_count<=r.budget).all() and (r.query_count>=0).all()
    assert (r.completion_time_min<=180+1e-8).all()
    assert (r.loc[r.infeasible_flag==0,"tasks_completed"]==r.loc[r.infeasible_flag==0,"n_customers"]).all()
    hashes=r.groupby(["experiment","condition","seed"])[["order_hash","weather_hash"]].nunique()
    assert (hashes==1).all().all(),"Unpaired exogenous scenarios"
    main=r[r.experiment=="main"]
    sizes=main.groupby(["n_customers","budget","policy"]).seed.nunique()
    assert sizes.min()>=30,"Full study requires >=30 seeds"
    # Unknown error strings occur only on explicitly flagged episodes.
    assert r.loc[r.infeasible_flag==0,"error"].fillna("").eq("").all()
    result=dict(rows=len(r),main_rows=len(main),unique_simulations=r.key.nunique(),seeds_per_main_cell=int(sizes.min()),required_metrics_finite=True,paired_orders_and_weather=True,query_budget_respected=True,incomplete_design_rows=int(r.infeasible_flag.sum()),incomplete_unique_episodes=int(r.loc[r.infeasible_flag==1,"key"].nunique()))
    (outdir/"audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return r,ci,result

def report(outdir="outputs/experiments"):
    outdir=Path(outdir); r,ci,audit_result=audit(outdir)
    main=r[r.experiment=="main"]; focus=main[(main.n_customers==8)&(main.budget==4)].groupby("policy")[["total_cost","completion_time_min","query_count","drone_sortie_count","incident_count","infeasible_flag"]].mean()
    effect=ci[(ci.experiment=="main")&(ci.metric=="total_cost")&(ci.budget==4)].sort_values("n_customers")
    heat=r[(r.experiment=="budget_delay")&(r.policy=="voi_query")].groupby(["delay_min","budget"]).total_cost.mean().unstack()
    text=["# 实验研究说明", "", "本项目使用合成订单、合成道路距离及风场代理模型。结果用于比较算法行为，不代表真实运营效益或飞行适航验证。", "", "## 实现与求解", "", "模型以一辆卡车和一架无人机为对象。联合调整卡车客户访问次序、车机服务分工及无人机起降节点，使用最近邻初始路线与 300 次邻域贪心搜索。每次规划共享 40 个成本情景，用 200 个风险样本筛查，再用另外 200 个独立样本检查最终方案。事件调度器冻结已启动的行驶边及架次，到站或回收后重规划。", "", "天气按区域独立马尔可夫转移。策略只能读取信念与已返回观测。延迟报告先在采集时刻做贝叶斯更新，再传播到当前时刻。approx_voi 使用有限候选计划集与共同等待前缀，按净价值决定是否查询，不承诺最优 POMDP 策略。", "", "## 实验协议", "", f"先运行种子 0:9 的六策略 sanity 检查，再运行完整设计。主实验为客户数 8/15/25、预算 0/2/4/8、六策略、每格 30 个配对种子，共 {audit_result['main_rows']} 行。准确率、延迟、初始强风概率、风险阈值的一因素敏感性及预算×延迟矩阵均各用 30 种子。所有设计共 {audit_result['rows']} 行，对完全相同且与政策无关的仿真做显式复用，共实际求解 {audit_result['unique_simulations']} 个唯一回合。复用不增加独立样本数。", "", "同一条件与种子下，订单和真实天气的 SHA256 均相同。环境、观测噪声与优化器使用分离的随机数。配对 bootstrap 对每个种子计算 VOI−prior 差，再有放回重采样 2000 次，取 2.5% 和 97.5% 分位数。CI 未作多重比较调整。oracle 使用未来真实天气的启发式，只是不可实现的参考，不能解释为严格下界。", "", "## 默认条件下的主要结果", "", "8 客户、预算 4、30 种子的均值：", "", "| 策略 | 综合成本 | 回合时长/min | 查询数 | 无人机架次 |", "|---|---:|---:|---:|---:|"]
    for p,d in focus.iterrows(): text.append(f"| {p} | {d.total_cost:.3f} | {d.completion_time_min:.3f} | {d.query_count:.3f} | {d.drone_sortie_count:.3f} |")
    text += ["", "预算 4 时，VOI−prior 的成本配对差（正数代表 VOI 成本更高）：", "", "| 客户数 | 平均差 | 相对差 | 配对 95% CI |", "|---|---:|---:|---:|"]
    for _,d in effect.iterrows(): text.append(f"| {int(d.n_customers)} | {d.mean_change:.3f} | {d.relative_change:.2%} | [{d.ci_low:.3f}, {d.ci_high:.3f}] |")
    text += ["", "这些结果没有支持默认配置下 VOI 显著降低综合成本。初始强风概率 0.15 高于单架次风险容忍 0.10，多区域飞行进一步增加风险。观测噪声与 3 分钟延迟会削弱信息效用。随机和熵查询通常消耗更多预算，却没有明显增加可执行的无人机任务。风险较宽松时飞行更多，也可能出现更多取消与惩罚。", "", "查询的有限候选重优化与实际滚动局部搜索还存在近似误差，所以规划净价值为正不保证事后成本一定下降。需要扩大候选集并改善延迟期间共同动作，才能检验算法改进是否有效。", "", "8 客户的预算×延迟 VOI 平均成本：", "", "| 延迟/min | 预算0 | 预算2 | 预算4 | 预算8 |", "|---|---:|---:|---:|---:|"]
    for delay,d in heat.iterrows(): text.append(f"| {delay:g} | "+" | ".join(f"{d[b]:.3f}" for b in [0,2,4,8])+" |")
    text += ["", "## 未完成与风险的处理", "", f"全设计有 {audit_result['incomplete_design_rows']} 行达到 180 分钟时限，来自 {audit_result['incomplete_unique_episodes']} 个唯一回合：25 客户、种子 1、VOI，预算 2/4/8。货物已取到并装车，但车尚未返回仓库，因此 infeasible_flag=1。tasks_completed 记录已装到卡车的订单数量，最终全部返回必须同时检查 infeasible_flag=0。时限截断回合保留在统计中，时长是截断值、成本是已发生值，不能视作完成全部任务的成本。", "", "出发前全航路安全互锁会读取起飞时真实风场，仅用于取消不安全架次，不把风况交给策略。它依赖理想化的全航路可行性检查，属于乐观执行代理。取消后计入事件与 200 成本，订单交回卡车。并非现实设备已经能够免费获知整条航路天气。", "", "## 适用边界与后续", "", "道路采用欧氏距离×1.30，地图为局部合成坐标，没有真实道路或禁飞区。无人机每架次冻结起飞时风场，跨网格积分空载与载货段。所有客户与回收点假设允许安全落地等待，回收后满电换电且电池充足。规划成本情景按预测的边际天气分布采样，在不同时刻共享随机分位数，属于近似耦合，不是完整的联合马尔可夫轨迹 rollout。机会约束为样本比例检查，没有有限样本保证。", "", "优先扩展真实路网与可起降点、区域相关风场、飞行途中天气演变，以及具有共同驾驶前缀的更大规模 VOI rollout。小规模实例可用精确随机规划检验启发式最优性差距。", "", "## 复现与文件", "", "运行命令、配置含义与文件入口见 README.md。raw_results.csv 保留每次回合指标和配对哈希，summary.csv 包含均值/标准差/计数，paired_ci.csv 给出成本、时间、查询数、架次及事件的配对区间。protocol.json 明确复用与 bootstrap 协议，audit.json 为数值和配对审计。地图示例使用 n=8、seed=4 的 VOI 回合，展示了实际观测及无人机架次。"]
    (outdir/"研究说明.md").write_text("\n".join(text),encoding="utf-8")
    payload=dict(audit=audit_result,focus_n8_b4=focus.reset_index().to_dict("records"),effect_b4=effect.to_dict("records"),heatmap=dict(budgets=[int(x) for x in heat.columns],delays=[float(x) for x in heat.index],values=heat.to_numpy().tolist()))
    (outdir/"research_data.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(audit_result,indent=2))

if __name__=="__main__": report()
