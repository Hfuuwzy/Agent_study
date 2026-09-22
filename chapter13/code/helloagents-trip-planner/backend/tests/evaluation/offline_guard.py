"""离线评测的进程内审计门（无写盘 / 无外网 / 无子进程的过程级证明支持）。

安装后（``sys.addaudithook``，进程全局、不可移除），任何受禁操作——写文件、文件系统
变更、外部 socket 连接、子进程启动——都**先**被记录为不可变违规对象并抛
:class:`OfflineGuardViolation`，在副作用发生之前拦截。即使调用方捕获了异常，违规
仍可通过 :attr:`OfflineGuard.violations` 观测。

检测面（CPython 审计事件，Windows/3.11 实测事件名与参数形状）：
- ``open``：mode 字符串含 ``w/a/x/+`` 之一，或数值 flags 含
  O_WRONLY / O_RDWR / O_CREAT / O_TRUNC / O_APPEND 任一（``os.open`` 的 mode 为 None，
  只走 flags 判定）；只读 open（模块加载 / 配置 / 场景 JSON）放行；
- 文件系统变更：``os.mkdir`` / ``os.remove``（unlink 同源）/ ``os.rmdir`` /
  ``os.rename``（含 replace）/ ``os.link`` / ``os.symlink``；
- 外部网络：``socket.connect`` / ``socket.bind`` / ``socket.listen``（非回环目标）
  与 ``socket.getaddrinfo``（DNS 属外网解析）；
- 子进程：``subprocess.Popen`` / ``os.system`` / ``os.posix_spawn`` /
  ``os.exec`` / ``os.spawn``。

回环豁免：asyncio/anyio 事件循环在 Windows 上经 ``socket.socketpair()`` 的回退实现
（bind 127.0.0.1|::1:0 -> listen -> connect -> accept）构建进程内自管道。这是本地
运行期管线，不是外网活动：``socket.bind`` / ``connect`` 到回环字面量（127.0.0.0/8、
::1）放行，``socket.listen`` 仅对**先前回环绑定过的同一 socket 对象**放行，其余
bind / connect / listen / getaddrinfo 一律拦截。

证明边界：本门只覆盖"本 Python 进程经审计事件暴露的离线路径"，不声称 OS 级沙箱。
"""

import os
import sys
import threading
from dataclasses import dataclass
from typing import Final, Tuple

#: mode 字符串中任一出现即视为可写（含 'r+' 的 '+'）。
_WRITE_MODE_CHARS: Final[frozenset[str]] = frozenset("wax+")
#: 数值 flags 的写位集合（O_WRONLY/O_RDWR/O_CREAT/O_TRUNC/O_APPEND）。
_WRITE_FLAG_BITS: Final[int] = (
    getattr(os, "O_WRONLY", 0)
    | getattr(os, "O_RDWR", 0)
    | getattr(os, "O_CREAT", 0)
    | getattr(os, "O_TRUNC", 0)
    | getattr(os, "O_APPEND", 0)
)

#: 文件系统变更类审计事件（实测事件名为 os.* 前缀；rename/replace 共用 os.rename）。
_FS_MUTATION_EVENTS: Final[frozenset[str]] = frozenset(
    {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink"}
)
#: 子进程/进程派生类审计事件。
_SPAWN_EVENTS: Final[frozenset[str]] = frozenset(
    {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn"}
)


@dataclass(frozen=True)
class Violation:
    """一条已记录的离线保护违规（不可变；构造后不再可变）。"""

    kind: str
    detail: str


class OfflineGuardViolation(RuntimeError):
    """离线保护拦截异常：违规已先行记录，异常只负责让触发方可见/被捕获。"""

    def __init__(self, violation: Violation) -> None:
        self.violation: Violation = violation
        super().__init__(f"离线保护拦截: [{violation.kind}] {violation.detail}")


def _truncate(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else f"{text[:limit]}..."


def _is_loopback_address(address: object) -> bool:
    """判断 sockaddr 是否为回环字面量（IPv4 127.0.0.0/8 或 IPv6 ::1）。"""
    if not isinstance(address, tuple) or len(address) < 1:
        return False
    host = address[0]
    if not isinstance(host, str):
        return False
    if host == "::1":
        return True
    parts = host.split(".")
    if len(parts) == 4 and parts[0] == "127":
        return all(part.isdigit() for part in parts)
    return False


class OfflineGuard:
    """安装一次即永久生效（audit hook 不可移除）；进程退出即随进程消失。"""

    def __init__(self) -> None:
        self._violations: list[Violation] = []
        self._loopback_bound: set[int] = set()
        self._lock = threading.Lock()
        self._installed = False

    def install(self) -> None:
        """在 import 应用/评估模块**之前**调用；重复调用幂等。"""
        if self._installed:
            return
        sys.addaudithook(self._audit)
        self._installed = True

    @property
    def violations(self) -> Tuple[Violation, ...]:
        """已记录的违规快照（不可变元组）。"""
        with self._lock:
            return tuple(self._violations)

    def record(self, kind: str, detail: str) -> None:
        """记录违规（不可变）后再抛异常：即使被捕获，记录仍可观测。"""
        violation = Violation(kind=kind, detail=detail)
        with self._lock:
            self._violations.append(violation)
        raise OfflineGuardViolation(violation)

    def _audit(self, event: str, args: tuple[object, ...]) -> None:
        if event == "open":
            if self._is_write_open(args):
                self.record("open-write", f"open{_truncate(repr(args))}")
            return
        if event in _FS_MUTATION_EVENTS:
            self.record("fs-mutation", f"{event}{_truncate(repr(args))}")
            return
        if event == "socket.bind":
            self._audit_bind(args)
            return
        if event == "socket.listen":
            self._audit_listen(args)
            return
        if event == "socket.connect":
            self._audit_connect(args)
            return
        if event == "socket.getaddrinfo":
            self.record("network", f"{event}{_truncate(repr(args))}")
            return
        if event in _SPAWN_EVENTS:
            self.record("process-spawn", f"{event}{_truncate(repr(args))}")

    def _audit_bind(self, args: tuple[object, ...]) -> None:
        address = args[1] if len(args) > 1 else None
        if _is_loopback_address(address):
            if args:
                self._mark_loopback_socket(args[0])
            return
        self.record("network", f"socket.bind{_truncate(repr(args))}")

    def _audit_listen(self, args: tuple[object, ...]) -> None:
        if args and id(args[0]) in self._loopback_bound:
            return
        self.record("network", f"socket.listen{_truncate(repr(args))}")

    def _audit_connect(self, args: tuple[object, ...]) -> None:
        address = args[1] if len(args) > 1 else None
        if _is_loopback_address(address):
            return
        self.record("network", f"socket.connect{_truncate(repr(args))}")

    def _mark_loopback_socket(self, sock: object) -> None:
        with self._lock:
            self._loopback_bound.add(id(sock))

    @staticmethod
    def _is_write_open(args: tuple[object, ...]) -> bool:
        """open 审计参数 (path, mode, flags)：字符串 mode 与数值 flags 任一命中即写。"""
        if len(args) < 3:
            return False
        mode = args[1]
        flags = args[2]
        if isinstance(mode, str) and any(ch in mode for ch in _WRITE_MODE_CHARS):
            return True
        if isinstance(flags, int) and (flags & _WRITE_FLAG_BITS):
            return True
        return False