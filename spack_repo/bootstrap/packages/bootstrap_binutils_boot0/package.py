# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapBinutilsBoot0(Package):
    """Binutils 2.46 (native as/ld/ar) built by bootstrap-gcc-9.

    The whole glibc cap is a plain native build (build == host == target ==
    the host GNU triplet, x86_64-linux-gnu | aarch64-linux-gnu; the predecessor
    gcc-9.5 is already native, no i686 cross).

    First stage of the glibc cap on top of the musl full-source bootstrap.
    Unlike the old i686 ``binutils-boot0`` -- a cross (i686 host, x86_64 target)
    because *its* predecessor was i686 -- this is a plain native build: gcc-9.5
    already runs and emits x86_64. gcc-boot0 (GCC 16, ``--without-headers``) uses
    these tools to assemble/link the first glibc.

    Built **static** (``--disable-shared``): the predecessor toolchain only has
    static musl, so there is no shared libc to link a shared libbfd against.
    make is bootstrap-gmake (jobserver-capable; no MAKEFLAGS clearing). No ``c``
    virtual: compiler wired explicitly to bootstrap-gcc-9."""

    homepage = "https://www.gnu.org/software/binutils/"
    url = "https://ftpmirror.gnu.org/binutils/binutils-2.46.tar.bz2"

    license("GPL-3.0-or-later")

    version("2.46.0", sha256="0f3152632a2a9ce066f20963e9bb40af7cf85b9b6c409ed892fd0676e84ecd12")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-9", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # No host flex in the sandbox; binutils 2.46 SHIPS its generated parsers
        # (maintainer-mode off), so the only obstacle is AC_PROG_LEX fatally
        # running $LEX. Preseeding ac_cv_prog_lex_root short-circuits every
        # configure (top + recursive) and sets LEX_OUTPUT_ROOT=lex.yy in the
        # Makefiles. See the bootstrap-binutils-no-host-flex memory.
        env.set("ac_cv_prog_lex_root", "lex.yy")

    def configure_args(self, spec, prefix):
        gcc = spec["bootstrap-gcc-9"].prefix
        triplet = "%s-linux-gnu" % spec.target.family
        return [
            "CONFIG_SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "CXX={0}/bin/g++".format(gcc),
            "MAKEINFO=true",
            # binutils' TOP-LEVEL constructs its host build tools as
            # ``${host_alias}-ar`` etc. (NOT a plain AC_CHECK_TOOL with fallback),
            # so with --host=x86_64-linux-gnu it tries x86_64-linux-gnu-ar and
            # configure-libsframe dies ("could not determine ...-ar interface").
            # The host binutils on PATH (bootstrap-binutils 2.30, used by gcc-9)
            # only installs PLAIN names, so set the host tools explicitly. (gcc-9
            # links via its baked specs, independent of these.)
            "AR=ar",
            "AS=as",
            "NM=nm",
            "RANLIB=ranlib",
            "OBJCOPY=objcopy",
            "OBJDUMP=objdump",
            "READELF=readelf",
            "STRIP=strip",
            "--build={0}".format(triplet),
            "--host={0}".format(triplet),
            "--target={0}".format(triplet),
            "--with-sysroot=/",
            "--prefix={0}".format(prefix),
            "--enable-install-libbfd",
            "--enable-deterministic-archives",
            "--enable-64-bit-bfd",
            # Static toolchain: gcc-9 only has static musl, no shared libc for a
            # shared libbfd/libopcodes to link against.
            "--enable-static",
            "--disable-shared",
            # gprofng needs bison + a C++ libstdc++ we don't have yet; not needed
            # by glibc. (binutils-final re-enables what's wanted.)
            "--disable-gprofng",
            "--disable-nls",
            "--disable-werror",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        sh("./configure", *self.configure_args(spec, prefix))
        make()
        make("install")
        self._add_triplet_symlinks(prefix, "%s-linux-gnu" % spec.target.family)

    def _add_triplet_symlinks(self, prefix, triplet):
        # A NATIVE build (build==host==target) installs only PLAIN tool names
        # (``ar``, ``as``, ``ld``, ...). But every downstream configure that
        # passes --host=<triplet> makes AC_CHECK_TOOL look for the
        # <triplet>-PREFIXED name first -- and the only one on PATH with
        # that prefix is the landlock-BLOCKED host /usr/bin/<triplet>-ar
        # (Ubuntu's multiarch binutils shares our target triplet), causing
        # "Permission denied". So add <triplet>-<tool> symlinks pointing
        # at our plain tools; PATH-prepended, they shadow the host's and make
        # the prefixed lookup resolve to us (gcc-boot0/glibc/libstdcxx/gcc-final).
        triplet_prefix = "{0}-".format(triplet)
        bindir = prefix.bin
        for name in os.listdir(bindir):
            if name.startswith(triplet_prefix):
                continue
            dst = join_path(bindir, "{0}{1}".format(triplet_prefix, name))
            if not os.path.lexists(dst):
                os.symlink(name, dst)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
