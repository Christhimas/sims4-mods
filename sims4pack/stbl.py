"""String tables (STBL v5) e códigos de idioma do The Sims 4."""

from __future__ import annotations

import struct
from typing import Dict

from .fnv import fnv64

STBL_TYPE = 0x220557DA
STBL_GROUP = 0x80000000

# Byte alto da instância do STBL = idioma. Conferir no Sims 4 Studio se algo
# não aparecer traduzido no jogo.
LOCALES: Dict[str, int] = {
    "en_us": 0x00,
    "zh_tw": 0x01,
    "zh_cn": 0x02,
    "cs_cz": 0x03,
    "da_dk": 0x04,
    "nl_nl": 0x05,
    "fi_fi": 0x06,
    "fr_fr": 0x07,
    "de_de": 0x08,
    "it_it": 0x0B,
    "ja_jp": 0x0C,
    "ko_kr": 0x0D,
    "no_no": 0x0E,
    "pl_pl": 0x0F,
    "pt_br": 0x11,
    "ru_ru": 0x12,
    "es_es": 0x13,
    "sv_se": 0x15,
}


def stbl_instance(table_name: str, locale: str) -> int:
    return (LOCALES[locale] << 56) | (fnv64(table_name) & 0x00FFFFFFFFFFFFFF)


def build_stbl(entries: Dict[int, str]) -> bytes:
    body = bytearray()
    total = 0
    for key in sorted(entries):
        raw = entries[key].encode("utf-8")
        if len(raw) > 0xFFFF:
            raise ValueError(f"String 0x{key:08X} longa demais")
        body += struct.pack("<IBH", key, 0, len(raw)) + raw
        total += len(raw) + 1
    header = b"STBL" + struct.pack("<HBQHI", 5, 0, len(entries), 0, total)
    return header + bytes(body)


def parse_stbl(data: bytes) -> Dict[int, str]:
    if data[:4] != b"STBL":
        raise ValueError("Não é um STBL")
    version, _compressed, count, _reserved, _total = struct.unpack_from("<HBQHI", data, 4)
    if version != 5:
        raise ValueError(f"STBL versão {version} não suportada")
    pos = 4 + struct.calcsize("<HBQHI")
    out: Dict[int, str] = {}
    for _ in range(count):
        key, _flags, length = struct.unpack_from("<IBH", data, pos)
        pos += 7
        out[key] = data[pos : pos + length].decode("utf-8")
        pos += length
    return out
