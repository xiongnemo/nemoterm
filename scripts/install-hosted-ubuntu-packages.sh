#!/bin/bash
# Only for the disposable Ubuntu 24.04 environments configured in Actions.
set -eu
case "$1" in
  busybox-build) pkgs=(gcc-mingw-w64-x86-64) ;;
  sixel) pkgs=(libsixel-bin) ;;
  tmux-vim) pkgs=(vim tmux ncurses-term) ;;
  vim) pkgs=(vim) ;;
  colour) pkgs=(ncurses-term) ;;
  paste-quote) pkgs=(python3) ;;
  pager) pkgs=(less) ;;
  *) exit 64 ;;
esac
. /etc/os-release
[[ "$ID:$VERSION_CODENAME:$(dpkg --print-architecture)" == ubuntu:noble:amd64 ]]
installed() {
    local p state
    for p in "${pkgs[@]}"; do
        state=$(dpkg-query -W -f='${Status}' "$p" 2>/dev/null) || return 1
        [[ "$state" == 'install ok installed' ]] || return 1
    done
}
receipt() { dpkg-query -W -f='${Package} ${Version} ${Architecture} ${Status}\n' "${pkgs[@]}"; }
if installed; then echo 'Required packages already installed'; receipt; exit 0; fi
export DEBIAN_FRONTEND=noninteractive
sources=$(mktemp --suffix=.list)
trap 'rm -f "$sources"' EXIT
for mirror in https://archive.ubuntu.com/ubuntu https://azure.archive.ubuntu.com/ubuntu; do
    printf 'Using %s on %s for %s\n' "$mirror" "$VERSION_CODENAME" "${pkgs[*]}"
    for suite in noble noble-updates noble-security; do
        printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] %s %s main universe\n' "$mirror" "$suite"
    done > "$sources"
    opts=(-o Dir::Etc::sourcelist="$sources" -o Dir::Etc::sourceparts=- -o Acquire::Languages=none -o Acquire::ForceIPv4=true -o Acquire::https::Timeout=12 -o Acquire::Retries=1)
    if apt-get "${opts[@]}" -o APT::Update::Error-Mode=any update && apt-get "${opts[@]}" -y --no-install-recommends install "${pkgs[@]}" && installed; then receipt; exit 0; fi
    echo "Package fetch/install failed using $mirror" >&2
done
exit 1
