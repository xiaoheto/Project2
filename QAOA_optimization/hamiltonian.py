import numpy as np
from qiskit.opflow import PauliSumOp


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
        pauli[num_qubits - 1 - qubit_index] = "Z"
    return "".join(pauli)


def problem_pauli_operator(h, J, num_qubits):
    pauli_h_list = [(get_pauli([i], "Z", num_qubits), h[i]) for i in range(num_qubits)]
    pauli_h = PauliSumOp.from_list(pauli_h_list, coeff=1.0)

    pauli_j_list = []
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            pauli_j_list.append((get_pauli([i, j], "ZZ", num_qubits), J[i][j]))
    pauli_j = PauliSumOp.from_list(pauli_j_list, coeff=1.0)

    return pauli_h, pauli_j, pauli_h + pauli_j
