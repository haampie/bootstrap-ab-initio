# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapMusl(Package):
    """musl 1.1.24, the real libc -- pristine (ZERO patches), built by gcc-stage0.

    Replaces the throwaway bootstrap-musl-scaffold. Every one of the patches the
    tcc-built scaffold needed was a tcc/HAVE_FLOAT artifact; compiled by a real
    GCC the pristine tarball builds clean and its printf("%f") is correct.

    Carried as ``type=(build,run)`` -- this is the sysroot libc
    bootstrap-gcc-stage1 links. No ``c`` virtual dependency."""

    homepage = "https://musl.libc.org/"
    url = "https://www.musl-libc.org/releases/musl-1.1.24.tar.gz"

    license("MIT")

    version("1.1.24", sha256="1370c9a812b2cf2a7d92802510cca0058cc37e66a7bedd70051f0a34015022a3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-stage0", type="build")
    depends_on("bootstrap-binutils", type=("build", "run"))
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-linux-headers", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        gcc = join_path(spec["bootstrap-gcc-stage0"].prefix, "bin", "gcc")
        binutils = spec["bootstrap-binutils"].prefix

        # Kernel uapi headers reach gcc via C_INCLUDE_PATH (set by the
        # bootstrap-linux-headers dependent env -- real gcc honors it).
        # "./configure" (not "configure"): musl derives srcdir from
        # ${0%/configure}; a bare name leaves srcdir="configure" and fails.
        sh(
            "./configure",
            "CC=" + gcc,
            "--target=%s-linux-musl" % spec.target.family,
            "--prefix=" + prefix,
            "--syslibdir=" + join_path(prefix, "lib"),
            "--disable-shared",
        )

        # Triples differ between gcc (…-unknown-linux-musl) and binutils
        # (…-linux-musl), so pin AR/RANLIB explicitly rather than relying on
        # musl's CROSS_COMPILE-derived tool names.
        ar = join_path(binutils, "bin", "ar")
        ranlib = join_path(binutils, "bin", "ranlib")
        # NOTE: x86_64 starts without -fno-tree-ccp (that was an AArch64 CCP
        # backend bug on musl's aio.c). Add CFLAGS=-fno-tree-ccp reactively if
        # cc1 segfaults.
        make("AR=" + ar, "RANLIB=" + ranlib)
        make("install", "AR=" + ar, "RANLIB=" + ranlib)

        for f in ("lib/libc.a", "lib/crt1.o"):
            assert os.path.exists(join_path(prefix, f)), "missing " + f

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
