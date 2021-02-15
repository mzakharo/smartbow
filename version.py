import subprocess
import os

version = os.getenv('RELEASE_VERSION', None) or subprocess.check_output('git describe --tag --dirty', shell=True).decode('utf-8').strip()
print('Version:', version)
with open('RELEASE_VERSION.py', 'w') as f:
    f.write(f'__version__ = "{version}"\n')
