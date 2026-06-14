import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.algorithms.optimizers import SPSA
from scipy.optimize import minimize


# 求解模块：把参数化量子线路包装成经典优化器可以调用的 loss 函数。

# 训练日志记录器，每迭代一次，就记录下loss
class OptimizationCallback:
    def __init__(self, step_size):
        self.step_size = step_size
        self.full_values = [] # 每次回调时的loss
        self._values = [] # 临时缓存
        self.values = [] # 按照step_size抽样保存的loss

    # nfev: 函数评估次数, parameters: 当前参数, value: 当前loss, step_size: 当前步长, accepted: 这一步是否被接受
    def __call__(self, nfev, parameters, value, stepsize, accepted):
        self.full_values.append(value)
        self._values.append(value)
        if len(self._values) == self.step_size:
            last_value = self._values[-1]
            self.values.append(last_value)
            self._values = []
            return self.values
        return None


def get_expectation(circuit, para_list, hamiltonian, simulator, num_qubits):
    # 把一个参数化量子电路包装成一个可以被经典优化器调用的loss函数
    def execute_circ(theta):
        qc = QuantumCircuit(num_qubits)

        p = len(theta) // 2
        # 参数向量约定为 [beta_0, ..., beta_{p-1}, gamma_0, ..., gamma_{p-1}]。
        beta = theta[:p]
        gamma = theta[p:]

        para_dict = {}
        for i in range(p):
            para_dict[para_list[i]] = beta[i]
            para_dict[para_list[i + p]] = gamma[i]

        # 每次优化迭代都把同一个参数化 ansatz 绑定成一个具体线路，再送入模拟器求期望值。
        qc.append(circuit, range(num_qubits))
        qc.assign_parameters(para_dict, inplace=True)
        circ = transpile(qc, simulator)
        result = simulator.run(circ).result()
        statevector = result.get_statevector(circ)
        loss = statevector.expectation_value(hamiltonian)

        assert np.imag(loss) < 1e-10
        return np.real(loss)

    return execute_circ


def optimize_parameters(expectation, layers, maxiter, use_scipy_optimizer, verbose=True):
    # 计算哈密顿量期望值，作为loss
    # 初始点设得很小，避免一开始就让旋转角过大导致搜索不稳定。
    start_point = np.random.uniform(0, 0.001 * np.pi, size=layers * 2)

    if use_scipy_optimizer:
        # COBYLA 是无梯度经典优化器，适合这里的黑盒期望值函数。
        res = minimize(expectation,
                       start_point,
                       method="COBYLA",
                       options={"maxiter": maxiter})
        if verbose:
            print("\nTraining Done! The output of optimizer: ")
            print(res)
        return res.x, res, None

    callback_func = OptimizationCallback(step_size=1)
    # SPSA 适合噪声环境和高维参数场景，这里直接对 QAOA 的 2p 个参数做优化。
    optimizer = SPSA(maxiter=maxiter, blocking=True, second_order=True, callback=callback_func)
    if hasattr(optimizer, "minimize"):
        opt_result = optimizer.minimize(fun=expectation, x0=start_point)
        res = (opt_result.x, opt_result.fun, opt_result.nfev)
    else:
        res = optimizer.optimize(num_vars=layers * 2,
                                 objective_function=expectation,
                                 initial_point=start_point)
    return res[0], res, callback_func
