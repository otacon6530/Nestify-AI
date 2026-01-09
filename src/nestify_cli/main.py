from __future__ import annotations
import sys
import time
from nestify_core.core import Core
from nestify_core.functions.error_envelope import build_error_envelope, emit_error
import uuid
from nestify_core.classes.arg_manager import ArgManager


def _run_stream(core: Core) -> int:
    print("Nestify run: streaming enabled. Type your message; Ctrl+C to exit.")
    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            print("[sending] ...")
            printed = False
            events = core.llm.generate(msg, stream=True)
            try:
                for ev in events:
                    if isinstance(ev, dict) and ev.get("type") == "token":
                        sys.stdout.write(ev.get("value", ""))
                        sys.stdout.flush()
                        printed = True
                    elif isinstance(ev, dict) and ev.get("type") == "final":
                        result = ev.get("result", {}) if isinstance(ev.get("result"), dict) else {}
                        final_text = result.get("text", "")
                        # Only print the final text if no tokens were printed
                        if final_text and not printed:
                            sys.stdout.write(final_text)
                            printed = True
                        sys.stdout.write("\n")
                        sys.stdout.flush()
            except TypeError:
                # Non-stream result fallback
                res = events
                if isinstance(res, dict):
                    txt = res.get("output") or res.get("text") or ""
                    if txt:
                        print(txt)
                        printed = True
            # If nothing was printed during streaming, fallback to non-stream call
            if not printed:
                res = core.llm.generate(msg, stream=False)
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
    # Enable streaming diagnostics if requested
    if isinstance(args, dict) and args.get("debug_stream"):
        import os
        os.environ["NESTIFY_STREAM_DEBUG"] = "1"
        sys.stderr.write("[stream-debug] enabled\n")
    if isinstance(args, dict) and args.get("error"):
        env = build_error_envelope(
            code="INVALID_ARGUMENT",
            message=args.get("message", "Invalid arguments"),
            component="CLI/ArgManager",
            correlation_id=args.get("correlation_id", str(uuid.uuid4())),
            suggestion="Use: nestify run | nestify exec \"<text>\" | nestify shell \"<cmd>\"",
        )
        rc = emit_error(env)
        usage = args.get("usage")
        if usage:
            sys.stderr.write(usage)
        return args.get("exit_code", rc)
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
