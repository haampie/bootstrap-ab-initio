# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class BootstrapLinuxHeadersSeed(Package):
    """Prebuilt Linux kernel headers seed -- the early-stage kernel uapi.

    The sanitized, sha256-pinned ``linux-libre-headers-stripped-4.14.67-i686-linux``
    tarball, unpacked as-is. No compiler and no ``make`` are involved, so the seed
    compiler (tcc-mes) is never asked to build ``fixdep``/``unifdef``.

    Why this exists (two-tier kernel headers): the only consumer that needs
    kernel uapi headers *before* a real GCC exists is bootstrap-musl-scaffold
    (and the tcc-built bootstrap-gcc-stage0 that links against it). Those take
    their headers from this seed. Once bootstrap-gcc-stage0 is built, the real
    ``bootstrap-linux-headers`` (``make headers`` with gcc-stage0 as HOSTCC)
    supplies x86_64 headers to the pristine musl + later gcc stages.

    Note on arch: the only prebuilt seed available is i686 4.14.67, so these are
    i686 headers. musl carries its own per-arch syscall numbers and uses kernel
    headers mainly for (largely x86-unified) structs/ioctls, so this suffices for
    the throwaway scaffold; the real x86_64 headers arrive with
    bootstrap-linux-headers.

    No ``c`` dependency."""

    homepage = "https://www.gnu.org/software/guix/"
    url = (
        "https://ftpmirror.gnu.org/guix/bootstrap/i686-linux/20190815/"
        "linux-libre-headers-stripped-4.14.67-i686-linux.tar.xz"
    )

    license("GPL-2.0-only")

    # Let Spack expand the seed tarball at stage time, i.e. BEFORE the build
    # sandbox is applied -- so the build needs no host tar/xz. The tarball ships
    # read-only directories (dr-xr-xr-x) and unpacks to ./include.
    version(
        "4.14.67",
        sha256="1acd8f83e27d2fac311a5ca78e9bf11a9a1638b82469870d5c854c4e7afaa26a",
    )

    conflicts("platform=darwin")
    conflicts("platform=windows")

    def install(self, spec, prefix):
        # Already unpacked by Spack at stage time (pre-sandbox). Spack strips the
        # single top-level "include/" dir, so the headers sit directly in the
        # source path (./asm, ./linux, ...); copy them into <prefix>/include.
        # install_tree creates writable destination dirs, so the read-only modes
        # in the seed tarball don't carry over to the prefix.
        install_tree(".", prefix.include)

    def setup_dependent_build_environment(self, env, dependent_spec):
        env.prepend_path("C_INCLUDE_PATH", self.prefix.include)
