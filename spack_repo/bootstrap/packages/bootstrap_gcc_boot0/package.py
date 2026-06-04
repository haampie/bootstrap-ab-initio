# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *

X86_64_TRIPLET = "x86_64-linux-gnu"


class BootstrapGccBoot0(Package):
    """GCC 16 'crippled' C/C++ compiler (``--without-headers``), built by gcc-9.5.

    The first half of the musl->glibc transition. gcc-9.5 is a native x86_64
    compiler but linked against *static musl*; install prefixes are immutable,
    so we cannot grow glibc in place. Instead we build a GCC 16 that knows no
    target libc at all (``--without-headers --disable-shared
    --disable-libstdc++-v3``) -- just enough cc1/libgcc to compile glibc 2.43.
    A later ``bootstrap-gcc-boot0-wrapped`` injects glibc's loader/startfiles,
    and ``bootstrap-gcc-final`` is the real shared compiler.

    Unlike the old i686 ``gcc-boot0`` this is NOT a cross: build==host==target
    ==x86_64-linux-gnu. Differences from that reference:

    * ``--disable-libcc1`` instead of borrowing a separate shared libstdc++:
      gcc-9 only has *static* musl, so a shared libcc1.so (which needs
      libstdc++.so) cannot be built. libcc1 is only gdb integration.
    * NO ``--with-static-standard-libraries=no``: here we WANT the build/host
      tools (cc1plus, gen*) to link gcc-9's *static* libstdc++.a -- there is no
      shared libstdc++ in the musl world.
    * No ``-g0`` (the predecessor's binutils is modern, not 2.20.1a).

    gmp/mpfr/mpc are built IN-TREE (compiled by gcc-9, which warns rather than
    errors on implicit-function-declaration, so no relax wrapper is needed --
    unlike gcc-final, whose host compiler is GCC 16). make is bootstrap-gmake.
    No ``c`` virtual. Ported from ``gcc-boot0`` (Guix ``gcc-cross-boot0``)."""

    homepage = "https://gcc.gnu.org/"
    url = "https://ftpmirror.gnu.org/gcc/gcc-16.1.0/gcc-16.1.0.tar.xz"

    license("GPL-3.0-or-later")

    version("16.1.0", sha256="50efb4d94c3397aff3b0d61a5abd748b4dd31d9d3f2ab7be05b171d36a510f79")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-9", type="build")
    depends_on("bootstrap-binutils-boot0", type=("build", "run"))
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    # In-tree GMP/MPFR/MPC (GCC 16's contrib/download_prerequisites set). The
    # ./gmp ./mpfr ./mpc layout makes GCC configure build them as part of itself.
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

    def configure_flags(self, spec, prefix):
        gcc = spec["bootstrap-gcc-9"].prefix
        return [
            "CONFIG_SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "CXX={0}/bin/g++".format(gcc),
            "MAKEINFO=true",
            "--prefix={0}".format(prefix),
            "--build={0}".format(X86_64_TRIPLET),
            "--host={0}".format(X86_64_TRIPLET),
            "--target={0}".format(X86_64_TRIPLET),
            # No target libc yet: just enough to compile glibc. No --with-sysroot
            # (a sysroot is where the TARGET libc's usr/include lives; we have
            # none). The old reference gcc-boot0 was a CROSS, where GCC auto-sets
            # inhibit_libc and routes the system-header dir to its internal
            # sys-include. We are NATIVE (host==target), so GCC does neither and
            # would search the host /usr/include -- landlock-blocked -> fatal on
            # GCC's <stdc-predef.h> preinclude, and fixincludes would scan it.
            # Replicate the cross behavior with three stock knobs (no host header
            # is ever read; matches a pure Guix/Nix env where /usr/include is
            # simply absent): force inhibit_libc=true (env), disable fixincludes,
            # and point the system-header dir at the conventional non-existent
            # ``/nonexistent`` sentinel (never created; clearly not a real path,
            # unlike ``/include``). With inhibit_libc + --without-headers the dir
            # is never actually consulted.
            "--without-headers",
            "--disable-fixincludes",
            "--with-native-system-header-dir=/nonexistent",
            "--disable-shared",
            "--enable-languages=c,c++",
            "--disable-libstdc++-v3",
            # gcc-9 has only static musl -> no shared libstdc++.so for a shared
            # libcc1.so. libcc1 is gdb-only; disable it entirely.
            "--disable-libcc1",
            # lto-plugin is ALWAYS built shared (liblto_plugin.so), but static
            # musl's libc.a holds non-PIC objects, so ``gcc -shared`` fails
            # ("R_X86_64_32S can not be used when making a shared object").
            # The crippled compiler doesn't need LTO; disable it (as gcc-9 does).
            "--disable-lto",
            "--disable-lto-plugin",
            "--without-isl",
            "--disable-bootstrap",
            "--disable-multilib",
            "--disable-decimal-float",
            "--disable-threads",
            "--disable-libatomic",
            "--disable-libgomp",
            "--disable-libitm",
            "--disable-libsanitizer",
            "--disable-libvtv",
            "--disable-libssp",
            "--disable-libquadmath",
            "--disable-nls",
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        # In-tree gmp's AC_PROG_LEX fatally runs flex's output probe if flex is
        # on PATH; flex is only used by gmp demos, so skip the probe.
        os.environ["ac_cv_prog_lex_root"] = "lex.yy"
        # Force inhibit_libc (GCC honors a pre-set value: ``: ${inhibit_libc=false}``).
        # A native --without-headers build would otherwise leave it false and try
        # to use a target libc; true makes libgcc build the minimal no-libc set,
        # exactly like the cross reference, so the absent /include is never needed.
        os.environ["inhibit_libc"] = "true"
        # Overwrite the bundled config.sub/guess in gmp/mpfr/mpc with GCC 16's
        # current pair (knows musl/gnu); harmless if already current.
        src = self.stage.source_path
        for sub in ("gmp", "mpfr", "mpc"):
            for f in ("config.sub", "config.guess"):
                copy(join_path(src, f), join_path(src, sub, f))

        mkdirp("build")
        with working_dir("build"):
            sh("../configure", *self.configure_flags(spec, prefix))
            make("-j{0}".format(make_jobs))
            make("install")

        # glibc links against libgcc_eh; provide it (Guix symlink-libgcc_eh).
        gcc_lib = join_path(prefix.lib, "gcc", X86_64_TRIPLET, str(spec.version))
        libgcc = join_path(gcc_lib, "libgcc.a")
        libgcc_eh = join_path(gcc_lib, "libgcc_eh.a")
        if os.path.exists(libgcc) and not os.path.lexists(libgcc_eh):
            os.symlink("libgcc.a", libgcc_eh)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
