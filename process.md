# 整体流程

这个项目做的是一个简化版的投资组合优化问题：不是预测股票价格，而是在已有历史价格数据的基础上，决定“选哪些股票”能让收益、风险和预算约束之间达到比较好的平衡。

项目使用 QAOA（Quantum Approximate Optimization Algorithm，量子近似优化算法）来求解这个 0/1 组合优化问题，并用经典暴力枚举和本源量子真机结果进行对比。

## 1. 整体流程

主入口是 `QAOA_optimization/qaoa_qiskit.py`。完整执行链路如下：

```text
股票价格 Excel
  -> 计算收益率、期望收益 mu、协方差矩阵 Sigma
  -> 建立均值-方差投资组合目标函数
  -> 把 0/1 优化问题转成 QUBO
  -> 把 QUBO 映射成 Z / ZZ 哈密顿量
  -> 构建 QAOA 参数化量子线路
  -> 用经典优化器训练 beta/gamma 参数
  -> 得到最终 bitstring 概率分布
  -> 和经典暴力枚举最优解比较
  -> 可选：导出线路并提交到本源量子真机
```

其中本地理论实验使用 Qiskit 的 `statevector` 模拟器；真机实验使用 `pyqpanda3` 将 OpenQASM 线路提交到本源量子云。

## 2. 数据处理

数据处理在 `data_utils.py` 中完成。

代码从 `data/stock_data.xlsx` 读取历史价格，只保留数值列，然后用相邻两期价格计算简单收益率：

```text
return_t = (P_t - P_{t-1}) / P_{t-1}
```

之后得到两个量：

```text
mu: 每只股票的平均收益
Sigma: 股票收益之间的协方差矩阵
```

这两个量是投资组合优化模型的核心输入。

## 3. 投资组合优化模型

每只股票用一个 0/1 变量表示：

```text
x_i = 1 表示买第 i 只股票
x_i = 0 表示不买
```

项目使用的评分函数为：

```text
R = theta1 * mu^T x
    - half_q * x^T Sigma x
    - eta * (B - sum_i x_i)^2
```

三个部分分别表示：

- `theta1 * mu^T x`：收益项，选中高收益股票会提高评分。
- `half_q * x^T Sigma x`：风险惩罚项，组合风险越大评分越低。
- `eta * (B - sum_i x_i)^2`：预算约束惩罚项，如果实际选股数量偏离预算 `B`，就会被惩罚。

所以模型的目标可以理解为：

```text
收益尽量高
风险尽量低
选股数量尽量接近预算
```

QAOA 通常写成最小化问题，因此代码中实际最小化的是：

```text
H_C = -R
```

评分越高，对应的损失能量越低。

## 4. 从 QUBO 到哈密顿量

这一步在 `hamiltonian.py` 中完成。

QAOA 不能直接处理普通的 0/1 变量表达式，而是需要把问题写成量子比特上的 Pauli 算符。代码使用替换：

```text
x_i = (I - Z_i) / 2
```

这个替换的直觉是：

```text
bit = 0  对应 Z 的本征值 +1
bit = 1  对应 Z 的本征值 -1
```

替换后，原来的目标函数会整理成：

```text
H_C = sum_i h_i Z_i + sum_ij J_ij Z_i Z_j + 常数项
```

常数项不会影响哪个 bitstring 最优，因此可以忽略。代码中主要计算：

```text
h_i: 单个 qubit 的 Z 系数
J_ij: 两个 qubit 之间的 ZZ 系数
```

直观理解：

```text
h_i 表示单独选择某只股票的倾向
J_ij 表示两只股票一起选择时的联动影响
```

最后 `problem_pauli_operator()` 会把这些系数组装成 Qiskit 的 `PauliSumOp`，供后续 statevector 期望值计算使用。

## 5. QAOA 线路原理

线路构造在 `circuit_builder.py` 中完成。

QAOA 的线路结构可以分成三部分：

```text
初态准备
cost layer
mixer layer
```

第一步，对所有 qubit 加 `H` 门：

```text
|00...0> -> 所有候选 bitstring 的均匀叠加
```

这相当于一开始把所有可能的选股组合都放进候选空间。

之后重复 `p` 层 QAOA。这里的 `p` 就是代码中的 `layers`。

每一层包含：

```text
RZ / RZZ: cost layer，用目标函数给不同状态编码相位
RX: mixer layer，让不同 bitstring 之间发生概率转移
```

具体对应关系：

```text
RZ  对应 h_i Z_i
RZZ 对应 J_ij Z_i Z_j
RX  对应 mixer
```

直观上：

```text
cost layer 负责告诉线路哪些解更好
mixer layer 负责让概率在不同解之间流动
```

多层叠加之后，理想情况下好解的测量概率会变高。

## 6. 2p 个参数是什么意思

如果 QAOA 有 `p` 层，那么每一层都有两个参数：

```text
gamma_k: 控制第 k 层 cost layer 的强度
beta_k: 控制第 k 层 mixer layer 的强度
```

因此总参数数量是：

```text
2p = p 个 beta + p 个 gamma
```

例如：

```text
layers = 3
参数 = beta_0, beta_1, beta_2, gamma_0, gamma_1, gamma_2
总数 = 6
```

在代码中，参数向量约定为：

```text
theta = [beta_0, ..., beta_{p-1}, gamma_0, ..., gamma_{p-1}]
```

这个约定在 `solvers.py` 和 `report_utils.py` 中都会用到。

## 7. QAOA 是如何训练的

训练逻辑在 `solvers.py` 中完成。

QAOA 的训练不是直接训练股票选择变量 `x`，而是训练线路参数：

```text
beta 和 gamma
```

训练时，经典优化器不断尝试一组参数 `theta`。每次尝试都会做以下步骤：

```text
1. 把 theta 拆成 beta 和 gamma
2. 将 beta/gamma 绑定到参数化 QAOA 线路
3. 用 statevector 模拟器运行线路
4. 得到最终量子态 |psi(theta)>
5. 计算期望值 <psi(theta)|H_C|psi(theta)>
6. 把该期望值作为 loss 返回给优化器
```

优化目标是：

```text
minimize <psi(theta)|H_C|psi(theta)>
```

因为能量越低，代表当前量子态越偏向高评分的投资组合。

项目支持两种经典优化器：

```text
默认：SPSA
加 --optimizer：SciPy COBYLA
```

可以这样理解这个混合优化过程：

```text
量子线路负责产生候选组合的概率分布
经典优化器负责调整 beta/gamma，让好组合的概率变高
```

这就是 QAOA 的“量子-经典混合优化”思想。

## 8. 输出结果怎么看

训练结束后，`report_utils.py` 会读取最终 statevector 中每个 bitstring 的概率，并按概率从高到低排序。

输出里有两个重要概念：

```text
QAOA most probable
```

表示最终量子态中概率最高的组合。

```text
Hamiltonian optimum
```

表示按照哈密顿量能量计算出来的最低能量组合。

理想情况下二者相同，但实际中不一定完全相同。原因是 QAOA 优化的是整体期望值，不保证最高概率态一定就是全局最优态。

项目还会调用 `classical_solver.py` 做经典暴力枚举：

```text
枚举所有 2^n 个 bitstring
逐个计算 utility 和 loss
找出真正的全局最优解
```

这个结果用于判断 QAOA 的输出是否接近真实最优解。

## 9. 各脚本之间的关系

本地理论实验主线：

```text
qaoa_qiskit.py
  -> data_utils.py
  -> model_config.py
  -> hamiltonian.py
  -> circuit_builder.py
  -> solvers.py
  -> classical_solver.py
  -> report_utils.py
```

各模块职责：

```text
data_utils.py
  读取 Excel，计算收益率、mu 和 Sigma

model_config.py
  保存预算、资产数量、二进制编码位数、QAOA 层数等配置

hamiltonian.py
  将目标函数映射为 Z / ZZ 哈密顿量

circuit_builder.py
  根据 h 和 J 构建 QAOA 参数化线路

solvers.py
  把量子线路包装成 loss 函数，并调用优化器训练 beta/gamma

classical_solver.py
  暴力枚举所有组合，作为经典最优基准

report_utils.py
  打印结果、排序概率、保存 npz 和线路图
```

eta 扫描实验：

```text
eta_sweep.py
  -> 复用本地理论实验模块
  -> 改变 eta
  -> 每个 eta 独立训练一次 QAOA
  -> 输出 eta_sweep.csv 和 eta_sweep.png
```

真机实验主线：

```text
export_hardware_qasm.py
  -> 本地训练小规模 QAOA
  -> 导出已绑定参数、带测量门的 OpenQASM 线路
  -> 保存本地理论概率 reference.csv

submit_originq_job.py
  -> 读取 OpenQASM
  -> 用 pyqpanda3 转成 QProg
  -> 提交到本源量子云 WK_C180
  -> 保存真机 counts JSON

compare_hardware_counts.py
  -> 读取真机 counts
  -> 读取本地 reference.csv
  -> 对齐 bitstring 顺序
  -> 输出理论概率、真机频率和差值
```

## 10. 本源量子真机实验

本地 QAOA 使用 `statevector` 模拟器，可以得到无噪声理论分布。但真实量子计算机不能返回完整 statevector，只能重复运行线路并测量，得到 counts。

因此真机实验采用小规模配置：

```text
num_assets = 4
budget = 2
layers = 1
eta = 6
shots = 2000
backend = WK_C180
```

本次真机实验结果：

```text
本地理论最优组合: 1100
理论概率: 12.3243%

真机最高频组合: 1100
真机频率: 9.95%
```

说明真机结果保留了理论结果的主要趋势：最优组合仍然是 `1100`。但真机概率比理论概率更低，整体分布更分散。

主要原因包括：

- 真实超导硬件存在单比特门和双比特门误差。
- qubit 会发生退相干。
- 测量读出存在误差。
- 线路需要编译和映射到真实芯片拓扑。
- 2000 shots 是有限采样，会有统计波动。

## 11. 一句话总结

这个项目的核心思想是：

```text
把投资组合选择问题写成 0/1 优化问题，
再映射成量子哈密顿量，
用 QAOA 参数化量子线路产生候选组合的概率分布，
用经典优化器训练 beta/gamma，
最后从最高概率 bitstring 中读出投资组合，
并用经典暴力枚举和真机实验验证结果。
```

最重要的理解点是：QAOA 不是直接“算出答案”，而是训练一个量子线路，让优质解在最终测量分布中的概率变高。
