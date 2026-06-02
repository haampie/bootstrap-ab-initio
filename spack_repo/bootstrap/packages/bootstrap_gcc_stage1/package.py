# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGccStage1(Package):
    """GCC 4.7.4 (Linaro 4.7-2013.11), C + C++ -- the chain's deliverable g++.

    Built by the C-only bootstrap-gcc-stage0 against the pristine bootstrap-musl.
    GCC 4.7's cc1plus is itself written in C (the C++ self-host switch was 4.8),
    so a C-only host compiler builds the whole C++ front-end -- the C++ configure
    probe is just pointed at stage0's gcc as a C compiler so the forbidden system
    /lib/cpp is never touched.

    Ported from MES-replacement/steps/07-gcc-4.7-stage2/. Source patches: 0001
    alloca, 0002 strsignal const-qualify, 0003 libstdc++ __GLIBC_PREREQ guard,
    0004 libstdc++ generic (musl) ctype. No ``c`` virtual dependency."""

    homepage = "https://gcc.gnu.org/"
    url = (
        "https://releases.linaro.org/archive/13.11/components/toolchain/"
        "gcc-linaro/4.7/gcc-linaro-4.7-2013.11.tar.bz2"
    )

    license("GPL-3.0-or-later")

    version("4.7-2013.11",
            sha256="d0ea2c72ceb66d3851986840dd8962941824a2980a8aca2a800abb5b489acedf")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-stage0", type="build")  # C-only host compiler
    depends_on("bootstrap-musl", type=("build", "run"))  # pristine sysroot libc
    depends_on("bootstrap-binutils", type=("build", "run"))
    depends_on("bootstrap-gmp", type="build")
    depends_on("bootstrap-mpfr", type="build")
    depends_on("bootstrap-mpc", type="build")
    depends_on("bootstrap-gmake-mes", type="build")
    depends_on("bootstrap-linux-headers", type="build")

    patch("0001-alloca.patch")
    patch("0002-strsignal.patch")
    patch("0003-libstdcxx-glibc-prereq.patch")
    patch("0004-libstdcxx-generic-ctype.patch")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake-mes"

    def setup_build_environment(self, env):
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def configure_args(self, spec, prefix):
        gcc = join_path(spec["bootstrap-gcc-stage0"].prefix, "bin", "gcc")
        sysroot = spec["bootstrap-musl"].prefix
        return [
            "CC=" + gcc,
            "CC_FOR_BUILD=" + gcc,
            # GCC 4.7's cc1plus is C; satisfy the C++ probe with stage0 gcc as a
            # C compiler so /lib/cpp is never consulted.
            "CXX=%s -x c" % gcc,
            "CXXCPP=%s -x c -E" % gcc,
            "CFLAGS=-DHAVE_ALLOCA_H",
            "MAKEINFO=true",
            "--prefix=" + prefix,
            "--build=x86_64-unknown-linux-musl",
            "--host=x86_64-unknown-linux-musl",
            "--target=x86_64-unknown-linux-musl",
            "--with-sysroot=" + str(sysroot),
            "--with-native-system-header-dir=/include",
            "--with-gmp=" + str(spec["bootstrap-gmp"].prefix),
            "--with-mpfr=" + str(spec["bootstrap-mpfr"].prefix),
            "--with-mpc=" + str(spec["bootstrap-mpc"].prefix),
            "--enable-languages=c,c++",
            "--enable-static",
            "--disable-shared",
            "--enable-threads=single",
            "--disable-threads",
            "--disable-libstdcxx-pch",
            "--disable-build-with-cxx",
            "--disable-bootstrap",
            "--disable-multilib",
            "--disable-decimal-float",
            "--disable-lto",
            "--disable-lto-plugin",
            "--disable-plugin",
            "--disable-libatomic",
            "--disable-libcilkrts",
            "--disable-libgomp",
            "--disable-libitm",
            "--disable-libmudflap",
            "--disable-libquadmath",
            "--disable-libsanitizer",
            "--disable-libssp",
            "--disable-libvtv",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        build = join_path(self.stage.source_path, "build")
        mkdirp(build)
        with working_dir(build):
            sh(join_path(self.stage.source_path, "configure"),
               *self.configure_args(spec, prefix))
            # Reactive: add CFLAGS_FOR_TARGET="-fno-tree-ccp" only on an x86_64
            # target-libgcc CCP segfault (an AArch64-only bug there).
            make()
            make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
