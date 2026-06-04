# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapM4(Package):
    """GNU M4 1.4.19 built by bootstrap-gcc-9 (static musl), for bootstrap-bison
    and bootstrap-glibc-boot0.

    M4 is bison's skeleton macro processor -- bison invokes m4 at run time to
    expand its skeleton files, and glibc's build pulls in bison. The new x86_64
    cap builds its own m4 (rather than borrowing the host's) so the toolchain
    that mints glibc is full-source.

    Native x86_64 build (the predecessor gcc-9.5 is already native; no i686
    cross), so unlike the old i686 ``m4-boot0`` there is no ``-g0`` DWARF dance
    and the triple is the musl triple gcc-9 emits. make is bootstrap-gmake
    (jobserver-capable -> parallel; no MAKEFLAGS clearing). No ``c`` virtual:
    the compiler is wired explicitly to bootstrap-gcc-9.

    Ported from ``m4-boot0`` (Guix ``gnu/packages/commencement.scm`` m4-boot0)."""

    homepage = "https://www.gnu.org/software/m4/"
    url = "https://ftpmirror.gnu.org/m4/m4-1.4.19.tar.bz2"

    license("GPL-3.0-or-later")

    version("1.4.19", sha256="b306a91c0fd93bc4280cfc2e98cb7ab3981ff75a187bea3293811f452c89a8c8")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-9", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

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
        )

        make()
        make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
