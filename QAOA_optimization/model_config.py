from dataclasses import dataclass

# \theta_1 \mu^T x - \text{half_q} \cdot x^T \Sigma x - \eta (B - \sum_i x_i)^2
@dataclass(frozen=True)
class PortfolioConfig:
    budget: int # 预算
    num_assets: int
    num_slices: int # 每只资产的二进制位数
    theta1: float
    half_q: float
    eta: float
    granularity: float # 一个最低位的qubit对应多少仓位
    layers: int # QAOA层数

    @property
    def num_qubits(self): # 总qubit数目
        return self.num_assets * self.num_slices

    def qubit_weight(self, qubit_index):
        return self.granularity * (2 ** (qubit_index % self.num_slices))

    def qubit_asset(self, qubit_index): # qubit_index属于哪只资产
        return qubit_index // self.num_slices
