import argparse
import uuid


def parse(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(prog="nestify", add_help=True)
    subparsers = parser.add_subparsers(dest="command")

    exec_p = subparsers.add_parser("exec")
    exec_p.add_argument("text", type=str, help="Text to execute one-and-done")

    args = parser.parse_args(argv)
    return {
        "command": args.command,
        "message": getattr(args, "text", None),
        "correlation_id": str(uuid.uuid4()),
    }
