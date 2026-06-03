# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import filecmp
import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *

#: AArch64 ``alloca``, the analogue of upstream tcc's lib/alloca86_64.S. The
#: bootstrappable tcc 0.9.26 fork does not inline alloca(); a source-level
#: alloca(n) compiles to ``bl alloca`` (size in x0, result in x0). musl ships no
#: such symbol, so this trampoline supplies it. tcc's arm64 assembler accepts
#: only ``.int``/``.word`` data directives, so each instruction is its raw
#: little-endian opcode -- the exact encodings arm64-gen.c emits for VLAs. It is
#: a leaf function: on AArch64 the return address is in x30 (not on the stack,
#: unlike x86's pop/repush), and the lowered sp is reclaimed for free by every
#: caller's ``mov sp,x29`` epilogue (arm64-gen.c gfunc_epilog).
_ALLOCA_ARM64_S = """\
.globl alloca
alloca:
    .int 0x91003c00   /* add x0, x0, #15   ; round the request size up... */
    .int 0x927cec00   /* bic x0, x0, #15   ; ...to a multiple of 16        */
    .int 0xcb2063ff   /* sub sp, sp, x0    ; grow the stack                */
    .int 0x910003e0   /* mov x0, sp        ; return a pointer to the block */
    .int 0xd65f03c0   /* ret               ; br x30                        */
"""


class BootstrapTccMuslStage1(Package):
    """tcc 0.9.26 linked against the (broken) scaffold musl -- the INTERMEDIATE
    compiler whose only job is to build a correct bootstrap-musl-boot.

    Same tcc 0.9.26 source as bootstrap-tcc-mes, but compiled by the seed tcc
    (tcc-mes) and linked against bootstrap-musl-scaffold instead of mes libc.
    Scaffold musl's strtod is correct, so this compiler rounds FP literals
    properly (unlike the mes-libc seed) and its x86_64 codegen is sound -- but
    scaffold musl's *printf* is miscompiled by tcc-mes (NUL-corrupted ``%016lx``
    and ``%f`` -> 0.0), so anything this stage's binary itself prints is garbage.
    That does not matter: it only ever compiles bootstrap-musl-boot (a correct
    musl), and the final bootstrap-tcc-musl is rebuilt against THAT. It self-hosts
    in three stages and the fixed point (stage2 == stage3 byte-identical) is
    asserted. See the bootstrap-scaffold-musl-printf-broken memory.

    Ported from MES-replacement/steps/03-tcc-musl/ (+ musl-1.1.24/log.md).

    THE critical flag is ``-DHAVE_FLOAT=1``: the bootstrappable 0.9.26 fork wraps
    all floating-point handling in ``#if HAVE_FLOAT``; without it every
    float/double literal compiles to 0.0 and silently miscompiles GCC's cc1
    downstream. No ``c`` virtual dependency."""

    homepage = "https://www.iwriteiam.nl/MES-replacement.html"

    # Same bootstrappable TCC 0.9.26 snapshot as bootstrap-tcc-mes.
    version(
        "0.9.26",
        sha256="6b8cbd0a5fed0636d4f0f763a603247bc1935e206e1cc5bda6a2818bab6e819f",
        url="https://lilypond.org/janneke/tcc/tcc-0.9.26-1147-gee75a10c.tar.gz",
    )

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-mes", type="build")
    depends_on("bootstrap-musl-scaffold", type="build")

    # Same per-arch tcc source fixes as bootstrap-tcc-mes (applied pre-sandbox).
    patch("tcc-static-plt.patch", when="target=x86_64:")
    patch("tcc-va-list.patch", when="target=x86_64:")
    patch("tcc-arm64-01-asm-wiring.patch", when="target=aarch64:")
    patch("tcc-arm64-02-codegen.patch", when="target=aarch64:")
    patch("tcc-arm64-03-varargs.patch", when="target=aarch64:")
    patch("tcc-arm64-04-long-double-suffix.patch", when="target=aarch64:")

    @property
    def mes_arch(self):
        """GNU-ish arch spelling used by mes/tcc (``x86_64`` | ``aarch64``)."""
        return "aarch64" if str(self.spec.target.family) == "aarch64" else "x86_64"

    def install(self, spec, prefix):
        src = self.stage.source_path
        seed = join_path(spec["bootstrap-tcc-mes"].prefix, "bin", "tcc")
        musl = spec["bootstrap-musl-scaffold"].prefix
        musllib = join_path(musl, "lib")
        muslinc = join_path(musl, "include")

        # x86_64 | aarch64; selects the TCC target macro and the libtcc1 runtime.
        mes_arch = self.mes_arch
        tcc_target = "X86_64" if mes_arch == "x86_64" else "ARM64"
        tcc_target_def = "-DTCC_TARGET_%s=1" % tcc_target

        libdir = join_path(prefix, "lib", "mes")  # keep tcc-mes-style layout
        tccdir = join_path(libdir, "tcc")
        bindir = prefix.bin
        mkdirp(bindir, tccdir)

        def chmod_x(p):
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # tcc.h:25 does #include "config.h"; all config comes via -D below.
        open(join_path(src, "config.h"), "w").close()

        # libtcc1.a (compiler runtime helpers), built by the seed tcc.
        #
        # x86_64 MUST include alloca86_64.S: tcc does NOT inline alloca --
        # libtcc.c maps __builtin_alloca -> the *symbol* alloca, which lives in
        # lib/alloca86_64.S. Unlike mes libc (which ships its own `alloca`), musl
        # has none (it relies on the compiler builtin), so without this every
        # alloca-using program tcc-musl links (make, binutils, gcc) gets
        # "undefined symbol alloca", and their configure falls back to gnulib's
        # C_ALLOCA path. Archive members are pulled only when referenced, so
        # tcc.c's own self-host (no alloca) and the stage2==stage3 fixpoint are
        # unaffected.
        #
        # aarch64 needs lib-arm64.c: the TFmode soft-float helpers
        # (__addtf3/__multf3/... + float/int conversions) that 128-bit
        # ``long double`` requires (aarch64 has no hardware quad-float). It ALSO
        # needs alloca-arm64.S, the exact analogue of alloca86_64.S: this tcc
        # fork does not inline alloca() -- it emits a plain ``bl alloca`` -- and
        # musl ships no such symbol, so without it every alloca-using program
        # this tcc links (make, binutils, gcc) fails with "undefined symbol
        # alloca" (same reason x86_64 archives alloca86_64.S above). tcc's arm64
        # assembler accepts only .int data words, so the trampoline is emitted
        # as raw opcodes (the same ones arm64-gen.c uses for VLAs); see
        # ``_ALLOCA_ARM64_S``. Note aarch64 does NOT compile upstream
        # lib/libtcc1.c: that file's only non-portable code is an i386 inline-asm
        # block guarded ``#if !X86_64 && !ARM`` -> on aarch64 it falls through to
        # ``#error unsupported CPU type``, and its 64-bit integer helpers
        # (__divdi3/__udivmoddi4/...) are unneeded since aarch64 divides
        # natively (cf. steps/musl-1.1.24/log.md step 4).
        libtcc1 = join_path(tccdir, "libtcc1.a")
        with working_dir(src):
            if mes_arch == "x86_64":
                Executable(seed)(
                    "-c", "-DHAVE_FLOAT=1", "-DHAVE_LONG_LONG=1", tcc_target_def,
                    "-I", "include", "-o", "libtcc1.o", "lib/libtcc1.c",
                )
                Executable(seed)(
                    "-c", tcc_target_def, "-o", "alloca86_64.o", "lib/alloca86_64.S",
                )
                Executable(seed)("-ar", "cr", libtcc1, "libtcc1.o", "alloca86_64.o")
            else:
                Executable(seed)(
                    "-c", "-DHAVE_FLOAT=1", "-DHAVE_LONG_LONG=1", tcc_target_def,
                    "-I", "include", "-o", "lib-arm64.o", "lib/lib-arm64.c",
                )
                with open(join_path(src, "alloca-arm64.S"), "w") as f:
                    f.write(_ALLOCA_ARM64_S)
                Executable(seed)(
                    "-c", tcc_target_def, "-o", "alloca-arm64.o", "alloca-arm64.S",
                )
                Executable(seed)("-ar", "cr", libtcc1, "lib-arm64.o", "alloca-arm64.o")

        def defs():
            return [
                "-DBOOTSTRAP=1",
                "-DHAVE_FLOAT=1",
                "-DHAVE_BITFIELD=1",
                "-DHAVE_LONG_LONG=1",
                "-DHAVE_SETJMP=1",
                tcc_target_def,
                '-DCONFIG_TCCDIR="%s"' % tccdir,
                '-DCONFIG_SYSROOT="/"',
                '-DCONFIG_TCC_CRTPREFIX="%s"' % musllib,
                '-DCONFIG_TCC_ELFINTERP="/musl/loader"',  # static; unused
                '-DCONFIG_TCC_SYSINCLUDEPATHS="%s"' % muslinc,
                '-DCONFIG_TCC_LIBPATHS="%s:%s"' % (musllib, tccdir),
                '-DTCC_LIBGCC="%s/libc.a"' % musllib,
                '-DTCC_LIBTCC1="libtcc1.a"',
                "-DCONFIG_TCCBOOT=1",
                "-DCONFIG_TCC_STATIC=1",
                "-DCONFIG_USE_LIBGCC=1",
                '-DTCC_VERSION="0.9.26"',
                "-DONE_SOURCE=1",
            ]

        def build_stage(cc, out):
            # Fully explicit static link against scaffold musl crt + libc.
            with working_dir(src):
                Executable(cc)(
                    "-g", "-static", "-nostdlib", "-nostdinc",
                    *defs(),
                    "-I", ".", "-I", muslinc,
                    "-o", out,
                    join_path(musllib, "crt1.o"),
                    join_path(musllib, "crti.o"),
                    "tcc.c",
                    join_path(musllib, "libc.a"),
                    libtcc1,
                    join_path(musllib, "crtn.o"),
                )
                chmod_x(join_path(src, out))
                Executable(join_path(src, out))("-version")
            return join_path(src, out)

        stage1 = build_stage(seed, "tcc-stage1")
        stage2 = build_stage(stage1, "tcc-stage2")
        stage3 = build_stage(stage2, "tcc-stage3")

        # Fixed-point criterion: stage2 == stage3 byte-for-byte.
        assert filecmp.cmp(stage2, stage3, shallow=False), (
            "tcc self-host did not reach a fixed point (stage2 != stage3)"
        )

        install(stage3, join_path(bindir, "tcc"))
        install(stage3, join_path(bindir, "tcc-0.9.26"))
        for f in ("tcc", "tcc-0.9.26"):
            chmod_x(join_path(bindir, f))

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
