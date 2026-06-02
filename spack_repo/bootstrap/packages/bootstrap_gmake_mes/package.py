# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGmakeMes(Package):
    """GNU Make 4.4.1, built by the seed tcc (tcc-mes) against mes libc.

    First non-tcc brick of the new bootstrap chain and a prerequisite for musl
    (whose build is driven by make). 4.4 (not 4.2.x) is required for the
    named-pipe **fifo jobserver** (``--jobserver-style=fifo``).

    It depends on nothing but ``tcc-mes`` (the seed tcc 0.9.26 + mes libc). We
    build it the way GNU make bootstraps itself with no pre-existing make: run
    ``./configure`` (which wires gnulib replacements for the functions mes libc
    lacks) and then make's bundled ``./build.sh`` (compiles make with just the
    shell + CC). The compiler is the seed tcc, driven through a small ``mes-tcc``
    cc-wrapper that spells out the mes crt/lib locations -- ported from
    ``MES-replacement/steps/08-gmake-4.4.1/``.

    No ``c`` virtual dependency: the compiler is wired explicitly to tcc-mes."""

    homepage = "https://www.gnu.org/software/make/"
    url = "https://ftpmirror.gnu.org/make/make-4.4.1.tar.gz"

    license("GPL-3.0-or-later")

    version("4.4.1", sha256="dd16fb1d67bfab79a72f5e8390735c49e3e8e70b4945a15ab1f81ddb78658fb3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-mes", type="build")

    def setup_build_environment(self, env):
        # build.sh doesn't use a jobserver; clear Spack's inherited flags.
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def install(self, spec, prefix):
        tcc = spec["bootstrap-tcc-mes"].prefix
        libmes = join_path(tcc, "lib", "mes")
        incmes = join_path(tcc, "include", "mes")

        # cc-wrapper: drive the seed tcc as an ordinary "cc". On a link tcc's
        # mes target needs the crt/libc spelled out under -nostdlib; on -c/-E/-S
        # just add the mes include/lib dirs. (Ported from steps/08-gmake-4.4.1/
        # mes-tcc, with tcc-mes's prefix baked in.)
        mes_tcc = join_path(self.stage.source_path, "mes-tcc")
        with open(mes_tcc, "w") as f:
            f.write(
                "#!/bin/sh\n"
                'TCC="%s/bin/tcc"\n' % tcc
                + 'M="%s"\n' % libmes
                + 'INC="%s"\n' % incmes
                + "link=1\n"
                'for a in "$@"; do case "$a" in -c|-E|-S) link=0;; esac; done\n'
                'if [ "$link" -eq 1 ]; then\n'
                '  exec "$TCC" -I"$INC" -L"$M" -B"$M/tcc" -nostdlib '
                '"$M/crt1.o" "$M/crti.o" "$@" -lc "$M/tcc/libtcc1.a" "$M/crtn.o"\n'
                "else\n"
                '  exec "$TCC" -I"$INC" -L"$M" -B"$M/tcc" "$@"\n'
                "fi\n"
            )
        os.chmod(mes_tcc, os.stat(mes_tcc).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        sh = Executable("/bin/sh")
        sh(
            "configure",
            "CONFIG_SHELL=/bin/sh",
            "SHELL=/bin/sh",
            "CC=" + mes_tcc,
            # No make yet -> config.status can't bootstrap depfile fragments.
            "--disable-dependency-tracking",
            "--disable-nls",
            "--without-guile",
            "--disable-load",
            "--prefix=" + prefix,
        )

        # configure hardcodes AR='ar' (host binutils) in build.cfg; reroute it
        # through tcc's own archiver so no host `ar` is needed. Raw tcc -- not
        # the mes-tcc wrapper, which would inject crt/libc and corrupt the
        # archive. ARFLAGS stays 'cr', matching `tcc -ar cr`.
        filter_file(r"^AR='ar'", "AR='%s/bin/tcc -ar'" % tcc, "build.cfg")

        # No make yet: build make with its bootstrap shell script (shell + CC).
        sh("./build.sh")

        make = Executable(join_path(self.stage.source_path, "make"))
        make("--version")

        mkdirp(prefix.bin)
        install("make", prefix.bin)
        # version-sniffing configure scripts often look for "gmake" first.
        symlink("make", join_path(prefix.bin, "gmake"))

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
