# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapBinutilsFinal(Package):
    """Native x86_64 binutils 2.46 -- the first glibc-linked binutils.

    Built by gcc-boot0-wrapped against glibc-boot0. gprofng is built by linking
    the static libstdcxx-boot1 via LDFLAGS. make is bootstrap-gmake.
    ``diff``/``cmp`` come from the host (sandbox). No ``c`` virtual."""

    homepage = "https://www.gnu.org/software/binutils/"
    url = "https://ftpmirror.gnu.org/binutils/binutils-2.46.tar.bz2"

    license("GPL-3.0-or-later")

    version("2.46.0", sha256="0f3152632a2a9ce066f20963e9bb40af7cf85b9b6c409ed892fd0676e84ecd12")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-boot0-wrapped", type="build")
    depends_on("bootstrap-glibc-boot0", type=("build", "run"))
    depends_on("bootstrap-linux-headers", type="build")  # autoconf CPP sanity check
    depends_on("bootstrap-libstdcxx-boot1", type="build")  # for gprofng
    depends_on("bootstrap-bison", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def setup_build_environment(self, env):
        # No host flex; binutils ships its generated parsers (maintainer-mode
        # off). Preseed ac_cv_prog_lex_root so AC_PROG_LEX short-circuits.
        env.set("ac_cv_prog_lex_root", "lex.yy")

    def configure_flags(self, spec, prefix):
        gcc = spec["bootstrap-gcc-boot0-wrapped"].prefix
        libstdcxx = spec["bootstrap-libstdcxx-boot1"].prefix
        triplet = "%s-linux-gnu" % spec.target.family
        return [
            "CONFIG_SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "CXX={0}/bin/g++".format(gcc),
            "MAKEINFO=true",
            # libstdc++.a lands in lib64 (GCC's x86_64 target libdir); explicit
            # -L so gprofng's g++ link finds -lstdc++.
            "LDFLAGS=-L{0}/lib64 -L{0}/lib".format(libstdcxx),
            # See binutils-boot0: the top-level builds ``${host_alias}-ar`` etc.,
            # so set the host tools explicitly (binutils-boot0 on PATH installs
            # only plain names).
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
            "--prefix={0}".format(prefix),
            "--disable-multilib",
            "--disable-werror",
            "--disable-nls",
            "--enable-deterministic-archives",
            "--enable-64-bit-bfd",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        mkdirp("build")
        with working_dir("build"):
            sh("../configure", *self.configure_flags(spec, prefix))
            make()
            make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
