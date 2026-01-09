import sys
from nestify_cli.main import app_main
rc = app_main(["exec", "hello stream"])
print("RC:", rc)
