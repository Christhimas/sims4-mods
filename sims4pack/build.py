"""Pipeline de build: tuning + STBL -> .package, scripts -> .ts4script."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import dbpf, stbl, tuning
from .fnv import string_key

REPO_ROOT = Path(__file__).resolve().parent.parent

# Cabeçalho (magic) dos .pyc por versão. O build recusa .pyc de outra versão.
PYC_MAGIC = {"3.7": bytes.fromhex("420d0d0a")}

_FORMAT_TOKEN = re.compile(r"\{[^{}]*\}")


class BuildError(Exception):
    pass


@dataclass
class Mod:
    path: Path
    id: str
    title: str
    version: str
    package_name: str
    script_package: Optional[str]
    game_python: str
    warnings: List[str] = field(default_factory=list)

    @property
    def build_dir(self) -> Path:
        return REPO_ROOT / "build" / self.package_name


def load_mod(mod_id: str) -> Mod:
    repo_cfg = json.loads((REPO_ROOT / "sims4mods.json").read_text(encoding="utf-8"))
    mod_dir = REPO_ROOT / "mods" / mod_id
    cfg_path = mod_dir / "mod.json"
    if not cfg_path.exists():
        raise BuildError(f"Mod '{mod_id}' não encontrado ({cfg_path})")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return Mod(
        path=mod_dir,
        id=cfg["id"],
        title=cfg["title"],
        version=cfg["version"],
        package_name=cfg["package_name"],
        script_package=cfg.get("script_package"),
        game_python=repo_cfg["game_python"],
    )


# ---------------------------------------------------------------- strings

def load_strings(mod: Mod, release: bool) -> Dict[str, Dict[str, str]]:
    sdir = mod.path / "strings"
    tables: Dict[str, Dict[str, str]] = {}
    for f in sorted(sdir.glob("*.json")):
        locale = f.stem
        if locale not in stbl.LOCALES:
            raise BuildError(f"{f.name}: idioma desconhecido (veja stbl.LOCALES)")
        tables[locale] = json.loads(f.read_text(encoding="utf-8"))
    if "en_us" not in tables:
        raise BuildError("strings/en_us.json é obrigatório (é o fallback de todos os idiomas)")

    en = tables["en_us"]
    for locale, table in tables.items():
        extra = set(table) - set(en)
        if extra:
            raise BuildError(f"{locale}: chaves que não existem em en_us: {sorted(extra)}")
        for key, text in table.items():
            if sorted(_FORMAT_TOKEN.findall(text)) != sorted(_FORMAT_TOKEN.findall(en[key])):
                raise BuildError(f"{locale}.{key}: tokens {{...}} diferentes do en_us")

    missing = sorted(set(en) - set(tables.get("pt_br", {})))
    if missing:
        msg = f"pt_br sem tradução para: {missing}"
        if release:
            raise BuildError(msg + " (tradução PT-BR completa é obrigatória no release)")
        mod.warnings.append(msg)
    return tables


def build_stbls(mod: Mod, tables: Dict[str, Dict[str, str]], hashes: Dict[str, int]):
    table_name = f"{mod.package_name}:strings"
    en = tables["en_us"]
    for locale in stbl.LOCALES:
        merged = dict(en)
        merged.update(tables.get(locale, {}))
        data = stbl.build_stbl({hashes[k]: v for k, v in merged.items()})
        key = dbpf.ResourceKey(stbl.STBL_TYPE, stbl.STBL_GROUP, stbl.stbl_instance(table_name, locale))
        yield key, data


# ---------------------------------------------------------------- scripts

def find_game_python(version: str) -> List[str]:
    env = os.environ.get("SIMS4_PYTHON")
    if env:
        return [env]
    exe = shutil.which(f"python{version}")
    if exe:
        return [exe]
    if sys.platform == "win32" and shutil.which("py"):
        return ["py", f"-{version}"]
    raise BuildError(
        f"Python {version} (versão do jogo) não encontrado. Defina SIMS4_PYTHON com o caminho "
        f"do interpretador {version}, ou use --no-scripts para buildar só o .package."
    )


def git_describe() -> str:
    """Commit curto + '-sujo' se houver mudanças; 'sem-git' se não der para saber."""
    git = os.environ.get("GIT") or shutil.which("git")
    if not git:
        return "sem-git"
    try:
        run = lambda *a: subprocess.run([git, *a], cwd=REPO_ROOT, capture_output=True,
                                        text=True, check=True).stdout.strip()
        commit = run("rev-parse", "--short", "HEAD")
        dirty = run("status", "--porcelain", "--untracked-files=no")
        return commit + ("-sujo" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "sem-git"


def compile_scripts(mod: Mod, ids: Dict[str, int], hashes: Dict[str, int], out: Path) -> None:
    src = mod.path / "scripts"
    if not mod.script_package or not (src / mod.script_package).is_dir():
        raise BuildError(f"scripts/{mod.script_package}/ não encontrado")

    py = find_game_python(mod.game_python)
    got = subprocess.run(py + ["-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                         capture_output=True, text=True, check=True).stdout.strip()
    if got != mod.game_python:
        raise BuildError(f"Interpretador é Python {got}, mas o jogo usa {mod.game_python}")

    stage = REPO_ROOT / "build" / "_stage" / mod.package_name
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(src, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    generated = stage / mod.script_package / "_generated.py"
    generated.write_text(
        "# Gerado pelo build. Não editar.\n"
        f"MOD_ID = {mod.id!r}\nVERSION = {mod.version!r}\n"
        f"BUILD_TIME = {time.strftime('%Y-%m-%d %H:%M:%S')!r}\n"
        f"GIT_COMMIT = {git_describe()!r}\n"
        f"TUNING_IDS = {json.dumps(ids, indent=4, sort_keys=True)}\n"
        f"STRING_KEYS = {json.dumps(hashes, indent=4, sort_keys=True)}\n",
        encoding="utf-8",
    )

    subprocess.run(py + ["-m", "compileall", "-b", "-f", "-q", str(stage)], check=True)

    pycs = sorted(stage.rglob("*.pyc"))
    if not pycs:
        raise BuildError("Nenhum .pyc gerado")
    expected = PYC_MAGIC.get(mod.game_python)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for pyc in pycs:
            header = pyc.read_bytes()[:4]
            if expected and header != expected:
                raise BuildError(f"{pyc.name}: .pyc não é de Python {mod.game_python}")
            zf.write(pyc, pyc.relative_to(stage).as_posix())


# ---------------------------------------------------------------- build

def build(mod_id: str, release: bool = False, scripts: bool = True) -> Mod:
    mod = load_mod(mod_id)
    if release and not scripts:
        raise BuildError("--no-scripts não é permitido em release")

    tables = load_strings(mod, release)
    hashes = {k: string_key(f"{mod.id}:{k}") for k in tables["en_us"]}
    if len(set(hashes.values())) != len(hashes):
        raise BuildError("Colisão de hash entre chaves de string; renomeie uma chave")

    tuning_files = sorted((mod.path / "tuning").glob("*.xml"))
    if release:
        problems = []
        for f in tuning_files + sorted((mod.path / "scripts").rglob("*.py")):
            problems += tuning.lint(f)
        if problems:
            raise BuildError("Marcadores pendentes (release bloqueado):\n  " + "\n  ".join(problems))

    ids = tuning.scan_names(tuning_files)
    resources = []
    for f in tuning_files:
        res = tuning.render(f, ids, hashes, tables["en_us"])
        resources.append((dbpf.ResourceKey(res.type, 0, res.instance), res.xml))
    resources += list(build_stbls(mod, tables, hashes))

    out = mod.build_dir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    dbpf.write_package(str(out / f"{mod.package_name}.package"), resources)
    if scripts:
        compile_scripts(mod, ids, hashes, out / f"{mod.package_name}.ts4script")
    else:
        mod.warnings.append("scripts NÃO compilados (--no-scripts)")
    return mod


def default_mods_dir() -> Path:
    env = os.environ.get("SIMS4_MODS_DIR")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "Electronic Arts" / "The Sims 4" / "Mods"


def install(mod: Mod, mods_dir: Path) -> Path:
    if not mods_dir.is_dir():
        raise BuildError(f"Pasta Mods não existe: {mods_dir} (defina SIMS4_MODS_DIR)")
    target = mods_dir / mod.package_name
    target.mkdir(exist_ok=True)
    built = {f.name for f in mod.build_dir.iterdir()}
    for old in target.iterdir():
        # Preserva logs de testes anteriores; remove o resto que não veio do build.
        if old.name not in built and not old.name.endswith((".log", ".log.old")):
            shutil.rmtree(old) if old.is_dir() else old.unlink()
    for f in mod.build_dir.iterdir():
        shutil.copy2(f, target / f.name)
    return target


def make_release_zip(mod: Mod) -> Path:
    dist = REPO_ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zpath = dist / f"{mod.package_name}_v{mod.version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(mod.build_dir.iterdir()):
            zf.write(f, f"{mod.package_name}/{f.name}")
    return zpath
