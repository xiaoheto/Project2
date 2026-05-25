from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


def insert_rx(num_qubits, beta):
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rx(2 * beta, i)
    qc.barrier()
    return qc


def insert_rz(num_qubits, gamma, h):
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rz(2 * gamma * h[i], i)
    return qc


def insert_rzz(num_qubits, gamma, J):
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            if abs(J[i][j]) > 1e-15:
                qc.rzz(2 * gamma * J[i][j], i, j)
    qc.barrier()
    return qc


def insert_h(num_qubits):
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.h(i)
    qc.barrier()
    return qc


def one_circuit(num_qubits, h, J, beta, gamma):
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_rz(num_qubits, gamma, h), range(num_qubits))
    qc.append(insert_rzz(num_qubits, gamma, J), range(num_qubits))
    qc.append(insert_rx(num_qubits, beta), range(num_qubits))
    return qc


def build_parameters(layers):
    beta = []
    gamma = []
    for i in range(layers):
        beta.append(Parameter("β%d" % i))
        gamma.append(Parameter("γ%d" % i))
    return beta, gamma, beta + gamma


def build_qaoa_circuit(num_qubits, h, J, beta, gamma, layers):
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_h(num_qubits), range(num_qubits))
    for i in range(layers):
        qc.append(one_circuit(num_qubits, h, J, beta[i], gamma[i]), range(num_qubits))
    qc.save_statevector()
    return qc


def build_one_layer_circuit(num_qubits, h, J, beta, gamma):
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_h(num_qubits), range(num_qubits))
    qc.append(one_circuit(num_qubits, h, J, beta[0], gamma[0]), range(num_qubits))
    return qc
