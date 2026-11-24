import json
import tempfile
import unittest
from pathlib import Path

from sims4pack import dbpf, stbl, tuning
from sims4pack.fnv import HIGH_BIT_64, fnv32, fnv64, tuning_instance_id


class FnvTest(unittest.TestCase):
    def test_known_vectors(self):
        self.assertEqual(fnv32(""), 0x811C9DC5)
        self.assertEqual(fnv32("a"), 0x050C5D7E)
        self.assertEqual(fnv64("a"), 0xAF63BD4C8601B7BE)

    def test_case_insensitive_and_high_bit(self):
        self.assertEqual(fnv64("ABC"), fnv64("abc"))
        self.assertTrue(tuning_instance_id("x") & HIGH_BIT_64)


class StblTest(unittest.TestCase):
    def test_roundtrip_utf8(self):
        entries = {0x1234: "Fofocar sobre a Novela", 0xBEEF: "Ação, coração {0.SimFirstName}"}
        self.assertEqual(stbl.parse_stbl(stbl.build_stbl(entries)), entries)

    def test_locale_in_high_byte(self):
        self.assertEqual(stbl.stbl_instance("t", "pt_br") >> 56, 0x11)
        self.assertEqual(stbl.stbl_instance("t", "en_us") >> 56, 0x00)


class DbpfTest(unittest.TestCase):
    def test_roundtrip(self):
        res = {
            dbpf.ResourceKey(0xE882D22F, 0, 0x8000000000000001): b"<I/>" * 50,
            dbpf.ResourceKey(stbl.STBL_TYPE, stbl.STBL_GROUP, 0x1100000000000002): b"x",
        }
        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "t.package")
            dbpf.write_package(p, res.items())
            raw = Path(p).read_bytes()
            self.assertEqual(raw[:4], b"DBPF")
            self.assertEqual(dbpf.read_package(p), res)

    def test_duplicate_keys_rejected(self):
        k = dbpf.ResourceKey(1, 2, 3)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                dbpf.write_package(str(Path(d) / "t.package"), [(k, b"a"), (k, b"b")])


class TuningTest(unittest.TestCase):
    XML = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<I c="X" i="interaction" m="m" n="me_A" s="{{id}}">\n'
           '  <T n="display_name">{{str:name}}</T>\n'
           '  <T n="other">{{tuning:me_A}}</T>\n</I>\n')

    def test_render(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "A.xml"
            p.write_text(self.XML, encoding="utf-8")
            ids = tuning.scan_names([p])
            res = tuning.render(p, ids, {"name": 0xABCDEF01}, {"name": "Hi -- there"})
            xml = res.xml.decode()
            self.assertIn(f's="{ids["me_A"]}"', xml)
            self.assertIn("0xABCDEF01<!--Hi - - there-->", xml)
            self.assertEqual(res.type, 0xE882D22F)

    def test_unknown_string_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "A.xml"
            p.write_text(self.XML, encoding="utf-8")
            with self.assertRaises(tuning.TuningError):
                tuning.render(p, tuning.scan_names([p]), {}, {})


class ExampleModTest(unittest.TestCase):
    def test_example_mod_builds_package(self):
        from sims4pack import build as b
        mod = b.build("novela_fofoca", scripts=False)
        pkg = dbpf.read_package(str(mod.build_dir / f"{mod.package_name}.package"))
        stbls = {k: v for k, v in pkg.items() if k.type == stbl.STBL_TYPE}
        self.assertEqual(len(stbls), len(stbl.LOCALES))
        pt = next(v for k, v in stbls.items() if k.instance >> 56 == 0x11)
        en_pt = json.loads((mod.path / "strings" / "pt_br.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(stbl.parse_stbl(pt).values()), sorted(en_pt.values()))

    def test_install_keeps_logs(self):
        from sims4pack import build as b
        mod = b.build("novela_fofoca", scripts=False)
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / mod.package_name
            target.mkdir()
            (target / "teste.log").write_text("antigo", encoding="utf-8")
            (target / "lixo.package").write_text("x", encoding="utf-8")
            b.install(mod, Path(d))
            names = sorted(p.name for p in target.iterdir())
            self.assertIn("teste.log", names)
            self.assertNotIn("lixo.package", names)
            self.assertIn(f"{mod.package_name}.package", names)


if __name__ == "__main__":
    unittest.main()
