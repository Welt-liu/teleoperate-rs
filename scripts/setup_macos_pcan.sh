#!/usr/bin/env bash
set -euo pipefail

# Install / repair MacCAN PCBUSB so motorbridge can dlopen the bare name PCBUSB.
#   ./scripts/setup_macos_pcan.sh
#   ./scripts/setup_macos_pcan.sh --install
#   ./scripts/setup_macos_pcan.sh --user-local
#
# --install     download the tarball and run sudo ./install.sh into /usr/local
# --user-local  copy the library into ~/.local/lib (no sudo)
# default       only create the PCBUSB symlink + conda DYLD_FALLBACK script

usage() {
  cat <<'USAGE'
Configure macOS PCAN runtime for teleoperate-rs / motorbridge.

  ./scripts/setup_macos_pcan.sh              # symlink + conda activate.d
  ./scripts/setup_macos_pcan.sh --install    # sudo install.sh then the above
  ./scripts/setup_macos_pcan.sh --user-local # ~/.local/lib, no sudo

motorbridge dlopens the bare name PCBUSB, not libPCBUSB.dylib.
Do not use ctypes.CDLL('libPCBUSB.dylib') as a readiness check.
USAGE
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: 只支持 macOS" >&2
  exit 1
fi

mode="link"
archive_url="https://raw.githubusercontent.com/tianrking/motorbridge/main/third_party/pcan/macos/macOS_Library_for_PCANUSB_v0.13.tar.gz"
user_prefix="${HOME}/.local"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      mode="install"
      shift
      ;;
    --user-local)
      mode="user"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

extract_pcbusb() {
  local tmpdir="$1"
  local archive="$2"
  tar -xzf "$archive" -C "$tmpdir"
  if [[ -d "$tmpdir/PCBUSB" ]]; then
    echo "$tmpdir/PCBUSB"
    return
  fi
  local maybe
  maybe="$(find "$tmpdir" -maxdepth 2 -type d -name PCBUSB | head -n1 || true)"
  if [[ -z "$maybe" ]]; then
    echo "error: 解压后找不到 PCBUSB 目录" >&2
    exit 1
  fi
  echo "$maybe"
}

download_archive() {
  local dest="$1"
  echo "[pcan] download ${archive_url}"
  curl -L -o "$dest" "$archive_url"
}

ensure_symlink() {
  local lib_dir="$1"
  local dylib="${lib_dir}/libPCBUSB.dylib"
  local soname="${lib_dir}/PCBUSB"
  if [[ ! -e "$dylib" ]]; then
    echo "error: 未找到 ${dylib}" >&2
    echo "install.sh 只会安装 libPCBUSB.dylib。请先 --install 或 --user-local。" >&2
    exit 1
  fi
  if [[ "$lib_dir" == "/usr/local/lib" ]]; then
    if [[ ! -e "$soname" ]]; then
      echo "[pcan] sudo ln -sf ${dylib} ${soname}"
      sudo ln -sf "$dylib" "$soname"
    fi
  else
    ln -sf "$dylib" "$soname"
  fi
  echo "[pcan] soname: ${soname} -> $(readlink "$soname" 2>/dev/null || echo "$dylib")"
}

write_conda_fallback() {
  local lib_dir="$1"
  if [[ -z "${CONDA_PREFIX:-}" ]]; then
    echo "[pcan] 当前不在 conda 环境里。激活 teleoperate-rs 后再跑一次本脚本，才会写入 activate.d。"
    echo "[pcan] 或手动:"
    echo "  mkdir -p \"\$CONDA_PREFIX/etc/conda/activate.d\""
    echo "  echo 'export DYLD_FALLBACK_LIBRARY_PATH=\"${lib_dir}\${DYLD_FALLBACK_LIBRARY_PATH:+:\$DYLD_FALLBACK_LIBRARY_PATH}\"' \\"
    echo "    > \"\$CONDA_PREFIX/etc/conda/activate.d/pcbusb_dyld.sh\""
    return
  fi
  local activate_dir="${CONDA_PREFIX}/etc/conda/activate.d"
  mkdir -p "$activate_dir"
  cat > "${activate_dir}/pcbusb_dyld.sh" <<EOF
# motorbridge dlopens PCBUSB; keep /usr/local/lib (or ~/.local/lib) on dyld fallback.
# Do not use DYLD_LIBRARY_PATH: it replaces the process search order.
export DYLD_FALLBACK_LIBRARY_PATH="${lib_dir}\${DYLD_FALLBACK_LIBRARY_PATH:+:\$DYLD_FALLBACK_LIBRARY_PATH}"
EOF
  echo "[pcan] wrote ${activate_dir}/pcbusb_dyld.sh"
  echo "[pcan] 重新激活后生效: conda deactivate && conda activate $(basename "$CONDA_PREFIX")"
}

if [[ "$mode" == "install" ]]; then
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT
  archive="${tmpdir}/macOS_Library_for_PCANUSB_v0.13.tar.gz"
  download_archive "$archive"
  pkg_dir="$(extract_pcbusb "$tmpdir" "$archive")"
  if [[ ! -x "${pkg_dir}/install.sh" ]]; then
    echo "error: 包里没有 install.sh" >&2
    exit 1
  fi
  echo "[pcan] sudo ${pkg_dir}/install.sh"
  sudo "${pkg_dir}/install.sh"
  ensure_symlink "/usr/local/lib"
  write_conda_fallback "/usr/local/lib"
elif [[ "$mode" == "user" ]]; then
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT
  archive="${tmpdir}/macOS_Library_for_PCANUSB_v0.13.tar.gz"
  download_archive "$archive"
  pkg_dir="$(extract_pcbusb "$tmpdir" "$archive")"
  mkdir -p "${user_prefix}/lib" "${user_prefix}/include"
  dylib_versioned="$(find "$pkg_dir" -maxdepth 1 -type f -name 'libPCBUSB.*.dylib' | sort -V | tail -n1 || true)"
  if [[ -z "$dylib_versioned" ]]; then
    echo "error: 包里没有 libPCBUSB.*.dylib" >&2
    exit 1
  fi
  cp -f "$dylib_versioned" "${user_prefix}/lib/"
  dylib_base="$(basename "$dylib_versioned")"
  ln -sf "${user_prefix}/lib/${dylib_base}" "${user_prefix}/lib/libPCBUSB.dylib"
  if [[ -f "${pkg_dir}/PCBUSB.h" ]]; then
    cp -f "${pkg_dir}/PCBUSB.h" "${user_prefix}/include/PCBUSB.h"
  fi
  ensure_symlink "${user_prefix}/lib"
  write_conda_fallback "${user_prefix}/lib"
else
  lib_dir="/usr/local/lib"
  if [[ ! -e "${lib_dir}/libPCBUSB.dylib" && -e "${user_prefix}/lib/libPCBUSB.dylib" ]]; then
    lib_dir="${user_prefix}/lib"
  fi
  if [[ ! -e "${lib_dir}/libPCBUSB.dylib" ]]; then
    echo "error: 找不到 libPCBUSB.dylib。请先安装 PCBUSB：" >&2
    echo "  ./scripts/setup_macos_pcan.sh --install" >&2
    echo "  或无需 sudo: ./scripts/setup_macos_pcan.sh --user-local" >&2
    exit 1
  fi
  ensure_symlink "$lib_dir"
  write_conda_fallback "$lib_dir"
fi

echo
echo "[pcan] 检查是否就绪（先插入 PCAN 适配器）:"
echo "  echo \$DYLD_FALLBACK_LIBRARY_PATH"
echo "  python -m teleoperate_rs ports"
echo "不要用 ctypes.CDLL('libPCBUSB.dylib')；motorbridge 加载的是 PCBUSB。"
