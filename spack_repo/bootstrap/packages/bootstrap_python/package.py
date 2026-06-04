# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapPython(Package):
    """Python 3.5.9 built by bootstrap-gcc-9 (static musl), for bootstrap-glibc-boot0.

    glibc requires Python >= 3.4 at build time (scripts/gen-as-const.py and
    friends). This stage provides a minimal x86_64 Python 3.5.9 compiled by
    gcc-9.5 and linked against the static musl sysroot.

    Python 3.5 is the highest version that builds without pthreads (not yet
    available in this scaffold) without extra patches; 3.6+ needs threading
    backports. (User-accepted highest-risk sub-task of the cap: a static-musl
    CPython. If it proves intractable, the escape hatch is host ``python3`` via
    the sandbox allow_read -- python is in CLAUDE.md's assumed host userland.)

    Disabled at configure/build time:
    - ctypes (_ctypes.c) -- requires libffi, not present here.
    - ossaudiodev -- requires Linux ALSA/OSS kernel headers, not present here.
    - the test suite is removed post-install.

    ``_PYTHON_HOST_PLATFORM=linux-x86_64`` makes setup.py skip /usr/include and
    /usr/local probing (the sandbox blocks those reads). Native x86_64 build,
    so build==host (cross_compiling=no) and python can run its own freeze
    steps. make is bootstrap-gmake. No ``c`` virtual.

    Ported from ``python-boot0`` (Guix ``gnu/packages/commencement.scm``)."""

    homepage = "https://www.python.org/"
    url = "https://www.python.org/ftp/python/3.5.9/Python-3.5.9.tar.xz"

    license("Python-2.0")

    version("3.5.9", sha256="c24a37c63a67f53bdd09c5f287b5cff8e8b98f857bf348c577d454d3f74db049")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-9", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        gcc = self.spec["bootstrap-gcc-9"].prefix
        env.set("CC", "{0}/bin/gcc".format(gcc))
        env.set("CXX", "{0}/bin/g++".format(gcc))
        # Suppress setup.py's /usr/include and /usr/local probing (the
        # cross_compiling branch in setup.py skips inc_dirs += ['/usr/include']),
        # which would otherwise hit a landlock "Permission denied" in the sandbox.
        env.set("_PYTHON_HOST_PLATFORM", "linux-x86_64")

    def install(self, spec, prefix):
        gcc = spec["bootstrap-gcc-9"].prefix
        make = Executable(spec[self.make_provider].prefix.bin.make)
        triple = "%s-linux-musl" % spec.target.family

        # Disable ctypes (_ctypes.c) -- requires libffi not present here.
        filter_file(r"extensions\.append\(ctypes\)", "", "setup.py")
        # Disable ossaudiodev -- requires ALSA/OSS kernel headers.
        # setup.py: `if sys.platform in ('linux', 'freebsd4', ...):`
        filter_file(r"'linux', ", "", "setup.py")

        # Static musl has no dlopen -> "Dynamic loading not supported", so the
        # usual shared C-extension modules (built by setup.py) can't be imported.
        # glibc's gen-as-const.py needs them (argparse -> gettext -> struct ->
        # _struct, and locale -> _locale). Link the dep-free stdlib C extensions
        # STATICALLY into the interpreter via Modules/Setup.local (the ``*static*``
        # directive); listing them here makes setup.py skip the shared build.
        with open(join_path("Modules", "Setup.local"), "w") as f:
            f.write(
                "*static*\n"
                "array arraymodule.c\n"
                "math mathmodule.c _math.c\n"
                "cmath cmathmodule.c _math.c\n"
                "_struct _struct.c\n"
                "_random _randommodule.c\n"
                "_bisect _bisectmodule.c\n"
                "_heapq _heapqmodule.c\n"
                "_datetime _datetimemodule.c\n"
                "_pickle _pickle.c\n"
                "_json _json.c\n"
                "_csv _csv.c\n"
                "unicodedata unicodedata.c\n"
                "fcntl fcntlmodule.c\n"
                "select selectmodule.c\n"
                "_posixsubprocess _posixsubprocess.c\n"
                # _socket omitted: musl lacks struct sockaddr_can (Linux CAN
                # socket bits), and glibc's build scripts don't need it.
                "_locale _localemodule.c\n"
                "binascii binascii.c\n"
                # hashlib's pure-C backends (no OpenSSL): random.py imports
                # sha512, and random is pulled in by tempfile -> glibcextract.
                "_md5 md5module.c\n"
                "_sha1 sha1module.c\n"
                "_sha256 sha256module.c\n"
                "_sha512 sha512module.c\n"
            )

        sh = Executable("/bin/sh")
        sh(
            "configure",
            "CONFIG_SHELL=/bin/sh",
            "SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "--build={0}".format(triple),
            "--host={0}".format(triple),
            "--prefix={0}".format(prefix),
            "--without-ensurepip",
            "--without-threads",
            # Static-only; no shared libpython needed.
            "--disable-shared",
        )

        make()
        make("install")

        # Remove the large test suite (Guix: remove-tests phase).
        test_dir = join_path(prefix.lib, "python3.5", "test")
        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir)

        # Provide a 'python3' symlink alongside 'python3.5'.
        py35 = join_path(prefix.bin, "python3.5")
        py3 = join_path(prefix.bin, "python3")
        if os.path.exists(py35) and not os.path.exists(py3):
            os.symlink("python3.5", py3)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
