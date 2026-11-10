# 有限天气观测下的卡车—无人机协同取件优化

`tdw/` 为本次 M1–M3 的权威实现。联合决定何时查询哪个区域、卡车路线、客户由谁取件以及无人机在哪起飞与回收。所有参数均为合成示意值，不代表运营报价或适航结论。

根目录旧脚本、`results/`、旧 `map_view.html` 和早期 PPT 属于 legacy 固定路线演示，保留供参考。它们与本次 `outputs/` 使用不同模型，不能混用结论。

## 快速开始

从本目录运行，已配置 Python 3.10 的 `.venv`，不使用系统旧版 Anaconda Python 3.8：

```powershell
.\.venv\Scripts\python.exe -m tdw.cli run --config configs/base.yaml --policy prior --seed 42
.\.venv\Scripts\python.exe -m tdw.cli run --config configs/base.yaml --policy voi_query --seed 42
.\.venv\Scripts\python.exe -m tdw.cli run --config configs/map_demo.yaml --policy voi_query --seed 4 --output outputs/map_demo
.\.venv\Scripts\python.exe -m tdw.cli compare --config configs/base.yaml --policies truck_only,prior,random_query,entropy_query,voi_query,oracle --seeds 0:9 --output outputs/sanity
.\.venv\Scripts\python.exe -m tdw.cli sweep --config configs/experiment.yaml --seeds 0:29 --workers 6 --output outputs/experiments
.\.venv\Scripts\python.exe -m tdw.reporting
.\.venv\Scripts\python.exe -m pytest -q
```

新环境安装（Python 3.10/3.11）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

包直接位于项目根目录 `tdw/`，因此未安装也可从根目录运行 `python -m tdw.cli`。不依赖 Gurobi 或商业优化器。`--seeds 0:29` 的两端均包含。`--quick` 仅缩小主矩阵，不替代正式实验。多进程数可用 `--workers` 调整。

## 已执行结果

21 项 pytest 全部通过。先执行六策略、种子 0:9 的 60 回合 sanity 检查，再完成 6480 行正式实验（2700 个唯一仿真，重复条件明确复用），每格 30 个配对种子。主实验 2160 行，其余为准确率、延迟、初始强风概率、风险阈值及预算×延迟敏感性。

8 客户、预算 4、30 种子：prior 平均成本 48.268，VOI 为 48.405；平均时间分别为 72.558 和 72.610 分钟。本次结果没有支持默认配置下近似 VOI 稳定降低总成本。随机与熵策略往往支付了更多查询费用。完整比较和配对区间见 `outputs/experiments/研究说明.md`，不能预设主动观测总会更好。

25 客户、种子 1、VOI 的预算 2/4/8 三个回合达到 180 分钟仍未回仓，均保留并标记 `infeasible_flag=1`。货物虽已装车，任务最终完成仍须回仓。时限截断成本是已发生的部分成本，不能解释为完成全部订单的成本。

## 地图与报告入口

- `outputs/map_demo/map_replay.html`：离线浏览器地图，可切换卡车基线/VOI、播放、拖动时间、显示隐藏风况审计。
- `outputs/map_demo/route_compare.png`：8 客户 seed 4 的实际执行路线，查询 2 次、无人机 1 架次。
- `outputs/map_demo/weather_timeline.png`：隐藏天气、查询提交/返回和回合结束时刻。
- `outputs/map_demo/vehicle_gantt.png`：行驶、服务、等待、无人机飞行/落地回收、查询并发时序。
- `outputs/single/`：默认配置 seed 42。VOI 不查询、全部卡车取件，102.091 分钟，成本 65.766。
- `outputs/experiments/raw_results.csv`：全部明细与条件、种子、共同订单/天气哈希。
- `outputs/experiments/summary.csv`：均值、标准差、计数。`paired_ci.csv`：VOI−prior 的配对 bootstrap 95% CI。
- `outputs/experiments/` 下四张比较图：成本、时间与预算、预算×延迟、时间成本点图。
- `outputs/experiments/研究说明.md`、`audit.json`、`protocol.json`：结果解释、审计与复现协议。
- `ppt_output/有限天气观测_联合优化与仿真实验_20261027.pptx`：基于本次结果的新版汇报。

地图使用合成局部坐标与直线路径代理，不是真实 GIS 路网。

## 决策模型

订单集合 C，节点 V={o,d}∪C，同一仓库拆成起点 o 和终点 d。区域集合 R，隐藏天气 W，信念 b。

- `x_ik∈{0,1}`：卡车是否走 i→k。
- `y_ijk∈{0,1}`：是否执行单客户架次 i→j→k。
- `u_rt∈{0,1}`：时刻 t 是否提交区域 r 查询。
- `A_i,D_i,L_a,R_a,C_j`：卡车到离站、架次起飞/落地、取件结束时间。

代码使用路线序列与 `Sortie(i,j,k)` 等价编码这些离散决策，时间由同步调度器递推，不是求解上述变量的精确多阶段 MILP。

目标为最小化期望综合成本：

`E[cT·truck_km + cE·drone_Wh + cO·query_count + cH·completion_min + cLate·sum_late + cIncident·incident_count]`。

约束包含：客户唯一分配，连通的起终仓库路线，无隐性子回路，起飞早于回收，单架无人机架次不重叠，载重、电池及余量，先空载后载货的分区能耗积分，车机回收同步，最早取件时间窗与迟到软惩罚，已开始动作不可撤回，货物最后随车回仓，查询预算/并发/延迟，以及信念下样本危险概率≤epsilon。总货重超过卡车容量直接标记不可行。

查询报告到达前的动作必须对所有可能标签相同。延迟 δ 的后验采用采集时刻先验更新，再按跨越的天气 tick 数传播。未返回标签不进入普通策略接口。

## 求解与执行

M1：最近邻全卡车初始解，300 次贪心邻域搜索，包括 relocate、swap、2-opt、卡车客户转无人机、无人机转卡车、起降点调整。每个候选先验证硬约束。

M2：每次规划共享 40 个成本情景，风险检查用 200 个样本，最后再用独立的 200 个样本检查选中方案。失败时保守回退全卡车方案。`prior` 可以在安全先验下飞行，无观测并不自动禁飞。

M3：离散事件调度器记录查询、天气 tick、卡车出发/到站、无人机起飞/取件/落地/回收。每 5 分钟及报告到达触发重规划请求，实际优化延迟到安全边界。行驶边、取件服务和飞行期间的承诺不撤销。架次起飞后，卡车冻结到回收点的整个路线前缀，保留中间客户服务，避免回收死锁。

`approx_voi` 仅在未来 30 分钟附近航线覆盖区域考虑查询，比较有限候选计划集的 `min E[C]` 与 `query_cost + E_label[min E[C|label]]`，包含各标签共同的完整等待前缀及时间成本。查询费只扣一次。净价值均非正则不查。VOI 策略实际等待报告后再优化，其他查询策略可与驾驶并行。候选计划集与实际局部搜索不完全一致，因此近似净价值不保证事后成本改善。

## 公平性和统计

环境、订单、噪声、优化器随机数分离。观测噪声由 `(seed,region,round(acquisition_time,6))` 稳定键生成，查询顺序不改变环境。普通 Context 不持有天气环境或未来轨迹。`oracle` 才有显式特权回调，用于启发式理想信息参考，不是严格数学下界。

每条件 30 个独立种子，策略在同一种子上配对。bootstrap 对种子差值有放回抽样 2000 次，固定 bootstrap seed 90210，给出 2.5%–97.5% 分位数。没有多重比较调整。图中边际误差条为 1.96×标准误，正式配对比较使用 CSV。oracle 不参与公平显著性结论。

完全相同条件复用仿真；不查询策略对观测设置不敏感，预算为零的查询策略等价 prior。`reused_episode`、`key`、`protocol.json` 明确记录复用，不增加独立样本数。缓存 `episode_cache.jsonl` 支持中断后恢复；修改核心实现后应改用新的输出目录，避免复用旧版本缓存。

`infeasible_flag=0` 才表示全部货物返回仓库。`tasks_completed` 为已装车订单数，`query_wait_min` 为 VOI 实际主动等待，`truck_wait_min` 为时间窗/会合等待，两者分开统计。`incident_count` 指出发前互锁拒绝，未模拟空中事故。时限截断时无人机能量记为已承诺架次的总能量，不声称为实时电表读数。

## 模型边界

- 道路距离为欧氏距离×1.30，天气区域独立，区域风向固定可知。风速 2/6/11 m/s，危险门限 9 m/s。
- 跨网格航段精确分割，空载和载货能耗分别积分。地速和功率是合成代理，未做实测标定。
- 一架次内冻结起飞时区域风场。所有客户与回收点允许安全落地等待，地面等待不耗飞行能量。回收后有无限满电换电供应。
- 成本情景按未来边际天气分布采样，在不同时刻共享随机分位数，是近似耦合，不是完整马尔可夫联合轨迹 rollout。
- 样本机会约束没有有限样本概率保证。出发前互锁读取整条航路的真实冻结风场，属于乐观全路径代理，现实中仍需传感器、航路安全规则和途中应急策略。
- 没有动态新订单、禁飞区、地形、交通拥堵或实际 GIS 道路。没有全局最优性保证，也没有证明当前 VOI 是最优查询策略。

## 项目结构

`models/instance` 管理配置与合成订单，`flight/scheduler` 负责动力代理和同步，`routing/evaluator` 负责联合搜索与风险，`weather/belief/observation` 隔离真值和信息，`simulator/policies` 执行滚动决策，`experiments/plots/map_view/reporting/cli` 组织实验、地图、统计与报告。原始任务规范备份于 `configs/IMPLEMENTATION_SPEC.md`，原始默认参数保存在 `configs/base.yaml`。
"# low-air" 
