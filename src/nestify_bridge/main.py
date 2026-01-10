import sys
import json
from nestify_core.core import Core


def main():
    try:
        core = Core()
        startup_status = core.startup()
        if startup_status is not None:
            sys.stdout.write(json.dumps({"type": "error", "exit_code": startup_status}) + "\n")
            sys.stdout.flush()
            sys.exit(startup_status)
        # Signal ready to the caller
        sys.stdout.write(json.dumps({"type": "ready"}) + "\n")
        sys.stdout.flush()

        for line in sys.stdin:
            try:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    sys.stdout.write(json.dumps({"type": "error", "message": "invalid json"}) + "\n")
                    sys.stdout.flush()
                    continue
                if msg.get("type") == "exec":
                    text = msg.get("text", "")
                    try:
                        events = core.generate(text, stream=True)
                        for ev in events:
                            if isinstance(ev, dict) and ev.get("type") == "token":
                                sys.stdout.write(json.dumps({"type": "token", "value": ev.get("value", "")}) + "\n")
                                sys.stdout.flush()
                            elif isinstance(ev, dict) and ev.get("type") == "final":
                                sys.stdout.write(json.dumps({"type": "final", "result": ev.get("result", {})}) + "\n")
                                sys.stdout.flush()
                    except Exception as e:
                        sys.stdout.write(json.dumps({"type": "error", "message": f"Exec error: {e}"}) + "\n")
                        sys.stdout.flush()
                        sys.exit(1)
                elif msg.get("type") == "probe":
                    sys.stdout.write(json.dumps({"type": "ok"}) + "\n")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(json.dumps({"type": "error", "message": "unknown command"}) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                sys.stdout.write(json.dumps({"type": "error", "message": f"Bridge loop error: {e}"}) + "\n")
                sys.stdout.flush()
                sys.exit(1)
    except Exception as e:
        sys.stdout.write(json.dumps({"type": "error", "message": f"Core init failed: {e}"}) + "\n")
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
