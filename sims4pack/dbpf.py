"""Leitura/escrita mínima de pacotes DBPF 2.1 (.package) do The Sims 4.

Escrita: todos os recursos comprimidos com zlib (tipo 0x5A42), índice sem campos
constantes. Leitura: suficiente para inspecionar e testar o que geramos (e
pacotes comuns de mods), suportando zlib e recursos não comprimidos.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

HEADER_SIZE = 96
COMPRESSION_NONE = 0x0000
COMPRESSION_ZLIB = 0x5A42
COMPRESSION_DELETED = 0xFFE0


@dataclass(frozen=True, order=True)
class ResourceKey:
    type: int
    group: int
    instance: int

    def __str__(self) -> str:
        return f"{self.type:08X}:{self.group:08X}:{self.instance:016X}"


def write_package(path: str, resources: Iterable[Tuple[ResourceKey, bytes]]) -> None:
    items = list(resources)
    keys = [k for k, _ in items]
    if len(keys) != len(set(keys)):
        dupes = sorted({str(k) for k in keys if keys.count(k) > 1})
        raise ValueError(f"Chaves de recurso duplicadas: {dupes}")

    body = bytearray(HEADER_SIZE)
    entries = []
    for key, data in items:
        stored = zlib.compress(data, 9)
        offset = len(body)
        body += stored
        entries.append((key, offset, len(stored), len(data)))

    index = bytearray(struct.pack("<I", 0))  # flags: nenhum campo constante
    for key, offset, file_size, mem_size in entries:
        index += struct.pack(
            "<IIIIIIIHH",
            key.type,
            key.group,
            (key.instance >> 32) & 0xFFFFFFFF,
            key.instance & 0xFFFFFFFF,
            offset,
            file_size | 0x80000000,  # bit alto: entrada tem tipo de compressão
            mem_size,
            COMPRESSION_ZLIB,
            1,  # committed
        )
    index_offset = len(body)
    body += index

    struct.pack_into("<4sII", body, 0, b"DBPF", 2, 1)
    struct.pack_into("<I", body, 36, len(entries))
    struct.pack_into("<I", body, 44, len(index))
    struct.pack_into("<I", body, 60, 3)  # versão menor do índice
    struct.pack_into("<I", body, 64, index_offset)

    with open(path, "wb") as fh:
        fh.write(bytes(body))


def read_package(path: str) -> Dict[ResourceKey, bytes]:
    with open(path, "rb") as fh:
        raw = fh.read()
    return parse_package(raw)


def parse_package(raw: bytes) -> Dict[ResourceKey, bytes]:
    magic, major, minor = struct.unpack_from("<4sII", raw, 0)
    if magic != b"DBPF" or (major, minor) != (2, 1):
        raise ValueError(f"Não é um DBPF 2.1 (magic={magic!r}, versão={major}.{minor})")
    count = struct.unpack_from("<I", raw, 36)[0]
    index_offset = struct.unpack_from("<I", raw, 64)[0] or struct.unpack_from("<I", raw, 40)[0]

    pos = index_offset
    flags = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    const = {}
    for bit, name in ((0, "type"), (1, "group"), (2, "inst_hi")):
        if flags & (1 << bit):
            const[name] = struct.unpack_from("<I", raw, pos)[0]
            pos += 4

    out: Dict[ResourceKey, bytes] = {}
    for _ in range(count):
        fields: List[int] = []
        for name in ("type", "group", "inst_hi"):
            if name in const:
                fields.append(const[name])
            else:
                fields.append(struct.unpack_from("<I", raw, pos)[0])
                pos += 4
        inst_lo, offset, file_size, mem_size = struct.unpack_from("<IIII", raw, pos)
        pos += 16
        compression = COMPRESSION_NONE
        if file_size & 0x80000000:
            compression, _committed = struct.unpack_from("<HH", raw, pos)
            pos += 4
        file_size &= 0x7FFFFFFF
        if compression == COMPRESSION_DELETED:
            continue
        blob = raw[offset : offset + file_size]
        if compression == COMPRESSION_ZLIB:
            data = zlib.decompress(blob)
        elif compression == COMPRESSION_NONE:
            data = blob
        else:
            raise ValueError(f"Compressão 0x{compression:04X} não suportada")
        if len(data) != mem_size:
            raise ValueError("Tamanho descomprimido não confere")
        key = ResourceKey(fields[0], fields[1], (fields[2] << 32) | inst_lo)
        out[key] = data
    return out
