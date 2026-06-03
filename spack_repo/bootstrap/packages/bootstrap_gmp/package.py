# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGmp(Package):
    """GMP 4.3.2, a GCC 4.7 prerequisite, built by tcc-musl against scaffold musl.

    The version GCC 4.7 expects in-tree; here a standalone package (the chain
    keeps gmp/mpfr/mpc as separate bricks). Built before GCC by tcc-musl with
    binutils ar/ranlib on PATH. No ``c`` virtual dependency.

    ``--disable-assembly`` is mandatory: tcc cannot assemble GMP's hand-written
    asm. (This is a tcc-assembler limitation, not arch-specific.)"""

    homepage = "https://gmplib.org/"
    url = "https://ftpmirror.gnu.org/gmp/gmp-4.3.2.tar.gz"

    license("LGPL-3.0-or-later")

    version("4.3.2", sha256="7be3ad1641b99b17f6a8be6a976f1f954e997c41e919ad7e0c418fe848c13c97")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-musl", type="build")
    depends_on("bootstrap-musl-boot", type="build")
    depends_on("bootstrap-binutils", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # AC_PROG_LEX fatally runs the detected flex ("checking lex output file
        # root... cannot find output from flex; giving up") when a flex is on
        # PATH but its output probe fails in this build environment. flex is only
        # used by GMP's demos/calc lexer, never the library, so short-circuit the
        # probe exactly like bootstrap-binutils: pre-seed the cache var so every
        # configure skips the check (and sets LEX_OUTPUT_ROOT=lex.yy). The old
        # x86_64 host had no flex on PATH, so AC_PROG_LEX never ran this probe
        # there; this keeps both arches building regardless of host flex.
        env.set("ac_cv_prog_lex_root", "lex.yy")

    def configure_args(self, spec, prefix):
        tcc = join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")
        musllib = join_path(spec["bootstrap-musl-boot"].prefix, "lib")
        return [
            "CC=%s -L%s" % (tcc, musllib),
            "CFLAGS=-DHAVE_ALLOCA_H",
            # Force the generic C mpn (no asm) via the "none" CPU. GMP 4.3.2
            # predates --disable-assembly (added in GMP 5.0), so that flag is
            # silently ignored; with a real x86_64 host GMP picks its hand-written
            # mpn asm, which tcc's assembler can't handle (e.g. `movabsq`). A CPU
            # of "none" is unrecognized by configure's CPU case -> generic C only.
            # The triple also dodges the musl-unaware 2010 config.sub.
            "--build=none-unknown-linux-gnu",
            "--host=none-unknown-linux-gnu",
            "--prefix=" + prefix,
            "--enable-static",
            "--disable-shared",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        sh("configure", *self.configure_args(spec, prefix))
        make()
        make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
