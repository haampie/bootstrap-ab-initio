# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import filecmp
import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapTccMusl(Package):
    """tcc 0.9.26 rebuilt against (scaffold) musl -- the compiler that builds
    binutils, gmp/mpfr/mpc and GCC stage 0.

    Same tcc 0.9.26 source as bootstrap-tcc-mes, but compiled by the seed tcc
    (tcc-mes) and linked against bootstrap-musl-scaffold instead of mes libc.
    musl's strtod is correct, so this compiler rounds FP literals properly
    (unlike the mes-libc seed). It self-hosts in three stages and the fixed
    point (stage2 == stage3 byte-identical) is asserted.

    Ported from MES-replacement/steps/03-tcc-musl/ (+ musl-1.1.24/log.md).

    THE critical flag is ``-DHAVE_FLOAT=1``: the bootstrappable 0.9.26 fork wraps
    all floating-point handling in ``#if HAVE_FLOAT``; without it every
    float/double literal compiles to 0.0 and silently miscompiles GCC's cc1
    downstream. No ``c`` virtual dependency."""

    homepage = "https://www.iwriteiam.nl/MES-replacement.html"

    # Same bootstrappable TCC 0.9.26 snapshot as bootstrap-tcc-mes.
    version(
        "0.9.26",
        sha256="6b8cbd0a5fed0636d4f0f763a603247bc1935e206e1cc5bda6a2818bab6e819f",
        url="file:///home/harmen/projects/MES-replacement/distfiles/tcc-0.9.26.tar.gz",
    )

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-mes", type="build")
    depends_on("bootstrap-musl-scaffold", type="build")

    # Same amd64 tcc source fixes as bootstrap-tcc-mes (applied pre-sandbox).
    patch("tcc-static-plt.patch")
    patch("tcc-va-list.patch")

    def install(self, spec, prefix):
        src = self.stage.source_path
        seed = join_path(spec["bootstrap-tcc-mes"].prefix, "bin", "tcc")
        musl = spec["bootstrap-musl-scaffold"].prefix
        musllib = join_path(musl, "lib")
        muslinc = join_path(musl, "include")

        libdir = join_path(prefix, "lib", "mes")  # keep tcc-mes-style layout
        tccdir = join_path(libdir, "tcc")
        bindir = prefix.bin
        mkdirp(bindir, tccdir)

        def chmod_x(p):
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # tcc.h:25 does #include "config.h"; all config comes via -D below.
        open(join_path(src, "config.h"), "w").close()

        # libtcc1.a (compiler runtime helpers). x86_64 likely needs few/none for
        # a static tcc.c link, but build + include it to honor CONFIG_TCC_LIBPATHS
        # (harmless if unused). Built by the seed tcc.
        libtcc1 = join_path(tccdir, "libtcc1.a")
        with working_dir(src):
            Executable(seed)(
                "-c", "-DHAVE_FLOAT=1", "-DHAVE_LONG_LONG=1", "-DTCC_TARGET_X86_64=1",
                "-I", "include", "-o", "libtcc1.o", "lib/libtcc1.c",
            )
            Executable(seed)("-ar", "cr", libtcc1, "libtcc1.o")

        def defs():
            return [
                "-DBOOTSTRAP=1",
                "-DHAVE_FLOAT=1",
                "-DHAVE_BITFIELD=1",
                "-DHAVE_LONG_LONG=1",
                "-DHAVE_SETJMP=1",
                "-DTCC_TARGET_X86_64=1",
                '-DCONFIG_TCCDIR="%s"' % tccdir,
                '-DCONFIG_SYSROOT="/"',
                '-DCONFIG_TCC_CRTPREFIX="%s"' % musllib,
                '-DCONFIG_TCC_ELFINTERP="/musl/loader"',  # static; unused
                '-DCONFIG_TCC_SYSINCLUDEPATHS="%s"' % muslinc,
                '-DCONFIG_TCC_LIBPATHS="%s:%s"' % (musllib, tccdir),
                '-DTCC_LIBGCC="%s/libc.a"' % musllib,
                '-DTCC_LIBTCC1="libtcc1.a"',
                "-DCONFIG_TCCBOOT=1",
                "-DCONFIG_TCC_STATIC=1",
                "-DCONFIG_USE_LIBGCC=1",
                '-DTCC_VERSION="0.9.26"',
                "-DONE_SOURCE=1",
            ]

        def build_stage(cc, out):
            # Fully explicit static link against scaffold musl crt + libc.
            with working_dir(src):
                Executable(cc)(
                    "-g", "-static", "-nostdlib", "-nostdinc",
                    *defs(),
                    "-I", ".", "-I", muslinc,
                    "-o", out,
                    join_path(musllib, "crt1.o"),
                    join_path(musllib, "crti.o"),
                    "tcc.c",
                    join_path(musllib, "libc.a"),
                    libtcc1,
                    join_path(musllib, "crtn.o"),
                )
                chmod_x(join_path(src, out))
                Executable(join_path(src, out))("-version")
            return join_path(src, out)

        stage1 = build_stage(seed, "tcc-stage1")
        stage2 = build_stage(stage1, "tcc-stage2")
        stage3 = build_stage(stage2, "tcc-stage3")

        # Fixed-point criterion: stage2 == stage3 byte-for-byte.
        assert filecmp.cmp(stage2, stage3, shallow=False), (
            "tcc self-host did not reach a fixed point (stage2 != stage3)"
        )

        install(stage3, join_path(bindir, "tcc"))
        install(stage3, join_path(bindir, "tcc-0.9.26"))
        for f in ("tcc", "tcc-0.9.26"):
            chmod_x(join_path(bindir, f))

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
