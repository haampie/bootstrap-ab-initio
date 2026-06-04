# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapLibstdcxxBoot1(Package):
    """Intermediate x86_64 libstdc++ (static-only) from GCC 16 source.

    gcc-boot0 was built ``--disable-libstdc++-v3``, so there is no GCC-16
    libstdc++ yet -- but binutils-final (gprofng) and gcc-final's build tools
    need to link one. This stage builds a native static ``libstdc++.a`` with
    gcc-boot0-wrapped against glibc-boot0. ``--disable-shared`` so downstream
    binaries link it statically (no runtime libstdc++.so dependency).

    make is bootstrap-gmake. ``find``/``diff`` come from the host (sandbox
    allow_read): libtool merges the libsupc++/c++NN convenience archives into
    libstdc++.a by extracting them and enumerating objects with ``find`` --
    without a real find, libstdc++.a ships only the 8 compatibility*.o and every
    downstream C++ link breaks. No ``c`` virtual. Mirrors Guix ``libstdc++``
    (make-libstdc++ gcc-boot0, boot2 stage) / the old ``libstdcxx-boot1``."""

    homepage = "https://gcc.gnu.org/"
    url = "https://ftpmirror.gnu.org/gcc/gcc-16.1.0/gcc-16.1.0.tar.xz"

    license("GPL-3.0-or-later")

    version("16.1.0", sha256="50efb4d94c3397aff3b0d61a5abd748b4dd31d9d3f2ab7be05b171d36a510f79")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-boot0-wrapped", type="build")
    depends_on("bootstrap-glibc-boot0", type=("build", "run"))
    depends_on("bootstrap-linux-headers", type="build")  # autoconf CPP sanity check
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def configure_flags(self, spec, prefix):
        gcc = spec["bootstrap-gcc-boot0-wrapped"].prefix
        triplet = "%s-linux-gnu" % spec.target.family
        return [
            "CONFIG_SHELL=/bin/sh",
            "CC={0}/bin/gcc".format(gcc),
            "CXX={0}/bin/g++".format(gcc),
            "MAKEINFO=true",
            "--build={0}".format(triplet),
            "--host={0}".format(triplet),
            "--prefix={0}".format(prefix),
            "--disable-multilib",
            "--disable-nls",
            "--disable-shared",
            "--disable-libstdcxx-pch",
            # NOTE: unlike the GCC-14 reference we do NOT pass
            # --disable-libstdcxx-threads / --disable-libstdcxx-dual-abi. glibc-boot0
            # is full glibc 2.43 (real pthreads, cxx11 ABI), and GCC 16's C++20
            # src/c++20/tzdb.cc requires both: with the cxx11 ABI off, <chrono>'s
            # tzdb struct omits its `zones`/`links` members but tzdb.cc still
            # references them ("tzdb has no member named 'zones'"). Defaults
            # (threads on, dual-abi on) build a normal static libstdc++.a.
            "--with-gxx-include-dir={0}/include".format(prefix),
        ]

    def install(self, spec, prefix):
        sh = Executable("/bin/sh")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        # libstdc++-v3 configure probes ``g++ -v``; make it a no-op so the
        # probe cannot fail when the compiler binary name differs.
        filter_file(r"g\+\+ -v", "true", join_path("libstdc++-v3", "configure"))

        mkdirp("build")
        with working_dir("build"):
            sh("../libstdc++-v3/configure", *self.configure_flags(spec, prefix))
            make()
            make("install")

    def setup_dependent_build_environment(self, env, dependent_spec):
        # libstdc++.a installs into lib64 (GCC's x86_64 target libdir), and lib.
        env.prepend_path("LIBRARY_PATH", join_path(self.prefix, "lib64"))
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
        # C++ headers; prepend so they precede glibc/kernel headers (which their
        # providers append) -- libstdc++'s <cstdlib> #include_next <stdlib.h>
        # must reach glibc's copy. bits/c++config.h lives in an arch subdir.
        env.prepend_path("CPLUS_INCLUDE_PATH", self.prefix.include)
        triplet = "%s-linux-gnu" % self.spec.target.family
        env.prepend_path(
            "CPLUS_INCLUDE_PATH", join_path(self.prefix.include, triplet)
        )
