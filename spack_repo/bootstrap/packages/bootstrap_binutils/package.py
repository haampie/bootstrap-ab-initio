# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

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
    depends_on("bootstrap-musl-boot", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``. bootstrap-gmake (musl-linked, real
    #: sigaction) -- NOT gmake-mes -- so this heavy stage parallelizes via
    #: Spack's jobserver without the gmake-mes deadlock. No MAKEFLAGS clearing.
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # No host flex/bison (this chain treats them as host tools, but they may
        # be absent -- and binutils 2.30 SHIPS the generated parsers, ldgram.c /
        # ldlex.c / arlex.c / ..., used as-is since maintainer-mode is off). The
        # only obstacle is AC_PROG_LEX, which fatally runs $LEX ("cannot find
        # output from <flex>; giving up") -- but that check is skipped when
        # ``ac_cv_prog_lex_root`` is already set. Export it so EVERY configure
        # (top + recursive configure-binutils/gas/ld) short-circuits and uses
        # the shipped .c. This also sets LEX_OUTPUT_ROOT=lex.yy in the Makefiles,
        # so no post-configure sed is needed. (binutils-mesboot0 needed no flex
        # either; cf. commencement.scm using flex/bison as inputs only.)
        env.set("ac_cv_prog_lex_root", "lex.yy")

        # libtool's runtime probe misdetects max_cmd_len=512 in this env, so for
        # libbfd (~50 objects) it falls back to "piecewise archive linking" --
        # several ``$AR rc libbfd.a <batch>`` calls. But tcc's ``-ar`` RECREATES
        # the archive each call (tcctools.c fopen(lib,"wb"); no append), so only
        # the LAST batch survives -> libbfd.a loses archive.o/bfd.o/init.o and
        # gas's as-new link fails with "undefined symbol bfd_init/bfd_scan_vma".
        # Export the libtool cache var (skips the probe in every sub-configure)
        # so each archive is built in ONE ar call. 128K is far under ARG_MAX
        # (~3.2M) and dwarfs any archive command here. Needed by gcc-stage0 too.
        env.set("lt_cv_sys_max_cmd_len", "131072")

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        tcc = join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")
        musllib = join_path(spec["bootstrap-musl-boot"].prefix, "lib")

        # tcc-musl already has the scaffold-musl crt/headers/libc baked into its
        # CONFIG_* paths, so it works as a self-contained "cc". The extra -L is
        # belt-and-suspenders. ar/ranlib are tcc's own; MAKEINFO=true avoids texi.
        # M4 from the host (present); flex/bison are not needed (shipped parsers).
        sh(
            "configure",
            "CC=%s -L%s" % (tcc, musllib),
            "LD=" + tcc,
            "AR=%s -ar" % tcc,
            "RANLIB=true",
            "MAKEINFO=true",
            "CFLAGS=-g",
            "--build=x86_64-linux-musl",
            "--host=x86_64-linux-musl",
            "--target=x86_64-linux-musl",
            "--prefix=" + prefix,
            "--with-sysroot=/",
            # ld/ generates its emulation sources via a recursive `make
            # run-genscripts`, which -includes .deps/*.Po. automake doesn't know
            # tcc's depmode, so the .Po placeholders aren't created, and under
            # parallel make the sub-make can run before the main compile creates
            # them -> "No rule to make target '.deps/ldlang.Po'". Dependency
            # tracking is useless for a one-shot build; disabling it drops the
            # .Po include entirely and makes the parallel build deterministic.
            "--disable-dependency-tracking",
            "--enable-64-bit-bfd",
            "--disable-nls",
            "--enable-static",
            "--disable-shared",
            "--disable-werror",
            "--disable-plugins",
            "--enable-deterministic-archives",
        )

        make("MAKEINFO=true", "M4=/usr/bin/m4")
        make("install", "MAKEINFO=true", "M4=/usr/bin/m4")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
