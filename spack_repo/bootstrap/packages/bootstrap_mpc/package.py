# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapMpc(Package):
    """MPC 1.0.3, a GCC 4.7 prerequisite, built by tcc-musl on top of gmp + mpfr.

    Standalone companion to bootstrap-gmp/bootstrap-mpfr. No ``c`` virtual."""

    homepage = "https://www.multiprecision.org/"
    url = "https://ftpmirror.gnu.org/mpc/mpc-1.0.3.tar.gz"

    license("LGPL-3.0-or-later")

    version("1.0.3", sha256="617decc6ea09889fb08ede330917a00b16809b8db88c29c31bfbb49cbf88ecc3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-musl", type="build")
    depends_on("bootstrap-musl-scaffold", type="build")
    depends_on("bootstrap-binutils", type="build")
    depends_on("bootstrap-gmp", type="build")
    depends_on("bootstrap-mpfr", type="build")
    depends_on("bootstrap-gmake-mes", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake-mes"

    def setup_build_environment(self, env):
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def configure_args(self, spec, prefix):
        tcc = join_path(spec["bootstrap-tcc-musl"].prefix, "bin", "tcc")
        musllib = join_path(spec["bootstrap-musl-scaffold"].prefix, "lib")
        return [
            "CC=%s -L%s" % (tcc, musllib),
            "CFLAGS=-DHAVE_ALLOCA_H",
            "--build=x86_64-linux-musl",
            "--host=x86_64-linux-musl",
            "--prefix=" + prefix,
            "--with-gmp=" + str(spec["bootstrap-gmp"].prefix),
            "--with-mpfr=" + str(spec["bootstrap-mpfr"].prefix),
            "--enable-static",
            "--disable-shared",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        sh("configure", *self.configure_args(spec, prefix))
        make("-j1")
        make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
