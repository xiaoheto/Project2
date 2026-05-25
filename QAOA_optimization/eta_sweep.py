import argparse
import csv
import os
from pathlib import Path

import numpy as np
from qiskit_aer import AerSimulator

from circuit_builder import build_parameters, build_qaoa_circuit
from classical_solver import brute_force_solution
from data_utils import load_portfolio_data
from hamiltonian import calc_J, calc_h, problem_pauli_operator
from model_config import PortfolioConfig
from report_utils import ensure_output_dir, get_sorted_probabilities
from solvers import get_expectation, optimize_parameters

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_eta_values(raw):
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etas", type=str, default="0.1,0.5,1,2,3,4,6,8,10,12",
                        help="Comma-separated eta values.")
    parser.add_argument("--budget", type=int, default=4)
    parser.add_argument("--num_assets", type=int, default=6)
    parser.add_argument("--g", type=int, default=1)
    parser.add_argument("--theta1", type=float, default=1.0)
    parser.add_argument("--half_q", type=float, default=0.25)
    parser.add_argument("--Gf", type=float, default=1.0)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=80)
    parser.add_argument("--seed", type=int, default=123456)
    parser.add_argument("--data", type=str, default=None)
    return parser.parse_args()


def build_config(args, eta):
    return PortfolioConfig(
        budget=args.budget,
        num_assets=args.num_assets,
        num_slices=args.g,
        theta1=args.theta1,
        half_q=args.half_q,
        eta=eta,
        granularity=args.Gf,
        layers=args.layers,
    )


def run_single_eta(args, eta, exp_ret, cov_mat, simulator):
    config = build_config(args, eta)
    J = calc_J(config, cov_mat)
    h = calc_h(config, exp_ret, cov_mat)
    _, _, pauli_sum = problem_pauli_operator(h, J, config.num_qubits)

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

    classical_selection, classical_loss, classical_utility = brute_force_solution(config, exp_ret, cov_mat)
    probabilities = get_sorted_probabilities(qaoa_circuit, para_list, solution, simulator, config.num_qubits)
    probability_map = dict(probabilities)

    optimum_key = classical_selection[::-1]
    qaoa_top_key, qaoa_top_probability = probabilities[0]
    optimum_probability = probability_map.get(optimum_key, 0.0)

    return {
        "eta": eta,
        "classical_selection": classical_selection,
        "classical_loss": classical_loss,
        "classical_utility": classical_utility,
        "optimum_probability": optimum_probability,
        "qaoa_top_selection": qaoa_top_key[::-1],
        "qaoa_top_probability": qaoa_top_probability,
        "optimizer_fun": getattr(optimizer_result, "fun", None),
    }


def write_csv(rows, path):
    fieldnames = [
        "eta",
        "classical_selection",
        "classical_loss",
        "classical_utility",
        "optimum_probability",
        "qaoa_top_selection",
        "qaoa_top_probability",
        "optimizer_fun",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_eta_sweep(rows, path):
    etas = [row["eta"] for row in rows]
    optimum_probabilities = [row["optimum_probability"] for row in rows]
    top_probabilities = [row["qaoa_top_probability"] for row in rows]

    plt.figure(figsize=(8, 5))
    plt.plot(etas, optimum_probabilities, marker="o", label="Classical optimum probability")
    plt.plot(etas, top_probabilities, marker="s", label="QAOA top-state probability")
    plt.xlabel("eta")
    plt.ylabel("probability")
    plt.title("Effect of eta on QAOA portfolio selection")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main():
    args = parse_args()
    np.random.seed(args.seed)

    project_dir = Path(__file__).resolve().parent
    output_dir = ensure_output_dir(project_dir)
    data_path = Path(args.data) if args.data is not None else project_dir / "data" / "stock_data.xlsx"
    exp_ret, cov_mat = load_portfolio_data(data_path, args.num_assets)

    simulator = AerSimulator(method="statevector")
    simulator.set_options(
        max_parallel_threads=0,
        max_parallel_experiments=1,
        max_parallel_shots=0,
        statevector_parallel_threshold=14,
    )

    rows = []
    for eta in parse_eta_values(args.etas):
        row = run_single_eta(args, eta, exp_ret, cov_mat, simulator)
        rows.append(row)
        print("eta={:.3f}, optimum={}, p(optimum)={:.6f}, top={}, p(top)={:.6f}".format(
            row["eta"],
            row["classical_selection"],
            row["optimum_probability"],
            row["qaoa_top_selection"],
            row["qaoa_top_probability"],
        ))

    csv_path = output_dir / "eta_sweep.csv"
    png_path = output_dir / "eta_sweep.png"
    write_csv(rows, csv_path)
    plot_eta_sweep(rows, png_path)
    print("Saved eta sweep table to {}".format(csv_path))
    print("Saved eta sweep plot to {}".format(png_path))


if __name__ == "__main__":
    main()
