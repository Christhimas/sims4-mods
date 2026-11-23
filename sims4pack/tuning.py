"""Processamento de tuning XML com placeholders.

Placeholders aceitos nos arquivos de `tuning/`:
  {{id}}            -> ID de instância deste tuning (decimal), use em s="{{id}}"
  {{tuning:Nome}}   -> ID de outro tuning DESTE mod (pelo atributo n)
  {{str:chave}}     -> 0xHASH<!--texto EN--> da chave em strings/en_us.json
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .fnv import tuning_instance_id

# Atributo i="..." da raiz -> tipo de recurso. Adicione conforme precisar
# (conferindo o tipo no Sims 4 Studio).
TUNING_TYPES: Dict[str, int] = {
    "interaction": 0xE882D22F,
    "snippet": 0x7DF2169C,
    "buff": 0x6017E896,
    "action": 0x0C772E27,  # loots
    "trait": 0xCB5FDDC7,
}

_ROOT_NAME = re.compile(r'<I\b[^>]*\bn="([^"]+)"')
_PLACEHOLDER = re.compile(r"\{\{\s*(id|tuning:[^}\s]+|str:[^}\s]+)\s*\}\}")
LINT_MARKERS = ("VALIDAR", "TODO")


@dataclass
class TuningResource:
    name: str
    type: int
    instance: int
    xml: bytes
    source: Path


class TuningError(Exception):
    pass


def _xml_comment(text: str) -> str:
    return "<!--" + text.replace("--", "- -").rstrip("-") + "-->"


def scan_names(paths: List[Path]) -> Dict[str, int]:
    names: Dict[str, int] = {}
    for p in paths:
        m = _ROOT_NAME.search(p.read_text(encoding="utf-8"))
        if not m:
            raise TuningError(f"{p.name}: raiz <I ... n=\"...\"> não encontrada")
        name = m.group(1)
        if name in names:
            raise TuningError(f"Nome de tuning duplicado: {name}")
        names[name] = tuning_instance_id(name)
    return names


def render(path: Path, ids: Dict[str, int], string_hashes: Dict[str, int],
           en_strings: Dict[str, str]) -> TuningResource:
    text = path.read_text(encoding="utf-8")
    name = _ROOT_NAME.search(text).group(1)
    own_id = ids[name]

    def sub(m: "re.Match[str]") -> str:
        token = m.group(1)
        if token == "id":
            return str(own_id)
        kind, _, arg = token.partition(":")
        if kind == "tuning":
            if arg not in ids:
                raise TuningError(f"{path.name}: tuning '{arg}' não existe neste mod")
            return str(ids[arg])
        if arg not in string_hashes:
            raise TuningError(f"{path.name}: string '{arg}' não existe em en_us.json")
        return f"0x{string_hashes[arg]:08X}{_xml_comment(en_strings[arg])}"

    rendered = _PLACEHOLDER.sub(sub, text)
    leftover = re.search(r"\{\{[^}]*\}\}", rendered)
    if leftover:
        raise TuningError(f"{path.name}: placeholder inválido {leftover.group(0)}")

    try:
        root = ET.fromstring(rendered.encode("utf-8"))
    except ET.ParseError as exc:
        raise TuningError(f"{path.name}: XML inválido: {exc}") from exc
    if root.tag != "I":
        raise TuningError(f"{path.name}: raiz deve ser <I>")
    kind = root.get("i")
    if kind not in TUNING_TYPES:
        raise TuningError(f"{path.name}: i=\"{kind}\" sem tipo mapeado em TUNING_TYPES")
    if root.get("s") != str(own_id):
        raise TuningError(f"{path.name}: use s=\"{{{{id}}}}\" na raiz")

    return TuningResource(name, TUNING_TYPES[kind], own_id, rendered.encode("utf-8"), path)


def lint(path: Path) -> List[str]:
    problems = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for marker in LINT_MARKERS:
            if marker in line:
                problems.append(f"{path}:{lineno}: contém '{marker}'")
    return problems
