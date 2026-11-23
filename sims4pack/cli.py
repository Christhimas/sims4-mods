"""CLI: python -m sims4pack <comando> ..."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import build as b
from . import dbpf, stbl


def cmd_build(args) -> int:
    mod = b.build(args.mod, release=args.release, scripts=not args.no_scripts)
    for w in mod.warnings:
        print(f"AVISO: {w}")
    print(f"OK: {mod.build_dir}")
    if args.install:
        target = b.install(mod, Path(args.mods_dir) if args.mods_dir else b.default_mods_dir())
        print(f"Instalado em: {target}")
    if args.release:
        print(f"Release: {b.make_release_zip(mod)}")
    return 0


def cmd_inspect(args) -> int:
    res = dbpf.read_package(args.package)
    for key, data in sorted(res.items()):
        label = ""
        if key.type == stbl.STBL_TYPE:
            label = f"STBL {len(stbl.parse_stbl(data))} strings, idioma 0x{key.instance >> 56:02X}"
        elif data.lstrip().startswith(b"<?xml"):
            m = re.search(rb"<I\b[^>]*>", data)
            label = "XML " + (m.group(0)[:100].decode("utf-8", "replace") if m else "?")
        print(f"{key}  {len(data):7d} B  {label}")
    return 0


def cmd_lastexc(args) -> int:
    root = b.default_mods_dir().parent
    files = sorted(root.glob("lastException*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    files += sorted(b.default_mods_dir().rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print(f"Nenhum lastException*.txt ou .log em {root}")
        return 0
    for f in files[: args.n]:
        print(f"===== {f}")
        print(f.read_text(encoding="utf-8", errors="replace")[-args.chars:])
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sims4pack")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="builda um mod de mods/<id>")
    pb.add_argument("mod")
    pb.add_argument("--install", action="store_true", help="copia para a pasta Mods")
    pb.add_argument("--mods-dir", help="pasta Mods (padrão: SIMS4_MODS_DIR ou Documents)")
    pb.add_argument("--release", action="store_true", help="checagens estritas + zip em dist/")
    pb.add_argument("--no-scripts", action="store_true", help="pula o .ts4script (só dev)")
    pb.set_defaults(func=cmd_build)

    pi = sub.add_parser("inspect", help="lista recursos de um .package")
    pi.add_argument("package")
    pi.set_defaults(func=cmd_inspect)

    pl = sub.add_parser("lastexc", help="mostra lastException*.txt e logs dos mods")
    pl.add_argument("-n", type=int, default=3)
    pl.add_argument("--chars", type=int, default=4000)
    pl.set_defaults(func=cmd_lastexc)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (b.BuildError, b.tuning.TuningError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
