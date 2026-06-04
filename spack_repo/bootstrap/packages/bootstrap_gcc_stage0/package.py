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

    Single source patch: 0001 alloca; every other historical workaround was a
    HAVE_FLOAT artifact removed once tcc was rebuilt with -DHAVE_FLOAT=1. No
    ``c`` virtual dependency.

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
    depends_on("bootstrap-musl-boot", type="build")
    depends_on("bootstrap-gmp", type="build")
    depends_on("bootstrap-mpfr", type="build")
    depends_on("bootstrap-mpc", type="build")
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-linux-headers-seed", type="build")

    patch("0001-alloca.patch")

    languages = "c"

    #: build tool providing ``make``. bootstrap-gmake (musl-linked, real
    #: sigaction) parallelizes via Spack's jobserver; gmake-mes would deadlock.
    make_provider = "bootstrap-gmake"



    def host_cc(self, spec):
        return join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")

    def sysroot(self, spec):
        return spec["bootstrap-musl-boot"].prefix

    def configure_args(self, spec, prefix):
        cc = self.host_cc(spec)
        triple = "%s-unknown-linux-musl" % spec.target.family
        return [
            "CC=" + cc,
            "CC_FOR_BUILD=" + cc,
            "CFLAGS=-DHAVE_ALLOCA_H",
            "MAKEINFO=true",
            "--prefix=" + prefix,
            "--build=" + triple,
            "--host=" + triple,
            "--target=" + triple,
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
        # x86_64 DOES hit the CCP/TImode backend segfault after all: the freshly
        # built stage0 cc1 ICEs (SIGSEGV) compiling target libgcc's TImode
        # helpers (__negti2/__ashlti3/__ashrti3 in libgcc2.c). Disabling the
        # tree-ccp pass for target code dodges it, exactly as on AArch64.
        return ["CFLAGS_FOR_TARGET=-O2 -fno-tree-ccp"]

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
        self._install_no_ccp_specs(prefix)

    def _install_no_ccp_specs(self, prefix):
        # gcc-stage0's cc1 was compiled by tcc-musl, whose codegen miscompiles
        # gcc's tree-ccp pass: this gcc ICEs on TImode (the CFLAGS_FOR_TARGET
        # workaround above) AND silently miscompiles ordinary -O1/-O2 code (a
        # fixdep it builds spins forever; pristine musl and gcc-stage1's own
        # cc1plus would be corrupted too). Ship a specs file that appends
        # -fno-tree-ccp to every cc1/cc1plus invocation, so EVERY consumer this
        # gcc compiles is built correctly with no per-package flags. (gcc reads
        # `specs` from its libgcc dir automatically.) gcc-stage1, compiled clean
        # by THIS gcc, ships no such specs and keeps a working tree-ccp.
        gcc = Executable(join_path(prefix, "bin", "gcc"))
        libgcc = gcc("-print-libgcc-file-name", output=str).strip()
        with open(join_path(os.path.dirname(libgcc), "specs"), "w") as f:
            f.write("*cc1_options:\n+ -fno-tree-ccp\n\n")

    def setup_dependent_build_environment(self, env, dependent_spec):
        # Acts as the host CC for stage-1; expose its own headers/libs.
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
        env.prepend_path("PATH", self.prefix.bin)
