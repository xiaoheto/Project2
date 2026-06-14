from dataclasses import dataclass

# \theta_1 \mu^T x - \text{half_q} \cdot x^T \Sigma x - \eta (B - \sum_i x_i)^2
@dataclass(frozen=True)
class PortfolioConfig:
    # 保存投资组合模型和 QAOA 线路的公共配置，供所有模块共享。
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
        # 当 g > 1 时，同一资产的不同 qubit 表示二进制位权：1, 2, 4, ...
        return self.granularity * (2 ** (qubit_index % self.num_slices))

    def qubit_asset(self, qubit_index): # qubit_index属于哪只资产
        # qubit 按资产分块排列，例如 g=2 时 q0/q1 属于资产0，q2/q3 属于资产1。
        return qubit_index // self.num_slices
