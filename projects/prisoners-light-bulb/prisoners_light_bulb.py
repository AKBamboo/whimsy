#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟“100 囚徒与一个灯泡”谜题。

协议
----
- 指定 1 名囚徒为计数器，其余 n-1 人为跟随者。
- 跟随者第一次发现灯关着时，把灯打开；此后不再动开关。
- 计数器每次进入房间，如果灯亮着，就把灯关掉并计数。
- 计数器第 n-1 次关灯时，宣布所有人都已被审问过。

说明：跟随者的“第一次”指第一次发现灯关着。若把它理解为“第一次进入
房间时灯必须恰好关着，否则以后永远不作为”，那么灯亮时首次进入的
跟随者将永远无法被计数，协议也就不能保证成功。
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Sequence


def simulate_once(n: int, rng: random.Random, counter: int = 0) -> int:
    """模拟一次实验，返回直到宣布获释时的审问总次数。"""
    if n <= 0:
        raise ValueError("囚徒人数必须是正整数")
    if not 0 <= counter < n:
        raise ValueError("计数器编号越界")
    if n == 1:
        return 1

    light_on = False
    # follower_done[i] 表示跟随者 i 是否已经开过一次灯。
    follower_done = [False] * n
    follower_done[counter] = True
    counter_turns_off = 0
    interrogations = 0

    while True:
        prisoner = rng.randrange(n)
        interrogations += 1

        if prisoner == counter:
            if light_on:
                light_on = False
                counter_turns_off += 1
                if counter_turns_off == n - 1:
                    return interrogations
        elif not follower_done[prisoner] and not light_on:
            light_on = True
            follower_done[prisoner] = True


def simulate(n: int, trials: int, seed: int | None = None) -> list[int]:
    """独立模拟 trials 次，返回每次所需审问次数的列表。"""
    if trials <= 0:
        raise ValueError("模拟次数必须是正整数")
    rng = random.Random(seed)
    return [simulate_once(n, rng) for _ in range(trials)]


def percentile(sorted_values: Sequence[int], q: float) -> float:
    """线性插值分位数，q 取 0 到 1。"""
    if not sorted_values:
        raise ValueError("空序列没有分位数")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q 必须在 [0, 1] 内")
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def theoretical_mean(n: int) -> float:
    """给定协议下的理论期望值：n(n-1) + n * H_(n-1)。"""
    if n == 1:
        return 1.0
    harmonic = sum(1.0 / k for k in range(1, n))
    return n * (n - 1) + n * harmonic


def print_report(results: Sequence[int], n: int, seed: int | None) -> None:
    trials = len(results)
    print("一百囚徒与一个灯泡 —— 蒙特卡洛模拟")
    print(f"囚徒人数 n = {n}，模拟次数 = {trials}，随机种子 = {seed}")
    print("-" * 52)
    for i, count in enumerate(results, start=1):
        print(f"第 {i:3d} 次：{count:>8d} 次审问")
    print("-" * 52)

    ordered = sorted(results)
    mean = statistics.mean(results)
    std = statistics.stdev(results) if trials >= 2 else 0.0
    sem = std / math.sqrt(trials) if trials >= 2 else 0.0
    print(f"最小值       ：{min(results):>8d}")
    print(f"第 25 百分位 ：{percentile(ordered, 0.25):>8.1f}")
    print(f"中位数       ：{statistics.median(results):>8.1f}")
    print(f"第 75 百分位 ：{percentile(ordered, 0.75):>8.1f}")
    print(f"最大值       ：{max(results):>8d}")
    print(f"平均值       ：{mean:>8.2f}")
    print(f"样本标准差   ：{std:>8.2f}")
    print(f"均值 95% CI  ：[{mean - 1.96 * sem:.2f}, {mean + 1.96 * sem:.2f}]")
    print(f"理论期望     ：{theoretical_mean(n):>8.2f}")


def write_csv(path: Path, results: Sequence[int]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["trial", "interrogations"])
        for trial, count in enumerate(results, start=1):
            writer.writerow([trial, count])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="模拟一百囚徒与一个灯泡谜题，统计获释所需的审问次数。"
    )
    parser.add_argument("-n", "--prisoners", type=int, default=100,
                        help="囚徒人数（默认 100）")
    parser.add_argument("-t", "--trials", type=int, default=100,
                        help="模拟次数（默认 100）")
    parser.add_argument("-s", "--seed", type=int, default=42,
                        help="随机种子（默认 42；设为 -1 则使用系统随机源）")
    parser.add_argument("--csv", type=Path,
                        help="可选：把每次实验的结果写入 CSV 文件")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    args = parse_args(argv)
    seed = None if args.seed == -1 else args.seed
    try:
        results = simulate(args.prisoners, args.trials, seed)
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2

    print_report(results, args.prisoners, args.seed)
    if args.csv is not None:
        write_csv(args.csv, results)
        print(f"\n结果已写入：{args.csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
