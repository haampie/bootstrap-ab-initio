# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapBison(Package):
    """Bison 3.8.2 built by bootstrap-gcc-9 (static musl), required by
    bootstrap-glibc-boot0.

    glibc unconditionally checks for bison >= 2.7 in configure and invokes it at
    make time to generate ``intl/plural.c`` from ``intl/plural.y`` (intl/ is
    always in all-subdirs). Bison itself needs m4 at run time (to expand its
    skeleton files) -- supplied by bootstrap-m4 and prepended to PATH via
    setup_dependent_build_environment.

    Native x86_64 build (no i686 cross, no ``-g0``); make is bootstrap-gmake.
    Tests are skipped (the suite needs perl and a working flex). No ``c``
    virtual: compiler wired explicitly to bootstrap-gcc-9."""

    homepage = "https://www.gnu.org/software/bison/"
    url = "https://ftpmirror.gnu.org/bison/bison-3.8.2.tar.xz"

    license("GPL-3.0-or-later")

    version("3.8.2", sha256="9bba0214ccf7f1079c5d59210045227bcf619519840ebfa80cd3849cff5a5bf2")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-9", type="build")
    depends_on("bootstrap-gmake", type="build")
    # m4 must be on PATH for bison to work at run time.
    depends_on("bootstrap-m4", type=("build", "run"))

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # No usable host flex in the sandbox; bison SHIPS its generated scanners
        # (maintainer-mode off), so flex is never actually needed. AC_PROG_LEX
        # otherwise runs $LEX and fails its output-file probe ("cannot find
        # output from flex"). Preseeding ac_cv_prog_lex_root short-circuits it
        # (same as bootstrap-binutils-boot0 / bootstrap-binutils-final).
        env.set("ac_cv_prog_lex_root", "lex.yy")

    def install(self, spec, prefix):
        gcc = spec["bootstrap-gcc-9"].prefix
        make = Executable(spec[self.make_provider].prefix.bin.make)
        triple = "%s-linux-musl" % spec.target.family

        sh = Executable("/bin/sh")
        sh(
            "configure",
            "CONFIG_SHELL=/bin/sh",
            "SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "--build={0}".format(triple),
            "--host={0}".format(triple),
            "--prefix={0}".format(prefix),
            "--disable-nls",
            # Zero timestamps in liby.a so the archive is reproducible with the
            # bootstrap binutils (ar default is "cru", not "crD").
            "ARFLAGS=crD",
        )

        make()
        make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
