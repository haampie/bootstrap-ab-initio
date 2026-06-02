# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


def write_mes_tcc(path, tcc_prefix):
    """/bin/sh cc-wrapper driving the seed tcc (tcc-mes) as a plain "cc".

    Same shape as bootstrap-gmake-mes' mes-tcc, with two kernel-build tweaks:

    * The link path pulls in mes ``libgetopt.a`` -- the kernel's
      ``scripts/unifdef`` (a host tool ``make headers`` compiles) uses getopt,
      which mes libc keeps in a separate archive. ``-lgetopt`` is harmless
      (static) when unreferenced.
    * The kernel host-tool rules pass GCC depfile flags (``-Wp,-MMD,<file>``,
      and friends) that seed tcc 0.9.26 doesn't understand. tcc generates no
      depfiles and this is a one-shot build, so we silently drop them; without
      the filter ``scripts/basic/fixdep`` fails to compile.
    """
    libmes = join_path(tcc_prefix, "lib", "mes")
    incmes = join_path(tcc_prefix, "include", "mes")
    with open(path, "w") as f:
        f.write(
            "#!/bin/sh\n"
            'TCC="%s/bin/tcc"\n' % tcc_prefix
            + 'M="%s"\n' % libmes
            + 'INC="%s"\n' % incmes
            + "link=1\n"
            # Filter out depfile flags tcc 0.9.26 rejects; rebuild the arg list.
            # Kernel host args carry no spaces, so word-splitting on $A is fine.
            "A=\n"
            'for a in "$@"; do\n'
            "  case \"$a\" in\n"
            "    -Wp,-MMD,*|-Wp,-MD,*|-MMD|-MD|-MMD,*|-MD,*) continue;;\n"
            "    -c|-E|-S) link=0;;\n"
            "  esac\n"
            '  A="$A $a"\n'
            "done\n"
            'if [ "$link" -eq 1 ]; then\n'
            '  exec "$TCC" -I"$INC" -L"$M" -B"$M/tcc" -nostdlib '
            '"$M/crt1.o" "$M/crti.o" $A -lc -lgetopt "$M/tcc/libtcc1.a" "$M/crtn.o"\n'
            "else\n"
            '  exec "$TCC" -I"$INC" -L"$M" -B"$M/tcc" $A\n'
            "fi\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class BootstrapLinuxHeaders(Package):
    """Linux x86_64 kernel uapi headers, built via ``make headers``.

    musl needs the kernel uapi headers (asm/, asm-generic/, linux/, ...). The
    new chain has no kernel-header seed, so we sanitize them from a pristine
    kernel tarball with ``make headers`` (Guix's linux-libre-headers-boot0
    approach) -- a copy+sed+unifdef pass, no kernel compile. Output lands in
    ``usr/include`` and we copy the ``*.h`` into the prefix.

    Structure mirrors the working spack-packages ``linux-headers-boot0`` recipe
    (``make headers ARCH=x86_64 HOSTCC=...``; copy ``usr/include/**.h``; write
    ``include/config/kernel.release``). The one difference: that stage had a real
    gcc (gcc-mesboot) for HOSTCC, whereas here the only compiler is the seed tcc,
    so ``scripts/unifdef`` is built by a ``mes-tcc`` cc-wrapper. No ``c`` virtual.

    NOTE (likely iteration point): if unifdef fails to compile/link under mes
    libc, adjust the wrapper (the getopt dep is already wired) or, as a last
    resort, prebuild unifdef with the seed tcc by hand. make = bootstrap-gmake-mes."""

    homepage = "https://www.kernel.org/"
    url = "https://www.kernel.org/pub/linux/kernel/v6.x/linux-6.9.1.tar.xz"

    license("GPL-2.0-only")

    version("6.9.1", sha256="01b414ba98fd189ecd544435caf3860ae2a790e3ec48f5aa70fdf42dc4c5c04a")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-tcc-mes", type="build")
    depends_on("bootstrap-gmake-mes", type="build")

    #: build tool providing ``make``
    make_provider = "bootstrap-gmake-mes"

    def url_for_version(self, version):
        return "https://www.kernel.org/pub/linux/kernel/v{0}.x/linux-{1}.tar.xz".format(
            version.up_to(1), version
        )

    def setup_build_environment(self, env):
        env.set("MAKEFLAGS", "")
        env.set("MFLAGS", "")

    def install(self, spec, prefix):
        tcc = spec["bootstrap-tcc-mes"].prefix
        make = Executable(spec[self.make_provider].prefix.bin.make)

        mes_tcc = join_path(self.stage.source_path, "mes-tcc")
        write_mes_tcc(mes_tcc, tcc)

        # headers_install.sh strips __force/__user, #ifdef __KERNEL__ (via
        # scripts/unifdef, the only HOSTCC-built tool), #include <linux/compiler*>.
        # Result populates usr/include/. ARCH=x86_64 selects asm/. No .config
        # needed; Spack always unpacks a fresh tree (no `make mrproper`).
        make("headers", "ARCH=x86_64", "HOSTCC=" + mes_tcc)

        # Install usr/include/**.h into <prefix>/include (Guix install phase).
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
