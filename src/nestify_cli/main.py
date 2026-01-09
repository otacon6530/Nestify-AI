from __future__ import annotations
import sys
from nestify_core.core import Core
from nestify_core.classes.arg_manager import ArgManager


def app_main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    args = ArgManager().parse(argv)
    core = Core()
    startup_status = core.startup()
    if startup_status is not None:
        return startup_status

    if args.get("command") == "exec":
        text = args.get("message") or ""
        return core.exec_once(text)

    # No command: show help-like guidance
    sys.stderr.write("Usage: nestify exec \"<text>\"\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(app_main())
