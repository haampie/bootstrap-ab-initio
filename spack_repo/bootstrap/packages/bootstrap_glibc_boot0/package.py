# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGlibcBoot0(Package):
    """glibc 2.43 -- the production x86_64 libc, built by the crippled gcc-boot0.

    The second half of the musl->glibc transition and the kept production libc:
    built once, never rebuilt. gcc-boot0 (GCC 16, ``--without-headers``) knows
    no libc, but glibc's own build drives ``-nostdlib`` for its bootstrap, so it
    is built by the *unwrapped* gcc-boot0 -- no chicken-and-egg. Every later cap
    stage (gcc-boot0-wrapped, libstdcxx-boot1, binutils-final, gcc-final) links
    against this glibc.

    Native build (build==host==x86_64-linux-gnu; the kernel is x86_64).
    ``--with-headers`` points at bootstrap-linux-headers (kernel 6.9.1 x86_64).
    C_INCLUDE_PATH/CPLUS_INCLUDE_PATH are unset before configure so no stray
    include dir shadows glibc's own. Needs Python (gen-as-const), bison +
    m4 (intl/plural.c), and make >= 4 (bootstrap-gmake 4.4.1).

    No ``c`` virtual: compiler wired explicitly to gcc-boot0. Ported from
    ``glibc-boot0`` (Guix glibc-final-with-bootstrap-bash + base.scm glibc)."""

    homepage = "https://www.gnu.org/software/libc/"
    url = "https://ftpmirror.gnu.org/glibc/glibc-2.43.tar.xz"

    license("LGPL-2.0-or-later AND LGPL-2.1-or-later")

    # NOTE: this is the sha256 of the .tar.XZ (verified against ftp.gnu.org);
    # the builtin glibc package pins the .tar.GZ (different hash, e1e622cb...).
    version("2.43", sha256="d9c86c6b5dbddb43a3e08270c5844fc5177d19442cf5b8df4be7c07cd5fa3831")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-boot0", type="build")
    depends_on("bootstrap-binutils-boot0", type=("build", "run"))
    # Run dep too: we symlink the kernel headers into our own include/ so that
    # gcc-final's baked --with-native-system-header-dir suffices; the symlink
    # targets must persist at runtime.
    depends_on("bootstrap-linux-headers", type=("build", "run"))
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-python", type="build")
    depends_on("bootstrap-bison", type="build")
    depends_on("bootstrap-m4", type="build")

    #: build tool providing ``make`` (4.4.1 handles the jobserver -> parallel)
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # Unset inherited include paths so kernel/musl headers don't shadow
        # glibc's own (Guix: pre-configure phase). bootstrap-gmake handles the
        # jobserver, so do NOT clear MAKEFLAGS (parallel build).
        env.unset("C_INCLUDE_PATH")
        env.unset("CPLUS_INCLUDE_PATH")

    def install(self, spec, prefix):
        gcc_boot = spec["bootstrap-gcc-boot0"].prefix
        headers = spec["bootstrap-linux-headers"].prefix
        python = spec["bootstrap-python"].prefix
        make = Executable(spec[self.make_provider].prefix.bin.make)

        cc = join_path(gcc_boot.bin, "gcc")
        triplet = "%s-linux-gnu" % spec.target.family

        configure_flags = [
            "CONFIG_SHELL=/bin/sh",
            "SHELL=/bin/sh",
            "CC={0}".format(cc),
            # glibc generates scripts that hardcode this shell.
            "BASH_SHELL=/bin/sh",
            # Python for gen-as-const and friends; glibc's configure lists
            # 'python' as critic_missing, so point it at our bootstrap python3.
            "PYTHON={0}/bin/python3".format(python),
            "--build={0}".format(triplet),
            "--host={0}".format(triplet),
            "--prefix={0}".format(prefix),
            "--with-headers={0}/include".format(headers),
            "--enable-kernel=3.2.0",
            "--disable-nls",
            "--disable-werror",
            "--disable-profile",
            # NOTE: do NOT pass --disable-multi-arch -- it strips the IFUNC CPU
            # dispatch (tuned memcpy/str*/libmvec) and kills vector-math perf.
            # (multi-arch != multilib; see glibc-multi-arch-ifunc memory.)
            # Suppress ld.so.cache path rewriting (Guix-ism).
            "--with-default-link=no",
        ]

        # glibc requires an out-of-tree build.
        build_dir = "build"
        mkdirp(build_dir)
        with working_dir(build_dir):
            sh = Executable("/bin/sh")
            sh("../configure", *configure_flags)
            make()
            make("install")

        # Make <prefix>/include a complete /usr/include: glibc installs the libc
        # headers; symlink in the kernel headers (linux/, asm/, asm-generic/, ...)
        # so a single --with-native-system-header-dir=<prefix>/include covers
        # both for the shipped gcc-final. See glibc-copy-kernel-headers memory.
        kernel_include = spec["bootstrap-linux-headers"].prefix.include
        for name in os.listdir(kernel_include):
            dst = join_path(prefix.include, name)
            if not os.path.lexists(dst):
                os.symlink(join_path(kernel_include, name), dst)

    def setup_dependent_build_environment(self, env, dependent_spec):
        # Downstream stages need glibc's headers and startup files.
        # CPLUS_INCLUDE_PATH is APPENDED so libstdc++ providers (which prepend)
        # stay ahead -- libstdc++'s <cstdlib> #include_next <stdlib.h> must reach
        # glibc's copy. Mirrors Guix %gcc-search-paths.
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.append_path("CPLUS_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", join_path(self.prefix, "lib"))
