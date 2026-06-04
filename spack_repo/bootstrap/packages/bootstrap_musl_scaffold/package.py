# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapMuslScaffold(Package):
    """musl 1.1.24, the throwaway scaffold libc, built by the seed tcc (tcc-mes).

    This is the *scaffold* musl: good enough to build the rest of the chain, but
    its floating-point formatting is wrong (the seed tcc's out-of-line va_arg
    only classifies GP, so printf %f won't round-trip). It is discarded once
    bootstrap-gcc-stage0 rebuilds a *pristine* musl (the bootstrap-musl package).

    Built with bare tcc-mes as ``CC`` (``CC="${TCC}"`` -- no cc-wrapper).
    tcc-mes bakes its own crt/libc/libtcc1
    search paths in (CONFIG_TCC_CRTPREFIX/LIBPATHS), and musl compiles with
    ``-nostdinc`` shipping its own freestanding headers, so the seed needs no
    ``-I``/``-B`` help; configure is cross-aware (``--target``) so its link
    test never executes (no ``/mes/loader`` needed at build time). make from
    bootstrap-gmake-mes; kernel uapi headers from the prebuilt
    bootstrap-linux-headers-seed. No ``c`` virtual dependency.

    Shared patches have no arch condition; arch-specific patches use
    ``when="target=<arch>:"``.

    Shared (both architectures):
      0001 EMPTY_LIB_NAMES += g   (tcc emits -lg at link; musl ships no libg.a)
      0004 remove crt/rcrt1.c     (static-PIE startup, unused with --disable-shared)
      0006 strip C99 [static N]   (tcc rejects ``T buf[static N]`` declarators)
      0020 EMPTY_LIBS get obj/empty.o (tcc -ar refuses an empty archive)
      src/complex and the arch-specific src/math/<arch> are removed in patch()
      via shutil.rmtree (tcc cannot parse _Complex; the arch math shims are .s
      or rely on inline asm).

    x86_64-only:
      0002 sigsetjmp PLT stub      (x86_64 specific)
      0030 out-of-line syscall wrappers (x86_64 raw asm, replaces inline asm)
      0031 fenv                    (x86_64 specific)
      0040 SysV-AMD64 va_list      (routes va_* through 4-arg __va_start/__va_arg
                                   from tcc-mes' tcc_x86_64_stdarg.h; also
                                   drops tcc's va_list.c into src/stdarg/ so
                                   __va_start/__va_arg land in libc.a.
                                   __va_arg's arg_type is hardcoded GP so
                                   ``%f`` won't round-trip -- scaffold FP
                                   limitation, fixed downstream.)

    aarch64-only (tcc has no AArch64 assembler/inline-asm operands).  These are
    three concern-grouped unified diffs (see each patch header for the upstream
    numbers it subsumes):
      aarch64-01-va_list          (alltypes.h.in + <stdarg.h>: AAPCS64 va_list
                                   via tcc's 2-arg __va_start/__va_arg builtins)
      aarch64-02-asm-to-c         (every AArch64 .s / inline-asm source rewritten
                                   as C emitting raw instruction words: crt_arch,
                                   syscall, atomic, pthread_arch, and the crt/
                                   fenv/ldso/setjmp/signal/thread .s files)
      aarch64-03-drop-asm-barriers (drop the anti-DCE asm barriers in
                                   __libc_start_main and explicit_bzero)"""

    homepage = "https://musl.libc.org/"
    url = "https://www.musl-libc.org/releases/musl-1.1.24.tar.gz"

    license("MIT")

    version("1.1.24", sha256="1370c9a812b2cf2a7d92802510cca0058cc37e66a7bedd70051f0a34015022a3")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-mes", type="build")
    depends_on("bootstrap-gmake-mes", type="build")
    depends_on("bootstrap-linux-headers-seed", type="build")

    # Shared patches (both architectures).
    patch("0001-EMPTY_LIB_NAMES-add-g-so-tcc-can-resolve-lg.patch")
    patch("0004-Remove-crt-rcrt1.c-static-PIE-startup-unused-with-di.patch")
    patch("0006-Strip-C99-static-N-array-declarators.patch")
    patch("0020-Makefile-archive-an-empty-placeholder-.o-into-EMPTY_.patch")

    # x86_64-only patches.
    patch("0002-sigsetjmp-x86_64-plt.patch", when="target=x86_64:")
    patch("0030-syscall-x86_64.patch", when="target=x86_64:")
    patch("0040-x86_64-sysv-va_list.patch", when="target=x86_64:")

    # aarch64-only patches (concern-grouped; see module docstring).
    patch("aarch64-01-va_list.patch", when="target=aarch64:")
    patch("aarch64-02-asm-to-c.patch", when="target=aarch64:")
    patch("aarch64-03-drop-asm-barriers.patch", when="target=aarch64:")

    def patch(self):
        # tcc cannot parse C99 _Complex, so src/complex goes on both arches.
        # The arch-specific math dir is .s/inline-asm tcc cannot build; drop the
        # one matching the host arch (the other arch's dir is harmless but we
        # only ever stage one tree per build).
        src = self.stage.source_path
        shutil.rmtree(join_path(src, "src", "complex"))
        arch = "aarch64" if str(self.spec.target.family) == "aarch64" else "x86_64"
        shutil.rmtree(join_path(src, "src", "math", arch))

    def install(self, spec, prefix):
        cc = join_path(spec["bootstrap-tcc-mes"].prefix.bin, "tcc")
        kheaders = spec["bootstrap-linux-headers-seed"].prefix
        sh = Executable("/bin/sh")
        tcc = Executable(cc)
        make = Executable(spec["bootstrap-gmake-mes"].prefix.bin.make)

        # --disable-shared: no dynamic loader. --disable-gcc-wrapper: the
        # musl-gcc wrapper assumes gcc-style arg handling tcc doesn't share.
        # "./configure" (not "configure"): musl derives srcdir from
        # ${0%/configure}; a bare name leaves srcdir="configure" -> failure.
        sh(
            "./configure",
            "CC=" + cc,
            f"--target={spec.target.family}-linux-musl",
            "--prefix=" + prefix,
            "--syslibdir=" + join_path(prefix, "lib"),
            "--disable-shared",
            "--disable-gcc-wrapper",
        )

        # patch 0020 makes the EMPTY_LIBS (libg/libm/...) depend on obj/empty.o
        # but ships no rule to build it; generate it by hand (build.sh step 4).
        mkdirp("obj")
        with open("obj/empty.c", "w"):
            pass
        tcc("-c", "-o", "obj/empty.o", "obj/empty.c")

        # -DSYSCALL_NO_TLS: tcc has no __thread storage class. AR="tcc -ar" +
        # RANLIB=true: tcc bundles its own ar; the archives need no index.
        # Kernel uapi headers come in via -I (tcc doesn't honor C_INCLUDE_PATH).
        cflags = "-DSYSCALL_NO_TLS -I" + join_path(kheaders, "include")
        ar = cc + " -ar"
        make("CC=" + cc, "AR=" + ar, "RANLIB=true", "CFLAGS=" + cflags)
        make("install", "CC=" + cc, "AR=" + ar, "RANLIB=true")

        # Sanity: the static libc + startfiles landed.
        for f in ("lib/libc.a", "lib/crt1.o", "lib/crti.o", "lib/crtn.o"):
            assert os.path.exists(join_path(prefix, f)), "missing " + f

    def setup_build_environment(self, env):
        # Drop Spack's inherited jobserver. gmake-mes' seed MES libc ships a
        # *stub* sigaction (lib/stub/sigaction.c: `return 0`, no syscall), so
        # make never installs its SIGCHLD handler -- its blocking jobserver
        # read() is never EINTR'd by a finished child and it deadlocks under
        # -jN (children pile up as zombies). Clearing MAKEFLAGS keeps every
        # gmake-mes build serial and safe until a musl-linked make (real
        # sigaction) exists. See TODO.md and the gmake-mes-sigaction memory.
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def setup_dependent_build_environment(self, env, dependent_spec):
        # tcc-musl + gmp/mpfr/mpc + gcc link/compile against this libc.
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
        env.prepend_path("LIBRARY_PATH", self.prefix.lib)
