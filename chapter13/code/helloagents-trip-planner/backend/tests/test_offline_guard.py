"""离线评测无副作用（不写盘 / 不联网 / 不拉子进程）的过程级证明测试。

全部经 subprocess 运行独立的 ``python -B -m tests.evaluation.guarded_worker``：
该 worker 在 import app/evaluate **之前**安装审计门（audit hook 进程全局、不可移除），
随后跑真实默认离线评测器或执行负向对照探测。覆盖：

- 受保护全量离线运行：5 条 PASS + SUMMARY + ``GUARD violations=0``，退出 0，
  stdout 无应用噪音且 stderr 为空；
- 负向对照：写 / 文件树变更 / 外部连接 / 子进程四类探测都被记录并拒绝在副作用
  发生之前（写与目录探测目标保持不存在），退出码 1 = 被拦截；探测目标预先存在
  时输出 ``GUARD PREEXISTING`` 并退出 3；
- 守卫前零文件系统变更：worker 内不存在调用 ``tempfile.gettempdir()`` 的代码路径
  （AST 级证明，gettempdir 首次调用会创建/删除探测文件），``set_tempdir_from_env``
  只读复用已存在的 TEMP/TMP 环境目录作为 ``tempfile.tempdir`` 缓存。

探测目标为 backend 下的稳定路径，**只在不存在时才探测**；本测试不删除任何东西，
完全依赖"拦截先行"保证目标永不出现。所有输出经管道捕获，不写任何临时文件。
"""

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.evaluation.guarded_worker import (
    MKDIR_PROBE_PATH,
    WRITE_PROBE_PATH,
    set_tempdir_from_env,
)
from tests.evaluation import guarded_worker as guarded_worker_module

BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKER_MODULE = "tests.evaluation.guarded_worker"

BLOCKED_KINDS = {
    "write": "open-write",
    "mutation": "fs-mutation",
    "socket": "network",
    "subprocess": "process-spawn",
}


def _run_worker(*args: str, env_updates: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_updates:
        env.update(env_updates)
    return subprocess.run(
        [sys.executable, "-B", "-m", WORKER_MODULE, *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=300,
    )


class OfflineGuardTest(unittest.TestCase):
    """进程级证明：审计门先于任何 app 导入，默认离线评测零违规。"""

    def test_guarded_full_offline_run_passes_with_zero_violations(self) -> None:
        result = _run_worker()
        self.assertEqual(result.returncode, 0, f"受保护离线评测必须全过：\n{result.stderr}")
        self.assertEqual(result.stderr, "", "受保护离线运行不得产生 stderr 噪音")
        stdout = result.stdout
        for scenario_id in ("happy_path", "missing_date", "empty_search", "schema_retry_exhausted", "malicious_input"):
            self.assertTrue(
                any(line.startswith(f"PASS {scenario_id}: ") for line in stdout.splitlines()),
                f"缺少场景 {scenario_id} 的 PASS 行：\n{stdout}",
            )
        self.assertIn("SUMMARY passed=5 failed=0 total=5 mode=offline", stdout)
        self.assertIn("GUARD violations=0", stdout)
        for line in stdout.splitlines():
            self.assertTrue(
                line.startswith(("PASS ", "SUMMARY ", "GUARD ")),
                f"stdout 混入噪音行：{line!r}\n{stdout}",
            )

    def test_probe_targets_are_absent_before_any_probe(self) -> None:
        self.assertFalse(WRITE_PROBE_PATH.exists(), f"写探测目标不应预先存在: {WRITE_PROBE_PATH}")
        self.assertFalse(MKDIR_PROBE_PATH.exists(), f"目录探测目标不应预先存在: {MKDIR_PROBE_PATH}")

    def test_worker_has_no_gettempdir_code_path(self) -> None:
        """守卫前不得调用 tempfile.gettempdir()（其首次调用会创建/删除探查文件）。

        AST 级证明：guarded_worker 的代码里不存在任何 ``gettempdir`` 属性/调用节点
        （docstring/注释文本不进入 AST，故不误报）。
        """
        source = Path(guarded_worker_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "gettempdir":
                self.fail(f"guarded_worker 存在 gettempdir 代码路径: 第 {node.lineno} 行")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "gettempdir":
                self.fail(f"guarded_worker 调用 gettempdir(): 第 {node.lineno} 行")

    def test_set_tempdir_from_env_uses_existing_dir_readonly(self) -> None:
        """set_tempdir_from_env 只读复用已存在的 TEMP/TMP 环境目录作为 tempfile 缓存。"""
        previous = tempfile.tempdir
        try:
            expected = os.environ.get("TEMP") or os.environ.get("TMP") or os.environ.get("TMPDIR")
            assert expected is not None, "TEMP/TMP/TMPDIR 环境变量必须至少提供一个目录"
            tempfile.tempdir = None
            set_tempdir_from_env()
            self.assertEqual(tempfile.tempdir, expected, "tempdir 必须来自 TEMP/TMP/TMPDIR 环境变量")
            self.assertTrue(os.path.isdir(expected), f"环境目录必须真实存在: {expected}")
        finally:
            tempfile.tempdir = previous

    def test_blocked_write_probe_does_not_create_target(self) -> None:
        self.assertFalse(WRITE_PROBE_PATH.exists(), f"写探测目标不应预先存在: {WRITE_PROBE_PATH}")
        result = _run_worker("--probe", "write")
        self.assertEqual(result.returncode, 1, f"写探测必须被拦截：\n{result.stdout}")
        self.assertIn("GUARD BLOCKED kind=open-write", result.stdout)
        self.assertIn("GUARD violations=1", result.stdout)
        self.assertFalse(WRITE_PROBE_PATH.exists(), "被拦截的写探测不得创建目标文件")
        self.assertEqual(result.stderr, "")

    def test_blocked_mutation_probe_does_not_create_dir(self) -> None:
        self.assertFalse(MKDIR_PROBE_PATH.exists(), f"目录探测目标不应预先存在: {MKDIR_PROBE_PATH}")
        result = _run_worker("--probe", "mutation")
        self.assertEqual(result.returncode, 1, f"目录变更探测必须被拦截：\n{result.stdout}")
        self.assertIn("GUARD BLOCKED kind=fs-mutation", result.stdout)
        self.assertIn("GUARD violations=1", result.stdout)
        self.assertFalse(MKDIR_PROBE_PATH.exists(), "被拦截的目录变更探测不得创建目标目录")

    def test_blocked_socket_probe_is_observed(self) -> None:
        result = _run_worker("--probe", "socket")
        self.assertEqual(result.returncode, 1, f"外部连接探测必须被拦截：\n{result.stdout}")
        self.assertIn("GUARD BLOCKED kind=network", result.stdout)
        self.assertIn("GUARD violations=1", result.stdout)

    def test_blocked_subprocess_probe_is_observed(self) -> None:
        result = _run_worker("--probe", "subprocess")
        self.assertEqual(result.returncode, 1, f"子进程探测必须被拦截：\n{result.stdout}")
        self.assertIn("GUARD BLOCKED kind=process-spawn", result.stdout)
        self.assertIn("GUARD violations=1", result.stdout)

    def test_all_blocked_kinds_report_their_kind(self) -> None:
        for probe, kind in BLOCKED_KINDS.items():
            with self.subTest(probe=probe):
                result = _run_worker("--probe", probe)
                self.assertEqual(result.returncode, 1, f"{probe} 探测必须被拦截")
                self.assertIn(f"GUARD BLOCKED kind={kind}", result.stdout)


if __name__ == "__main__":
    unittest.main()