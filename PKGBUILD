pkgname=dgt-driving-exams
pkgver=1.0.0
pkgrel=1
pkgdesc="DGT Driving Exams Statistics desktop application"
arch=('x86_64')
license=('custom')
depends=('qt6-base')
makedepends=('python-pip')
options=('!strip' '!debug')
source=('dgt-driving-exams.desktop' 'dgt-driving-exams.png')
sha256sums=('SKIP' 'SKIP')

build() {
  cd "$startdir"
  rm -rf build dist
  if [[ -x "$startdir/venv/bin/pyinstaller" ]]; then
    "$startdir/venv/bin/pyinstaller" --noconfirm --clean --name dgt-driving-exams --windowed main.py
  elif command -v pyinstaller >/dev/null 2>&1; then
    pyinstaller --noconfirm --clean --name dgt-driving-exams --windowed main.py
  else
    echo "pyinstaller not found. Install it in ./venv with: pip install pyinstaller" >&2
    return 1
  fi
}

package() {
  install -dm755 "$pkgdir/opt/dgt-driving-exams"
  cp -a "$startdir/dist/dgt-driving-exams/." "$pkgdir/opt/dgt-driving-exams/"

  install -dm755 "$pkgdir/usr/bin"
  cat > "$pkgdir/usr/bin/dgt-driving-exams" << 'EOF'
#!/bin/sh
exec /opt/dgt-driving-exams/dgt-driving-exams "$@"
EOF
  chmod 755 "$pkgdir/usr/bin/dgt-driving-exams"

  install -Dm644 "$srcdir/dgt-driving-exams.desktop" "$pkgdir/usr/share/applications/dgt-driving-exams.desktop"
  install -Dm644 "$srcdir/dgt-driving-exams.png" "$pkgdir/usr/share/icons/hicolor/256x256/apps/dgt-driving-exams.png"
}
