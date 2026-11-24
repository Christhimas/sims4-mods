"""Babado!: entrada do script. M1 = só detecção + log, sem efeitos no jogo."""

import sys

import sims4.commands
import sims4.resources
from sims4.tuning.instance_manager import InstanceManager

from . import _generated, detect
from .log import LOG_PATH, log, log_exception, start_session

_installed = False
_original_load = InstanceManager.load_data_into_class_instances


def _patched_load(self, *args, **kwargs):
    result = _original_load(self, *args, **kwargs)
    global _installed
    try:
        # OBJECT carrega depois de INTERACTION; neste ponto as interações já existem.
        if self.TYPE == sims4.resources.Types.OBJECT and not _installed:
            _installed = True
            detect.install_hooks()
    except Exception:
        log_exception("install_hooks")
    return result


InstanceManager.load_data_into_class_instances = _patched_load


def _header():
    return "{} v{} build {} ({})".format(
        _generated.MOD_ID, _generated.VERSION, _generated.BUILD_TIME, _generated.GIT_COMMIT)


@sims4.commands.Command("babado.info", command_type=sims4.commands.CommandType.Live)
def _cmd_info(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    lines = [
        _header(),
        "Python {}".format(sys.version.split()[0]),
        "Contadores: {}".format(detect.stats),
        "Config: {}".format(detect.settings),
        "Log: {}".format(LOG_PATH),
    ]
    for line in lines:
        output(line)
    log("babado.info -> " + " | ".join(lines), "TESTE")


@sims4.commands.Command("babado.flerte", command_type=sims4.commands.CommandType.Live)
def _cmd_flerte(value=None, _connection=None):
    output = sims4.commands.CheatOutput(_connection)
    if value in ("on", "off"):
        detect.settings["flerte_conta"] = value == "on"
    output("Flerte conta como traição: {}".format(detect.settings["flerte_conta"]))
    log("babado.flerte {} -> {}".format(value, detect.settings["flerte_conta"]), "TESTE")


@sims4.commands.Command("babado.relacoes", command_type=sims4.commands.CommandType.Live)
def _cmd_relacoes(_connection=None):
    """Lista, para os Sims instanciados, com quem cada um tem compromisso (apoio aos testes)."""
    import services
    output = sims4.commands.CheatOutput(_connection)
    try:
        for sim in services.sim_info_manager().instanced_sims_gen():
            info = sim.sim_info
            partners = [
                "{} [{}]".format(detect._name(detect._sim_info_by_id(pid)), label)
                for pid, label in detect.committed_partners(info)
            ]
            line = "{} ({}): {}".format(detect._name(info), getattr(info.age, "name", info.age),
                                        ", ".join(partners) or "sem compromisso")
            output(line)
            log("babado.relacoes -> " + line, "TESTE")
    except Exception:
        log_exception("babado.relacoes")


start_session("Carregado {} | Python {}".format(_header(), sys.version))
