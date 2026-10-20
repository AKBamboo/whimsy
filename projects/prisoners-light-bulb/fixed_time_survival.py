#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定在第 T 次审讯后宣布“100 人都已被抽到过”的生存概率。

模型
----
每次审讯独立、均匀地随机抽取 100 名囚徒之一（可重复）。囚徒不使用灯泡
传递任何信息，只是选定一个固定的全局审讯次数 T，在第 T 次审讯后宣布
所有人至少被抽到过一次。

若宣布时 100 人都已出现过，则获释；否则被处决。因此：

    P(存活) = P(T 次抽样覆盖全部 100 人)

这正是优惠券收集问题。程序同时给出：
1. 用容斥原理计算的精确概率；
2. 蒙特卡洛模拟结果，用于交叉验证。
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Sequence


CHECKPOINTS = tuple(range(1000, 10001, 1000))


def exact_failure_probability(n: int, t: int) -> Decimal:
    """返回 T 次抽样后至少有一人没被抽到的精确概率。

    容斥原理：
        P(至少一人缺失)
          = sum_{k=1..n} (-1)^(k+1) C(n,k) ((n-k)/n)^T
    """
    if n <= 0:
        raise ValueError("人数必须是正整数")
    if t < 0:
        raise ValueError("审讯次数不能为负")

    with localcontext() as ctx:
        ctx.prec = 80
        total = Decimal(0)
        for k in range(1, n + 1):
            p = Decimal(n - k) / Decimal(n)
            term = Decimal(math.comb(n, k)) * (p ** t)
            if k % 2 == 1:
                total += term
            else:
                total -= term
        return +total


def exact_survival_probability(n: int, t: int) -> Decimal:
    """返回 T 次抽样覆盖全部 n 人的精确概率。"""
    with localcontext() as ctx:
        ctx.prec = 80
        return Decimal(1) - exact_failure_probability(n, t)


def simulate_completion_times(
    n: int,
    trials: int,
    rng: random.Random,
    max_t: int,
) -> list[int]:
    """模拟 trials 次，返回每次集齐全部 n 人所需的审讯次数。

    若到 max_t 次仍未集齐，则记录 max_t + 1，表示这些实验在所有待考察
    的时间点上都失败。
    """
    if n <= 0 or trials <= 0 or max_t < 0:
        raise ValueError("参数必须为正数（max_t 可为 0）")

    completion_times: list[int] = []
    for _ in range(trials):
        seen: set[int] = set()
        t = 0
        while len(seen) < n and t < max_t:
            seen.add(rng.randrange(n))
            t += 1
        completion_times.append(t if len(seen) == n else max_t + 1)
    return completion_times


def format_exact(failure: Decimal) -> tuple[str, str]:
    """把精确的失败概率格式化为（存活概率, 死亡概率）字符串。"""
    with localcontext() as ctx:
        ctx.prec = 80
        survival_pct = (Decimal(1) - failure) * Decimal(100)

        if failure >= Decimal("0.001"):
            survival_text = f"{survival_pct:.10f}%"
            death_text = f"{failure * 100:.10f}%"
        elif failure >= Decimal("1e-12"):
            survival_text = f"{survival_pct:.12f}%"
            death_text = f"{failure:.6e}"
        else:
            survival_text = f"1 - {failure:.6e}"
            death_text = f"{failure:.6e}"

    return survival_text, death_text


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """二项比例的 Wilson 95% 置信区间。"""
    if trials <= 0:
        raise ValueError("试验次数必须为正")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="计算固定审讯次数后宣布“全员已被抽到”的生存概率。"
    )
    parser.add_argument("-n", "--prisoners", type=int, default=100,
                        help="囚徒人数（默认 100）")
    parser.add_argument("--trials", type=int, default=100_000,
                        help="蒙特卡洛模拟次数（默认 100000）")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子（默认 42；-1 表示使用系统随机源）")
    parser.add_argument("--csv", type=Path,
                        help="可选：把结果写入 CSV 文件")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    args = parse_args(argv)
    if args.prisoners <= 1:
        print("人数必须大于 1。", file=sys.stderr)
        return 2
    if args.trials <= 0:
        print("模拟次数必须为正。", file=sys.stderr)
        return 2

    checkpoints = CHECKPOINTS
    max_t = checkpoints[-1]
    seed = None if args.seed == -1 else args.seed
    rng = random.Random(seed)

    print("固定时间宣布策略：生存概率（优惠券收集问题）")
    print(
        f"囚徒人数 n = {args.prisoners}，"
        f"蒙特卡洛次数 = {args.trials}，随机种子 = {args.seed}"
    )
    print("假设：每次审讯独立、均匀随机抽取一名囚徒；T 为全局审讯次数。")
    print()

    completion_times = simulate_completion_times(
        args.prisoners, args.trials, rng, max_t
    )

    rows: list[dict[str, object]] = []
    header = (
        f"{'T':>5}  {'精确存活概率':>24}  {'精确死亡概率':>14}  "
        f"{'模拟存活率':>12}  {'模拟死亡次数':>10}  {'95% CI 下限':>11}"
    )
    print(header)
    print("-" * len(header))

    for t in checkpoints:
        failure = exact_failure_probability(args.prisoners, t)
        survival_text, death_text = format_exact(failure)
        successes = sum(1 for c in completion_times if c <= t)
        failures = args.trials - successes
        simulated = successes / args.trials
        ci_low, ci_high = wilson_interval(successes, args.trials)
        print(
            f"{t:>5}  {survival_text:>24}  {death_text:>14}  "
            f"{simulated * 100:>11.6f}%  {failures:>10d}  {ci_low * 100:>10.4f}%"
        )
        rows.append({
            "T": t,
            "exact_survival": str(exact_survival_probability(args.prisoners, t)),
            "exact_failure": str(failure),
            "simulated_survival": f"{simulated:.12f}",
            "simulated_survival_percent": f"{simulated * 100:.9f}",
            "simulated_failures": failures,
            "simulation_trials": args.trials,
            "ci95_low_percent": f"{ci_low * 100:.9f}",
            "ci95_high_percent": f"{ci_high * 100:.9f}",
        })

    print()
    mean_completion = sum(min(c, max_t + 1) for c in completion_times) / args.trials
    print(f"集齐全部 {args.prisoners} 人的理论平均审讯次数："
          f"{args.prisoners * sum(1.0 / k for k in range(1, args.prisoners + 1)):.3f}")
    print(f"本次模拟的平均集齐时间（超过 {max_t} 次按 {max_t + 1} 计）："
          f"{mean_completion:.3f}")

    if args.csv is not None:
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n结果已写入：{args.csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
