from conans import ConanFile, tools, AutoToolsBuildEnvironment
from contextlib import contextmanager
import os

class ReadStatConan(ConanFile):
    name = "ReadStat"
    version = "1.1.7"
    license = "MIT"
    author = "WizardMac"
    url = "https://github.com/WizardMac/ReadStat"
    description = "Command-line tool (+ C library) for converting SAS, Stata, and SPSS files"
    topics = ("spss", "stata", "sas", "sas7bdat", "readstat")
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }

    default_options = {
        "shared": False,
        "fPIC": True,
    }

    _autotools = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _is_msvc(self):
        return str(self.settings.compiler) in ["Visual Studio", "msvc"]

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    @property
    def _user_info_build(self):
        return getattr(self, "user_info_build", self.deps_user_info)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            del self.options.fPIC
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

    def build_requirements(self):
        # self.build_requires("libtool/2.4.6")
        if self._settings_build.os == "Windows" and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/cci.latest")

    def source(self):
        tools.get(**self.conan_data["sources"][self.version], strip_root=True,
                  destination=self._source_subfolder)

    @contextmanager
    def _build_context(self):
        if self._is_msvc:
            with tools.vcvars(self):
                env = {
                    "CC": "cl -nologo",
                    "CXX": "cl -nologo",
                    "LD": "link -nologo",
                    "AR": "{} lib".format(tools.unix_path(self._user_info_build["automake"].ar_lib)),
                }
                with tools.environment_append(env):
                    yield
        else:
            yield

    def _configure_autotools(self):
        if self._autotools:
            return self._autotools
        self._autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)

        self._autotools.libs = []
        yes_no = lambda v: "yes" if v else "no"
        args = [
            "--enable-shared={}".format(yes_no(self.options.shared)),
            "--enable-static={}".format(yes_no(not self.options.shared)),
        ]
        if self.settings.os == "Windows":
            self._autotools.defines.extend(["HAVE_WIN_IEEE_INTERFACE", "WIN32"])
            # if self.options.shared:
            #     self._autotools.defines.append("GSL_DLL")

        if self.settings.os == "Linux" and "x86" in self.settings.arch:
            self._autotools.defines.append("HAVE_GNUX86_IEEE_INTERFACE")

        if self._is_msvc:
            if self.settings.compiler == "Visual Studio" and \
               tools.Version(self.settings.compiler.version) >= "12":
                self._autotools.flags.append("-FS")
            self._autotools.cxx_flags.append("-EHsc")
            args.extend([
                "ac_cv_func_memcpy=yes",
                "ac_cv_func_memmove=yes",
                "ac_cv_c_c99inline=no",
            ])
        self._autotools.configure(args=args, configure_dir=self._source_subfolder)
        return self._autotools

    def build(self):
        # self._patch_source()
        with self._build_context():
            autotools = self._configure_autotools()
            autotools.make()

    def package(self):
        self.copy("COPYING", dst="licenses", src=self._source_subfolder)
        with self._build_context():
            autotools = self._configure_autotools()
            autotools.install()
        tools.rmdir(os.path.join(self.package_folder, "share"))
        tools.rmdir(os.path.join(self.package_folder, "lib", "pkgconfig"))
        tools.remove_files_by_mask(os.path.join(self.package_folder, "lib"), "*.la")
        tools.remove_files_by_mask(os.path.join(self.package_folder, "include", "readstat"), "*.c")

        if self._is_msvc and self.options.shared:
            pjoin = lambda p: os.path.join(self.package_folder, "lib", p)
            tools.rename(pjoin("readstat.dll.lib"), pjoin("readstat.lib"))
            # tools.rename(pjoin("gslcblas.dll.lib"), pjoin("gslcblas.lib"))

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_file_name", "ReadStat")
        self.cpp_info.set_property("cmake_target_name", "ReadStat::readstat")
        self.cpp_info.set_property("pkg_config_name", "readstat")

        self.cpp_info.components["libreadstat"].set_property("cmake_target_name", "ReadStat::readstat")
        self.cpp_info.components["libreadstat"].libs = ["readstat"]
        # self.cpp_info.components["libreadstat"].requires = ["libiconv/1.16"]


        if self.settings.os in ("FreeBSD", "Linux"):
            self.cpp_info.components["libreadstat"].system_libs = ["m"]

        bin_path = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment var: {}".format(bin_path))
        self.env_info.PATH.append(bin_path)

        # TODO: to remove in conan v2 once cmake_find_package* generators removed
        self.cpp_info.names["cmake_find_package"] = "ReadStat"
        self.cpp_info.names["cmake_find_package_multi"] = "ReadStat"
        self.cpp_info.components["libreadstat"].names["cmake_find_package"] = "readstat"
        self.cpp_info.components["libreadstat"].names["cmake_find_package_multi"] = "readstat"
