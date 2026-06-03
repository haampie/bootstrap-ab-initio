# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapMuslBoot(Package):
    """musl 1.1.24, the toolchain libc -- correct printf, built by tcc-musl-stage1.

    The scaffold musl (bootstrap-musl-scaffold) is compiled by the seed tcc
    (tcc-mes), which miscompiles musl's printf in two ways: the wide-``long``
    integer path emits NUL bytes (``%016lx`` -> corrupt, which makes binutils
    ``nm`` output unparseable -- every ``nm | grep`` downstream then mis-fires),
    and ``%f`` rounds to 0.0. This package rebuilds the SAME musl with
    bootstrap-tcc-musl-stage1 (whose x86_64 codegen is correct), fixing the
    integer path outright, and carries a float-classifying ``0040`` va_list patch
    that routes double varargs through the XMM save area, so ``%f`` round-trips.

    It is the libc the working bootstrap-tcc-musl bakes into its CONFIG_* paths
    and that binutils / gmp / mpfr / mpc / gcc-stage0 link against. (The pristine
    zero-patch bootstrap-musl, built later by gcc-stage0, is the final gcc-stage1
    sysroot; this one is the bootstrap-stage toolchain libc.)

    Built freestanding (``-nostdinc``, musl ships its own headers; ``-c`` + ar
    only, no link), so the scaffold musl that tcc-musl-stage1's *own binary*
    links never enters these objects. Patches are the tcc language-gap subset
    shared with bootstrap-musl-scaffold; only ``0040`` differs (float-correct
    va_arg here vs the scaffold's GP-only variant). No ``c`` virtual dependency.
    """

    homepage = "https://musl.libc.org/"
    url = "https://www.musl-libc.org/releases/musl-1.1.24.tar.gz"

    license("MIT")

    version("1.1.24", sha256="1370c9a812b2cf2a7d92802510cca0058cc37e66a7bedd70051f0a34015022a3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-musl-stage1", type="build")
    depends_on("bootstrap-gmake-mes", type="build")
    depends_on("bootstrap-linux-headers-seed", type="build")

    # Shared patches (both architectures).
    patch("0001-EMPTY_LIB_NAMES-add-g-so-tcc-can-resolve-lg.patch")
    patch("0004-Remove-crt-rcrt1.c-static-PIE-startup-unused-with-di.patch")
    patch("0006-Strip-C99-static-N-array-declarators.patch")
    patch("0020-Makefile-archive-an-empty-placeholder-.o-into-EMPTY_.patch")

    # x86_64-only patches.
    patch("0002-sigsetjmp-x86_64-plt.patch", when="target=x86_64:")
    patch("0030-syscall-x86_64.patch", when="target=x86_64:")
    patch("0031-fenv.patch", when="target=x86_64:")
    patch("0040-x86_64-sysv-va_list.patch", when="target=x86_64:")

    # aarch64-only patches (the same concern-grouped set as bootstrap-musl-scaffold;
    # this is the same musl source with the same tcc language gaps).
    patch("aarch64-01-va_list.patch", when="target=aarch64:")
    patch("aarch64-02-asm-to-c.patch", when="target=aarch64:")
    patch("aarch64-03-drop-asm-barriers.patch", when="target=aarch64:")

    def patch(self):
        # tcc cannot parse C99 _Complex (src/complex, both arches); the
        # arch-specific src/math/<arch> shims are .s/inline-asm tcc cannot build.
        src = self.stage.source_path
        shutil.rmtree(join_path(src, "src", "complex"))
        arch = "aarch64" if str(self.spec.target.family) == "aarch64" else "x86_64"
        shutil.rmtree(join_path(src, "src", "math", arch))

    def install(self, spec, prefix):
        cc = join_path(spec["bootstrap-tcc-musl-stage1"].prefix.bin, "tcc")
        kheaders = spec["bootstrap-linux-headers-seed"].prefix
        sh = Executable("/bin/sh")
        tcc = Executable(cc)
        make = Executable(spec["bootstrap-gmake-mes"].prefix.bin.make)

        sh(
            "./configure",
            "CC=" + cc,
            f"--target={spec.target.family}-linux-musl",
            "--prefix=" + prefix,
            "--syslibdir=" + join_path(prefix, "lib"),
            "--disable-shared",
            "--disable-gcc-wrapper",
        )

        # patch 0020 makes EMPTY_LIBS depend on obj/empty.o but ships no rule;
        # generate it by hand (build.sh step 4).
        mkdirp("obj")
        with open("obj/empty.c", "w"):
            pass
        tcc("-c", "-o", "obj/empty.o", "obj/empty.c")

        cflags = "-DSYSCALL_NO_TLS -I" + join_path(kheaders, "include")
        ar = cc + " -ar"
        make("CC=" + cc, "AR=" + ar, "RANLIB=true", "CFLAGS=" + cflags)
        make("install", "CC=" + cc, "AR=" + ar, "RANLIB=true")

        for f in ("lib/libc.a", "lib/crt1.o", "lib/crti.o", "lib/crtn.o"):
            assert os.path.exists(join_path(prefix, f)), "missing " + f

    def setup_build_environment(self, env):
        # gmake-mes deadlocks under Spack's inherited jobserver (stub sigaction in
        # the seed MES libc -> no SIGCHLD). Run serial. See the
        # bootstrap-gmake-mes-jobserver memory.
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
