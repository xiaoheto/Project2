'''
根据h和J搭建QAOA量子线路
H门: 确定态 -> 叠加态, 把所有解都放在初始中
RX门: 绕X轴旋转一个角度, 用来做mixer, 让状态在不同解之间流动 
RZ门: 绕Z轴旋转一个角度, 用来编码目标函数里的单比特项
RZZ门: 双比特门
'''
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


def insert_rx(num_qubits, beta):
    # mixer演化
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rx(2 * beta, i)
    qc.barrier()
    return qc


def insert_rz(num_qubits, gamma, h):
    # 单比特cost演化
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rz(2 * gamma * h[i], i)
    return qc


def insert_rzz(num_qubits, gamma, J):
    #双比特cost演化
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            if abs(J[i][j]) > 1e-15:
                qc.rzz(2 * gamma * J[i][j], i, j)
    qc.barrier()
    return qc


def insert_h(num_qubits):
    # 初态准备
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.h(i)
    qc.barrier()
    return qc


def one_circuit(num_qubits, h, J, beta, gamma):
    # 拼成一层QAOA
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_rz(num_qubits, gamma, h), range(num_qubits))
    qc.append(insert_rzz(num_qubits, gamma, J), range(num_qubits))
    qc.append(insert_rx(num_qubits, beta), range(num_qubits))
    return qc


def build_parameters(layers):
    # 生成参数beta, gamma
    beta = []
    gamma = []
    for i in range(layers):
        beta.append(Parameter("β%d" % i))
        gamma.append(Parameter("γ%d" % i))
    return beta, gamma, beta + gamma


def build_qaoa_circuit(num_qubits, h, J, beta, gamma, layers):
    # 构建完整多层QAOA电路
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_h(num_qubits), range(num_qubits))
    for i in range(layers):
        qc.append(one_circuit(num_qubits, h, J, beta[i], gamma[i]), range(num_qubits))
    qc.save_statevector()
    return qc


def build_one_layer_circuit(num_qubits, h, J, beta, gamma):
    # 构建单层版本
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_h(num_qubits), range(num_qubits))
    qc.append(one_circuit(num_qubits, h, J, beta[0], gamma[0]), range(num_qubits))
    return qc
