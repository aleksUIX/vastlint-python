Place release shared libraries here before publishing the wheel.

Expected layout:

- darwin_arm64/libvastlint.dylib
- darwin_amd64/libvastlint.dylib
- linux_arm64/libvastlint.so
- linux_amd64/libvastlint.so

Use ../../../scripts/fetch-libs.sh to download the platform tarballs from a tagged vastlint GitHub Release and copy the shared libraries into this directory.
