# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGccStage0(Package):
    """GCC 4.7.4 (Linaro 4.7-2013.11), C only -- the first real C compiler.

    Built by tcc-musl against the scaffold musl, with binutils as/ld/ar on PATH
    and gmp/mpfr/mpc as prerequisites. It exists to (a) recompile musl correctly
    (bootstrap-musl) and (b) host the C+C++ stage-1 build (bootstrap-gcc-stage1).

    Ported from MES-replacement/steps/05-gcc-4.7-stage1/ (mirrors Guix
    gcc-muslboot0). Single source patch: 0001 alloca (= Guix fix-alloca); every
    other historical workaround was a HAVE_FLOAT artifact removed once tcc was
    rebuilt with -DHAVE_FLOAT=1. No ``c`` virtual dependency.

    The Linaro 4.7-2013.11 snapshot is used (rather than FSF 4.7.4) so the same
    recipe + patches serve AArch64, where 4.7 is the lowest GCC with target
    support; on x86_64 it is a normal 4.7.4-era GCC."""

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

    # build+run so this gcc's as/ld (binutils) reach the PATH of stage-1.
    depends_on("bootstrap-binutils", type=("build", "run"))
    depends_on("bootstrap-tcc-musl", type="build")
    depends_on("bootstrap-musl-scaffold", type="build")
    depends_on("bootstrap-gmp", type="build")
    depends_on("bootstrap-mpfr", type="build")
    depends_on("bootstrap-mpc", type="build")
    depends_on("bootstrap-gmake-mes", type="build")
    depends_on("bootstrap-linux-headers-seed", type="build")

    patch("0001-alloca.patch")

    languages = "c"

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake-mes"

    def setup_build_environment(self, env):
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def host_cc(self, spec):
        return join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")

    def sysroot(self, spec):
        return spec["bootstrap-musl-scaffold"].prefix

    def configure_args(self, spec, prefix):
        cc = self.host_cc(spec)
        return [
            "CC=" + cc,
            "CC_FOR_BUILD=" + cc,
            "CFLAGS=-DHAVE_ALLOCA_H",
            "MAKEINFO=true",
            "--prefix=" + prefix,
            "--build=x86_64-unknown-linux-musl",
            "--host=x86_64-unknown-linux-musl",
            "--target=x86_64-unknown-linux-musl",
            "--with-sysroot=" + str(self.sysroot(spec)),
            "--with-native-system-header-dir=/include",
            "--with-gmp=" + str(spec["bootstrap-gmp"].prefix),
            "--with-mpfr=" + str(spec["bootstrap-mpfr"].prefix),
            "--with-mpc=" + str(spec["bootstrap-mpc"].prefix),
            "--enable-languages=" + self.languages,
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

    def make_args(self, spec):
        # Reactive escape hatch (AArch64 needed CFLAGS_FOR_TARGET="-O2
        # -fno-tree-ccp" for a CCP/TImode backend segfault in target libgcc).
        # x86_64 is not expected to hit it; start clean and add only if needed.
        return []

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        # Out-of-tree build (GCC dislikes in-tree configure).
        build = join_path(self.stage.source_path, "build")
        mkdirp(build)
        with working_dir(build):
            sh(join_path(self.stage.source_path, "configure"),
               *self.configure_args(spec, prefix))
            make(*self.make_args(spec))
            make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        # Acts as the host CC for stage-1; expose its own headers/libs.
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
        env.prepend_path("PATH", self.prefix.bin)
