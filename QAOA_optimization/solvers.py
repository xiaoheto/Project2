import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.algorithms.optimizers import SPSA
from scipy.optimize import minimize


class OptimizationCallback:
    def __init__(self, step_size):
        self.step_size = step_size
        self.full_values = []
        self._values = []
        self.values = []

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
    def execute_circ(theta):
        qc = QuantumCircuit(num_qubits)

        p = len(theta) // 2
        beta = theta[:p]
        gamma = theta[p:]

        para_dict = {}
        for i in range(p):
            para_dict[para_list[i]] = beta[i]
            para_dict[para_list[i + p]] = gamma[i]

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
    start_point = np.random.uniform(0, 0.001 * np.pi, size=layers * 2)

    if use_scipy_optimizer:
        res = minimize(expectation,
                       start_point,
                       method="COBYLA",
                       options={"maxiter": maxiter})
        if verbose:
            print("\nTraining Done! The output of optimizer: ")
            print(res)
        return res.x, res, None

    callback_func = OptimizationCallback(step_size=1)
    optimizer = SPSA(maxiter=maxiter, blocking=True, second_order=True, callback=callback_func)
    if hasattr(optimizer, "minimize"):
        opt_result = optimizer.minimize(fun=expectation, x0=start_point)
        res = (opt_result.x, opt_result.fun, opt_result.nfev)
    else:
        res = optimizer.optimize(num_vars=layers * 2,
                                 objective_function=expectation,
                                 initial_point=start_point)
    return res[0], res, callback_func
