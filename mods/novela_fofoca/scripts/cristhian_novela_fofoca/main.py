"""Fofoca da Novela: injeta a interação e expõe um comando de diagnóstico."""

import sys

import services
import sims4.commands
import sims4.resources
from sims4.tuning.instance_manager import InstanceManager

from . import _generated
from .log import log, log_exception

INTERACTION_NAME = "cristhian_NovelaFofoca_Mixer"

# Alvo da injeção. Para um mixer social, o normal é injetar numa AffordanceList
# (snippet) de mixers; para uma super interaction, no tuning do objeto Sim.
# VALIDAR: confirmar no Sims 4 Studio e preencher o ID certo. 0 = desligado.
TARGET_AFFORDANCE_LIST_ID = 0
SIM_OBJECT_ID = 14965  # object_sim (usado só se INJECT_INTO_SIM for True)
INJECT_INTO_SIM = False

_injected = False


def _affordance():
    manager = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    return manager.get(_generated.TUNING_IDS[INTERACTION_NAME])


def _inject_into_affordance_list(snippet_id, affordance):
    snippet = services.get_instance_manager(sims4.resources.Types.SNIPPET).get(snippet_id)
    if snippet is None:
        log("AffordanceList {} não encontrada".format(snippet_id))
        return
    if affordance not in snippet.value:
        snippet.value = tuple(snippet.value) + (affordance,)
        log("Injetado em AffordanceList {}".format(snippet_id))


def _inject_into_sim(affordance):
    sim_tuning = services.get_instance_manager(sims4.resources.Types.OBJECT).get(SIM_OBJECT_ID)
    if sim_tuning is None:
        log("object_sim {} não encontrado".format(SIM_OBJECT_ID))
        return
    if affordance not in sim_tuning._super_affordances:
        sim_tuning._super_affordances = sim_tuning._super_affordances + (affordance,)
        log("Injetado em object_sim")


_original_load = InstanceManager.load_data_into_class_instances


def _patched_load(self, *args, **kwargs):
    result = _original_load(self, *args, **kwargs)
    global _injected
    try:
        if self.TYPE == sims4.resources.Types.OBJECT and not _injected:
            _injected = True
            affordance = _affordance()
            if affordance is None:
                log("Interação {} não carregou (confira o .package)".format(INTERACTION_NAME))
            else:
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
    output("{} v{} | Python {}".format(_generated.MOD_ID, _generated.VERSION, sys.version.split()[0]))
    output("Interação carregada: {}".format(_affordance() is not None))


log("Carregado {} v{} | Python {}".format(_generated.MOD_ID, _generated.VERSION, sys.version))
