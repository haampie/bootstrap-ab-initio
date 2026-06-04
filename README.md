# bootstrap

This Spack package repository grows a current C/C++ toolchain (GCC 16.1.0 with
glibc 2.43 and binutils 2.46) from a single small binary seed, with no
pre-existing compiler, climbing libc tiers from mes libc to musl libc to glibc.

After registering the package repo, just run `spack -e . install`.

The `spack.yaml` below is not committed; it is an example environment. Copy it,
adjust the absolute paths to your machine, and use it as your environment file.
The `config:sandbox:allow_read` list (the host text/file utilities the build
systems invoke, plus their `ldd` shared-library closure) is specific to one
Ubuntu 24.04 machine and must be regenerated for yours; no host C/C++ compiler
is listed, by design.

```yaml
spack:
  specs:
  - bootstrap-gcc-final
  view: false
  concretizer:
    unify: true
  config:
    sandbox:
      enable: true
      allow_network: false
      allow_read:
      - /bin/sh
      - /dev/urandom
      - /path/to/spack-packages/repos/spack_repo/builtin
      - /path/to/bootstrap-ab-initio/spack_repo/bootstrap
      - /path/to/spack/etc  # needs a spack bug fix to be dropped
      - /proc
      # coreutils
      - /usr/bin/arch
      - /usr/bin/basename
      - /usr/bin/cat
      - /usr/bin/chmod
      - /usr/bin/comm
      - /usr/bin/cp
      - /usr/bin/cut
      - /usr/bin/date
      - /usr/bin/dirname
      - /usr/bin/echo
      - /usr/bin/env
      - /usr/bin/expr
      - /usr/bin/head
      - /usr/bin/install
      - /usr/bin/ln
      - /usr/bin/ls
      - /usr/bin/mkdir
      - /usr/bin/mktemp
      - /usr/bin/mv
      - /usr/bin/od
      - /usr/bin/printf
      - /usr/bin/readlink
      - /usr/bin/rm
      - /usr/bin/rmdir
      - /usr/bin/sleep
      - /usr/bin/sort
      - /usr/bin/tail
      - /usr/bin/touch
      - /usr/bin/tr
      - /usr/bin/true
      - /usr/bin/uname
      - /usr/bin/uniq
      - /usr/bin/wc
      # diffutils (todo: remove)
      - /usr/bin/cmp
      - /usr/bin/diff
      # findutils (todo: remove)
      - /usr/bin/find
      - /usr/bin/xargs
      # gawk (todo: remove)
      - /usr/bin/gawk
      # grep (todo: remove)
      - /usr/bin/grep
      # gzip (todo: remove)
      - /usr/bin/gzip
      # sed (todo: remove)
      - /usr/bin/sed
      # tar (todo: remove)
      - /usr/bin/tar
      # libc libs
      - /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2
      - /usr/lib/x86_64-linux-gnu/libc.so.6
      - /usr/lib/x86_64-linux-gnu/libm.so.6
      # shared libs of executables above (from ldd output)
      - /usr/lib/x86_64-linux-gnu/libacl.so.1
      - /usr/lib/x86_64-linux-gnu/libattr.so.1
      - /usr/lib/x86_64-linux-gnu/libcrypto.so.3
      - /usr/lib/x86_64-linux-gnu/libgmp.so.10
      - /usr/lib/x86_64-linux-gnu/libmpfr.so.6
      - /usr/lib/x86_64-linux-gnu/libpcre2-8.so.0
      - /usr/lib/x86_64-linux-gnu/libreadline.so.8
      - /usr/lib/x86_64-linux-gnu/libselinux.so.1
      - /usr/lib/x86_64-linux-gnu/libsigsegv.so.2
      - /usr/lib/x86_64-linux-gnu/libtinfo.so.6
    install_tree:
      root: ./stuff
  repos:
    bootstrap: /path/to/bootstrap-ab-initio/spack_repo/bootstrap
```
