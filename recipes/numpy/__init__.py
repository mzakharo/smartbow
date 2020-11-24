from pythonforandroid.recipe import CompiledComponentsPythonRecipe, sh, info, current_directory, shprint
from multiprocessing import cpu_count
from os.path import join
import glob

class NumpyRecipe(CompiledComponentsPythonRecipe):

    version = '1.18.1'
    url = 'https://pypi.python.org/packages/source/n/numpy/numpy-{version}.zip'
    site_packages_name = 'numpy'
    depends = ['setuptools']
    install_in_hostpython = True
    call_hostpython_via_targetpython = False

    patches = [
        join('patches', 'add_libm_explicitly_to_build.patch'),
        join('patches', 'do_not_use_system_libs.patch'),
        join('patches', 'remove_unittest_call.patch'),
        ]

    #hack -> eneded to add --force or it would not work
    def _build_compiled_components(self, arch):
        info('Building compiled components in {}'.format(self.name))

        env = self.get_recipe_env(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            hostpython = sh.Command(self.hostpython_location)
            if self.install_in_hostpython:
                shprint(hostpython, 'setup.py', 'clean', '--all', '--force', _env=env)
            shprint(hostpython, 'setup.py', self.build_cmd, '-v',
                    _env=env, *self.setup_extra_args)
            build_dir = glob.glob('build/lib.*')[0]
            shprint(sh.find, build_dir, '-name', '"*.o"', '-exec',
                    env['STRIP'], '{}', ';', _env=env)


    def build_compiled_components(self, arch):
        self.setup_extra_args = ['-j', str(cpu_count())]
        self._build_compiled_components(arch)
        self.setup_extra_args = []

    #hack -> eneded to add --force or it would not work
    def _rebuild_compiled_components(self, arch, env):
        info('Rebuilding compiled components in {}'.format(self.name))

        hostpython = sh.Command(self.real_hostpython_location)
        shprint(hostpython, 'setup.py', 'clean', '--all', '--force', _env=env)
        shprint(hostpython, 'setup.py', self.build_cmd, '-v', _env=env,
                *self.setup_extra_args)

    def rebuild_compiled_components(self, arch, env):
        self.setup_extra_args = ['-j', str(cpu_count())]
        self._rebuild_compiled_components(arch, env)
        self.setup_extra_args = []


recipe = NumpyRecipe()
