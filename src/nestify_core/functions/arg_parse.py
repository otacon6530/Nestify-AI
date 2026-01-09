import argparse
import uuid


def parse(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(prog="nestify", add_help=True)
    parser.add_argument("--mode", choices=["default", "plan"], default="default")
    parser.add_argument("--debug-stream", action="store_true", help="Log raw SSE lines to stderr for streaming diagnostics")
    subparsers = parser.add_subparsers(dest="command")

    exec_p = subparsers.add_parser("exec")
    exec_p.add_argument("text", type=str, help="Text to execute one-and-done")

    run_p = subparsers.add_parser("run")
    # Allow placing the debug flag after the subcommand for convenience
    run_p.add_argument("--debug-stream", action="store_true", help="Log raw SSE lines to stderr for streaming diagnostics")

    shell_p = subparsers.add_parser("shell")
    shell_p.add_argument("cmd", type=str, help="Shell command to run with approval flow")

    try:
        args = parser.parse_args(argv)
        return {
            "command": args.command,
            "message": getattr(args, "text", None),
            "shell_command": getattr(args, "cmd", None),
            "mode": getattr(args, "mode", "default"),
            "debug_stream": bool(getattr(args, "debug_stream", False)),
            "correlation_id": str(uuid.uuid4()),
        }
    except SystemExit as e:
        # Argparse error; surface a structured error for CLI to emit
        return {
            "error": "INVALID_ARGUMENT",
            "message": "Invalid CLI arguments",
            "usage": parser.format_usage(),
            "exit_code": int(getattr(e, "code", 2) or 2),
            "correlation_id": str(uuid.uuid4()),
        }
