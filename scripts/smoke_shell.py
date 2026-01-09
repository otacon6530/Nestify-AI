import sys
from nestify_cli.main import app_main
# Note: interactive approvals; this will prompt. Provide 'y' then Enter to approve.
app_main(["shell", "echo hi from shell tool"])
