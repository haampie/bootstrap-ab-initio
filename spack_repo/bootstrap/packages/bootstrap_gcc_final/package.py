# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import glob
import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *

# ELF interpreter basename per arch (glibc installs the loader under lib/).
DYNAMIC_LINKER = {
    "x86_64": "ld-linux-x86-64.so.2",
    "aarch64": "ld-linux-aarch64.so.1",
}


class BootstrapGccFinal(Package):
    """Native x86_64 GCC 16.1.0 -- the final, shared compiler of the bootstrap.

    Built by gcc-boot0-wrapped against glibc-boot0 and binutils-final, with
    ``--enable-shared``: its libstdc++/libgcc_s are shared and its binaries link
    dynamically against glibc-boot0. After install a specs file is written into
    the GCC prefix so plain ``gcc``/``g++`` find glibc-boot0's startfiles,
    dynamic linker, and binutils-final's as/ld with no wrapper or env vars.

    The host compiler here is GCC 16 (gcc-boot0-wrapped), which makes
    implicit-function-declaration an error -- so the in-tree gmp build-compiler
    tests need a relax wrapper (``cc-relaxed.sh``), and the in-tree libstdc++
    build needs CPLUS_INCLUDE_PATH reset to just glibc (the external
    libstdcxx-boot1 shares include guards with the in-tree copy). make is
    bootstrap-gmake; ``find``/``diff``/``cmp`` from the host (sandbox). No ``c``
    virtual."""

    homepage = "https://gcc.gnu.org/"
    url = "https://ftpmirror.gnu.org/gcc/gcc-16.1.0/gcc-16.1.0.tar.xz"

    license("GPL-3.0-or-later")

    version("16.1.0", sha256="50efb4d94c3397aff3b0d61a5abd748b4dd31d9d3f2ab7be05b171d36a510f79")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-boot0-wrapped", type="build")
    depends_on("bootstrap-glibc-boot0", type=("build", "run"))
    depends_on("bootstrap-linux-headers", type="build")  # autoconf CPP sanity check
    depends_on("bootstrap-binutils-final", type=("build", "run"))
    depends_on("bootstrap-libstdcxx-boot1", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    # In-tree GMP/MPFR/MPC -- same sources as gcc-boot0 (GCC 16's set).
    resource(name="gmp", placement="gmp",
             url="https://ftpmirror.gnu.org/gmp/gmp-6.3.0.tar.bz2",
             sha256="ac28211a7cfb609bae2e2c8d6058d66c8fe96434f740cf6fe2e47b000d1c20cb",
             when="@16.1.0")
    resource(name="mpfr", placement="mpfr",
             url="https://ftpmirror.gnu.org/mpfr/mpfr-4.2.1.tar.bz2",
             sha256="b9df93635b20e4089c29623b19420c4ac848a1b29df1cfd59f26cab0d2666aa0",
             when="@16.1.0")
    resource(name="mpc", placement="mpc",
             url="https://ftpmirror.gnu.org/mpc/mpc-1.3.1.tar.gz",
             sha256="ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8",
             when="@16.1.0")

    def configure_flags(self, spec, prefix, cc):
        gcc = spec["bootstrap-gcc-boot0-wrapped"].prefix
        glibc = spec["bootstrap-glibc-boot0"].prefix
        libstdcxx = spec["bootstrap-libstdcxx-boot1"].prefix
        binutils = spec["bootstrap-binutils-final"].prefix
        triplet = "%s-linux-gnu" % spec.target.family
        return [
            "CONFIG_SHELL=/bin/sh",
            # CC is the relax-wrapper around gcc-boot0-wrapped's gcc (see
            # install): GCC 16 errors on implicit-function-declaration, which
            # breaks the in-tree gmp build-compiler tests (main(){exit(0);}).
            "CC={0}".format(cc),
            "CXX={0}/bin/g++".format(gcc),
            "MAKEINFO=true",
            # libstdcxx-boot1 (static libstdc++.a) for the build tools GCC
            # compiles (collect2 etc.); lib64 is the target libdir on both
            # x86_64 and aarch64 (lib kept as fallback).
            "LDFLAGS=-L{0}/lib64 -L{0}/lib".format(libstdcxx),
            "--build={0}".format(triplet),
            "--host={0}".format(triplet),
            "--target={0}".format(triplet),
            "--prefix={0}".format(prefix),
            "--with-native-system-header-dir={0}/include".format(glibc),
            # Use binutils-final's NATIVE as/ld and bake them into the
            # installed driver (complements the specs -B<binutils-final>).
            "--with-as={0}/bin/as".format(binutils),
            "--with-ld={0}/bin/ld".format(binutils),
            "--enable-shared",
            "--enable-languages=c,c++",
            "--enable-threads=posix",
            "--enable-__cxa_atexit",
            "--disable-bootstrap",
            "--disable-multilib",
            "--disable-werror",
            "--disable-nls",
            "--without-isl",
            "--without-zstd",
            "--disable-plugin",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        # In-tree gmp's AC_PROG_LEX fatally runs flex's output probe if flex is
        # on PATH; flex is only used by gmp demos, so skip the probe.
        os.environ["ac_cv_prog_lex_root"] = "lex.yy"

        # Strip the external libstdcxx-boot1 from CPLUS_INCLUDE_PATH for EVERY
        # libstdc++-v3 C++ compile (GCC 11+ regression bugzilla/100017). The
        # external libstdc++ headers
        # share include guards with the in-tree libstdc++ being built, so an
        # in-tree <fenv.h>'s #include_next would hit the boot1 wrapper and never
        # reach glibc's real <fenv.h>. Reset CPLUS_INCLUDE_PATH to just glibc;
        # --with-native-system-header-dir=glibc keeps libc/kernel headers
        # available (kernel headers are symlinked into glibc's include).
        glibc_include = spec["bootstrap-glibc-boot0"].prefix.include
        cpath_reset = "CPLUS_INCLUDE_PATH = {0}\nexport CPLUS_INCLUDE_PATH\n".format(
            glibc_include
        )
        for makefile in find("libstdc++-v3", "Makefile.in", recursive=True):
            filter_file(r"AM_CXXFLAGS = ", cpath_reset + "AM_CXXFLAGS = ", makefile)
        # The precompiled-header rules use PCHFLAGS, not AM_CXXFLAGS. Anchor with
        # ^ so the literal-line match excludes "glibcxx_PCHFLAGS = ".
        filter_file(
            r"^PCHFLAGS = ",
            cpath_reset + "PCHFLAGS = ",
            join_path("libstdc++-v3", "include", "Makefile.in"),
        )

        # Relax GCC 16's implicit-function-declaration error for the build/host
        # compiler: the in-tree gmp's configure tests compile with no CFLAGS and
        # would otherwise fail.
        real_cc = join_path(spec["bootstrap-gcc-boot0-wrapped"].prefix.bin, "gcc")
        cc_wrap = os.path.abspath("cc-relaxed.sh")
        with open(cc_wrap, "w") as f:
            f.write(
                "#!/bin/sh\n"
                'exec {0} "$@" -Wno-error=implicit-function-declaration\n'.format(real_cc)
            )
        os.chmod(cc_wrap, os.stat(cc_wrap).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        mkdirp("build")
        with working_dir("build"):
            sh("../configure", *self.configure_flags(spec, prefix, cc_wrap))
            make()
            make("install")

    @run_after("install")
    def write_specs_file(self):
        """Write a specs file into the installed GCC prefix so that plain
        gcc/g++ find glibc-boot0's startfiles + dynamic linker and use
        binutils-final's as/ld -- no wrapper scripts or env vars."""
        spec = self.spec
        prefix = self.prefix
        glibc = spec["bootstrap-glibc-boot0"].prefix
        binutils = spec["bootstrap-binutils-final"].prefix
        triplet = "%s-linux-gnu" % spec.target.family
        ld_so = DYNAMIC_LINKER[str(spec.target.family)]

        # Find which directory holds the GCC runtime shared libraries.
        for dir in ["lib64", "lib"]:
            libdir = join_path(prefix, dir)
            if glob.glob(join_path(libdir, "libgcc_s.*")):
                rpath_dir = libdir
                break
        else:
            raise InstallError("No libgcc_s.* found in lib/lib64")

        # Seed the specs file with the FULL built-in spec set (gcc -dumpspecs)
        # so the *cc1_cpu section (-march=native autodetection) is present; a
        # partial prefix specs file silently disables native detection.
        gcc_exe = Executable(join_path(prefix.bin, "gcc"))
        builtin_specs = gcc_exe("-dumpspecs", output=str)

        specs_dir = join_path(prefix.lib, "gcc", triplet, str(spec.version))
        mkdirp(specs_dir)
        with open(join_path(specs_dir, "specs"), "w") as f:
            # Exactly ONE blank line before the comment: GCC's specs parser
            # treats a double blank line before a '#' comment as malformed.
            f.write(builtin_specs.rstrip("\n"))
            f.write("\n\n# Generated by Spack: glibc-boot0 loader/startfiles + binutils-final\n\n")
            f.write(f"*startfile_prefix_spec:\n{glibc}/lib/\n\n")
            f.write(
                f"*link:\n"
                f"+ %{{!static:%{{!static-pie:"
                f"--dynamic-linker {glibc}/lib/{ld_so}}}}}\n\n"
            )
            f.write(
                f"*link_libgcc:\n"
                f"+ -rpath {glibc}/lib -L{rpath_dir} -rpath {rpath_dir}\n\n"
            )
            f.write(f"*self_spec:\n+ -B{binutils}/bin/\n")

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
