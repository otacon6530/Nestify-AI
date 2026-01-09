import sys, os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from nestify_cli.main import app_main
rc = app_main(['exec', 'hello world'])
print('RC=', rc)
