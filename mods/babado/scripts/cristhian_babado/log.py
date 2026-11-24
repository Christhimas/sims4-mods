"""Log de diagnóstico em arquivo, ao lado do .ts4script na pasta Mods.

Todo teste no jogo deve deixar rastro aqui; leia depois com
`python -m sims4pack lastexc`.
"""

import os
import time
import traceback

_LOG_NAME = "cristhian_babado.log"
_MAX_BYTES = 1024 * 1024


def _log_path():
    path = os.path.abspath(__file__)
    # __file__ fica DENTRO do zip: .../Mods/Pasta/Mod.ts4script/pacote/log.pyc
    while path and not path.lower().endswith(".ts4script"):
        parent = os.path.dirname(path)
        if parent == path:
            return os.path.join(os.path.expanduser("~"), _LOG_NAME)
        path = parent
    return os.path.join(os.path.dirname(path), _LOG_NAME)


LOG_PATH = _log_path()


def _rotate():
    try:
        if os.path.getsize(LOG_PATH) > _MAX_BYTES:
            old = LOG_PATH + ".old"
            if os.path.exists(old):
                os.remove(old)
            os.rename(LOG_PATH, old)
    except OSError:
        pass


def log(msg, level="INFO"):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("{} [{}] {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), level, msg))
    except Exception:
        pass


def log_exception(context):
    log("em {}:\n{}".format(context, traceback.format_exc()), level="ERRO")


def start_session(header):
    _rotate()
    log("=" * 70, level="SESSAO")
    log(header, level="SESSAO")
