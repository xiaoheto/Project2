import argparse
import csv
import json
from pathlib import Path

import numpy as np
from qiskit import qasm2
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from circuit_builder import build_parameters, build_qaoa_circuit, insert_h, one_circuit
from classical_solver import brute_force_solution
from data_utils import load_portfolio_data
from hamiltonian import calc_J, calc_h, problem_pauli_operator
from model_config import PortfolioConfig
from report_utils import ensure_output_dir, get_sorted_probabilities
from solvers import get_expectation, optimize_parameters


# 真机前处理脚本：先在本地训练 QAOA，再导出“已绑定参数 + 带测量”的 OpenQASM。
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=2)
    parser.add_argument("--num_assets", type=int, default=4)
    parser.add_argument("--g", type=int, default=1)
    parser.add_argument("--theta1", type=float, default=1.0)
    parser.add_argument("--half_q", type=float, default=0.25)
    parser.add_argument("--eta", type=float, default=6.0)
    parser.add_argument("--Gf", type=float, default=1.0)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--maxiter", type=int, default=120)
    parser.add_argument("--seed", type=int, default=123456)
    parser.add_argument("--shots", type=int, default=2000)
    parser.add_argument("--data", type=str, default=None)
    return parser.parse_args()


def build_config(args):
    # 默认配置使用 4 qubit、1 层 QAOA，降低真实硬件上的噪声影响。
    return PortfolioConfig(
        budget=args.budget,
        num_assets=args.num_assets,
        num_slices=args.g,
        theta1=args.theta1,
        half_q=args.half_q,
        eta=args.eta,
        granularity=args.Gf,
        layers=args.layers,
    )


def build_measurement_circuit(num_qubits, h, J, beta, gamma, layers, solution):
    # 不能直接复用 build_qaoa_circuit，因为其中包含 save_statevector，真机不支持。
    circuit = QuantumCircuit(num_qubits)
    circuit.append(insert_h(num_qubits), range(num_qubits))
    for i in range(layers):
        circuit.append(one_circuit(num_qubits, h, J, beta[i], gamma[i]), range(num_qubits))

    para_dict = {}
    p = len(solution) // 2
    for i in range(p):
        # solution 的前半部分是 beta，后半部分是 gamma。
        para_dict[beta[i]] = solution[i]
        para_dict[gamma[i]] = solution[i + p]

    circuit.assign_parameters(para_dict, inplace=True)
    # 展开复合门，导出的 QASM 更容易被其他 SDK 或云平台解析。
    circuit = circuit.decompose(reps=4)
    # 真机只能返回测量采样 counts，不能返回完整 statevector。
    circuit.measure_all()
    return circuit


def main():
    args = parse_args()
    np.random.seed(args.seed)

    project_dir = Path(__file__).resolve().parent
    output_dir = ensure_output_dir(project_dir)
    data_path = Path(args.data) if args.data is not None else project_dir / "data" / "stock_data.xlsx"

    config = build_config(args)
    # 以下流程和 qaoa_qiskit.py 保持一致，保证真机线路使用同一个目标哈密顿量。
    exp_ret, cov_mat = load_portfolio_data(data_path, config.num_assets)
    J = calc_J(config, cov_mat)
    h = calc_h(config, exp_ret, cov_mat)
    _, _, pauli_sum = problem_pauli_operator(h, J, config.num_qubits)

    simulator = AerSimulator(method="statevector")
    beta, gamma, para_list = build_parameters(config.layers)
    qaoa_circuit = build_qaoa_circuit(config.num_qubits, h, J, beta, gamma, config.layers)
    expectation = get_expectation(qaoa_circuit, para_list, pauli_sum, simulator, config.num_qubits)
    solution, optimizer_result, _ = optimize_parameters(
        expectation=expectation,
        layers=config.layers,
        maxiter=args.maxiter,
        use_scipy_optimizer=True,
        verbose=False,
    )

    # reference.csv 保存本地理论概率，真机 counts 会用它做对比。
    probabilities = get_sorted_probabilities(qaoa_circuit, para_list, solution, simulator, config.num_qubits)
    classical_selection, classical_loss, classical_utility = brute_force_solution(config, exp_ret, cov_mat)
    measurement_circuit = build_measurement_circuit(
        config.num_qubits, h, J, beta, gamma, config.layers, solution
    )

    tag = "assets_{}_budget_{}_layers_{}_eta_{}".format(
        config.num_assets, config.budget, config.layers, config.eta
    )
    qasm_path = output_dir / "hardware_{}.qasm".format(tag)
    params_path = output_dir / "hardware_{}_params.json".format(tag)
    csv_path = output_dir / "hardware_{}_reference.csv".format(tag)

    # 三个文件分别对应：真机输入线路、参数记录、理论概率参考。
    qasm_path.write_text(qasm2.dumps(measurement_circuit), encoding="utf-8")
    params_path.write_text(json.dumps({
        "num_assets": config.num_assets,
        "budget": config.budget,
        "layers": config.layers,
        "eta": config.eta,
        "shots": args.shots,
        "solution": [float(x) for x in solution],
        "optimizer_fun": float(getattr(optimizer_result, "fun", np.nan)),
        "classical_selection": classical_selection,
        "classical_loss": float(classical_loss),
        "classical_utility": float(classical_utility),
        "qaoa_top_selection": probabilities[0][0][::-1],
        "qaoa_top_probability": float(probabilities[0][1]),
    }, indent=2), encoding="utf-8")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "selection", "qiskit_bitstring", "probability"])
        for rank, (bitstring, probability) in enumerate(probabilities):
            writer.writerow([rank, bitstring[::-1], bitstring, float(probability)])

    print("classical_selection:", classical_selection)
    print("classical_loss:", classical_loss)
    print("qaoa_top_selection:", probabilities[0][0][::-1])
    print("qaoa_top_probability:", probabilities[0][1])
    print("solution:", [float(x) for x in solution])
    print("qasm:", qasm_path)
    print("params:", params_path)
    print("reference:", csv_path)


if __name__ == "__main__":
    main()
