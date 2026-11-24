"""Extrai tuning XML da EA direto dos arquivos do jogo, SÓ PARA REFERÊNCIA LOCAL.

Lê (somente leitura) o recurso CombinedTuning (0x62E94D38) de
Data/Simulation/SimulationFullBuild0.package, que é um XML onde nós repetidos
ficam num grupo "merged" e são referenciados por <r x="N"/>. Reconstrói cada
instância <I> como o XML individual que o Sims 4 Studio mostraria.

Limitação: o FullBuild é o tuning do jogo base na versão "cheia"; patches mais
recentes ficam no DeltaBuild em formato binário (não suportado aqui). Para
clonar algo, confira no jogo se o comportamento bate.

A saída vai para reference/ (no .gitignore). NUNCA comitar nem redistribuir.
"""

from __future__ import annotations

import copy
import os
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Dict, Iterator, List, Optional

COMBINED_TUNING_TYPE = 0x62E94D38

_STEAM_GUESSES = [
    r"C:\Program Files\EA Games\The Sims 4",
    r"C:\Program Files (x86)\Steam\steamapps\common\The Sims 4",
    "/Applications/The Sims 4.app/Contents",
]


def default_game_dir() -> Optional[Path]:
    env = os.environ.get("SIMS4_GAME_DIR")
    if env:
        return Path(env)
    guesses = list(_STEAM_GUESSES)
    for drive in "CDEFG":
        guesses.append(fr"{drive}:\SteamLibrary\steamapps\common\The Sims 4")
    for g in guesses:
        if (Path(g) / "Data" / "Simulation").is_dir():
            return Path(g)
    return None


def _read_combined_xml(package: Path) -> bytes:
    with open(package, "rb") as fh:
        head = fh.read(96)
        count = struct.unpack_from("<I", head, 36)[0]
        off = struct.unpack_from("<I", head, 64)[0] or struct.unpack_from("<I", head, 40)[0]
        size = struct.unpack_from("<I", head, 44)[0]
        fh.seek(off)
        raw = fh.read(size)
        pos = 0
        flags = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        const = {}
        for bit in range(3):
            if flags & (1 << bit):
                const[bit] = struct.unpack_from("<I", raw, pos)[0]
                pos += 4
        for _ in range(count):
            fields = []
            for bit in range(3):
                if bit in const:
                    fields.append(const[bit])
                else:
                    fields.append(struct.unpack_from("<I", raw, pos)[0])
                    pos += 4
            _il, offset, fsize, _msize = struct.unpack_from("<IIII", raw, pos)
            pos += 16
            comp = 0
            if fsize & 0x80000000:
                comp = struct.unpack_from("<H", raw, pos)[0]
                pos += 4
            if fields[0] != COMBINED_TUNING_TYPE:
                continue
            fh.seek(offset)
            blob = fh.read(fsize & 0x7FFFFFFF)
            data = zlib.decompress(blob) if comp == 0x5A42 else blob
            if not data.startswith(b"<combined"):
                raise ValueError(f"{package.name}: CombinedTuning em formato binário (não suportado)")
            return data
    raise ValueError(f"{package.name}: sem CombinedTuning")


class CombinedTuning:
    def __init__(self, game_dir: Path):
        pkg = game_dir / "Data" / "Simulation" / "SimulationFullBuild0.package"
        root = ET.fromstring(_read_combined_xml(pkg))
        self.shared: Dict[str, ET.Element] = {}
        self.instances: List[ET.Element] = []
        for group in root:
            if group.get("s") == "merged":
                for node in group:
                    self.shared[node.get("x")] = node
            else:
                self.instances.extend(e for e in group.iter("I"))

    def _expand(self, elem: ET.Element) -> ET.Element:
        if elem.tag == "r":
            target = copy.deepcopy(self.shared[elem.get("x")])
            target.attrib.pop("x", None)
            if elem.get("n") is not None:
                target.set("n", elem.get("n"))
            elif "n" in target.attrib:
                del target.attrib["n"]
            return self._expand(target)
        out = ET.Element(elem.tag, {k: v for k, v in elem.attrib.items() if k != "x"})
        out.text, out.tail = elem.text, None
        for child in elem:
            out.append(self._expand(child))
        return out

    def find(self, pattern: str, cls: Optional[str] = None) -> Iterator[ET.Element]:
        rx = re.compile(pattern, re.IGNORECASE)
        for inst in self.instances:
            if rx.search(inst.get("n", "")) and (cls is None or inst.get("c") == cls):
                yield inst

    def by_id(self, instance_id: int) -> Optional[ET.Element]:
        sid = str(instance_id)
        return next((i for i in self.instances if i.get("s") == sid), None)

    def to_xml(self, inst: ET.Element) -> str:
        full = self._expand(inst)
        ET.indent(full, space="  ") if hasattr(ET, "indent") else None
        return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(full, encoding="unicode")
