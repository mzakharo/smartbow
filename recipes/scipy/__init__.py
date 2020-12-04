from pythonforandroid.recipe import CompiledComponentsPythonRecipe, Recipe
from multiprocessing import cpu_count
from os.path import join
import sh


class ThisRecipe(CompiledComponentsPythonRecipe):

    version = '1.5.4'
    url = f'https://github.com/scipy/scipy/releases/download/v{version}/scipy-{version}.zip'
    site_packages_name = 'scipy'
    depends = ['setuptools', 'cython', 'numpy', 'lapack']
    call_hostpython_via_targetpython = False

    def build_compiled_components(self, arch):
        self.setup_extra_args = ['-j', str(cpu_count())]
        super().build_compiled_components(arch)
        self.setup_extra_args = []

    def rebuild_compiled_components(self, arch, env):
        self.setup_extra_args = ['-j', str(cpu_count())]
        super().rebuild_compiled_components(arch, env)
        self.setup_extra_args = []

    def get_recipe_env(self, arch):	 
        env = super().get_recipe_env(arch)

        #hard-coded parameters
        GCC_VER = '4.9'
        HOST = 'linux-x86_64'
        LIB = 'lib64'

        if sh.which('ccache') is not  None:
            raise Exception("'ccache' is not supported by numpy C++ distutils, please uninstall 'ccache'")

        #generated paths/variables
        prefix = env['TOOLCHAIN_PREFIX']
        lapack_dir = join(Recipe.get_recipe('lapack', self.ctx).get_build_dir(arch.arch), 'build', 'install')
        sysroot = f"{self.ctx.ndk_dir}/platforms/{env['NDK_API']}/{arch.platform_dir}"
        sysroot_include = f'{self.ctx.ndk_dir}/toolchains/llvm/prebuilt/{HOST}/sysroot/usr/include'
        libgfortran = f'{self.ctx.ndk_dir}/toolchains/{prefix}-{GCC_VER}/prebuilt/{HOST}/{prefix}/{LIB}'
        #libcpp =  f'{self.ctx.ndk_dir}/toolchains/llvm/prebuilt/{HOST}/sysroot/usr/lib/{prefix}'
        numpylib = self.ctx.get_python_install_dir() + '/numpy/core/lib'
        LDSHARED_opts = env['LDSHARED'].split('clang')[1]

        env['LAPACK']       = f'{lapack_dir}/lib'
        env['BLAS']         = env['LAPACK']
        env['F90']          = f'{prefix}-gfortran'
        env['CFLAGS']       += f' -I{lapack_dir}/include'
        env['CPPFLAGS'] += f' --sysroot={sysroot} -I{sysroot_include}/c++/v1 -I{sysroot_include}'
        #distutils unixccompiler expects LDSHARED to be just one word
        env['LDSHARED']     = 'clang'
        #one word LDSHARED (above) breaks linking, so add missing LDSHARED_opts to LDFLAGS
        env['LDFLAGS'] += f' {LDSHARED_opts} -lstdc++ -lc++_shared --sysroot={sysroot} -L{libgfortran} -L{numpylib}'
        return env

recipe = ThisRecipe()
