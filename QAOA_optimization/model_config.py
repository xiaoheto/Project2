from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioConfig:
    budget: int
    num_assets: int
    num_slices: int
    theta1: float
    half_q: float
    eta: float
    granularity: float
    layers: int

    @property
    def num_qubits(self):
        return self.num_assets * self.num_slices

    def qubit_weight(self, qubit_index):
        return self.granularity * (2 ** (qubit_index % self.num_slices))

    def qubit_asset(self, qubit_index):
        return qubit_index // self.num_slices
