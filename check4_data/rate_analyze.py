#!/usr/bin/env python3

import csv
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


SUMMARY_PATTERN = re.compile(
    r"(?P<sent>\d+)\s+packets transmitted,"
    r"\s+(?P<received>\d+)\s+received"
)

DURATION_PATTERN = re.compile(
    r"time\s+(?P<duration_ms>\d+)ms"
)


def parse_ping_summary(path: Path):
    """
    从一份短 ping 实验文件中读取：

    - 发送数量
    - 回复数量
    - 总持续时间
    """

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    summary_matches = list(
        SUMMARY_PATTERN.finditer(text)
    )

    duration_matches = list(
        DURATION_PATTERN.finditer(text)
    )

    if not summary_matches:
        raise ValueError(
            f"{path} 中没有找到 packets transmitted 摘要"
        )

    if not duration_matches:
        raise ValueError(
            f"{path} 中没有找到总持续时间"
        )

    summary = summary_matches[-1]
    duration = duration_matches[-1]

    sent = int(summary.group("sent"))
    received = int(summary.group("received"))

    duration_seconds = (
        int(duration.group("duration_ms")) / 1000.0
    )

    if duration_seconds <= 0:
        raise ValueError(f"{path} 的持续时间不合理")

    return sent, received, duration_seconds


def analyze_target(
    name: str,
    directory: Path,
    packet_size_bytes: int,
):
    """
    分析一个目标的所有不同发送间隔实验。
    """

    intervals = [
        0.2,
        0.1,
        0.05,
        0.02,
        0.01,
    ]

    results = []

    for interval in intervals:
        filename = f"i_{interval}.txt"
        path = directory / filename

        if not path.exists():
            print(f"找不到文件：{path}")
            continue

        sent, received, duration = parse_ping_summary(path)

        request_rate_mbps = (
            packet_size_bytes
            * sent
            * 8
            / duration
            / 1_000_000
        )

        reply_rate_mbps = (
            packet_size_bytes
            * received
            * 8
            / duration
            / 1_000_000
        )

        delivery_rate = (
            received / sent
            if sent > 0
            else 0.0
        )

        result = {
            "target": name,
            "interval_seconds": interval,
            "packet_size_bytes": packet_size_bytes,
            "sent": sent,
            "received": received,
            "duration_seconds": duration,
            "delivery_rate": delivery_rate,
            "request_rate_mbps": request_rate_mbps,
            "reply_rate_mbps": reply_rate_mbps,
        }

        results.append(result)

    results.sort(
        key=lambda item: item["request_rate_mbps"]
    )

    return results


def print_results(name: str, results: list[dict]):
    print(f"\n========== {name} ==========")

    for result in results:
        print(
            f"interval={result['interval_seconds']:.3f}s, "
            f"sent={result['sent']}, "
            f"received={result['received']}, "
            f"delivery={result['delivery_rate'] * 100:.2f}%, "
            f"request={result['request_rate_mbps']:.4f} Mbit/s, "
            f"reply={result['reply_rate_mbps']:.4f} Mbit/s"
        )


def save_csv(
    all_results: list[dict],
    output_path: Path,
):
    fieldnames = [
        "target",
        "interval_seconds",
        "packet_size_bytes",
        "sent",
        "received",
        "duration_seconds",
        "delivery_rate",
        "request_rate_mbps",
        "reply_rate_mbps",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(all_results)


def plot_all_targets(
    target_results: dict[str, list[dict]],
    output_path: Path,
):
    figure, axis = plt.subplots(figsize=(8, 6))

    for name, results in target_results.items():
        if not results:
            continue

        request_rates = [
            item["request_rate_mbps"]
            for item in results
        ]

        reply_rates = [
            item["reply_rate_mbps"]
            for item in results
        ]

        axis.plot(
            request_rates,
            reply_rates,
            "o-",
            label=name,
        )

    # 理想情况：每个请求都收到回复，
    # 因此回复速率等于请求速率。
    maximum = max(
        item["request_rate_mbps"]
        for results in target_results.values()
        for item in results
    )

    axis.plot(
        [0, maximum],
        [0, maximum],
        "--",
        color="gray",
        label="Ideal: reply rate = request rate",
    )

    axis.set_xlabel("Request data rate (Mbit/s)")
    axis.set_ylabel("Reply data rate (Mbit/s)")

    axis.set_title(
        "Ping reply data rate versus request data rate"
    )

    axis.grid(True, alpha=0.3)
    axis.legend()

    figure.tight_layout()
    figure.savefig(output_path, dpi=180)

    plt.close(figure)


def main():
    data_dir = Path(__file__).resolve().parent

    experiment_dir = (
        data_dir / "rate_experiment"
    )

    packet_size_bytes = 1000

    directories = {
        "baidu": experiment_dir / "baidu",
        "1111": experiment_dir / "1111",
        "canterbury": experiment_dir / "canterbury",
    }

    target_results = {}
    all_results = []

    for name, directory in directories.items():
        results = analyze_target(
            name,
            directory,
            packet_size_bytes,
        )

        target_results[name] = results
        all_results.extend(results)

        print_results(name, results)

    output_csv = (
        experiment_dir / "rate_results.csv"
    )

    output_figure = (
        experiment_dir / "reply_rate.png"
    )

    save_csv(all_results, output_csv)

    if all_results:
        plot_all_targets(
            target_results,
            output_figure,
        )

    print("\n短期速率实验分析完成。")
    print(f"统计数据：{output_csv}")
    print(f"图表：{output_figure}")


if __name__ == "__main__":
    main()