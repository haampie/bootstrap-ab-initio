# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapGcc9(Package):
    """GCC 9.5.0, C + C++ -- an intermediate compiler built by gcc-stage1 (4.7.4).

    GCC 9 has mature C++17 support, so it can build the latest and future GCC
    releases, while still being old enough to build cleanly on musl (much cheaper
    to bootstrap than glibc). GCC 9 bootstraps with a C++98 host compiler (C++11 is
    required only from GCC 10.5/11), so gcc-stage1's 4.7.4 g++ builds it directly,
    in a single C+C++ step -- no stage0/stage1 doubling (that only ever existed to
    climb past tcc).

    This GCC is itself only scaffolding: its sole job is to build the next GCC, so
    it is kept minimal (C+C++ only, no Graphite/ISL, aggressive --disable-* of
    runtime libs). Its sysroot is the modern bootstrap-musl-12 (musl 1.2.5, minted
    by gcc-stage1); gmp/mpfr/mpc are built IN-TREE like bootstrap-gcc-stage1.
    No ``c`` virtual dependency."""

    homepage = "https://gcc.gnu.org/"
    url = "https://ftpmirror.gnu.org/gcc/gcc-9.5.0/gcc-9.5.0.tar.xz"

    license("GPL-3.0-or-later")

    version("9.5.0",
            sha256="27769f64ef1d4cd5e2be8682c0c93f9887983e6cfd1a927ce5a0a2915a95cf8f")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-stage1", type="build")  # host C+C++ compiler (4.7.4 g++)
    depends_on("bootstrap-musl-12", type=("build", "run"))  # modern sysroot libc (1.2.5)
    depends_on("bootstrap-binutils", type=("build", "run"))
    depends_on("bootstrap-gmake", type="build")
    depends_on("bootstrap-linux-headers", type="build")

    # gmp/mpfr/mpc built IN-TREE (GCC 9.5's download_prerequisites set): their
    # *sources* are unpacked into the GCC tree as gmp/ mpfr/ mpc/ and built as part
    # of this GCC, so configure auto-detects them and the version/link check is
    # sidestepped. ISL is deliberately omitted (Graphite only; --without-isl).
    resource(name="gmp", placement="gmp",
             url="https://ftpmirror.gnu.org/gmp/gmp-6.1.0.tar.bz2",
             sha256="498449a994efeba527885c10405993427995d3f86b8768d8cdf8d9dd7c6b73e8")
    resource(name="mpfr", placement="mpfr",
             url="https://ftpmirror.gnu.org/mpfr/mpfr-3.1.4.tar.bz2",
             sha256="d3103a80cdad2407ed581f3618c4bed04e0c92d1cf771a65ead662cc397f7775")
    resource(name="mpc", placement="mpc",
             url="https://ftpmirror.gnu.org/mpc/mpc-1.0.3.tar.gz",
             sha256="617decc6ea09889fb08ede330917a00b16809b8db88c29c31bfbb49cbf88ecc3")

    # No patches: GCC 9's libstdc++ already handles musl/__GLIBC_PREREQ, and the
    # 4.7-era alloca/strsignal/ctype fixes do not apply. Add reactively only.

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def configure_args(self, spec, prefix):
        gcc = join_path(spec["bootstrap-gcc-stage1"].prefix, "bin", "gcc")
        gxx = join_path(spec["bootstrap-gcc-stage1"].prefix, "bin", "g++")
        sysroot = spec["bootstrap-musl-12"].prefix
        return [
            "CC=" + gcc,
            "CXX=" + gxx,
            "CC_FOR_BUILD=" + gcc,
            "CXX_FOR_BUILD=" + gxx,
            "MAKEINFO=true",
            "--prefix=" + prefix,
            "--build=x86_64-unknown-linux-musl",
            "--host=x86_64-unknown-linux-musl",
            "--target=x86_64-unknown-linux-musl",
            "--with-sysroot=" + str(sysroot),
            "--with-native-system-header-dir=/include",
            # NO --with-gmp/--with-mpfr/--with-mpc: in-tree gmp/ mpfr/ mpc/ dirs
            # are auto-detected and built as part of GCC.
            "--without-isl",
            # Minimal: this GCC only has to build the next GCC.
            "--enable-languages=c,c++",
            "--enable-static",
            "--disable-shared",
            "--disable-bootstrap",
            "--disable-multilib",
            "--disable-libstdcxx-pch",
            "--disable-decimal-float",
            "--disable-lto",
            "--disable-lto-plugin",
            "--disable-plugin",
            "--disable-libatomic",
            "--disable-libcilkrts",
            "--disable-libgomp",
            "--disable-libitm",
            "--disable-libmudflap",
            "--disable-libquadmath",
            "--disable-libsanitizer",
            "--disable-libssp",
            "--disable-libvtv",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)
        # Let the in-tree mpfr.h (mpfr/src) be found while GCC compiles, before
        # the in-tree mpfr is installed into the build (mirrors bootstrap-gcc-stage1).
        os.environ["C_INCLUDE_PATH"] = os.pathsep.join(
            filter(None, [join_path(self.stage.source_path, "mpfr", "src"),
                          os.environ.get("C_INCLUDE_PATH", "")])
        )
        # gmp-6.1.0/mpfr-3.1.4/mpc-1.0.3 predate or borderline-support the `musl`
        # OS in their bundled config.sub; GCC 9.5's top-level pair knows it, so
        # overwrite the bundled ones to be safe (harmless if already current).
        src = self.stage.source_path
        for sub in ("gmp", "mpfr", "mpc"):
            for f in ("config.sub", "config.guess"):
                copy(join_path(src, f), join_path(src, sub, f))
        build = join_path(self.stage.source_path, "build")
        mkdirp(build)
        with working_dir(build):
            sh(join_path(self.stage.source_path, "configure"),
               *self.configure_args(spec, prefix))
            make()
            make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
