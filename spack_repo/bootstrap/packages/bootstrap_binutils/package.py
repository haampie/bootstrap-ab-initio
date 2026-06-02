# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import re

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapBinutils(Package):
    """GNU Binutils 2.30 (as/ld/ar/...), built by tcc-musl against scaffold musl.

    The first real assembler/linker of the new chain, used to build gmp/mpfr/mpc
    and GCC. Ported from MES-replacement/steps/04-binutils-2.30/ (which mirrors
    Guix's binutils-muslboot0), retargeted x86_64.

    Carried as ``type=(build,run)`` by the gcc/musl stages so as/ld/ar reach
    their PATH (cf. the bootstrap-toolchain-run-deps memory). No ``c`` virtual.

    Patches: NONE. The two AArch64 patches in the steps dir are arch-specific
    (the elfnn-aarch64 HOWTO preprocessor fix) or only kept for Guix parallelism
    (dropping gas/read.c's wchar.h include -- musl *has* wchar.h). Add reactively.

    Host bison/flex/m4 build the generated parsers binutils 2.30 doesn't ship;
    they don't enter the artifact (only the generated .c files do)."""

    homepage = "https://www.gnu.org/software/binutils/"
    url = "https://ftp.gnu.org/gnu/binutils/binutils-2.30.tar.gz"

    license("GPL-3.0-or-later")

    version("2.30", sha256="8c3850195d1c093d290a716e20ebcaa72eda32abf5e3d8611154b39cff79e9ea")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-musl", type="build")
    depends_on("bootstrap-musl-scaffold", type="build")
    depends_on("bootstrap-gmake-mes", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake-mes"

    def setup_build_environment(self, env):
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        tcc = join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")
        musllib = join_path(spec["bootstrap-musl-scaffold"].prefix, "lib")

        # tcc-musl already has the scaffold-musl crt/headers/libc baked into its
        # CONFIG_* paths, so it works as a self-contained "cc". The extra -L is
        # belt-and-suspenders. ar/ranlib are tcc's own; MAKEINFO=true avoids texi.
        host_tools = ["LEX=/usr/bin/flex", "YACC=/usr/bin/bison -y", "M4=/usr/bin/m4"]
        sh(
            "configure",
            "CC=%s -L%s" % (tcc, musllib),
            "LD=" + tcc,
            "AR=%s -ar" % tcc,
            "RANLIB=true",
            "MAKEINFO=true",
            *host_tools,
            "CFLAGS=-g",
            "--build=x86_64-linux-musl",
            "--host=x86_64-linux-musl",
            "--target=x86_64-linux-musl",
            "--prefix=" + prefix,
            "--with-sysroot=/",
            "--enable-64-bit-bfd",
            "--disable-nls",
            "--enable-static",
            "--disable-shared",
            "--disable-werror",
            "--disable-plugins",
            "--enable-deterministic-archives",
        )

        # autoconf's AC_PROG_LEX leaves LEX_OUTPUT_ROOT='' in every sub-Makefile
        # in this environment; a command-line override is reset by the recursive
        # sub-make, so patch the Makefiles directly (cf. steps/04 build.sh).
        pat = re.compile(r"^LEX_OUTPUT_ROOT = $", re.M)
        for root, _dirs, files in os.walk(self.stage.source_path):
            if "Makefile" in files:
                mk = join_path(root, "Makefile")
                with open(mk) as f:
                    text = f.read()
                if pat.search(text):
                    with open(mk, "w") as f:
                        f.write(pat.sub("LEX_OUTPUT_ROOT = lex.yy", text))

        build_tools = ["MAKEINFO=true", "M4=/usr/bin/m4", "BISON=/usr/bin/bison",
                       "YACC=/usr/bin/bison -y", "FLEX=/usr/bin/flex", "LEX=/usr/bin/flex"]
        make("-j1", *build_tools)
        make("install", *build_tools)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
