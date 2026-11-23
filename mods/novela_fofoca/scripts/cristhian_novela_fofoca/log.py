"""Log simples em arquivo, ao lado do .ts4script na pasta Mods."""

import os
import time
import traceback

_LOG_NAME = "cristhian_novela_fofoca.log"


def _log_path():
    path = os.path.abspath(__file__)
    # __file__ fica DENTRO do zip: .../Mods/Pasta/Mod.ts4script/pacote/log.pyc
    while path and not path.lower().endswith(".ts4script"):
        parent = os.path.dirname(path)
        if parent == path:
            return os.path.join(os.path.expanduser("~"), _LOG_NAME)
        path = parent
    return os.path.join(os.path.dirname(path), _LOG_NAME)


def log(msg):
    try:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write("{} {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def log_exception(context):
    log("ERRO em {}:\n{}".format(context, traceback.format_exc()))
