from __future__ import annotations
import sys
import time
from nestify_core.core import Core
from nestify_core.classes.arg_manager import ArgManager


def _run_stream(core: Core) -> int:
    print("Nestify run: streaming enabled. Type your message; Ctrl+C to exit.")
    spinner = "|/-\\"
    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            print("[sending] ...")
            i = 0
            events = core.llm.generate(msg, stream=True)
            try:
                for ev in events:
                    if isinstance(ev, dict) and ev.get("type") == "token":
                        sys.stdout.write(ev.get("value", ""))
                        sys.stdout.flush()
                        sys.stdout.write("\r" + spinner[i % len(spinner)])
                        sys.stdout.flush()
                        i += 1
                    elif isinstance(ev, dict) and ev.get("type") == "final":
                        sys.stdout.write("\r \r\n")
                        sys.stdout.flush()
            except TypeError:
                # Non-stream result fallback
                res = events
                if isinstance(res, dict):
                    txt = res.get("output") or res.get("text") or ""
                    if txt:
                        print(txt)
            print("[done]")
    except KeyboardInterrupt:
        print("\nBye.")
    return 0


def _shell_with_approval(cmd: str) -> int:
    from nestify_core.tools.shell import shell_tool
    # Request approval
    req = shell_tool(cmd, approve=None)
    print(f"Shell command requested: {req['command']}")
    while True:
        ans = input("Approve (y), Deny (n), Approve All (a): ").strip().lower()
        if ans in ("y", "yes"):
            res = shell_tool(cmd, approve="yes")
            break
        elif ans in ("n", "no"):
            res = shell_tool(cmd, approve="no")
            break
        elif ans in ("a", "all"):
            res = shell_tool(cmd, approve="all")
            break
        else:
            print("Please enter y/n/a")
    if res.get("status") == "ok":
        print(res.get("stdout", ""))
        if res.get("stderr"):
            sys.stderr.write(res.get("stderr"))
        return res.get("exit_code", 0)
    elif res.get("status") == "denied":
        print("Denied.")
        return 0
    else:
        sys.stderr.write(str(res) + "\n")
        return 1


def app_main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    args = ArgManager().parse(argv)
    core = Core()
    startup_status = core.startup()
    if startup_status is not None:
        return startup_status

    cmd = args.get("command")
    if cmd == "exec":
        text = args.get("message") or ""
        return core.exec_once(text)
    if cmd == "run":
        return _run_stream(core)
    if cmd == "shell":
        shell_cmd = args.get("shell_command") or ""
        if not shell_cmd:
            sys.stderr.write("shell requires a command string\n")
            return 2
        return _shell_with_approval(shell_cmd)

    # No command: show help-like guidance
    sys.stderr.write("Usage: nestify run | nestify exec \"<text>\" | nestify shell \"<cmd>\"\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(app_main())
