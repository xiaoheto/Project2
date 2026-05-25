from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, transpile


def print_config(config):
    print("%%%%%%%%%%%%%%%%%%%% Configuration %%%%%%%%%%%%%%%%%%%%")
    print("budget: %d, g: %d, theta1: %f, half_q: %f, eta: %f, layers: %d" %
          (config.budget,
           config.num_slices,
           config.theta1,
           config.half_q,
           config.eta,
           config.layers))


def ensure_output_dir(base_dir):
    output_dir = Path(base_dir) / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def save_circuit_diagram(circuit, output_dir):
    diagram_path = Path(output_dir) / "qaoa_one_layer_circuit.txt"
    with open(diagram_path, "w", encoding="utf-8") as f:
        f.write(str(circuit.decompose(reps=2).draw(output="text", fold=-1)))
        f.write("\n")
    print("Circuit diagram saved to {}".format(diagram_path))


def str_to_statevector(string):
    dec = int(string, 2)
    state = np.zeros(2 ** len(string))
    state[dec] = 1.0
    return state[None, :]


def print_loss(res, callback_func):
    print("%%%%%%%%%%%%%%%%%%%% Optimization Output %%%%%%%%%%%%%%%%%%%%")
    loss_ls = callback_func.values
    print("minimal loss: %s, \nmaxIter: %d, func_eval: %d" %
          (res[1], len(callback_func.full_values), res[2]))
    print("Parameters Found:", res[0])
    print("\n----------------- Loss (%d steps from %d iterations) -----------------" %
          (len(loss_ls), len(callback_func.full_values)))
    print("iter\t\tloss")
    print("------------------------------------------------------------------------")
    for i, loss in enumerate(loss_ls):
        print("%d\t\t%.10f" % (i, loss))


def print_classical_result(selection, loss, utility):
    print("\nClassical brute force: selection {}, full loss {:.8f}, utility {:.8f}".format(
        selection, loss, utility))


def print_qaoa_result(circuit, hamiltonian_matrix, para_list, solution, simulator, config, output_dir):
    result = get_sorted_probabilities(circuit, para_list, solution, simulator, config.num_qubits)

    states = []
    for bitstring, _ in result:
        states.append(str_to_statevector(bitstring))
    states = np.concatenate(states, axis=0)
    values = np.real_if_close(np.sum((states @ hamiltonian_matrix) * states, axis=1))

    min_index = np.argmin(values)
    qaoa_selection, qaoa_probability = result[0]
    hamiltonian_selection, hamiltonian_probability = result[min_index]
    print("\nQAOA most probable: selection {}, probability {:.8f}, Hc(no const) {:.8f}".format(
        qaoa_selection[::-1], qaoa_probability, values[0]))
    print("Hamiltonian optimum: selection {}, probability {:.8f}, Hc(no const) {:.8f}".format(
        hamiltonian_selection[::-1], hamiltonian_probability, values[min_index]))

    print("\n----------------- Full result ---------------------", flush=True)
    print("rank\tselection\tHc(no const)\tprobability")
    print("---------------------------------------------------", flush=True)

    value_save = []
    probability_save = []
    utility_save = []
    for i, (bitstring, probability) in enumerate(result):
        value = values[i]
        assert np.imag(value) < 1e-10
        value = np.real(value)
        value_save.append(value)
        probability_save.append(probability)
        utility_save.append(-value)
        print("%d\t%-10s\t%.8f\t\t%.8f" % (i, bitstring[::-1], value, probability), flush=True)

    np.savez(Path(output_dir) / "budget_{}_layers_{}_eta_{}.npz".format(
             config.budget, config.layers, config.eta),
             value=np.array(value_save),
             probability=np.array(probability_save),
             utility=np.array(utility_save))


def get_sorted_probabilities(circuit, para_list, solution, simulator, num_qubits):
    qc = QuantumCircuit(num_qubits)

    p = len(solution) // 2
    beta = solution[:p]
    gamma = solution[p:]

    para_dict = {}
    for i in range(p):
        para_dict[para_list[i]] = beta[i]
        para_dict[para_list[i + p]] = gamma[i]

    qc.append(circuit, range(num_qubits))
    qc.assign_parameters(para_dict, inplace=True)
    circ = transpile(qc, simulator)
    result = simulator.run(circ).result()
    statevector = result.get_statevector(circ).to_dict()

    probabilities = {}
    for bitstring, amplitude in statevector.items():
        probabilities[bitstring] = np.abs(np.array(amplitude)) ** 2
    return sorted(probabilities.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
