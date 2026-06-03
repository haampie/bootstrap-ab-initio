# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGmake(Package):
    """GNU Make 4.4.1 linked against (scaffold) musl, built by bootstrap-tcc-musl.

    The jobserver-capable make for the heavy downstream stages. Unlike
    bootstrap-gmake-mes -- which links the seed MES libc whose ``sigaction`` is
    a no-op stub (``return 0``, no syscall), so make never installs its SIGCHLD
    handler and DEADLOCKS under any jobserver (blocking jobserver ``read()``
    never EINTR'd by a finished child) -- this make links real musl: its
    ``sigaction`` issues ``rt_sigaction`` with the x86_64 SA_RESTORER
    trampoline and the handler actually runs (verified). It can therefore use
    Spack's FIFO jobserver and build later stages in parallel; gmake-mes stays
    serial. See TODO.md and the ``bootstrap-gmake-mes-jobserver-j1`` memory.

    Same build as bootstrap-gmake-mes (configure + bundled ``./build.sh`` -- no
    make-to-build-make), retargeted from tcc-mes/mes-libc to tcc-musl/scaffold
    musl. musl is a complete libc, so none of the reference's mes-compat shims
    (steps/08-gmake-4.4.1/mes-compat.*) are needed. No ``c`` virtual dependency:
    the compiler is wired explicitly to tcc-musl."""

    homepage = "https://www.gnu.org/software/make/"
    url = "https://ftpmirror.gnu.org/make/make-4.4.1.tar.gz"

    license("GPL-3.0-or-later")

    version("4.4.1", sha256="dd16fb1d67bfab79a72f5e8390735c49e3e8e70b4945a15ab1f81ddb78658fb3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-musl", type="build")
    depends_on("bootstrap-musl-boot", type="build")

    def install(self, spec, prefix):
        tcc = join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")

        # Bare tcc-musl as CC -- no cc-wrapper. tcc-musl bakes scaffold musl's
        # crt/libc/headers into its CONFIG_* (CRTPREFIX/LIBPATHS/SYSINCLUDEPATHS),
        # so it links and finds headers self-contained. Crucially musl headers
        # are *system* includes (searched AFTER -I), so gnulib's own -Ilib
        # replacements (glob.h's __GLOB_FLAGS, ...) win over musl's -- a wrapper
        # that injected `-I<muslinc>` first would shadow them and break the build.
        sh = Executable("/bin/sh")
        sh(
            "configure",
            "CONFIG_SHELL=/bin/sh",
            "SHELL=/bin/sh",
            "CC=" + tcc,
            # build.sh path: no make yet to bootstrap depfile fragments.
            "--disable-dependency-tracking",
            "--disable-nls",
            "--without-guile",
            "--disable-load",
            "--prefix=" + prefix,
        )

        # configure hardcodes AR='ar' (host binutils) in build.cfg; reroute it
        # through tcc-musl's own archiver.
        filter_file(r"^AR='ar'", "AR='%s -ar'" % tcc, "build.cfg")

        # Build make with its bootstrap shell script (shell + CC, no make).
        sh("./build.sh")

        make = Executable(join_path(self.stage.source_path, "make"))
        make("--version")
        # Confirm the fifo jobserver compiled in (the whole point of this make).
        out = make("-p", "-f", "/dev/null", output=str, error=os.devnull, fail_on_error=False)
        assert "jobserver" in out, "fifo jobserver not compiled into make"

        mkdirp(prefix.bin)
        install("make", prefix.bin)
        # version-sniffing configure scripts often look for "gmake" first.
        symlink("make", join_path(prefix.bin, "gmake"))
