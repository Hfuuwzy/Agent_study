"""evaluate.py — 工单 06 黄金评测集 CLI：离线桩场景（默认）与真实 Key 快乐路径（显式开关）。

用法（backend 目录下）：
    python -B evaluate.py                          # 全部 5 条离线场景
    python -B evaluate.py --case happy_path        # 只运行指定场景
    python -B evaluate.py --real --case happy_path # 真实 Key 快乐路径（唯一真实模式）

输出契约（逐条后打印汇总）：
    PASS <id>: <reason>
    FAIL <id>: <reason>
    SUMMARY passed=N failed=N total=N mode=offline|real

退出码：0 = 全部通过；1 = 存在失败或未预期错误；2 = 用法错误 / 未知场景 / 真实模式预检失败。

噪音控制：每个场景运行期间把应用输出（stdout/stderr 的 print 与 loguru 日志）捕获进
内存缓冲并丢弃，保证 PASS/FAIL/SUMMARY 行干净可读；绝不打印凭据、提示词或载荷。

异常策略（顶层 CLI 边界）：
- 场景级只捕获 ``AssertionError``（视为该场景失败，用其消息作失败原因），继续后续场景；
- 其余未预期异常不在此层吞掉，统一上抛到 ``main`` 的顶层宽捕获——CLI 是单次进程，
  ``main`` 即进程边界，此处显式允许 broad catch，把异常转为单行净化后的失败原因并退出 1。
"""

import argparse
import io
import sys
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from typing import Final, Sequence

# 抑制第三方库（starlette/httpx/fastapi）的弃用告警——二者均为 UserWarning 子类
# （StarletteDeprecationWarning / FastAPIDeprecationWarning），保持 CLI 输出干净。
# 必须早于 tests.evaluation -> app 的 import 链执行，故其后的 import 被评 E402（有意为之）。
warnings.filterwarnings("ignore", category=UserWarning)

from loguru import logger  # noqa: E402

from tests.evaluation.checks import assert_scenario  # noqa: E402
from tests.evaluation.harness import run_scenario  # noqa: E402
from tests.evaluation.real_mode import (  # noqa: E402
    REAL_CASE_ID,
    RealPreflightError,
    run_real_happy_path,
    validate_real_happy_path,
)
from tests.evaluation.scenario_models import Scenario, load_scenarios  # noqa: E402

EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1
EXIT_USAGE: Final = 2

SUMMARY_MODE_OFFLINE: Final = "offline"
SUMMARY_MODE_REAL: Final = "real"


@contextmanager
def _quiet_run() -> Iterator[None]:
    """把应用噪音（stdout/stderr 的 print 与 loguru）捕获进内存缓冲并丢弃。

    CLI 是单次进程：进入时移除既有 loguru handler 并挂内存 sink，退出时再移除该 sink；
    进程结束前无需恢复全局 handler。stdout/stderr 经 ExitStack 原样恢复。
    """
    buffer = io.StringIO()
    logger.remove()
    logger.add(buffer, format="{message}", level="INFO")
    try:
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(buffer))
            stack.enter_context(redirect_stderr(buffer))
            yield
    finally:
        logger.remove()


def _sanitize_reason(exc: BaseException | str) -> str:
    """把异常/文本压成单行、截断的原因（不泄露载荷细节）。"""
    return " ".join(str(exc).split())[:300]


def _summary_line(passed: int, failed: int, total: int, mode: str) -> str:
    return f"SUMMARY passed={passed} failed={failed} total={total} mode={mode}"


def _run_offline(scenarios: dict[str, Scenario], only: str | None) -> int:
    """按顺序运行离线场景：每条 PASS/FAIL 一行，最后打印 SUMMARY。"""
    ordered = list(scenarios.values()) if only is None else [scenarios[only]]
    passed = 0
    failed = 0
    for scenario in ordered:
        try:
            with _quiet_run():
                run = run_scenario(scenario)
                assert_scenario(run)
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {scenario.id}: {_sanitize_reason(exc)}")
            continue
        passed += 1
        print(f"PASS {scenario.id}: {scenario.name}")
    print(_summary_line(passed, failed, len(ordered), SUMMARY_MODE_OFFLINE))
    return EXIT_OK if failed == 0 else EXIT_FAILURE


def _run_real() -> int:
    """真实 Key 快乐路径：预检失败退出 2；校验失败退出 1；通过退出 0。"""
    try:
        with _quiet_run():
            outcome = run_real_happy_path()
            validate_real_happy_path(outcome)
    except RealPreflightError as exc:
        for problem in exc.problems:
            print(f"REAL_PREFLIGHT: {_sanitize_reason(problem)}", file=sys.stderr)
        return EXIT_USAGE
    except AssertionError as exc:
        print(f"FAIL {REAL_CASE_ID}: {_sanitize_reason(exc)}")
        print(_summary_line(0, 1, 1, SUMMARY_MODE_REAL))
        return EXIT_FAILURE
    print(f"PASS {REAL_CASE_ID}: 真实 Key 快乐路径结构校验通过")
    print(_summary_line(1, 0, 1, SUMMARY_MODE_REAL))
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluate.py",
        description="工单 06 黄金评测集 CLI：离线桩场景（默认）或真实 Key 快乐路径（--real）",
    )
    parser.add_argument("--case", metavar="ID", help="只运行指定场景（如 happy_path）")
    parser.add_argument("--real", action="store_true", help=f"真实 Key 模式（仅 --case {REAL_CASE_ID}）")
    return parser


def _main_inner(argv: Sequence[str] | None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    scenarios = {scenario.id: scenario for scenario in load_scenarios()}

    if args.real and args.case != REAL_CASE_ID:
        parser.error(f"--real 仅支持 --case {REAL_CASE_ID}（当前唯一真实模式）")
    if args.case is not None and args.case not in scenarios:
        parser.error(f"未知场景 {args.case!r}（可用: {', '.join(sorted(scenarios))}）")

    if args.real:
        return _run_real()
    return _run_offline(scenarios, only=args.case)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 进程边界：未预期异常在此宽捕获（见模块 docstring）并转为净化失败原因。

    ``SystemExit`` / ``KeyboardInterrupt`` 属 ``BaseException``，不在此捕获，正常上抛。
    """
    try:
        return _main_inner(argv)
    except Exception as exc:
        print(f"FAIL: {_sanitize_reason(exc)}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())