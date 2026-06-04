# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapLinuxHeaders(Package):
    """Linux x86_64 kernel uapi headers, built via ``make headers``.

    musl needs the kernel uapi headers (asm/, asm-generic/, linux/, ...). The
    new chain has no kernel-header seed for the x86_64 cap, so we sanitize them
    from a pristine kernel tarball with ``make headers`` -- a copy+sed+unifdef
    pass, no kernel compile. Output lands in ``usr/include`` and we copy the
    ``*.h`` into prefix.

    HOSTCC is **bootstrap-gcc-stage0** (a real GCC). ``make headers`` compiles a
    couple of host tools (``scripts/basic/fixdep``, ``scripts/unifdef``); an
    earlier version drove the seed tcc (tcc-mes) through a cc-wrapper, but
    mes-libc's broken ``strerror``/file-I/O makes ``fixdep`` die
    (``error opening file: sterror: unknown error``). The only consumers of these
    headers are bootstrap-musl (pristine) and bootstrap-gcc-stage1, both built
    *after* gcc-stage0, so depending on gcc-stage0 introduces no cycle (gcc-stage0
    itself uses the prebuilt bootstrap-linux-headers-seed, not this package).
    gcc-stage0 carries its binutils as a run dep, so ``as``/``ld`` are on PATH,
    and it links its musl-boot sysroot automatically -- no wrapper needed.
    make = bootstrap-gmake (musl-linked, handles the jobserver). No ``c`` virtual.
    """

    homepage = "https://www.kernel.org/"
    url = "https://www.kernel.org/pub/linux/kernel/v6.x/linux-6.9.1.tar.xz"

    license("GPL-2.0-only")

    version("6.9.1", sha256="01b414ba98fd189ecd544435caf3860ae2a790e3ec48f5aa70fdf42dc4c5c04a")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-stage0", type="build")
    depends_on("bootstrap-gmake", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake"

    def url_for_version(self, version):
        return "https://www.kernel.org/pub/linux/kernel/v{0}.x/linux-{1}.tar.xz".format(
            version.up_to(1), version
        )

    def install(self, spec, prefix):
        gcc = join_path(spec["bootstrap-gcc-stage0"].prefix, "bin", "gcc")
        make = Executable(spec[self.make_provider].prefix.bin.make)

        # headers_install.sh strips __force/__user, #ifdef __KERNEL__ (via
        # scripts/unifdef, a HOSTCC-built tool), #include <linux/compiler*>.
        # Result populates usr/include/. ARCH=x86_64 selects asm/. No .config
        # needed; Spack always unpacks a fresh tree (no `make mrproper`).
        #
        # The kernel builds its host tools (fixdep/unifdef) at -O2. gcc-stage0's
        # cc1 (built by tcc-musl) miscompiles -O1/-O2 code via a broken tree-ccp
        # pass (a miscompiled fixdep spins forever), but gcc-stage0 ships a specs
        # file that disables tree-ccp for everything it compiles, so HOSTCC just
        # works here -- no per-build flag needed. See bootstrap-gcc-stage0.
        #
        # Linux's ARCH= uses its own arch names: aarch64 -> arm64 (selects the
        # arm64 asm/ uapi); x86_64 stays x86_64.
        karch = "arm64" if spec.target.family == "aarch64" else "x86_64"
        make("headers", "ARCH=" + karch, "HOSTCC=" + gcc)

        # Install usr/include/**.h into <prefix>/include.
        for dirpath, _dirs, files in os.walk("usr/include"):
            for fname in files:
                if not fname.endswith(".h"):
                    continue
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, "usr/include")
                dst = os.path.join(str(prefix.include), rel)
                mkdirp(os.path.dirname(dst))
                shutil.copy2(src, dst)

        mkdirp(str(prefix.include.config))
        with open(os.path.join(str(prefix.include.config), "kernel.release"), "w") as f:
            f.write("{0}-default\n".format(spec.version))

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.append_path("CPLUS_INCLUDE_PATH", self.prefix.include)
