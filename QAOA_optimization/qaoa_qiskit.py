import argparse
from pathlib import Path
import time

import numpy as np
from qiskit_aer import AerSimulator

from circuit_builder import build_one_layer_circuit, build_parameters, build_qaoa_circuit
from classical_solver import brute_force_solution
from data_utils import load_portfolio_data
from hamiltonian import calc_J, calc_h, problem_pauli_operator
from model_config import PortfolioConfig
from report_utils import (
    ensure_output_dir,
    print_classical_result,
    print_config,
    print_loss,
    print_qaoa_result,
    save_circuit_diagram,
)
from solvers import get_expectation, optimize_parameters


# 主入口脚本：把“数据读取 -> 哈密顿量构造 -> QAOA 线路 -> 参数训练 -> 结果对比”串起来。
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=4, help="Total assets.")
    parser.add_argument("--num_assets", type=int, default=6, help="The number of assets.")
    parser.add_argument("--g", type=int, default=1, help="The number of binary bits required to represent one asset.")
    parser.add_argument("--theta1", type=float, default=1.0, help="Coefficient of the linear return term.")
    parser.add_argument("--half_q", type=float, default=0.25, help="Coefficient of the quadratic risk term, q / 2.")
    parser.add_argument("--eta", type=float, default=1.0, help="Coefficient of the Lagrangian term.")
    parser.add_argument("--seed", type=int, default=123456, help="Random seed.")
    parser.add_argument("--optimizer", action="store_true", default=False, help="Use scipy COBYLA optimizer.")
    parser.add_argument("--maxiter", type=int, default=300, help="Max optimizer iterations.")
    parser.add_argument("--Gf", type=float, default=1.0, help="Granularity.")
    parser.add_argument("--layers", type=int, default=3, help="The number of QAOA layers.")
    parser.add_argument("--data", type=str, default=None, help="Path to stock price excel file.")
    return parser.parse_args()


def build_config(args):
    # 将命令行参数集中转成 PortfolioConfig，后续模块只依赖 config，不直接依赖 argparse。
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


def main():
    args = parse_args()
    config = build_config(args)
    project_dir = Path(__file__).resolve().parent
    data_path = Path(args.data) if args.data is not None else project_dir / "data" / "stock_data.xlsx"
    output_dir = ensure_output_dir(project_dir)

    print_config(config)
    np.random.seed(args.seed)

    # 1. 从股票价格数据中计算期望收益 mu 和协方差矩阵 Sigma。
    exp_ret, cov_mat = load_portfolio_data(data_path, config.num_assets)

    # 2. 把均值-方差目标函数映射成 Hc = sum h_i Z_i + sum J_ij Z_i Z_j。
    J = calc_J(config, cov_mat)
    h = calc_h(config, exp_ret, cov_mat)
    _, _, pauli_sum = problem_pauli_operator(h, J, config.num_qubits)

    # 3. statevector 模拟器用于得到无采样噪声的理论概率分布。
    simulator = AerSimulator(method="statevector")
    simulator.set_options(
        max_parallel_threads=0,
        max_parallel_experiments=1,
        max_parallel_shots=0,
        statevector_parallel_threshold=14,
    )

    # 4. 构造参数化 QAOA ansatz；beta/gamma 会在训练阶段由经典优化器调整。
    beta, gamma, para_list = build_parameters(config.layers)
    qaoa_circuit = build_qaoa_circuit(config.num_qubits, h, J, beta, gamma, config.layers)
    one_layer_circuit = build_one_layer_circuit(config.num_qubits, h, J, beta, gamma)
    save_circuit_diagram(one_layer_circuit, output_dir)

    print("\nCircuit Initialization Complete! Start Training...", flush=True)
    # expectation 是优化器看到的 loss 函数：输入 2p 个参数，输出哈密顿量期望值。
    expectation = get_expectation(qaoa_circuit, para_list, pauli_sum, simulator, config.num_qubits)

    start = time.time()
    solution, optimizer_result, callback_func = optimize_parameters(
        expectation=expectation,
        layers=config.layers,
        maxiter=args.maxiter,
        use_scipy_optimizer=args.optimizer,
    )
    if callback_func is not None:
        print_loss(optimizer_result, callback_func)
    print("\nTraining done! Total elapsed time:{:.2f}s".format(time.time() - start))

    # 5. 对小规模问题做经典暴力枚举，用作 QAOA 结果的基准答案。
    classical_selection, classical_loss, classical_utility = brute_force_solution(config, exp_ret, cov_mat)
    print_classical_result(classical_selection, classical_loss, classical_utility)

    # 6. 输出最终量子态的概率分布，并保存结果文件。
    print_qaoa_result(
        circuit=qaoa_circuit,
        hamiltonian_matrix=pauli_sum.to_matrix(),
        para_list=para_list,
        solution=solution,
        simulator=simulator,
        config=config,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
