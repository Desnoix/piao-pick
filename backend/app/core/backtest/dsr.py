"""
DSR (Deflated Sharpe Ratio)

基于 Bailey & de Prado (2014) 的实现。
校正因多次尝试策略而产生的多重检验偏差。

输入:
  N: 尝试的策略变体数量
  SR_observed: 观测到的最高样本内 Sharpe
  T: 样本长度（以年为单位）
  skew: 收益偏度 (可选)
  kurt: 收益峰度 (可选)

输出:
  校正后的 Sharpe 期望值
  p-value (观测 Sharpe 在多重检验下是否显著)
"""

import logging
import math
from dataclasses import dataclass

from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class DSRResult:
    """DSR 计算结果"""

    dsr: float  # Deflated Sharpe Ratio (校正后的 p-value)
    expected_max_sharpe: float  # N 次尝试下纯运气能达到的期望最高 Sharpe
    sharpe_std_error: float  # Sharpe 的标准误
    p_value: float  # 传统 (未校正) p-value
    deflated_p_value: float  # 多重检验校正后的 p-value
    n_trials: int  # 尝试次数 N
    observed_sharpe: float  # 观测到的 Sharpe
    is_significant: bool  # 在 α=0.05 下是否显著
    interpretation: str  # 文字说明


def compute_dsr(
    observed_sharpe: float,
    n_trials: int,
    n_observation_years: float,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    alpha: float = 0.05,
) -> DSRResult:
    """
    计算 Deflated Sharpe Ratio。

    Args:
        observed_sharpe: 观测到的最高 Sharpe Ratio
        n_trials: 尝试的策略变体数量 N
        n_observation_years: 观测期长度（年）
        skewness: 收益偏度 (默认 0，正态分布)
        kurtosis: 收益峰度 (默认 3，正态分布)
        alpha: 显著性水平 (默认 0.05)

    Returns:
        DSRResult
    """
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if n_observation_years <= 0:
        raise ValueError("n_observation_years must be > 0")

    # 年化观测数量 (月度调仓 → T = years * 12)
    T = n_observation_years * 12.0

    # 1. 计算 Sharpe 的标准误 (含偏度和峰度修正)
    #    σ_SR ≈ sqrt[(1 - skew*SR + ((kurt-1)/4)*SR²) / T]
    #    这是 Bailey & de Prado (2014) 的公式 (4)
    sr = observed_sharpe
    numerator = 1.0 - skewness * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    numerator = max(numerator, 0.001)  # 防止负值
    sharpe_std = math.sqrt(numerator / T)

    # 2. 计算 N 次独立尝试下，纯运气的期望最高 Sharpe
    #    E[max_SR] ≈ (1-γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(N*e))
    #    其中 γ = 0.5772 (Euler-Mascheroni 常数)
    #    这是 Bailey & de Prado (2014) 的公式 (8)
    gamma = 0.5772156649

    if n_trials == 1:
        expected_max_sr = 0.0
    else:
        inv_phi_1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
        inv_phi_2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        expected_max_sr = (1.0 - gamma) * inv_phi_1 + gamma * inv_phi_2

    # 3. 传统 p-value (未校正)
    #    H0: SR = 0
    #    z = SR / σ_SR
    z_traditional = sr / sharpe_std if sharpe_std > 0 else 0.0
    p_traditional = 1.0 - stats.norm.cdf(z_traditional)

    # 4. Deflated p-value
    #    H0: SR ≤ E[max_SR]  (零假设: 观测到的 SR 不高于纯运气期望)
    #    z = (SR - E[max_SR]) / σ_SR
    z_deflated = (sr - expected_max_sr) / sharpe_std if sharpe_std > 0 else 0.0
    p_deflated = 1.0 - stats.norm.cdf(z_deflated)

    is_significant = p_deflated < alpha

    # 文字说明
    if n_trials <= 1:
        interp = "仅尝试 1 个策略，无需多重检验校正"
    elif is_significant:
        interp = f"在尝试 {n_trials} 个策略变体后，观测 Sharpe {sr:.3f} 仍然显著 (p={p_deflated:.4f})"
    else:
        interp = (
            f"在尝试 {n_trials} 个策略变体后，"
            f"观测 Sharpe {sr:.3f} 不再显著 (p={p_deflated:.4f})。"
            f"纯运气期望最高 Sharpe 为 {expected_max_sr:.3f}，"
            f"观测值可能来自数据挖掘"
        )

    return DSRResult(
        dsr=round(observed_sharpe - expected_max_sr, 3),
        expected_max_sharpe=round(expected_max_sr, 3),
        sharpe_std_error=round(sharpe_std, 4),
        p_value=round(p_traditional, 4),
        deflated_p_value=round(p_deflated, 4),
        n_trials=n_trials,
        observed_sharpe=round(observed_sharpe, 3),
        is_significant=is_significant,
        interpretation=interp,
    )


def compute_multiple_testing_threshold(
    n_trials: int,
    n_observation_years: float,
    alpha: float = 0.05,
) -> float:
    """
    计算在给定尝试次数下，Sharpe 需要达到多少才算显著。

    即反向求解: 使 deflated p-value = alpha 的 SR 临界值。

    Args:
        n_trials: 尝试次数
        n_observation_years: 观测期年数
        alpha: 显著性水平

    Returns:
        Sharpe 临界值
    """
    T = n_observation_years * 12.0
    gamma = 0.5772156649

    if n_trials == 1:
        expected_max_sr = 0.0
    else:
        inv_phi_1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
        inv_phi_2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        expected_max_sr = (1.0 - gamma) * inv_phi_1 + gamma * inv_phi_2

    # SR_critical = E[max_SR] + z_alpha * σ_SR
    # σ_SR ≈ 1/sqrt(T) （在 SR≈0 附近的近似）
    z_alpha = stats.norm.ppf(1.0 - alpha)
    sharpe_std_approx = 1.0 / math.sqrt(T)
    sr_critical = expected_max_sr + z_alpha * sharpe_std_approx

    return round(sr_critical, 3)
