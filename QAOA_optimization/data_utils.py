import numpy as np
import pandas as pd


def data_preprocessing(file_path):
    """
    Read stock closing prices and return expected returns and covariance matrix.
    """
    df = pd.read_excel(file_path)
    df = df.select_dtypes(include=[np.number])
    if df.empty:
        raise ValueError("No numeric stock price columns found in {}".format(file_path))

    data = df.to_numpy(dtype=float)
    if data.shape[0] < 2:
        raise ValueError("At least two rows of stock prices are required.")

    returns = (data[1:, :] - data[:-1, :]) / data[:-1, :]
    exp_ret = pd.Series(returns.mean(axis=0), index=df.columns, name="expected_return")
    cov_mat = pd.DataFrame(np.cov(returns, rowvar=False, ddof=1),
                           index=df.columns,
                           columns=df.columns)
    return exp_ret, cov_mat


def load_portfolio_data(file_path, num_assets):
    exp_ret, cov_mat = data_preprocessing(file_path)
    exp_ret = exp_ret.to_numpy()
    cov_mat = cov_mat.to_numpy()
    if num_assets > len(exp_ret):
        raise ValueError("num_assets={} exceeds data columns={}.".format(num_assets, len(exp_ret)))
    return exp_ret[:num_assets], cov_mat[:num_assets, :num_assets]
