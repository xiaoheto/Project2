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

运行 PDF 第 3 题参数：

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

## 附加题 eta 扫描

第 4 题已经提供自动扫参脚本：

```bash
python eta_sweep.py --etas 0.1,0.5,1,2,3,4,6,8,10,12 --layers 2 --maxiter 80
```

输出文件：

- `output/eta_sweep.csv`：每个 `eta` 的经典最优组合、最优组合在 QAOA 结果中的概率、QAOA 最高概率组合。
- `output/eta_sweep.png`：最优组合概率随 `eta` 变化的折线图。

报告中可以引用 `eta_sweep.png` 并结合 `eta_sweep.csv` 分析。一般现象是：`eta` 太小时预算约束不够强，最高概率组合可能不满足 `1^T x = B`；`eta` 增大后，满足预算约束的组合概率会更容易提升，但过大也可能让优化 landscape 更陡，增加参数优化难度。

混合层的作用是让量子态在不同二进制组合之间转移，避免只停留在初态或损失层相位编码上。除 `Rx` 外，也可用标准 QAOA 中的 `X` mixing Hamiltonian，或针对约束问题使用保持 Hamming weight 的 XY mixer。多个 qubit 编码一个股票可以表示不同持仓比例，但 qubit 数增加会扩大搜索空间，线路和经典模拟成本也会快速上升。

## 附加题 5 更现实模型

第 5 题的完整文字答案写在 `advanced_model.md`。核心思路是：

- 用整数变量 `y_i` 表示第 `i` 只股票买入股数。
- 用真实价格 `p_i` 写预算不等式 `sum_i p_i y_i <= B`。
- 引入 slack variable `s`，把不等式转成 `sum_i p_i y_i + s = B`。
- 将 `y_i` 和 `s` 都用二进制变量编码，展开后仍是 QUBO。
- 再用 `x = (I - Z) / 2` 映射到 `Z` 和 `ZZ` 哈密顿量，继续使用 QAOA 优化。
