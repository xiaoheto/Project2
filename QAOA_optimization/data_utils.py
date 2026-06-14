import numpy as np
import pandas as pd


# 数据处理模块：把 Excel 中的历史价格转成优化模型需要的 mu 和 Sigma。
def data_preprocessing(file_path):
    """
    Read stock closing prices and return expected returns and covariance matrix.
    """
    df = pd.read_excel(file_path)
    df = df.select_dtypes(include=[np.number]) # 只保留数值列
    if df.empty:
        raise ValueError("No numeric stock price columns found in {}".format(file_path))

    data = df.to_numpy(dtype=float)
    if data.shape[0] < 2:
        raise ValueError("At least two rows of stock prices are required.")

    # 用相邻两期价格计算简单收益率：(P_t - P_{t-1}) / P_{t-1}。
    returns = (data[1:, :] - data[:-1, :]) / data[:-1, :]
    exp_ret = pd.Series(returns.mean(axis=0), index=df.columns, name="expected_return") # 期望收益率
    cov_mat = pd.DataFrame(np.cov(returns, rowvar=False, ddof=1),
                           index=df.columns,
                           columns=df.columns) # 协方差矩阵
    return exp_ret, cov_mat


def load_portfolio_data(file_path, num_assets):
    # 只取前 num_assets 只股票，保持 qubit 数量可控。
    exp_ret, cov_mat = data_preprocessing(file_path)
    exp_ret = exp_ret.to_numpy()
    cov_mat = cov_mat.to_numpy()
    if num_assets > len(exp_ret):
        raise ValueError("num_assets={} exceeds data columns={}.".format(num_assets, len(exp_ret)))
    return exp_ret[:num_assets], cov_mat[:num_assets, :num_assets]
