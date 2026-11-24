"""Fofoca da Novela: injeta a interação e expõe um comando de diagnóstico."""

import sys

import services
import sims4.commands
import sims4.resources
from sims4.tuning.instance_manager import InstanceManager

from . import _generated
from .diag import trace_affordance
from .log import LOG_PATH, log, log_exception, start_session

INTERACTION_NAME = "cristhian_NovelaFofoca_Mixer"

# Alvo da injeção: AffordanceList social_Mixers_Friendly_NonTouching (24508),
# a mesma lista onde a EA coloca o mixer GossipAbout usado como base.
# Para uma super interaction, use INJECT_INTO_SIM. 0 = desligado.
TARGET_AFFORDANCE_LIST_ID = 24508
SIM_OBJECT_ID = 14965  # object_sim (usado só se INJECT_INTO_SIM for True)
INJECT_INTO_SIM = False

_injected = False


def _affordance():
    manager = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    return manager.get(_generated.TUNING_IDS[INTERACTION_NAME])


def _inject_into_affordance_list(snippet_id, affordance):
    snippet = services.get_instance_manager(sims4.resources.Types.SNIPPET).get(snippet_id)
    if snippet is None:
        log("AffordanceList {} não encontrada".format(snippet_id), "ERRO")
        return
    before = len(snippet.value)
    if affordance not in snippet.value:
        snippet.value = tuple(snippet.value) + (affordance,)
    log("AffordanceList {} ({}): {} -> {} itens, contém o mixer: {}".format(
        snippet_id, snippet.__name__, before, len(snippet.value), affordance in snippet.value))


def _inject_into_sim(affordance):
    sim_tuning = services.get_instance_manager(sims4.resources.Types.OBJECT).get(SIM_OBJECT_ID)
    if sim_tuning is None:
        log("object_sim {} não encontrado".format(SIM_OBJECT_ID), "ERRO")
        return
    if affordance not in sim_tuning._super_affordances:
        sim_tuning._super_affordances = sim_tuning._super_affordances + (affordance,)
    log("object_sim: contém a interação: {}".format(affordance in sim_tuning._super_affordances))


_original_load = InstanceManager.load_data_into_class_instances


def _patched_load(self, *args, **kwargs):
    result = _original_load(self, *args, **kwargs)
    global _injected
    try:
        if self.TYPE == sims4.resources.Types.OBJECT and not _injected:
            _injected = True
            affordance = _affordance()
            if affordance is None:
                log("Interação {} não carregou (confira o .package)".format(INTERACTION_NAME), "ERRO")
            else:
                log("Interação carregada: {} id={}".format(affordance.__name__, affordance.guid64))
                trace_affordance(affordance)
                if TARGET_AFFORDANCE_LIST_ID:
                    _inject_into_affordance_list(TARGET_AFFORDANCE_LIST_ID, affordance)
                if INJECT_INTO_SIM:
                    _inject_into_sim(affordance)
    except Exception:
        log_exception("injeção")
    return result


InstanceManager.load_data_into_class_instances = _patched_load


@sims4.commands.Command("fofoca.info", command_type=sims4.commands.CommandType.Live)
def _cmd_info(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    lines = [
        "{} v{} build {} ({})".format(_generated.MOD_ID, _generated.VERSION,
                                      _generated.BUILD_TIME, _generated.GIT_COMMIT),
        "Python {}".format(sys.version.split()[0]),
        "Interação carregada: {}".format(_affordance() is not None),
        "Log: {}".format(LOG_PATH),
    ]
    for line in lines:
        output(line)
    log("fofoca.info -> " + " | ".join(lines), "TESTE")


start_session("Carregado {} v{} build {} ({}) | Python {}".format(
    _generated.MOD_ID, _generated.VERSION, _generated.BUILD_TIME, _generated.GIT_COMMIT, sys.version))
