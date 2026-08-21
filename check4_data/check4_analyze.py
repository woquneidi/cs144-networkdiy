#!/usr/bin/env python3

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib

# 在 WSL 没有图形窗口的情况下，直接把图保存为 PNG
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np


@dataclass
class Reply:
    """一条成功收到的 ping 回复。"""

    timestamp: float
    sequence: int
    rtt: float
    rtt_operator: str


# 匹配这种回复行：
#
# [1787284835.808034] 64 bytes from 39.156.70.46:
# icmp_seq=1 ttl=50 time=22.8 ms
#
# 同时也兼容：
#
# time<1 ms
REPLY_PATTERN = re.compile(
    r"^\[(?P<timestamp>[0-9.]+)\]"
    r".*?"
    r"icmp_seq=(?P<sequence>[0-9]+)"
    r".*?"
    r"time(?P<operator>[=<])(?P<rtt>[0-9.]+)\s*ms"
)


# 匹配 ping 结束后的统计信息：
#
# 20910 packets transmitted, 17838 received
SUMMARY_PATTERN = re.compile(
    r"(?P<sent>[0-9]+)\s+packets transmitted,"
    r"\s+(?P<received>[0-9]+)\s+received"
)


def load_ping_file(path: Path):
    """
    读取 ping 输出文件。

    返回：
        sent:
            实际发送数量。如果文件有最终统计摘要，就使用摘要；
            否则使用最大的 icmp_seq 估计。

        replies:
            按序列号保存的成功回复。一个序列号只保留一次。

        duplicate_count:
            重复序列号的回复数量。
    """

    text = path.read_text(encoding="utf-8", errors="replace")

    replies_by_sequence: dict[int, Reply] = {}
    duplicate_count = 0

    for line in text.splitlines():
        match = REPLY_PATTERN.search(line)

        if match is None:
            continue

        reply = Reply(
            timestamp=float(match.group("timestamp")),
            sequence=int(match.group("sequence")),
            rtt=float(match.group("rtt")),
            rtt_operator=match.group("operator"),
        )

        if reply.sequence in replies_by_sequence:
            duplicate_count += 1
            continue

        replies_by_sequence[reply.sequence] = reply

    if not replies_by_sequence:
        raise ValueError(
            f"{path} 中没有找到有效的 ping 回复。"
            "请检查文件内容和正则表达式。"
        )

    # finditer 找到全部摘要，使用最后一个。
    summaries = list(SUMMARY_PATTERN.finditer(text))

    if summaries:
        sent = int(summaries[-1].group("sent"))
    else:
        # 如果 Ctrl+C 后统计摘要没有进入文件，
        # 就使用最大序列号估算发送数量。
        sent = max(replies_by_sequence)

    # 排除不合理地超出发送范围的回复。
    replies = [
        reply
        for sequence, reply in sorted(replies_by_sequence.items())
        if 1 <= sequence <= sent
    ]

    return sent, replies, duplicate_count


def make_delivery_status(sent: int, replies: list[Reply]):
    """
    构造每个 ping 是否收到回复的数组。

    status[i] 对应 icmp_seq=i+1：

        1：收到回复
        0：没有收到回复
    """

    status = np.zeros(sent, dtype=np.int8)

    for reply in replies:
        if 1 <= reply.sequence <= sent:
            status[reply.sequence - 1] = 1

    return status


def get_valid_rtt_replies(replies: list[Reply]):
    """
    选择可以用于 RTT 分析的回复。

    time=0.000 ms 不可能是当前远程路径的真实 RTT，
    因此只保留：

        operator == "="
        RTT > 0

    这些异常回复依旧被当成成功交付，只是不用于 RTT 统计。
    """

    valid = []
    invalid = []

    for reply in replies:
        if reply.rtt_operator == "=" and reply.rtt > 0:
            valid.append(reply)
        else:
            invalid.append(reply)

    return valid, invalid


def calculate_longest_runs(status: np.ndarray):
    """
    计算：

    1. 最长连续成功次数
    2. 最长连续丢包次数
    """

    longest_success = 0
    longest_loss = 0

    current_success = 0
    current_loss = 0

    for delivered in status:
        if delivered == 1:
            current_success += 1
            current_loss = 0
        else:
            current_loss += 1
            current_success = 0

        longest_success = max(longest_success, current_success)
        longest_loss = max(longest_loss, current_loss)

    return longest_success, longest_loss


def calculate_autocorrelation(
    status: np.ndarray,
    max_lag: int = 10,
):
    """
    计算教程要求的两个条件概率：

    P(N+k 成功 | N 成功)

    P(N+k 丢失 | N 丢失)

    k 的范围是 -10 到 10。
    """

    lags = np.arange(-max_lag, max_lag + 1)

    success_after_success = []
    loss_after_loss = []

    for lag in lags:
        if lag == 0:
            original = status
            shifted = status

        elif lag > 0:
            # original 对应 N
            # shifted 对应 N+k
            original = status[:-lag]
            shifted = status[lag:]

        else:
            # 例如 lag=-2：
            #
            # original 对应 N
            # shifted 对应 N-2
            original = status[-lag:]
            shifted = status[:lag]

        original_success = original == 1
        original_loss = original == 0

        if np.any(original_success):
            probability_success = np.mean(
                shifted[original_success] == 1
            )
        else:
            probability_success = np.nan

        if np.any(original_loss):
            probability_loss = np.mean(
                shifted[original_loss] == 0
            )
        else:
            probability_loss = np.nan

        success_after_success.append(probability_success)
        loss_after_loss.append(probability_loss)

    return (
        lags,
        np.array(success_after_success),
        np.array(loss_after_loss),
    )


def calculate_statistics(
    name: str,
    sent: int,
    replies: list[Reply],
    duplicate_count: int,
):
    """计算并返回一条路径的全部统计数据。"""

    status = make_delivery_status(sent, replies)

    received = int(np.sum(status))
    lost = sent - received

    delivery_rate = received / sent if sent else 0.0
    loss_rate = lost / sent if sent else 0.0

    longest_success, longest_loss = calculate_longest_runs(status)

    valid_replies, invalid_replies = get_valid_rtt_replies(replies)

    if not valid_replies:
        raise ValueError(f"{name} 没有可以用于 RTT 分析的有效数据")

    rtts = np.array(
        [reply.rtt for reply in valid_replies],
        dtype=float,
    )

    # 数据覆盖时间仍然使用全部成功回复，
    # 因为 RTT 异常不等于时间戳异常。
    all_timestamps = np.array(
        [reply.timestamp for reply in replies],
        dtype=float,
    )

    duration_seconds = (
        float(np.max(all_timestamps) - np.min(all_timestamps))
        if len(all_timestamps) >= 2
        else 0.0
    )

    statistics = {
        "name": name,
        "sent": sent,
        "received": received,
        "lost": lost,
        "delivery_rate": delivery_rate,
        "loss_rate": loss_rate,
        "longest_success": longest_success,
        "longest_loss": longest_loss,
        "minimum_rtt": float(np.min(rtts)),
        "average_rtt": float(np.mean(rtts)),
        "maximum_rtt": float(np.max(rtts)),
        "rtt_standard_deviation": float(np.std(rtts)),
        "valid_rtt_count": len(valid_replies),
        "invalid_rtt_count": len(invalid_replies),
        "duplicate_count": duplicate_count,
        "duration_seconds": duration_seconds,
    }

    return statistics, status, valid_replies, invalid_replies


def print_statistics(statistics: dict):
    """将统计结果打印到终端。"""

    print(f"\n========== {statistics['name']} ==========")

    print(f"发送数量:          {statistics['sent']}")
    print(f"收到回复:          {statistics['received']}")
    print(f"丢失数量:          {statistics['lost']}")

    print(
        "交付率:            "
        f"{statistics['delivery_rate'] * 100:.2f}%"
    )

    print(
        "丢包率:            "
        f"{statistics['loss_rate'] * 100:.2f}%"
    )

    print(
        "最长连续成功:      "
        f"{statistics['longest_success']}"
    )

    print(
        "最长连续丢包:      "
        f"{statistics['longest_loss']}"
    )

    print(
        "最小有效 RTT:      "
        f"{statistics['minimum_rtt']:.3f} ms"
    )

    print(
        "平均有效 RTT:      "
        f"{statistics['average_rtt']:.3f} ms"
    )

    print(
        "最大有效 RTT:      "
        f"{statistics['maximum_rtt']:.3f} ms"
    )

    print(
        "RTT 标准差:        "
        f"{statistics['rtt_standard_deviation']:.3f} ms"
    )

    print(
        "有效 RTT 样本:     "
        f"{statistics['valid_rtt_count']}"
    )

    print(
        "排除的异常 RTT:    "
        f"{statistics['invalid_rtt_count']}"
    )

    print(
        "重复回复数量:      "
        f"{statistics['duplicate_count']}"
    )

    print(
        "数据时间跨度:      "
        f"{statistics['duration_seconds'] / 60:.2f} 分钟"
    )


def save_invalid_rtts(
    name: str,
    invalid_replies: list[Reply],
    output_dir: Path,
):
    """将被排除的异常 RTT 保存到 CSV，方便在报告中说明。"""

    path = output_dir / f"{name}_invalid_rtts.csv"

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "timestamp",
                "local_time",
                "icmp_sequence",
                "operator",
                "rtt_ms",
            ]
        )

        for reply in invalid_replies:
            local_time = datetime.fromtimestamp(
                reply.timestamp
            ).isoformat(sep=" ")

            writer.writerow(
                [
                    reply.timestamp,
                    local_time,
                    reply.sequence,
                    reply.rtt_operator,
                    reply.rtt,
                ]
            )


def plot_rtt_over_time(
    name: str,
    valid_replies: list[Reply],
    figure_dir: Path,
):
    """绘制 RTT 随真实时间变化的图。"""

    times = [
        datetime.fromtimestamp(reply.timestamp)
        for reply in valid_replies
    ]

    rtts = np.array(
        [reply.rtt for reply in valid_replies],
        dtype=float,
    )

    figure, axis = plt.subplots(figsize=(13, 5))

    axis.plot(
        times,
        rtts,
        ".",
        markersize=1.5,
        alpha=0.7,
    )

    axis.set_xlabel("Local time")
    axis.set_ylabel("RTT (ms)")
    axis.set_title(f"{name}: RTT over time")

    axis.xaxis.set_major_formatter(
        mdates.DateFormatter("%H:%M:%S")
    )

    figure.autofmt_xdate()
    axis.grid(True, alpha=0.3)

    figure.tight_layout()

    figure.savefig(
        figure_dir / f"{name}_rtt_time.png",
        dpi=180,
    )

    plt.close(figure)


def plot_rtt_cdf(
    name: str,
    valid_replies: list[Reply],
    figure_dir: Path,
):
    """
    绘制 RTT 累积分布函数。

    对于某个 x：

        y = RTT 小于或等于 x 的样本比例
    """

    sorted_rtts = np.sort(
        np.array(
            [reply.rtt for reply in valid_replies],
            dtype=float,
        )
    )

    probabilities = (
        np.arange(1, len(sorted_rtts) + 1)
        / len(sorted_rtts)
    )

    figure, axis = plt.subplots(figsize=(8, 5))

    axis.plot(sorted_rtts, probabilities)

    axis.set_xlabel("RTT (ms)")
    axis.set_ylabel("Fraction of samples <= RTT")
    axis.set_title(f"{name}: RTT cumulative distribution")

    axis.set_ylim(0, 1.02)
    axis.grid(True, alpha=0.3)

    figure.tight_layout()

    figure.savefig(
        figure_dir / f"{name}_rtt_cdf.png",
        dpi=180,
    )

    plt.close(figure)


def plot_adjacent_rtt_scatter(
    name: str,
    valid_replies: list[Reply],
    figure_dir: Path,
):
    """
    绘制真正相邻的 ping N 和 ping N+1 的 RTT 散点图。

    如果 N+1 丢包，不会错误地把 N 和 N+2 配成一对。
    """

    rtt_by_sequence = {
        reply.sequence: reply.rtt
        for reply in valid_replies
    }

    x_rtts = []
    y_rtts = []

    for sequence, rtt in rtt_by_sequence.items():
        next_sequence = sequence + 1

        if next_sequence not in rtt_by_sequence:
            continue

        x_rtts.append(rtt)
        y_rtts.append(rtt_by_sequence[next_sequence])

    if not x_rtts:
        print(f"{name} 没有足够的相邻 RTT 数据，跳过散点图")
        return

    x_rtts = np.array(x_rtts, dtype=float)
    y_rtts = np.array(y_rtts, dtype=float)

    figure, axis = plt.subplots(figsize=(7, 7))

    axis.scatter(
        x_rtts,
        y_rtts,
        s=4,
        alpha=0.35,
    )

    low = min(float(np.min(x_rtts)), float(np.min(y_rtts)))
    high = max(float(np.max(x_rtts)), float(np.max(y_rtts)))

    axis.plot(
        [low, high],
        [low, high],
        "--",
        color="gray",
        linewidth=1,
        label="y = x",
    )

    correlation = np.corrcoef(x_rtts, y_rtts)[0, 1]

    axis.set_xlabel("RTT of ping N (ms)")
    axis.set_ylabel("RTT of ping N+1 (ms)")

    axis.set_title(
        f"{name}: Adjacent RTT scatter\n"
        f"Pearson correlation = {correlation:.3f}"
    )

    axis.grid(True, alpha=0.3)
    axis.legend()

    figure.tight_layout()

    figure.savefig(
        figure_dir / f"{name}_rtt_scatter.png",
        dpi=180,
    )

    plt.close(figure)


def plot_delivery_autocorrelation(
    name: str,
    status: np.ndarray,
    figure_dir: Path,
    output_dir: Path,
):
    """绘制并保存丢包自相关的条件概率。"""

    (
        lags,
        success_after_success,
        loss_after_loss,
    ) = calculate_autocorrelation(status)

    delivery_rate = float(np.mean(status == 1))
    loss_rate = float(np.mean(status == 0))

    figure, axis = plt.subplots(figsize=(10, 5.5))

    axis.plot(
        lags,
        success_after_success,
        "o-",
        label="P(success at N+k | success at N)",
    )

    if np.any(~np.isnan(loss_after_loss)):
        axis.plot(
            lags,
            loss_after_loss,
            "o-",
            label="P(loss at N+k | loss at N)",
        )

    # 无条件交付率，供比较。
    axis.axhline(
        delivery_rate,
        color="tab:blue",
        linestyle="--",
        alpha=0.5,
        label="Unconditional delivery rate",
    )

    # 无条件丢包率，供比较。
    axis.axhline(
        loss_rate,
        color="tab:orange",
        linestyle="--",
        alpha=0.5,
        label="Unconditional loss rate",
    )

    axis.set_xlabel("Offset k")
    axis.set_ylabel("Conditional probability")
    axis.set_title(f"{name}: Packet delivery autocorrelation")

    axis.set_xticks(lags)
    axis.set_ylim(-0.02, 1.02)

    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=8)

    figure.tight_layout()

    figure.savefig(
        figure_dir / f"{name}_loss_autocorrelation.png",
        dpi=180,
    )

    plt.close(figure)

    # 同时将精确数值保存为 CSV。
    csv_path = output_dir / f"{name}_autocorrelation.csv"

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "k",
                "P(success_N_plus_k_given_success_N)",
                "P(loss_N_plus_k_given_loss_N)",
            ]
        )

        for lag, success_probability, loss_probability in zip(
            lags,
            success_after_success,
            loss_after_loss,
        ):
            writer.writerow(
                [
                    int(lag),
                    success_probability,
                    loss_probability,
                ]
            )


def plot_packet_pattern(
    name: str,
    status: np.ndarray,
    figure_dir: Path,
):
    """
    绘制前 5000 个 ping 的成功/丢包状态。

    这张图不是教程强制要求，但有助于观察突发丢包。
    """

    sample_size = min(len(status), 5000)
    sample = status[:sample_size]

    sequences = np.arange(1, sample_size + 1)

    figure, axis = plt.subplots(figsize=(13, 2.8))

    axis.plot(
        sequences,
        sample,
        ".",
        markersize=1.5,
    )

    axis.set_yticks([0, 1])
    axis.set_yticklabels(["loss", "success"])

    axis.set_xlabel("ICMP sequence number")
    axis.set_title(
        f"{name}: Success/loss pattern "
        f"(first {sample_size} packets)"
    )

    axis.grid(True, axis="y", alpha=0.3)

    figure.tight_layout()

    figure.savefig(
        figure_dir / f"{name}_packet_pattern.png",
        dpi=180,
    )

    plt.close(figure)


def save_summary(
    all_statistics: list[dict],
    output_dir: Path,
):
    """把三条路径的汇总统计保存成 CSV。"""

    summary_path = output_dir / "summary.csv"

    fieldnames = [
        "name",
        "sent",
        "received",
        "lost",
        "delivery_rate",
        "loss_rate",
        "longest_success",
        "longest_loss",
        "minimum_rtt",
        "average_rtt",
        "maximum_rtt",
        "rtt_standard_deviation",
        "valid_rtt_count",
        "invalid_rtt_count",
        "duplicate_count",
        "duration_seconds",
    ]

    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(all_statistics)


def main():
    # 脚本位于 check4_data 目录，因此把脚本自己的目录
    # 作为数据目录。这样从任何位置运行都能找到文件。
    data_dir = Path(__file__).resolve().parent

    figure_dir = data_dir / "figures"
    output_dir = data_dir / "analysis_output"

    figure_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 左边是报告和图片中使用的名称，
    # 右边是你的实际文件名。
    files = {
        "baidu": data_dir / "baidu.txt",
        "1111": data_dir / "1111.txt",
        "canterbury": data_dir / "canterbury.txt",
    }

    all_statistics = []

    for name, path in files.items():
        if not path.exists():
            print(f"\n找不到文件：{path}")
            continue

        sent, replies, duplicate_count = load_ping_file(path)

        (
            statistics,
            status,
            valid_replies,
            invalid_replies,
        ) = calculate_statistics(
            name,
            sent,
            replies,
            duplicate_count,
        )

        print_statistics(statistics)
        all_statistics.append(statistics)

        save_invalid_rtts(
            name,
            invalid_replies,
            output_dir,
        )

        plot_rtt_over_time(
            name,
            valid_replies,
            figure_dir,
        )

        plot_rtt_cdf(
            name,
            valid_replies,
            figure_dir,
        )

        plot_adjacent_rtt_scatter(
            name,
            valid_replies,
            figure_dir,
        )

        plot_delivery_autocorrelation(
            name,
            status,
            figure_dir,
            output_dir,
        )

        plot_packet_pattern(
            name,
            status,
            figure_dir,
        )

    if all_statistics:
        save_summary(all_statistics, output_dir)

    print("\n分析完成。")
    print(f"图表目录：{figure_dir}")
    print(f"统计结果目录：{output_dir}")


if __name__ == "__main__":
    main()