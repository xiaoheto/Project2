import numpy as np
from qiskit.opflow import PauliSumOp

# \theta_1 \mu^T x - \text{half_q} \cdot x^T \Sigma x - \eta (B - \sum_i x_i)^2
# 哈密顿量模块：负责把 QUBO 目标函数整理成 QAOA cost layer 所需的 Z/ZZ 系数。
def calc_J(config, cov_mat):
    """
    Calculate ZZ coefficients in Hc = -R after replacing x_i with (I - Z_i) / 2.
    """
    J = np.zeros((config.num_qubits, config.num_qubits))

    for i in range(config.num_qubits):
        asset_i = config.qubit_asset(i)
        weight_i = config.qubit_weight(i)
        for j in range(i + 1, config.num_qubits):
            asset_j = config.qubit_asset(j)
            weight_j = config.qubit_weight(j)
            # ZZ 项只来自二次项：风险项 x^T Sigma x 和预算惩罚项 (sum x_i)^2。
            J[i][j] = 0.5 * config.half_q * cov_mat[asset_i][asset_j] * weight_i * weight_j
            J[i][j] += 0.5 * config.eta * weight_i * weight_j
            J[j][i] = J[i][j]

    return J


def calc_h(config, exp_ret, cov_mat):
    """
    Calculate Z coefficients in Hc = -R after replacing x_i with (I - Z_i) / 2.
    """
    h = np.zeros(config.num_qubits)
    total_weight = sum(config.qubit_weight(k) for k in range(config.num_qubits))

    for i in range(config.num_qubits):
        asset_i = config.qubit_asset(i)
        weight_i = config.qubit_weight(i)
        cov_sum = 0.0
        for j in range(config.num_qubits):
            asset_j = config.qubit_asset(j)
            weight_j = config.qubit_weight(j)
            cov_sum += cov_mat[asset_i][asset_j] * weight_j

        # Z 项由三部分合并而来：风险项展开后的线性部分、收益项、预算惩罚的线性部分。
        h[i] = -0.5 * config.half_q * weight_i * cov_sum
        h[i] += 0.5 * config.theta1 * exp_ret[asset_i] * weight_i
        h[i] += config.eta * weight_i * (config.budget - 0.5 * total_weight)

    return h


def get_pauli(index, pauli_type, num_qubits):
    if pauli_type == "Z":
        assert len(index) == 1
    elif pauli_type == "ZZ":
        assert len(index) == 2
    else:
        raise AssertionError()

    pauli = ["I"] * num_qubits
    for qubit_index in index:
        assert 0 <= qubit_index <= num_qubits - 1
        # Qiskit 的 Pauli 字符串按高位 qubit -> 低位 qubit 排列，所以这里要反向映射。
        pauli[num_qubits - 1 - qubit_index] = "Z"
    return "".join(pauli)


def problem_pauli_operator(h, J, num_qubits):
    # PauliSumOp 是 Qiskit 0.46 中表示哈密顿量的对象，可直接用于 statevector 期望值计算。
    pauli_h_list = [(get_pauli([i], "Z", num_qubits), h[i]) for i in range(num_qubits)]
    pauli_h = PauliSumOp.from_list(pauli_h_list, coeff=1.0)

    pauli_j_list = []
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            pauli_j_list.append((get_pauli([i, j], "ZZ", num_qubits), J[i][j]))
    pauli_j = PauliSumOp.from_list(pauli_j_list, coeff=1.0)

    return pauli_h, pauli_j, pauli_h + pauli_j
