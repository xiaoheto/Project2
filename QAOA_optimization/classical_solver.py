import numpy as np


def brute_force_solution(config, exp_ret, cov_mat):
    best_selection = None
    best_loss = None
    best_utility = None
    total_states = 2 ** config.num_qubits

    for dec in range(total_states):
        bits = np.array([(dec >> i) & 1 for i in range(config.num_qubits)], dtype=float)
        holdings = np.zeros(config.num_assets)
        for i in range(config.num_qubits):
            holdings[config.qubit_asset(i)] += bits[i] * config.qubit_weight(i)

        utility = config.theta1 * (exp_ret @ holdings)
        utility -= config.half_q * (holdings @ cov_mat @ holdings)
        utility -= config.eta * (config.budget - np.sum(holdings)) ** 2
        loss = -utility

        if best_loss is None or loss < best_loss:
            best_selection = "".join(str(int(v)) for v in bits)
            best_loss = loss
            best_utility = utility

    return best_selection, best_loss, best_utility
