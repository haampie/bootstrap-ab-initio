# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapMusl12(Package):
    """musl 1.2.5, the modern libc -- pristine (ZERO patches), built by gcc-stage1.

    Sibling of bootstrap-musl (1.1.24, built by gcc-stage0): once the chain has a
    real C+C++ GCC 4.7.4 (bootstrap-gcc-stage1), we mint a current musl with it,
    rather than mutating the proven 1.1.24 that gcc-stage1 itself links. This 1.2.5
    libc is the sysroot for the next compiler tier (bootstrap-gcc-9) only -- the
    per-tier "each compiler mints the next libc" model continues.

    Same build shape as bootstrap-musl. Carried as ``type=(build,run)`` -- this is
    the sysroot libc bootstrap-gcc-9 links. No ``c`` virtual dependency.

    (The package name drops the dot of musl "1.2": a ``.`` cannot appear in a Spack
    package name without breaking the package's Python module import.)"""

    homepage = "https://musl.libc.org/"
    url = "https://www.musl-libc.org/releases/musl-1.2.5.tar.gz"

    license("MIT")

    version("1.2.5", sha256="a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-stage1", type="build")
    depends_on("bootstrap-binutils", type=("build", "run"))
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-linux-headers", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        gcc = join_path(spec["bootstrap-gcc-stage1"].prefix, "bin", "gcc")
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
        make("AR=" + ar, "RANLIB=" + ranlib)
        make("install", "AR=" + ar, "RANLIB=" + ranlib)

        for f in ("lib/libc.a", "lib/crt1.o"):
            assert os.path.exists(join_path(prefix, f)), "missing " + f

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
