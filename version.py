import subprocess
version = subprocess.check_output('git describe --tag --dirty', shell=True).decode('utf-8').strip()
print('Version:', version)
with open('RELEASE_VERSION.py', 'w') as f:
    f.write(f'__version__ = "{version}"\n')
