"""evaluate.py CLI 的进程级测试：输出契约 / 退出码 / 离线默认与 Key 无关性。

全部经 subprocess 运行真实 CLI（``python -B evaluate.py``），证明：
- 全量离线输出 5 条 PASS + SUMMARY(mode=offline)，退出 0，stdout 不含应用噪音；
- ``--case`` 单选输出 1 条 + SUMMARY(total=1)，退出 0；
- 未知场景 / ``--real`` 用法错误退出 2；
- 环境里出现 Key 不会把离线默认切换成真实模式；
- ``--real --case happy_path`` 在缺 Key 时预检失败退出 2、绝不回退到桩。

Windows 控制台 UTF-8：子进程设置 ``PYTHONIOENCODING=utf-8``；
``PYTHONDONTWRITEBYTECODE=1`` 与 ``-B`` 双保险防止写入 pyc。
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
CLI = BACKEND_DIR / "evaluate.py"

ALL_SCENARIO_IDS = (
    "happy_path",
    "missing_date",
    "empty_search",
    "schema_retry_exhausted",
    "malicious_input",
)


def _run_cli(*args: str, env_updates: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_updates:
        env.update(env_updates)
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=180,
    )


class EvaluateCliTest(unittest.TestCase):
    """经进程级真实 CLI 验证输出契约与退出码（离线默认、不触碰网络）。"""

    def test_full_offline_run_outputs_five_passes_and_clean_summary(self) -> None:
        result = _run_cli()
        self.assertEqual(result.returncode, 0, f"CLI 应全量通过：\n{result.stderr}")
        pass_lines = [line for line in result.stdout.splitlines() if line.startswith("PASS ")]
        self.assertEqual(len(pass_lines), 5, f"应输出 5 条 PASS：\n{result.stdout}")
        for scenario_id in ALL_SCENARIO_IDS:
            self.assertTrue(
                any(line.startswith(f"PASS {scenario_id}: ") for line in pass_lines),
                f"缺少场景 {scenario_id} 的 PASS 行：\n{result.stdout}",
            )
        self.assertIn("SUMMARY passed=5 failed=0 total=5 mode=offline", result.stdout)
        # 应用噪音（print / loguru）必须被捕获：stdout 只允许 PASS/SUMMARY 行
        for line in result.stdout.splitlines():
            self.assertTrue(
                line.startswith(("PASS ", "SUMMARY ")),
                f"stdout 混入应用噪音行：{line!r}\n{result.stdout}",
            )

    def test_single_case_selection_outputs_one_pass(self) -> None:
        result = _run_cli("--case", "happy_path")
        self.assertEqual(result.returncode, 0, f"单选场景应通过：\n{result.stderr}")
        pass_lines = [line for line in result.stdout.splitlines() if line.startswith("PASS ")]
        self.assertEqual(len(pass_lines), 1, f"单选应只输出 1 条 PASS：\n{result.stdout}")
        self.assertTrue(pass_lines[0].startswith("PASS happy_path: "))
        self.assertIn("SUMMARY passed=1 failed=0 total=1 mode=offline", result.stdout)

    def test_invalid_case_exits_2_without_running(self) -> None:
        result = _run_cli("--case", "bogus")
        self.assertEqual(result.returncode, 2, "未知场景必须退出 2")
        self.assertIn("未知场景", result.stderr)
        self.assertNotIn("SUMMARY", result.stdout, "未知场景不得运行任何场景")

    def test_real_requires_happy_path_case(self) -> None:
        for args in (("--real",), ("--real", "--case", "empty_search")):
            with self.subTest(args=args):
                result = _run_cli(*args)
                self.assertEqual(result.returncode, 2, f"{args} 必须退出 2")
                self.assertNotIn("mode=offline", result.stdout, f"{args} 不得回退到离线模式")

    def test_configured_keys_do_not_opt_into_real_mode(self) -> None:
        result = _run_cli(
            env_updates={"OPENAI_API_KEY": "dummy-key", "AMAP_API_KEY": "dummy-amap", "LLM_API_KEY": ""}
        )
        self.assertEqual(result.returncode, 0, f"带 Key 的离线默认必须仍通过：\n{result.stderr}")
        self.assertIn("mode=offline", result.stdout, "默认离线模式不因 Key 存在而切换")
        self.assertNotIn("mode=real", result.stdout)

    def test_real_preflight_missing_keys_exits_2_without_stub_fallback(self) -> None:
        result = _run_cli(
            "--real", "--case", "happy_path",
            env_updates={"OPENAI_API_KEY": "", "AMAP_API_KEY": "", "LLM_API_KEY": ""},
        )
        self.assertEqual(result.returncode, 2, "真实模式缺 Key 必须预检失败退出 2")
        combined = result.stdout + result.stderr
        self.assertIn("REAL_PREFLIGHT", combined, "必须输出预检失败原因")
        self.assertIn("LLM", combined)
        self.assertIn("AMAP", combined)
        self.assertNotIn("mode=offline", combined, "预检失败不得静默回退到桩离线模式")
        self.assertNotIn("PASS happy_path", combined, "预检失败不得输出 PASS")


if __name__ == "__main__":
    unittest.main()