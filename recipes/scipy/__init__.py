from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from multiprocessing import cpu_count
from os.path import join


class ThisRecipe(CompiledComponentsPythonRecipe):

    version = '1.5.4'
    url = f'https://github.com/scipy/scipy/releases/download/v1.5.4/scipy-{version}.zip'
    site_packages_name = 'scipy'
    depends = ['setuptools', 'cython', 'numpy']

    '''
    patches = [
        join('patches', 'add_libm_explicitly_to_build.patch'),
        join('patches', 'do_not_use_system_libs.patch'),
        join('patches', 'remove_unittest_call.patch'),
        ]
    '''

    call_hostpython_via_targetpython = False

    def build_compiled_components(self, arch):
        self.setup_extra_args = ['-j', str(cpu_count())]
        super().build_compiled_components(arch)
        self.setup_extra_args = []

    def rebuild_compiled_components(self, arch, env):
        self.setup_extra_args = ['-j', str(cpu_count())]
        super().rebuild_compiled_components(arch, env)
        self.setup_extra_args = []


recipe = ThisRecipe()
