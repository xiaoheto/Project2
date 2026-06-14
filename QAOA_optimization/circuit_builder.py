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
    # mixer 演化：让不同 bitstring 之间发生概率转移。
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rx(2 * beta, i)
    qc.barrier()
    return qc


def insert_rz(num_qubits, gamma, h):
    # 单比特 cost 演化：对应 h_i Z_i 项。
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.rz(2 * gamma * h[i], i)
    return qc


def insert_rzz(num_qubits, gamma, J):
    # 双比特 cost 演化：对应 J_ij Z_i Z_j 项。
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            if abs(J[i][j]) > 1e-15:
                qc.rzz(2 * gamma * J[i][j], i, j)
    qc.barrier()
    return qc


def insert_h(num_qubits):
    # 初态准备：把 |00...0> 变成所有候选组合的均匀叠加。
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
    # 生成 2p 个参数：p 个 beta 控制 mixer，p 个 gamma 控制 cost。
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
    # 这是本地 statevector 模拟专用指令；真实量子计算机不能使用。
    qc.save_statevector()
    return qc


def build_one_layer_circuit(num_qubits, h, J, beta, gamma):
    # 构建单层版本
    qc = QuantumCircuit(num_qubits)
    qc.append(insert_h(num_qubits), range(num_qubits))
    qc.append(one_circuit(num_qubits, h, J, beta[0], gamma[0]), range(num_qubits))
    return qc
