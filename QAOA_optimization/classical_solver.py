import numpy as np

# \theta_1 \mu^T x - \text{half_q} \cdot x^T \Sigma x - \eta (B - \sum_i x_i)^2
# 经典基准：枚举所有 2^n 个 bitstring，得到小规模问题的真实最优解。
def brute_force_solution(config, exp_ret, cov_mat): # 指数级复杂度
    best_selection = None
    best_loss = None
    best_utility = None
    total_states = 2 ** config.num_qubits

    for dec in range(total_states): # 枚举全部状态
        bits = np.array([(dec >> i) & 1 for i in range(config.num_qubits)], dtype=float)
        holdings = np.zeros(config.num_assets)
        for i in range(config.num_qubits):
            # 将 qubit 位映射回每只资产的实际持仓；g=1 时就是 0/1 选择。
            holdings[config.qubit_asset(i)] += bits[i] * config.qubit_weight(i)

        # utility 和 README 中的 R 一致；QAOA 最小化的是 loss = -utility。
        utility = config.theta1 * (exp_ret @ holdings)
        utility -= config.half_q * (holdings @ cov_mat @ holdings)
        utility -= config.eta * (config.budget - np.sum(holdings)) ** 2
        loss = -utility

        if best_loss is None or loss < best_loss:
            best_selection = "".join(str(int(v)) for v in bits)
            best_loss = loss
            best_utility = utility

    return best_selection, best_loss, best_utility
