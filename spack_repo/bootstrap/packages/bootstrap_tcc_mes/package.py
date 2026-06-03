# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *

# MES/M2libc spell the two targets we support "amd64" and "arm64"; the rest of
# the toolchain (TCC_TARGET_*, the mes lib/<arch>-mes-gcc dirs, the kernel header
# dir) keys off the GNU-ish "x86_64"/"aarch64" spelling.  Map one host -> both.
_M2_ARCH = {"x86_64": "amd64", "aarch64": "arm64"}  # keyed by mes_arch
_TCC_TARGET = {"x86_64": "X86_64", "aarch64": "ARM64"}  # keyed by mes_arch


def _unified_libc(mes_arch):
    """UNIFIED_LIBC retargeted: the only arch-specific members are the four
    ``<arch>-mes-gcc`` runtime files (substring-substituted below)."""
    return [e.replace("x86_64-mes-gcc", mes_arch + "-mes-gcc") for e in UNIFIED_LIBC]


def _headers(mes_arch):
    """HEADERS retargeted: swap the ``linux/x86_64`` arch header dir, and ship
    ``tcc_x86_64_stdarg.h`` only on x86_64 (aarch64 has no such header)."""
    out = []
    for src, dst in HEADERS:
        if src == "tcc_x86_64_stdarg.h":
            if mes_arch == "x86_64":
                out.append((src, dst))
            continue
        out.append((src.replace("linux/x86_64/", "linux/%s/" % mes_arch), dst))
    return out


# --- order-significant lists ported verbatim from pass1.kaem (x86_64 form;
#     _unified_libc()/_headers() retarget them for aarch64) ---
UNIFIED_LIBC = [
    "ctype/isalnum.c",
    "ctype/isalpha.c",
    "ctype/isascii.c",
    "ctype/iscntrl.c",
    "ctype/isdigit.c",
    "ctype/isgraph.c",
    "ctype/islower.c",
    "ctype/isnumber.c",
    "ctype/isprint.c",
    "ctype/ispunct.c",
    "ctype/isspace.c",
    "ctype/isupper.c",
    "ctype/isxdigit.c",
    "ctype/tolower.c",
    "ctype/toupper.c",
    "dirent/closedir.c",
    "dirent/__getdirentries.c",
    "dirent/opendir.c",
    "linux/readdir.c",
    "linux/access.c",
    "linux/brk.c",
    "linux/chdir.c",
    "linux/chmod.c",
    "linux/clock_gettime.c",
    "linux/close.c",
    "linux/dup2.c",
    "linux/dup.c",
    "linux/execve.c",
    "linux/fcntl.c",
    "linux/fork.c",
    "linux/fsync.c",
    "linux/fstat.c",
    "linux/_getcwd.c",
    "linux/getdents.c",
    "linux/getegid.c",
    "linux/geteuid.c",
    "linux/getgid.c",
    "linux/getpid.c",
    "linux/getppid.c",
    "linux/getrusage.c",
    "linux/gettimeofday.c",
    "linux/getuid.c",
    "linux/ioctl.c",
    "linux/ioctl3.c",
    "linux/kill.c",
    "linux/link.c",
    "linux/lseek.c",
    "linux/lstat.c",
    "linux/malloc.c",
    "linux/mkdir.c",
    "linux/mknod.c",
    "linux/nanosleep.c",
    "linux/_open3.c",
    "linux/pipe.c",
    "linux/_read.c",
    "linux/readlink.c",
    "linux/rename.c",
    "linux/rmdir.c",
    "linux/setgid.c",
    "linux/settimer.c",
    "linux/setuid.c",
    "linux/signal.c",
    "linux/sigprogmask.c",
    "linux/symlink.c",
    "linux/stat.c",
    "linux/time.c",
    "linux/unlink.c",
    "linux/waitpid.c",
    "linux/wait4.c",
    "linux/ftruncate.c",
    "linux/mkfifo.c",
    "linux/x86_64-mes-gcc/_exit.c",
    "linux/x86_64-mes-gcc/syscall.c",
    "linux/x86_64-mes-gcc/_write.c",
    "math/ceil.c",
    "math/fabs.c",
    "math/floor.c",
    "mes/abtod.c",
    "mes/abtol.c",
    "mes/__assert_fail.c",
    "mes/assert_msg.c",
    "mes/__buffered_read.c",
    "mes/__init_io.c",
    "mes/cast.c",
    "mes/dtoab.c",
    "mes/eputc.c",
    "mes/eputs.c",
    "mes/fdgetc.c",
    "mes/fdgets.c",
    "mes/fdputc.c",
    "mes/fdputs.c",
    "mes/fdungetc.c",
    "mes/globals.c",
    "mes/itoa.c",
    "mes/ltoab.c",
    "mes/ltoa.c",
    "mes/__mes_debug.c",
    "mes/mes_open.c",
    "mes/ntoab.c",
    "mes/oputc.c",
    "mes/oputs.c",
    "mes/search-path.c",
    "mes/ultoa.c",
    "mes/utoa.c",
    "posix/alarm.c",
    "posix/buffered-read.c",
    "posix/execl.c",
    "posix/execlp.c",
    "posix/execv.c",
    "posix/execvp.c",
    "posix/getcwd.c",
    "posix/getenv.c",
    "posix/isatty.c",
    "posix/mktemp.c",
    "posix/open.c",
    "posix/pathconf.c",
    "posix/raise.c",
    "posix/sbrk.c",
    "posix/setenv.c",
    "posix/sleep.c",
    "posix/unsetenv.c",
    "posix/wait.c",
    "posix/write.c",
    "stdio/clearerr.c",
    "stdio/fclose.c",
    "stdio/fdopen.c",
    "stdio/feof.c",
    "stdio/ferror.c",
    "stdio/fflush.c",
    "stdio/fgetc.c",
    "stdio/fgets.c",
    "stdio/fileno.c",
    "stdio/fopen.c",
    "stdio/fprintf.c",
    "stdio/fputc.c",
    "stdio/fputs.c",
    "stdio/fread.c",
    "stdio/freopen.c",
    "stdio/fscanf.c",
    "stdio/fseek.c",
    "stdio/ftell.c",
    "stdio/fwrite.c",
    "stdio/getc.c",
    "stdio/getchar.c",
    "stdio/perror.c",
    "stdio/printf.c",
    "stdio/putc.c",
    "stdio/putchar.c",
    "stdio/remove.c",
    "stdio/snprintf.c",
    "stdio/sprintf.c",
    "stdio/sscanf.c",
    "stdio/ungetc.c",
    "stdio/vfprintf.c",
    "stdio/vfscanf.c",
    "stdio/vprintf.c",
    "stdio/vsnprintf.c",
    "stdio/vsprintf.c",
    "stdio/vsscanf.c",
    "stdio/tmpfile.c",
    "stdlib/abort.c",
    "stdlib/abs.c",
    "stdlib/alloca.c",
    "stdlib/atexit.c",
    "stdlib/atof.c",
    "stdlib/atoi.c",
    "stdlib/atol.c",
    "stdlib/calloc.c",
    "stdlib/__exit.c",
    "stdlib/exit.c",
    "stdlib/free.c",
    "stdlib/mbstowcs.c",
    "stdlib/puts.c",
    "stdlib/qsort.c",
    "stdlib/realloc.c",
    "stdlib/strtod.c",
    "stdlib/strtof.c",
    "stdlib/strtol.c",
    "stdlib/strtold.c",
    "stdlib/strtoll.c",
    "stdlib/strtoul.c",
    "stdlib/strtoull.c",
    "string/bcmp.c",
    "string/bcopy.c",
    "string/bzero.c",
    "string/index.c",
    "string/memchr.c",
    "string/memcmp.c",
    "string/memcpy.c",
    "string/memmem.c",
    "string/memmove.c",
    "string/memset.c",
    "string/rindex.c",
    "string/strcat.c",
    "string/strchr.c",
    "string/strcmp.c",
    "string/strcpy.c",
    "string/strcspn.c",
    "string/strdup.c",
    "string/strerror.c",
    "string/strlen.c",
    "string/strlwr.c",
    "string/strncat.c",
    "string/strncmp.c",
    "string/strncpy.c",
    "string/strpbrk.c",
    "string/strrchr.c",
    "string/strspn.c",
    "string/strstr.c",
    "string/strupr.c",
    "stub/atan2.c",
    "stub/bsearch.c",
    "stub/chown.c",
    "stub/__cleanup.c",
    "stub/cos.c",
    "stub/ctime.c",
    "stub/exp.c",
    "stub/fpurge.c",
    "stub/freadahead.c",
    "stub/frexp.c",
    "stub/getgrgid.c",
    "stub/getgrnam.c",
    "stub/getlogin.c",
    "stub/getpgid.c",
    "stub/getpgrp.c",
    "stub/getpwnam.c",
    "stub/getpwuid.c",
    "stub/gmtime.c",
    "stub/ldexp.c",
    "stub/localtime.c",
    "stub/log.c",
    "stub/mktime.c",
    "stub/modf.c",
    "stub/mprotect.c",
    "stub/pclose.c",
    "stub/popen.c",
    "stub/pow.c",
    "stub/putenv.c",
    "stub/rand.c",
    "stub/realpath.c",
    "stub/rewind.c",
    "stub/setbuf.c",
    "stub/setgrent.c",
    "stub/setlocale.c",
    "stub/setvbuf.c",
    "stub/sigaction.c",
    "stub/sigaddset.c",
    "stub/sigblock.c",
    "stub/sigdelset.c",
    "stub/sigemptyset.c",
    "stub/sigsetmask.c",
    "stub/sin.c",
    "stub/sys_siglist.c",
    "stub/system.c",
    "stub/sqrt.c",
    "stub/strftime.c",
    "stub/times.c",
    "stub/ttyname.c",
    "stub/umask.c",
    "stub/utime.c",
    "x86_64-mes-gcc/setjmp.c",
]

HEADERS = [
    ("alloca.h", "alloca.h"),
    ("argz.h", "argz.h"),
    ("ar.h", "ar.h"),
    ("assert.h", "assert.h"),
    ("ctype.h", "ctype.h"),
    ("dirent.h", "dirent.h"),
    ("dirstream.h", "dirstream.h"),
    ("dlfcn.h", "dlfcn.h"),
    ("endian.h", "endian.h"),
    ("errno.h", "errno.h"),
    ("fcntl.h", "fcntl.h"),
    ("features.h", "features.h"),
    ("float.h", "float.h"),
    ("getopt.h", "getopt.h"),
    ("grp.h", "grp.h"),
    ("inttypes.h", "inttypes.h"),
    ("libgen.h", "libgen.h"),
    ("limits.h", "limits.h"),
    ("locale.h", "locale.h"),
    ("math.h", "math.h"),
    ("memory.h", "memory.h"),
    ("pwd.h", "pwd.h"),
    ("setjmp.h", "setjmp.h"),
    ("signal.h", "signal.h"),
    ("stdarg.h", "stdarg.h"),
    ("tcc_x86_64_stdarg.h", "tcc_x86_64_stdarg.h"),
    ("stdbool.h", "stdbool.h"),
    ("stddef.h", "stddef.h"),
    ("stdint.h", "stdint.h"),
    ("stdio.h", "stdio.h"),
    ("stdlib.h", "stdlib.h"),
    ("stdnoreturn.h", "stdnoreturn.h"),
    ("string.h", "string.h"),
    ("strings.h", "strings.h"),
    ("termio.h", "termio.h"),
    ("time.h", "time.h"),
    ("unistd.h", "unistd.h"),
    ("linux/x86_64/kernel-stat.h", "arch/kernel-stat.h"),
    ("linux/x86_64/signal.h", "arch/signal.h"),
    ("linux/x86_64/syscall.h", "arch/syscall.h"),
    ("linux/syscall.h", "linux/syscall.h"),
    ("mes/builtins.h", "mes/builtins.h"),
    ("mes/cc.h", "mes/cc.h"),
    ("mes/constants.h", "mes/constants.h"),
    ("mes/lib.h", "mes/lib.h"),
    ("mes/lib-cc.h", "mes/lib-cc.h"),
    ("mes/lib-mini.h", "mes/lib-mini.h"),
    ("mes/mes.h", "mes/mes.h"),
    ("mes/symbols.h", "mes/symbols.h"),
    ("sys/cdefs.h", "sys/cdefs.h"),
    ("sys/dir.h", "sys/dir.h"),
    ("sys/file.h", "sys/file.h"),
    ("sys/ioctl.h", "sys/ioctl.h"),
    ("sys/mman.h", "sys/mman.h"),
    ("sys/param.h", "sys/param.h"),
    ("sys/resource.h", "sys/resource.h"),
    ("sys/select.h", "sys/select.h"),
    ("sys/stat.h", "sys/stat.h"),
    ("sys/timeb.h", "sys/timeb.h"),
    ("sys/time.h", "sys/time.h"),
    ("sys/times.h", "sys/times.h"),
    ("sys/types.h", "sys/types.h"),
    ("sys/ucontext.h", "sys/ucontext.h"),
    ("sys/user.h", "sys/user.h"),
    ("sys/wait.h", "sys/wait.h"),
]



class BootstrapTccMes(Package):
    """Bootstrappable TCC 0.9.26 (x86_64 or AArch64), grown from a hex0 seed with
    no system compiler.

    This is the first brick of the new full-source bootstrap: it replaces the
    GNU-Mes-based ``mes-boot`` -> ``tcc-boot0`` -> ``tcc-boot`` stages with the
    faster ``MES-replacement`` C-compiler (``tcc_cc``).

    The recipe is a faithful Python port of ``MES-replacement``'s
    ``target_<arch>/tools-*-kaem.kaem`` (toolchain) and
    ``steps/tcc-0.9.26/pass1.kaem`` (tcc), which is itself parameterised by
    ``${ARCH}`` (amd64/arm64). MES-replacement was written for live-bootstrap's
    pure chroot with zero host tools, so it bootstraps its own ``kaem`` shell,
    coreutils, ``simple-patch`` and a ``steps`` package manager. Spack already
    supplies all of that (fetch/checksum/extract/patch) in the parent process, so
    we discard it and keep only the irreducible core: the hex0 seed plus the
    compile sequence, driven from Python. No kaem, no chroot, no path relocation
    -- we use real build/prefix paths.

    The same recipe builds both targets: it selects the per-arch seed set, TCC
    target macro, mes ``<arch>-mes-gcc`` runtime files and (AArch64 only) the
    ``lib-arm64.c`` soft-float helpers + the nine arm64 tcc source patches.

    Like the rest of the early chain it does *not* ``depends_on("c")``."""

    homepage = "https://www.iwriteiam.nl/MES-replacement.html"

    # Main source: the bootstrappable TCC 0.9.26 snapshot (Jan Nieuwenhuizen's
    # tree). The version string tracks the tcc we produce.
    version(
        "0.9.26",
        sha256="6b8cbd0a5fed0636d4f0f763a603247bc1935e206e1cc5bda6a2818bab6e819f",
        url="https://lilypond.org/janneke/tcc/tcc-0.9.26-1147-gee75a10c.tar.gz",
    )

    # GNU Mes supplies the C library (headers + sources) tcc links against.
    # haampie/mes branch ``spack/0.27`` is v0.27.1 + the x86_64 libc features
    # later stages need (assert/NDEBUG, O_CLOEXEC/O_NONBLOCK/flock, DT_*, ENOTSUP,
    # _POSIX_VERSION, mktemp decl, O_DIRECTORY fix, ftruncate/mkfifo/tmpfile) +
    # the cherry-picked "Add aarch64 libc support" commit (the aarch64
    # <arch>-mes-gcc runtime, va.c helpers, and setjmp/stdarg/stdint cases). One
    # ref serves both arches.
    resource(
        name="mes",
        git="https://github.com/haampie/mes.git",
        commit="ee67b214fcbad0defc436bb25eece8894787a293",
        destination="",
        placement="mes",
    )

    # The make-generated seeds (``make -C MES-replacement/src``): per-arch hex0
    # ELF + the text intermediates that bootstrap hex2/M1/blood-elf/stack_c/
    # tcc_cc. One combined tarball with ``amd64/`` and ``arm64/`` subdirs (uniform
    # internal names); install() picks its arch. Local path for now; switch to a
    # GitHub release URL once stable.
    resource(
        name="seeds",
        sha256="0de6d1f05c66dbe233f82d0a1ef7f79c77b05af781b5fbdbf077d9976eb5bdd7",
        url="https://github.com/haampie/MES-replacement/releases/download/wip/tcc-mes-seeds.tar.gz",
        destination="",
        placement="seeds",
    )

    # x86_64 + aarch64 only; the chain emits and runs the host arch from the start.
    conflicts("platform=darwin")
    conflicts("platform=windows")

    # x86_64 source fixes (ported from MES-replacement's amd64 simple-patches),
    # applied by Spack *before* the sandbox.
    patch("tcc-static-plt.patch", when="target=x86_64:")  # tcc: relocate static-exec PLT stubs
    patch("tcc-va-list.patch", when="target=x86_64:")  # tcc: SysV AMD64 va_list, single def

    # AArch64 source fixes: tcc 0.9.26 has no arm64 assembler and the seed
    # tcc_cc miscompiles a few constructs.  These are real unified diffs derived
    # from MES-replacement's arm64 simple-patches, grouped by concern.  The
    # assembler body itself (``arm64-asm.c``) is dropped in during install()
    # from the seed set; the asm-wiring patch only adds the ``#include``.
    patch("tcc-arm64-01-asm-wiring.patch", when="target=aarch64:")
    patch("tcc-arm64-02-codegen.patch", when="target=aarch64:")
    patch("tcc-arm64-03-varargs.patch", when="target=aarch64:")
    patch("tcc-arm64-04-long-double-suffix.patch", when="target=aarch64:")

    @property
    def mes_arch(self):
        """GNU-ish arch spelling used by mes/tcc (``x86_64`` | ``aarch64``)."""
        return "aarch64" if str(self.spec.target.family) == "aarch64" else "x86_64"

    def install(self, spec, prefix):
        src = self.stage.source_path  # the tcc-0.9.26-1147-gee75a10c tree
        mes = join_path(src, "mes")

        mes_arch = self.mes_arch                  # x86_64 | aarch64
        m2 = _M2_ARCH[mes_arch]                   # amd64 | arm64 (seed subdir + -a flag)
        tcc_target = _TCC_TARGET[mes_arch]        # X86_64 | ARM64
        link_libarm64 = mes_arch == "aarch64"     # arm64 needs lib-arm64.c soft-float

        # combined seeds tarball -> seeds/<amd64|arm64>/ (uniform internal names).
        seeds = join_path(src, "seeds", m2)

        tmp = join_path(src, "tmp")
        tools = join_path(src, "tools")
        mkdirp(tmp, tools)

        bindir = prefix.bin
        libdir = join_path(prefix, "lib", "mes")
        incdir = join_path(prefix, "include", "mes")
        mkdirp(bindir, libdir, join_path(libdir, "tcc"), incdir)

        elf = join_path(seeds, "ELF-debug.hex2")
        intro = join_path(seeds, "stack_c_intro.M1")
        # tcc_cc keeps the current source filename in 101-byte position buffers
        # (tcc_cc.c) used to format its warnings, so any *source* path it opens
        # must stay short -- a long absolute path overflows them and segfaults.
        # We therefore feed it source inputs by short relative paths (cwd=src);
        # output (-o) and -D values are unaffected. ``seeds`` is ``src/seeds/<m2>``.
        stdlib_c = join_path("seeds", m2, "stdlib.c")

        # Order-significant lists ported from pass1.kaem, retargeted per arch.
        unified_libc = _unified_libc(mes_arch)
        headers = _headers(mes_arch)

        def chmod_x(path):
            st = os.stat(path).st_mode
            os.chmod(path, st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        def run(exe, *args, cwd=None):
            if cwd is None:
                Executable(exe)(*args)
            else:
                with working_dir(cwd):
                    Executable(exe)(*args)

        # ---- Phase 1: grow the bootstrap toolchain (tools-*-kaem.kaem) --------
        hex0 = join_path(seeds, "hex0-seed")
        chmod_x(hex0)
        hex2 = join_path(tools, "hex2")
        m1 = join_path(tools, "M1")
        blood_elf = join_path(tools, "blood-elf")
        stack_c = join_path(tools, "stack_c")
        tcc_cc = join_path(tools, "tcc_cc")

        run(hex0, join_path(seeds, "hex2.hex0"), hex2)
        chmod_x(hex2)
        run(hex2, "-o", blood_elf, elf,
            join_path(seeds, "blood-elf.macro"), join_path(seeds, "blood-elf.blood_elf"))
        chmod_x(blood_elf)
        run(hex2, "-o", m1, elf,
            join_path(seeds, "M1.macro"), join_path(seeds, "M1.blood_elf"))
        chmod_x(m1)

        run(blood_elf, "--64", "--file", join_path(seeds, "stack_c.M1"),
            "--little-endian", "--output", join_path(tmp, "stack_c.blood_elf"))
        run(m1, "-o", join_path(tmp, "stack_c.macro"), join_path(seeds, "stack_c.M1"))
        run(hex2, "-o", stack_c, elf,
            join_path(tmp, "stack_c.macro"), join_path(tmp, "stack_c.blood_elf"))
        chmod_x(stack_c)

        run(stack_c, "-i", intro, join_path(seeds, "tcc_cc.sl64"),
            "-o", join_path(tmp, "tcc_cc.M1"))
        run(blood_elf, "--64", "--file", join_path(tmp, "tcc_cc.M1"),
            "--little-endian", "--output", join_path(tmp, "tcc_cc.blood_elf"))
        run(m1, join_path(tmp, "tcc_cc.M1"), "-o", join_path(tmp, "tcc_cc.macro"))
        run(hex2, "-o", tcc_cc, elf,
            join_path(tmp, "tcc_cc.macro"), join_path(tmp, "tcc_cc.blood_elf"))
        chmod_x(tcc_cc)

        # ---- Phase 2a: config.h's --------------------------------------------
        # The per-arch tcc source fixes are already applied (Spack patch()
        # directives: x86_64 two, aarch64 four -- including arm64-asm.c). Empty
        # config.h's: all configuration comes via the -D flags below.
        for cfg in (join_path(mes, "include", "mes", "config.h"),
                    join_path(src, "config.h")):
            open(cfg, "w").close()

        # ---- Phase 2b: tcc_cc compiles tcc.c -> tcc_s -------------------------
        # -D values carrying a C string literal keep their embedded quotes (the
        # process gets the quotes in argv, exactly as kaem passed them).
        def tcc_defs(extra=()):
            d = [
                "-D", "BOOTSTRAP=1",
                "-D", "HAVE_LONG_LONG=1",
                "-D", "TCC_TARGET_%s=1" % tcc_target,
                "-D", 'CONFIG_TCCDIR="%s/tcc"' % libdir,
                "-D", 'CONFIG_TCC_CRTPREFIX="%s"' % libdir,
                "-D", 'CONFIG_TCC_ELFINTERP="/mes/loader"',
                "-D", 'CONFIG_TCC_SYSINCLUDEPATHS="%s"' % incdir,
                "-D", 'TCC_LIBGCC="%s/libc.a"' % libdir,
                "-D", "CONFIG_TCCBOOT=1",
                "-D", "CONFIG_TCC_STATIC=1",
                "-D", "CONFIG_USE_LIBGCC=1",
                "-D", 'TCC_VERSION="0.9.26"',
                "-D", "ONE_SOURCE=1",
            ]
            return list(extra) + d

        tcc_s = join_path(tools, "tcc_s")
        run(tcc_cc, "-a", m2, "-o", join_path(tmp, "tcc.sl"),
            *tcc_defs(("-D", 'CONFIG_SYSROOT="/"', "-D", "CONFIG_TCC_LIBTCC1_MES=0")),
            stdlib_c, "tcc.c", cwd=src)
        run(stack_c, "-i", intro, join_path(tmp, "tcc.sl"), "-o", join_path(tmp, "tcc_s.M1"))
        run(blood_elf, "-a", m2, "--file", join_path(tmp, "tcc_s.M1"),
            "--little-endian", "--output", join_path(tmp, "tcc_s.blood_elf"))
        run(m1, join_path(tmp, "tcc_s.M1"), "-o", join_path(tmp, "tcc_s.macro"))
        run(hex2, "-o", tcc_s, elf,
            join_path(tmp, "tcc_s.macro"), join_path(tmp, "tcc_s.blood_elf"))
        chmod_x(tcc_s)
        run(tcc_s, "-version")

        # ---- Phase 2c: install mes headers ------------------------------------
        with working_dir(join_path(mes, "include")):
            for srel, drel in headers:
                dst = join_path(incdir, drel)
                mkdirp(os.path.dirname(dst))
                install(srel, dst)
        open(join_path(incdir, "mes", "config.h"), "w").close()

        # ---- Phase 2d: assemble the unified mes libc translation unit ---------
        parts = []
        for rel in unified_libc:
            with open(join_path(mes, "lib", rel), "rb") as f:
                parts.append(f.read())
        # Append the va runtime: x86_64 uses the (patched) SysV AMD64 va_list.c
        # from the tcc tree; aarch64 uses the mes AAPCS64 __mes_va_arg_* helpers.
        if mes_arch == "x86_64":
            va_src = join_path(src, "lib", "va_list.c")
        else:
            va_src = join_path(mes, "lib", "%s-mes-gcc" % mes_arch, "va.c")
        with open(va_src, "rb") as f:
            parts.append(f.read())
        with open(join_path(mes, "unified-libc.c"), "wb") as f:
            f.write(b"".join(parts))

        inc = ["-I", "include", "-I", "include/linux/%s" % mes_arch]
        # arm64 long double is 128-bit with no hardware quad-float: libtcc1 needs
        # the lib-arm64.c TFmode soft-float helpers (LINK_LIBARM64 in pass1.kaem).
        lib_arm64_c = join_path(src, "lib", "lib-arm64.c")

        def build_libc(cc):
            """Compile crt1.o + libc.a + libtcc1.a with compiler ``cc`` (cwd=mes)."""
            with working_dir(mes):
                run(cc, "-c", "-D", "HAVE_CONFIG_H=1", *inc,
                    "-o", join_path(libdir, "crt1.o"),
                    "lib/linux/%s-mes-gcc/crt1.c" % mes_arch)
                run(cc, "-c", "-D", "HAVE_CONFIG_H=1", "-D", "HAVE_LONG_LONG=1",
                    "-D", "HAVE_FLOAT=1", *inc, "-o", "libtcc1.o", "lib/libtcc1.c")
                libtcc1_objs = ["libtcc1.o"]
                if link_libarm64:
                    run(cc, "-c", "-D", "HAVE_CONFIG_H=1", "-D", "HAVE_LONG_LONG=1",
                        "-D", "HAVE_FLOAT=1", *inc, "-o", "lib-arm64.o", lib_arm64_c)
                    libtcc1_objs.append("lib-arm64.o")
                run(cc, "-ar", "cr", join_path(libdir, "tcc", "libtcc1.a"), *libtcc1_objs)
                run(cc, "-c", "-D", "HAVE_CONFIG_H=1", *inc,
                    "-o", "unified-libc.o", "unified-libc.c")
                run(cc, "-ar", "cr", join_path(libdir, "libc.a"), "unified-libc.o")

        # First libc with tcc_s, plus the empty crti/crtn (both arches: only the
        # 32-bit x86 path builds real ones) and libgetopt.
        build_libc(tcc_s)
        open(join_path(libdir, "crti.o"), "w").close()
        open(join_path(libdir, "crtn.o"), "w").close()
        with working_dir(mes):
            run(tcc_s, "-c", "-D", "HAVE_CONFIG_H=1", *inc, "lib/posix/getopt.c")
            run(tcc_s, "-ar", "cr", join_path(libdir, "libgetopt.a"), "getopt.o")

        # ---- Phase 2e: self-host through tcc-boot0 -> 1 -> 2 ------------------
        def boot_defs(extra=()):
            d = [
                "-D", "BOOTSTRAP=1",
                "-D", "HAVE_FLOAT=1",
                "-D", "HAVE_BITFIELD=1",
                "-D", "HAVE_LONG_LONG=1",
                "-D", "HAVE_SETJMP=1",
                "-I", ".", "-I", incdir,
                "-D", "TCC_TARGET_%s=1" % tcc_target,
                "-D", 'CONFIG_TCCDIR="%s/tcc"' % libdir,
                "-D", 'CONFIG_TCC_CRTPREFIX="%s"' % libdir,
                "-D", 'CONFIG_TCC_ELFINTERP="/mes/loader"',
                "-D", 'CONFIG_TCC_LIBPATHS="%s:%s/tcc"' % (libdir, libdir),
                "-D", 'CONFIG_TCC_SYSINCLUDEPATHS="%s"' % incdir,
                "-D", 'TCC_LIBGCC="%s/libc.a"' % libdir,
                "-D", 'TCC_LIBTCC1="libtcc1.a"',
                "-D", "CONFIG_TCCBOOT=1",
                "-D", "CONFIG_TCC_STATIC=1",
                "-D", "CONFIG_USE_LIBGCC=1",
                "-D", 'TCC_VERSION="0.9.26"',
                "-D", "ONE_SOURCE=1",
            ]
            return d + list(extra)

        def boot(cc, out, link_extra):
            run(cc, "-g", "-v", "-static", "-o", out,
                *boot_defs(link_extra), "tcc.c", cwd=src)
            chmod_x(join_path(src, out))
            built = join_path(src, out)
            build_libc(built)
            run(built, "-version", cwd=src)
            return built

        # boot0 compiled by tcc_s (which lacks compiled-in CONFIG_TCC_LIBPATHS),
        # so it needs an explicit -L to the libdir; boot1/boot2 do not.
        boot0 = boot(tcc_s, "tcc-boot0", ["-L", ".", "-L", libdir])
        boot1 = boot(boot0, "tcc-boot1", ["-L", "."])
        boot2 = boot(boot1, "tcc-boot2", ["-L", "."])

        # ---- Phase 3: finalize + install deliverables -------------------------
        install(boot2, join_path(bindir, "tcc"))
        install(boot2, join_path(bindir, "tcc-0.9.26"))
        install(boot1, join_path(bindir, "tcc-boot1"))
        for f in ("tcc", "tcc-0.9.26", "tcc-boot1"):
            chmod_x(join_path(bindir, f))

        # libgetopt rebuilt with the final tcc (nothing is linked against it
        # during the boot stages).
        final_tcc = join_path(bindir, "tcc")
        with working_dir(mes):
            run(final_tcc, "-c", "-D", "HAVE_CONFIG_H=1", *inc, "lib/posix/getopt.c")
            run(final_tcc, "-ar", "cr", join_path(libdir, "libgetopt.a"), "getopt.o")
