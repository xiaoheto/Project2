# QAOA Portfolio Optimization

这个目录完成了 PDF 里的均值-方差投资组合优化 QAOA 任务。`qaoa_qiskit.py` 保留为主入口，默认读取 `data/stock_data.xlsx`，具体功能拆到了多个模块中。

## 代码结构

```text
QAOA_optimization/
├── qaoa_qiskit.py        # 主入口：解析参数、串联完整流程
├── model_config.py       # PortfolioConfig：保存模型和线路配置
├── data_utils.py         # 读取 Excel、计算收益率、mu 和 Sigma
├── hamiltonian.py        # 计算 Z/ZZ 系数，构造 Pauli 哈密顿量
├── circuit_builder.py    # 构造 H、RZ、RZZ、RX 和 QAOA 线路
├── solvers.py            # 构造期望值函数，调用 SPSA 或 COBYLA 优化
├── classical_solver.py   # 经典暴力枚举最优组合
├── report_utils.py       # 打印结果、保存 npz、导出线路图
├── data/
└── output/
```

这样拆分后，code review 时可以按“数据 -> 模型 -> 量子线路 -> 优化 -> 结果对比”的顺序解释。主入口仍然可以直接运行，符合课程模板习惯。

## 模型

原始评分函数定义为：

$$
R
=
\theta_1 \mu^\top x
-
\frac{q}{2} x^\top \Sigma x
-
\eta \left(B - \mathbf{1}^\top x \right)^2
$$

其中三项分别表示：

- $\theta_1 \mu^\top x$：组合的期望收益项。被选中的资产期望收益越高，评分越高。

- $\dfrac{q}{2} x^\top \Sigma x$：风险惩罚项。由资产方差与协方差共同决定；风险偏好参数 $q$ 越大，对风险的惩罚越强。

- $\eta \left(B - \mathbf{1}^\top x \right)^2$：预算约束惩罚项，用于约束最终选择的股票数量接近预算 $B$。

代码中将损失函数定义为：

$$
H_C = -R
$$

并使用变量替换：

$$
x_i = \frac{I - Z_i}{2}
$$

将目标函数映射为 QAOA 所需的 $Z$ 与 $ZZ$ 哈密顿量形式。

对于单 qubit 编码的股票选择问题，可得到：

$$
h_i
=
-\frac{q}{4}\sum_j \Sigma_{ij}
+
\frac{\theta_1}{2}\mu_i
+
\eta\left(B-\frac{n}{2}\right)
$$

以及：

$$
J_{ij}
=
\frac{q}{4}\Sigma_{ij}
+
\frac{\eta}{2}
$$


## 运行

建议使用 Python 3.8 环境安装依赖：

```bash
cd QAOA_optimization
pip install -r requirements.txt
```

运行第三题：

```bash
python qaoa_qiskit.py --budget 4 --half_q 0.25 --eta 6 --layers 3 --maxiter 300
```

使用 SciPy COBYLA 优化器：

```bash
python qaoa_qiskit.py --budget 4 --half_q 0.25 --eta 6 --layers 3 --maxiter 300 --optimizer
```

脚本会输出：

- QAOA 参数优化过程中的 loss。
- 经典暴力枚举最优组合，用于结果对比。
- QAOA 最终 statevector 中每个组合的损失值和概率。
- `output/qaoa_one_layer_circuit.txt` 单层 QAOA 门级线路图。
- `output/budget_<B>_layers_<p>_eta_<eta>.npz` 结果文件。

## 本源量子真机实验

为了和本地无噪声 statevector 理论结果对比，项目额外提供了一个适合真机运行的小规模实验配置：

```text
num_assets = 4
budget = 2
layers = 1
eta = 6
shots = 2000
backend = WK_C180
```

选择这个配置的原因是线路只有 4 个 qubit 和 1 层 QAOA，双比特门数量较少，比较适合第一次提交到真实超导量子计算机。直接提交 6 qubit、3 层线路也可以，但线路更深，噪声影响会更明显。

### 1. 导出真机线路

本地先训练 QAOA 参数，并导出一个不包含 `save_statevector`、只包含测量操作的 OpenQASM 文件：

```bash
conda run -n qaoa python QAOA_optimization/export_hardware_qasm.py \
  --num_assets 4 \
  --budget 2 \
  --half_q 0.25 \
  --eta 6 \
  --layers 1 \
  --maxiter 120 \
  --shots 2000
```

该命令会生成：

- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm`：提交到真机的 OpenQASM 线路。
- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_params.json`：训练得到的 QAOA 参数和最优组合记录。
- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_reference.csv`：本地 statevector 理论概率分布。

本次实验得到的本地理论结果为：

```text
经典暴力最优组合: 1100
QAOA 最大概率组合: 1100
QAOA 理论概率: 0.1232432830
最优参数 [beta_0, gamma_0]: [1.2884728618399324, -2.012525901022809]
```

### 2. 安装 PyQPanda3

本源量子官方 `pyqpanda3` 支持 Python 3.10 到 3.14，而本项目 Qiskit 依赖建议使用 Python 3.8。因此真机提交部分建议单独创建一个 Python 3.13 虚拟环境，不要和 Qiskit 环境混装：

```bash
python -m venv .venv_pyqpanda3
.venv_pyqpanda3/bin/python -m pip install -i https://pypi.org/simple pyqpanda3
```

如果默认 pip 镜像没有同步 `pyqpanda3`，需要像上面一样显式使用官方 PyPI 源。安装完成后，提交脚本会使用 `pyqpanda3.qcloud.QCloudService` 访问本源量子云。

### 3. 查看可用后端

不要把 API key 写进代码或提交到 git。可以使用 `--ask-key` 运行时输入：

```bash
.venv_pyqpanda3/bin/python QAOA_optimization/submit_originq_job.py \
  --ask-key \
  --list-backends \
  --qasm QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm
```

本次账号可见的后端为：

```text
HanYuan_01    False
PQPUMESH8     True
WK_C180       True
WK_C180_2     True
full_amplitude        True
partial_amplitude     True
single_amplitude      True
```

其中 `WK_C180` 是本次使用的本源悟空真机后端。

### 4. 提交真机任务

```bash
.venv_pyqpanda3/bin/python QAOA_optimization/submit_originq_job.py \
  --ask-key \
  --backend WK_C180 \
  --shots 2000 \
  --qasm QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm \
  --output QAOA_optimization/output/originq_wk_c180_counts.json
```

本次提交结果：

```text
job_id: B217D293EBA37E3A376D18A012C667C1
backend: WK_C180
shots: 2000
status: FINISHED
```

真机测量 counts 排名前几位为：

```text
1100: 199 / 2000 = 0.0995
0101: 190 / 2000 = 0.0950
0110: 190 / 2000 = 0.0950
1010: 188 / 2000 = 0.0940
1001: 177 / 2000 = 0.0885
0011: 168 / 2000 = 0.0840
```

### 5. 对比理论结果和真机结果

```bash
conda run -n qaoa python QAOA_optimization/compare_hardware_counts.py \
  --counts QAOA_optimization/output/originq_wk_c180_counts.json \
  --reference QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_reference.csv \
  --top 16 \
  --bit-order selection
```

核心对比结果：

```text
理论最优组合: 1100
理论概率: 0.123243
真机频率: 0.099500
差值: -0.023743
```

解释：本地 statevector 模拟是无噪声理论结果，真机实验来自真实超导芯片的有限 shots 采样。实验中最优组合 `1100` 仍然是真机测量频率最高的状态，说明真机结果保留了 QAOA 理论分布的主要趋势；但其概率从理论的约 `12.32%` 降到真机的约 `9.95%`，并且其他状态概率整体更分散。这主要来自真实硬件中的单/双比特门误差、退相干、读出误差、线路编译映射误差以及有限采样统计波动。

## 附加题 eta 扫描

第 4 题已经提供自动扫参脚本：

```bash
python eta_sweep.py --etas 0.1,0.5,1,2,3,4,6,8,10,12 --layers 2 --maxiter 80
```

输出文件：

- `output/eta_sweep.csv`：每个 `eta` 的经典最优组合、最优组合在 QAOA 结果中的概率、QAOA 最高概率组合。
- `output/eta_sweep.png`：最优组合概率随 `eta` 变化的折线图。

 `eta_sweep.png` 结合 `eta_sweep.csv` 分析。现象是：`eta` 太小时预算约束不够强，最高概率组合可能不满足 `1^T x = B`；`eta` 增大后，满足预算约束的组合概率会更容易提升，但过大也可能让优化 landscape 更陡，增加参数优化难度。

混合层的作用是让量子态在不同二进制组合之间转移，避免只停留在初态或损失层相位编码上。除 `Rx` 外，也可用标准 QAOA 中的 `X` mixing Hamiltonian，或针对约束问题使用保持 Hamming weight 的 XY mixer。多个 qubit 编码一个股票可以表示不同持仓比例，但 qubit 数增加会扩大搜索空间，线路和经典模拟成本也会快速上升。

## 附加题 5 更现实模型

第 5 题的完整文字答案写在 `advanced_model.md`。核心思路是：

- 用整数变量 `y_i` 表示第 `i` 只股票买入股数。
- 用真实价格 `p_i` 写预算不等式 `sum_i p_i y_i <= B`。
- 引入 slack variable `s`，把不等式转成 `sum_i p_i y_i + s = B`。
- 将 `y_i` 和 `s` 都用二进制变量编码，展开后仍是 QUBO。
- 再用 `x = (I - Z) / 2` 映射到 `Z` 和 `ZZ` 哈密顿量，继续使用 QAOA 优化。
