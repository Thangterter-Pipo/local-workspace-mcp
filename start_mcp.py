# -*- coding: utf-8 -*-
"""
Daemon supervisor for Local Workspace MCP.
Cross-platform: Windows and macOS / Linux.
Keeps local MCP server and optional SSH tunnel running in background quietly.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess as sp
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Identify OS-specific venv Python
if os.name == "nt":
    candidate_pw = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    candidate_p = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if candidate_pw.exists():
        VENV_PYTHON = candidate_pw
    elif candidate_p.exists():
        VENV_PYTHON = candidate_p
    else:
        VENV_PYTHON = Path(sys.executable)
else:
    candidate_p = BASE_DIR / ".venv" / "bin" / "python"
    if candidate_p.exists():
        VENV_PYTHON = candidate_p
    else:
        VENV_PYTHON = Path(sys.executable)

RUN_PY = BASE_DIR / "run.py"

if os.name == "nt":
    LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LocalWorkspaceMCP"
else:
    LOG_DIR = Path.home() / ".local_workspace_mcp"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOCK_FILE = LOG_DIR / "supervisor.lock"
SUP_LOG = LOG_DIR / "supervisor.log"
SERVER_LOG = LOG_DIR / "server.log"
TUNNEL_LOG = LOG_DIR / "tunnel.log"

PORT = int(os.environ.get("WORKSPACE_MCP_PORT") or os.environ.get("FLOW_VEO_MCP_PORT", "3080"))
SSH = shutil.which("ssh") or (r"C:\Windows\System32\OpenSSH\ssh.exe" if os.name == "nt" else "ssh")
SSH_HOST = (os.environ.get("WORKSPACE_MCP_SSH_HOST") or os.environ.get("FLOW_VEO_MCP_SSH_HOST", "")).strip()

_LOCK_FD = None


def try_lock() -> bool:
    """Acquire a single-instance lock. Returns False if another supervisor holds it."""
    global _LOCK_FD
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        _LOCK_FD = fd
        return True
    except Exception:
        return False


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    try:
        with SUP_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def get_clean_env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def start_server() -> sp.Popen:
    log("Starting MCP server...")
    with SERVER_LOG.open("ab") as logf:
        kwargs = {}
        if os.name == "nt":
            if hasattr(sp, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = sp.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True

        return sp.Popen(
            [str(VENV_PYTHON), str(RUN_PY)],
            cwd=str(BASE_DIR),
            stdout=logf,
            stderr=sp.STDOUT,
            env=get_clean_env(),
            **kwargs,
        )


def cleanup_vps_port(port: int = PORT, retries: int = 3) -> bool:
    """Free port on remote SSH host before (re)starting tunnel."""
    if not SSH_HOST:
        return False
    import re
    for _ in range(retries):
        try:
            out = sp.run(
                [SSH, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                 SSH_HOST, f"ss -tlnp | grep ':{port} '"],
                capture_output=True, text=True, timeout=25,
            ).stdout
            pids = set(re.findall(r"pid=(\d+)", out))
            for pid in pids:
                log(f"Freeing port {port} on remote host: killing pid {pid}")
                sp.run([SSH, "-o", "BatchMode=yes", SSH_HOST, f"kill {pid}"],
                       capture_output=True, timeout=20)
        except Exception as e:
            log(f"cleanup_vps_port error: {e}")
        try:
            chk = sp.run(
                [SSH, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                 SSH_HOST, f"ss -tln | grep -c ':{port} '"],
                capture_output=True, text=True, timeout=20,
            ).stdout.strip()
            if chk == "0":
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def start_tunnel(cleanup: bool = True) -> sp.Popen | None:
    if not SSH_HOST:
        log("No WORKSPACE_MCP_SSH_HOST configured; SSH reverse tunnel skipped.")
        return None

    log(f"Starting SSH reverse tunnel to {SSH_HOST} (0.0.0.0:{PORT} -> local {PORT})...")
    if cleanup:
        cleanup_vps_port(PORT)
    with TUNNEL_LOG.open("ab") as logf:
        kwargs = {}
        if os.name == "nt":
            if hasattr(sp, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = sp.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True

        return sp.Popen(
            [
                SSH,
                "-o", "ServerAliveInterval=15",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ConnectTimeout=15",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "TCPKeepAlive=yes",
                "-N",
                "-R", f"0.0.0.0:{PORT}:127.0.0.1:{PORT}",
                SSH_HOST,
            ],
            cwd=str(BASE_DIR),
            stdout=logf,
            stderr=sp.STDOUT,
            **kwargs,
        )


def terminate(proc: sp.Popen | None) -> None:
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def check_port(port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "status":
            mcp_up = check_port(PORT)
            print(f"MCP server (port {PORT}): {'RUNNING' if mcp_up else 'STOPPED'}")
            return
        elif cmd == "stop":
            if os.name == "nt":
                os.system("taskkill /F /IM pythonw.exe 2>nul")
                os.system("taskkill /F /IM ssh.exe 2>nul")
            else:
                os.system("pkill -f 'run.py' 2>/dev/null")
                os.system("pkill -f 'start_mcp.py' 2>/dev/null")
            print("Stop signal sent to processes.")
            return

    if not try_lock():
        log("Another supervisor instance is already running; exiting.")
        return

    log("Supervisor started.")
    server = start_server()
    tunnel = start_tunnel()

    try:
        while True:
            time.sleep(5)
            # Check Server
            if server.poll() is not None:
                log(f"MCP server died (code {server.returncode}), restarting...")
                server = start_server()

            # Check Tunnel if configured
            if SSH_HOST and tunnel is not None:
                if tunnel.poll() is not None:
                    log(f"SSH tunnel died (code {tunnel.returncode}), restarting in 3s...")
                    time.sleep(3)
                    tunnel = start_tunnel()

    except KeyboardInterrupt:
        pass
    finally:
        log("Supervisor exiting...")
        terminate(server)
        if tunnel:
            terminate(tunnel)


if __name__ == "__main__":
    main()
