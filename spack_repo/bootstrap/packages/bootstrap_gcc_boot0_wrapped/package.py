# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *

# ELF interpreter basename per arch, relative to glibc's lib/ (glibc installs the
# loader under lib/ on both arches).
DYNAMIC_LINKER = {
    "x86_64": "ld-linux-x86-64.so.2",
    "aarch64": "ld-linux-aarch64.so.1",
}

# Binutils tools to symlink from binutils-boot0 into the wrapper bin dir so
# that configure scripts and Makefiles find plain ``as``, ``ld``, ``ar`` etc.
BINUTILS_TOOLS = (
    "ar", "as", "ld", "nm", "objcopy", "objdump",
    "ranlib", "readelf", "strip",
)


class BootstrapGccBoot0Wrapped(Package):
    """Thin wrapper making the crippled gcc-boot0 target glibc-boot0.

    gcc-boot0 was built ``--without-headers`` and knows nothing about
    glibc-boot0. This package provides ``bin/gcc`` and ``bin/g++`` wrapper
    scripts that invoke the real compiler with:

    * ``-B<glibc-boot0>/lib`` -- find crt1.o/crti.o/crtn.o from the new libc.
    * ``-Wl,-dynamic-linker -Wl,<glibc-boot0>/lib/ld-linux-x86-64.so.2`` --
      linked executables use glibc-boot0's ELF interpreter.
    * ``-Wl,-rpath -Wl,<glibc-boot0>/lib`` -- runtime search path for libc.so.6.

    Native (not a cross), so the real binary is plain ``bin/gcc`` (gcc-boot0
    also installs an x86_64-linux-gnu-gcc; the plain name always exists). The
    binutils-boot0 tools are symlinked in under their plain names. ``has_code``
    is False -- this is a pure shim. Mirrors the gcc-boot0-wrapped /
    gcc-mesboot1-wrapper pattern (Guix ``cross-gcc-wrapper``)."""

    homepage = "https://gcc.gnu.org/"

    # No source tarball -- pure shim over gcc-boot0.
    has_code = False

    version("16.1.0")

    conflicts("platform=darwin")
    conflicts("platform=windows")

    depends_on("bootstrap-gcc-boot0@16.1.0", type=("build", "run"))
    depends_on("bootstrap-glibc-boot0", type=("build", "run"))
    depends_on("bootstrap-binutils-boot0", type=("build", "run"))

    def install(self, spec, prefix):
        gcc = spec["bootstrap-gcc-boot0"].prefix
        glibc = spec["bootstrap-glibc-boot0"].prefix
        binutils = spec["bootstrap-binutils-boot0"].prefix

        ld_so = join_path(glibc, "lib", DYNAMIC_LINKER[str(spec.target.family)])

        mkdirp(prefix.bin)

        # --- wrapper scripts for gcc and g++ ---
        for prog in ("gcc", "g++"):
            script = join_path(prefix.bin, prog)
            real = join_path(gcc.bin, prog)
            with open(script, "w") as f:
                f.write(
                    "#!/bin/sh\n"
                    "exec {real}"
                    " -B{glibc}/lib"
                    " -Wl,-dynamic-linker -Wl,{ld_so}"
                    " -Wl,-rpath -Wl,{glibc}/lib"
                    ' "$@"\n'.format(real=real, glibc=glibc, ld_so=ld_so)
                )
            os.chmod(script, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                     stat.S_IROTH | stat.S_IXOTH)

        # --- symlinks for binutils tools ---
        for tool in BINUTILS_TOOLS:
            src = join_path(binutils.bin, tool)
            dst = join_path(prefix.bin, tool)
            if os.path.exists(src) and not os.path.lexists(dst):
                os.symlink(src, dst)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("PATH", self.prefix.bin)
