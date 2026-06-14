# 项目运行指南

本项目有两套运行环境：

```text
本地 QAOA 训练 / Qiskit 模拟 / 导出 QASM：
  使用 conda 环境 qaoa

本源量子真机提交：
  使用虚拟环境 .venv_pyqpanda3
```

不要把两套环境混在一起。原因是本地 QAOA 使用 `qiskit==0.46.0`，适合 Python 3.8；本源官方 `pyqpanda3` 支持 Python 3.10 到 3.14，本项目中使用 Python 3.13 虚拟环境。

## 1. 进入项目目录

所有命令都建议先进入项目根目录：

```bash
cd /home/zining/Course/TI/Project2
```

## 2. 运行本地 QAOA 实验

激活本地 QAOA 环境：

```bash
conda activate qaoa
```

运行主实验：

```bash
python QAOA_optimization/qaoa_qiskit.py \
  --budget 4 \
  --half_q 0.25 \
  --eta 6 \
  --layers 3 \
  --maxiter 300
```

如果希望使用 SciPy 的 COBYLA 优化器：

```bash
python QAOA_optimization/qaoa_qiskit.py \
  --budget 4 \
  --half_q 0.25 \
  --eta 6 \
  --layers 3 \
  --maxiter 300 \
  --optimizer
```

运行后会输出：

- QAOA 参数训练过程。
- 经典暴力枚举最优组合。
- QAOA 最终 statevector 中各 bitstring 的概率。
- `QAOA_optimization/output/qaoa_one_layer_circuit.txt`。
- `QAOA_optimization/output/budget_<B>_layers_<p>_eta_<eta>.npz`。

也可以不激活环境，直接使用：

```bash
conda run -n qaoa python QAOA_optimization/qaoa_qiskit.py \
  --budget 4 \
  --half_q 0.25 \
  --eta 6 \
  --layers 3 \
  --maxiter 300
```

## 3. 运行 eta 扫描实验

仍然使用 `qaoa` 环境：

```bash
conda activate qaoa
```

运行：

```bash
python QAOA_optimization/eta_sweep.py \
  --etas 0.1,0.5,1,2,3,4,6,8,10,12 \
  --layers 2 \
  --maxiter 80
```

输出文件：

- `QAOA_optimization/output/eta_sweep.csv`
- `QAOA_optimization/output/eta_sweep.png`

## 4. 导出真机 QASM 线路

导出真机线路也使用 `qaoa` 环境，因为这一步仍然依赖 Qiskit 训练 QAOA 参数。

```bash
conda activate qaoa
```

运行：

```bash
python QAOA_optimization/export_hardware_qasm.py \
  --num_assets 4 \
  --budget 2 \
  --half_q 0.25 \
  --eta 6 \
  --layers 1 \
  --maxiter 120 \
  --shots 2000
```

该命令会生成：

- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm`
- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_params.json`
- `QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_reference.csv`

其中：

- `.qasm` 是提交到本源真机的量子线路。
- `_params.json` 记录 QAOA 参数和本地最优结果。
- `_reference.csv` 是本地 statevector 理论概率分布，用于和真机 counts 对比。

## 5. 运行本源量子真机任务

真机提交使用 `.venv_pyqpanda3` 环境。

激活环境：

```bash
source .venv_pyqpanda3/bin/activate
```

检查 `pyqpanda3` 是否可用：

```bash
python -c "import pyqpanda3; print(pyqpanda3.__version__)"
```

查看本源云可用后端：

```bash
python QAOA_optimization/submit_originq_job.py \
  --ask-key \
  --list-backends \
  --qasm QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm
```

运行时会要求输入 OriginQ API key。API key 不要写进代码，也不要提交到 git。

提交到 `WK_C180` 真机：

```bash
python QAOA_optimization/submit_originq_job.py \
  --ask-key \
  --backend WK_C180 \
  --shots 2000 \
  --qasm QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm \
  --output QAOA_optimization/output/originq_wk_c180_counts.json
```

运行完成后，真机 counts 会保存到：

```text
QAOA_optimization/output/originq_wk_c180_counts.json
```

退出 `.venv_pyqpanda3` 环境：

```bash
deactivate
```

## 6. 对比真机结果和理论结果

对比脚本只需要普通 Python 和 CSV/JSON 处理，用 `qaoa` 环境运行即可：

```bash
conda activate qaoa
```

运行：

```bash
python QAOA_optimization/compare_hardware_counts.py \
  --counts QAOA_optimization/output/originq_wk_c180_counts.json \
  --reference QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_reference.csv \
  --top 16 \
  --bit-order selection
```

输出含义：

```text
theory_p: 本地 statevector 理论概率
hardware_p: 真机测量频率
delta: 真机频率 - 理论概率
```

本次实验的核心结果为：

```text
理论最优组合: 1100
理论概率: 0.123243
真机频率: 0.099500
```

## 7. 常用命令速查

本地训练：

```bash
conda activate qaoa
python QAOA_optimization/qaoa_qiskit.py --budget 4 --half_q 0.25 --eta 6 --layers 3 --maxiter 300
```

导出真机线路：

```bash
conda activate qaoa
python QAOA_optimization/export_hardware_qasm.py --num_assets 4 --budget 2 --half_q 0.25 --eta 6 --layers 1 --maxiter 120 --shots 2000
```

提交真机：

```bash
source .venv_pyqpanda3/bin/activate
python QAOA_optimization/submit_originq_job.py --ask-key --backend WK_C180 --shots 2000 --qasm QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0.qasm --output QAOA_optimization/output/originq_wk_c180_counts.json
```

对比结果：

```bash
conda activate qaoa
python QAOA_optimization/compare_hardware_counts.py --counts QAOA_optimization/output/originq_wk_c180_counts.json --reference QAOA_optimization/output/hardware_assets_4_budget_2_layers_1_eta_6.0_reference.csv --top 16 --bit-order selection
```
