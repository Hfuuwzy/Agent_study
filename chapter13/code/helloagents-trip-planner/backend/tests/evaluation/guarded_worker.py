"""受保护的离线评测 worker 进程（过程级证明：默认离线不写盘 / 不联网 / 不拉子进程）。

用法（backend 目录下）：
    python -B -m tests.evaluation.guarded_worker                      # 跑真实默认离线评测
    python -B -m tests.evaluation.guarded_worker --probe write        # 负向对照：写文件
    python -B -m tests.evaluation.guarded_worker --probe mutation     # 负向对照：文件树变更
    python -B -m tests.evaluation.guarded_worker --probe socket       # 负向对照：外部连接
    python -B -m tests.evaluation.guarded_worker --probe subprocess   # 负向对照：子进程派生

本 worker 在 import app/evaluate **之前**安装审计门（audit hook 进程全局、不可移除），
随后调用真实 ``evaluate.main([])``（绝不重实现场景）或执行指定探测。所有输出经管道
（stdout/stderr），不写任何临时文件；``python -B`` + 环境 ``PYTHONDONTWRITEBYTECODE=1``
双保险禁用 pyc 写出（即使有写出也会被门记录为违规）。

**守卫前零文件系统变更**：本地临时目录缓存直接复用已存在的 ``TEMP/TMP/TMPDIR`` 环境
目录（只读 ``os.path.isdir`` 校验），不调用 ``tempfile.gettempdir()``——其首次调用会
创建并删除一个探测文件。仅有的守卫前 OS 自省是 ``platform.uname()``（导入链必需的
``cmd /c ver`` 子进程，非磁盘写入）。

退出码：完整运行 0=通过且零违规；探测模式 1=被拦截（负向对照预期）、2=门未生效、
3=探测目标已预先存在。
"""

import argparse
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Callable, Final, Sequence

from .offline_guard import OfflineGuard, OfflineGuardViolation

#: 稳定写/目录探测目标：必须永远不被创建；运行前断言不存在。
WRITE_PROBE_PATH: Final[Path] = Path(__file__).resolve().parent.parent.parent / ".evaluation-write-probe"
MKDIR_PROBE_PATH: Final[Path] = Path(__file__).resolve().parent.parent.parent / ".evaluation-dir-probe"

_PROBE_KINDS: Final[tuple[str, ...]] = ("write", "mutation", "socket", "subprocess")

EXIT_OK: Final = 0
EXIT_BLOCKED: Final = 1
EXIT_NOT_BLOCKED: Final = 2
EXIT_PREEXISTING: Final = 3


def set_tempdir_from_env() -> None:
    """守卫前把 ``tempfile.tempdir`` 直接设为已存在的 TEMP/TMP/TMPDIR 环境目录。

    只读校验存在性（``os.path.isdir``），绝不调用 ``tempfile.gettempdir()``：后者首次
    调用会在 ``_get_default_tempdir`` 里创建并删除一个探测文件，形成守卫前的磁盘写入。
    portalocker 等库在模块导入期调用 ``gettempdir()`` 时直接命中缓存，不再触发写探测。
    全部候选目录都不存在时保持未设置（守卫会如实拦下后续的写探测）。
    """
    for key in ("TEMP", "TMP", "TMPDIR"):
        candidate = os.environ.get(key)
        if candidate and os.path.isdir(candidate):
            tempfile.tempdir = candidate
            return


def _assert_absent(path: Path) -> int:
    if path.exists():
        print(f"GUARD PREEXISTING {path}", file=sys.stderr)
        return EXIT_PREEXISTING
    return EXIT_OK


def _report(guard: OfflineGuard) -> None:
    for violation in guard.violations:
        print(f"GUARD VIOLATION kind={violation.kind} detail={violation.detail}")
    print(f"GUARD violations={len(guard.violations)}")


def _attempt_write() -> None:
    with open(WRITE_PROBE_PATH, "w") as handle:
        handle.write("probe")


def _attempt_mkdir() -> None:
    os.mkdir(MKDIR_PROBE_PATH)


def _attempt_socket() -> None:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # TEST-NET-1（RFC 5737 文档段，无真实主机）：门在 OS 发起连接前拦截，
        # 证明外部连接尝试被拒绝在副作用发生之前。
        sock.connect(("192.0.2.1", 53))
    finally:
        sock.close()


def _attempt_subprocess() -> None:
    import subprocess

    subprocess.run([sys.executable, "-c", "pass"], capture_output=True, check=False, timeout=10)


_PROBES: dict[str, Callable[[], None]] = {
    "write": _attempt_write,
    "mutation": _attempt_mkdir,
    "socket": _attempt_socket,
    "subprocess": _attempt_subprocess,
}


def _expect_blocked(expected_kind: str, attempt: Callable[[], None]) -> int:
    try:
        attempt()
    except OfflineGuardViolation as exc:
        print(f"GUARD BLOCKED kind={exc.violation.kind}")
        return EXIT_BLOCKED
    print(f"GUARD NOT-BLOCKED expected={expected_kind}", file=sys.stderr)
    return EXIT_NOT_BLOCKED


def _probe(kind: str) -> int:
    if kind == "write":
        code = _assert_absent(WRITE_PROBE_PATH)
        if code:
            return code
        return _expect_blocked("open-write", _attempt_write)
    if kind == "mutation":
        code = _assert_absent(MKDIR_PROBE_PATH)
        if code:
            return code
        return _expect_blocked("fs-mutation", _attempt_mkdir)
    return _expect_blocked(kind, _PROBES[kind])


def _run_offline_evaluator(guard: OfflineGuard) -> int:
    # 审计门已安装，此后才导入真实评估器（app import 链全程受保护）。
    from evaluate import main as evaluate_main  # noqa: E402

    main_rc = evaluate_main([])
    violations = guard.violations
    _report(guard)
    if violations:
        return EXIT_BLOCKED
    return EXIT_OK if main_rc == EXIT_OK else main_rc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guarded_worker",
        description="受保护的离线评测 worker：先装审计门，再跑真实 evaluate.py",
    )
    parser.add_argument("--probe", choices=_PROBE_KINDS, help="只执行负向对照探测")
    args = parser.parse_args(argv)

    # 守卫前准备工作，全部只读、零文件系统变更：
    # - set_tempdir_from_env()：直接复用已存在的 TEMP/TMP 环境目录作为 tempfile 缓存，
    #   使 portalocker 等库导入期调用 gettempdir() 时命中缓存，不再创建/删除探测文件；
    # - platform.uname()：Windows 上惰性执行 `cmd /c ver` 的 OS 自省（app 导入链必调
    #   platform.system()），非磁盘写入；先于守卫完成，覆盖该自省路径。
    set_tempdir_from_env()
    platform.uname()

    guard = OfflineGuard()
    guard.install()  # 在任何 app/evaluate import 之前

    if args.probe is not None:
        code = _probe(args.probe)
        _report(guard)
        return code
    return _run_offline_evaluator(guard)


if __name__ == "__main__":
    sys.exit(main())