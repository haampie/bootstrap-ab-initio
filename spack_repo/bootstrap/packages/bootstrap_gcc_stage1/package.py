# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

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
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-linux-headers", type="build")

    # gmp/mpfr/mpc are built IN-TREE (Guix's unpack-gmp&co): their *sources* are
    # unpacked into the GCC tree as gmp/ mpfr/ mpc/, so gcc-stage0 (a real GCC
    # driving real binutils `as`) compiles them as part of this build. The
    # standalone bootstrap-gmp/mpfr/mpc packages are tcc-built and carry tcc
    # runtime symbols (alloca/__va_start/__va_arg/__floatundidf live in libtcc1);
    # a real GCC linking against them fails the configure link test ("correct
    # version of the gmp/mpfr/mpc libraries... no"). In-tree sidesteps that AND
    # the version/link check (configure uses the in-tree dirs when they exist).
    resource(name="gmp", placement="gmp",
             url="https://ftpmirror.gnu.org/gmp/gmp-4.3.2.tar.gz",
             sha256="7be3ad1641b99b17f6a8be6a976f1f954e997c41e919ad7e0c418fe848c13c97")
    resource(name="mpfr", placement="mpfr",
             url="https://ftpmirror.gnu.org/mpfr/mpfr-2.4.2.tar.gz",
             sha256="246d7e184048b1fc48d3696dd302c9774e24e921204221540745e5464022b637")
    resource(name="mpc", placement="mpc",
             url="https://ftpmirror.gnu.org/mpc/mpc-1.0.3.tar.gz",
             sha256="617decc6ea09889fb08ede330917a00b16809b8db88c29c31bfbb49cbf88ecc3")

    patch("0001-alloca.patch")
    patch("0002-strsignal.patch")
    patch("0003-libstdcxx-glibc-prereq.patch")
    patch("0004-libstdcxx-generic-ctype.patch")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"



    def configure_args(self, spec, prefix):
        gcc = join_path(spec["bootstrap-gcc-stage0"].prefix, "bin", "gcc")
        sysroot = spec["bootstrap-musl"].prefix
        triple = "%s-unknown-linux-musl" % spec.target.family
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
            "--build=" + triple,
            "--host=" + triple,
            "--target=" + triple,
            "--with-sysroot=" + str(sysroot),
            "--with-native-system-header-dir=/include",
            # NO --with-gmp/--with-mpfr/--with-mpc: the in-tree gmp/ mpfr/ mpc/
            # dirs are auto-detected and built as part of GCC.
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
        # Guix's setenv: let the in-tree mpfr.h (mpfr/src) be found while GCC and
        # libstdc++ compile, before the in-tree mpfr is installed into the build.
        os.environ["C_INCLUDE_PATH"] = os.pathsep.join(
            filter(None, [join_path(self.stage.source_path, "mpfr", "src"),
                          os.environ.get("C_INCLUDE_PATH", "")])
        )
        # In-tree gmp's AC_PROG_LEX fatally runs flex's output probe when flex is
        # on PATH (it is on the aarch64 host, absent on the old x86_64 box) and
        # dies "cannot find output from flex". flex is only used by gmp demos, so
        # preseed the cache var to skip the probe (same trick bootstrap-gmp uses).
        os.environ["ac_cv_prog_lex_root"] = "lex.yy"
        # gmp-4.3.2/mpfr-2.4.2/mpc-1.0.3 ship pre-2014 config.sub/config.guess
        # that don't know the `musl` OS, so their in-tree configure dies on
        # `x86_64-unknown-linux-musl`. GCC 4.7's own top-level pair (2012) does
        # accept it, so overwrite the bundled ones (gmp's config.sub is a wrapper
        # around configfsf.sub; replacing it with GCC's plain version is fine).
        src = self.stage.source_path
        for sub in ("gmp", "mpfr", "mpc"):
            for f in ("config.sub", "config.guess"):
                copy(join_path(src, f), join_path(src, sub, f))
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
