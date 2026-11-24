"""M2: testemunhas reagem à traição conforme a personalidade.

Fluxo: o script escolhe a reação pelos traços, aplica o buff do Babado na testemunha e
empurra a interação cristhian_Babado_Reacao (alvo = quem traiu); o tuning dela escolhe a
animação pelo buff que a testemunha tem.

Referências conferidas no jogo 1.129 (só IDs/nomes):
- Traços: Esquentado 16845, Romântico 27454, Malvado 16836, Maldoso 16857,
  Bonzinho 27915, Família 16838, Brincalhão 9337.
- Amizade: friend 15797, good_friends 15799, bff 15794 (+ variantes Evil 15798/15800/15795,
  bff_BromanticPartner 31211). Inimizade: disliked 15802, despised 15796, nemesis 15801.
- BuffComponent.add_buff_from_op(buff_type, buff_reason, buff_source),
  Sim.push_super_affordance(super_affordance, target, context),
  InteractionContext(sim, source, priority, ..., insert_strategy=...),
  build_buy.get_room_id(zone_id, position, level).
"""

import time

import services
import sims4.resources

from . import _generated
from .log import log, log_exception

WITNESS_RADIUS = 10.0
COOLDOWN_S = 60.0  # uma reação por testemunha a cada 60 s reais (mixers repetem muito)

TRAIT_HOTHEADED, TRAIT_ROMANTIC = 16845, 27454
TRAIT_EVIL, TRAIT_MEAN = 16836, 16857
TRAIT_GOOD, TRAIT_FAMILY = 27915, 16838
TRAIT_GOOFBALL = 9337

FRIEND_BITS = (15797, 15799, 15794, 15798, 15800, 15795, 31211)
ENEMY_BITS = (15802, 15796, 15801)

# Ordem = prioridade: o primeiro traço que bater define a reação.
TRAIT_RULES = (
    ((TRAIT_HOTHEADED,), "revoltado"),
    ((TRAIT_ROMANTIC,), "decepcionado"),
    ((TRAIT_EVIL, TRAIT_MEAN), "que_babado"),
    ((TRAIT_GOOD, TRAIT_FAMILY), "indignado"),
    ((TRAIT_GOOFBALL,), "rindo"),
)
DEFAULT_REACTION = "constrangido"

BUFF_NAMES = {
    "revoltado": "cristhian_Babado_Buff_Revoltado",
    "decepcionado": "cristhian_Babado_Buff_Decepcionado",
    "que_babado": "cristhian_Babado_Buff_QueBabado",
    "indignado": "cristhian_Babado_Buff_Indignado",
    "rindo": "cristhian_Babado_Buff_Rindo",
    "constrangido": "cristhian_Babado_Buff_Constrangido",
}
REACTION_INTERACTION = "cristhian_Babado_Reacao"

stats = {"reacoes": 0, "falhas_push": 0}
_last_reaction = {}
_room_warned = False


# ---------------------------------------------------------------- utilidades

def _manager(kind):
    return services.get_instance_manager(getattr(sims4.resources.Types, kind))


def _tuning(kind, name):
    return _manager(kind).get(_generated.TUNING_IDS[name])


def _get_many(kind, ids):
    manager = _manager(kind)
    return [x for x in (manager.get(i) for i in ids) if x is not None]


def _has_trait(info, trait_id):
    trait = _manager("TRAIT").get(trait_id)
    try:
        return trait is not None and info.trait_tracker.has_trait(trait)
    except Exception:
        return False


def _has_any_bit(info, other_id, bit_ids):
    try:
        return info.relationship_tracker.has_any_bits(other_id, _get_many("RELATIONSHIP_BIT", bit_ids))
    except Exception:
        return False


def _room_id(sim):
    global _room_warned
    try:
        from build_buy import get_room_id
        return get_room_id(services.current_zone_id(), sim.position, sim.level)
    except Exception:
        if not _room_warned:
            _room_warned = True
            log_exception("get_room_id (testemunhas usarão só distância)")
        return None


def _distance(a, b):
    pa, pb = a.position, b.position
    return ((pa.x - pb.x) ** 2 + (pa.z - pb.z) ** 2) ** 0.5


def check_tuning():
    """Loga se os buffs e a interação de reação do .package carregaram."""
    missing = [n for n in BUFF_NAMES.values() if _tuning("BUFF", n) is None]
    if _tuning("INTERACTION", REACTION_INTERACTION) is None:
        missing.append(REACTION_INTERACTION)
    if missing:
        log("Tuning do Babado NÃO carregou: {}".format(missing), "ERRO")
        return
    log("Tuning do Babado ok: {} buffs + {}".format(len(BUFF_NAMES), REACTION_INTERACTION))
    _trace_reaction(_tuning("INTERACTION", REACTION_INTERACTION))


def _trace_reaction(affordance):
    """Loga quando a reação termina (só na interação do mod)."""
    original = affordance._exited_pipeline

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            finishing = getattr(self, "finishing_type", None)
            log("REACAO_FIM testemunha={} resultado={} fim={}".format(
                getattr(getattr(self.sim, "sim_info", None), "first_name", "?"),
                getattr(self.global_outcome_result, "name", self.global_outcome_result),
                getattr(finishing, "name", finishing)), "TESTE")
        except Exception:
            log_exception("trace reação")
        return result

    affordance._exited_pipeline = wrapper


# ---------------------------------------------------------------- testemunhas

def find_witnesses(scene_sim, exclude_ids, is_adult):
    """[(sim, distância, mesmo_comodo)] de Sims adultos que viram a cena.

    Critério M2: mesmo andar, até WITNESS_RADIUS e no mesmo cômodo (ou ambos ao ar livre).
    Aproxima a linha de visão sem custo de raycast.
    """
    out = []
    scene_room = _room_id(scene_sim)
    level = getattr(scene_sim, "level", None)
    for sim in services.sim_info_manager().instanced_sims_gen():
        info = sim.sim_info
        if info.sim_id in exclude_ids or not is_adult(info):
            continue
        if level is not None and getattr(sim, "level", level) != level:
            continue
        dist = _distance(sim, scene_sim)
        if dist > WITNESS_RADIUS:
            continue
        room = _room_id(sim)
        same_room = scene_room is None or room is None or room == scene_room
        out.append((sim, dist, same_room))
    return sorted(out, key=lambda x: x[1])


# ---------------------------------------------------------------- reação

def choose_reaction(witness_info, cheater_info):
    if _has_any_bit(witness_info, cheater_info.sim_id, ENEMY_BITS):
        return "que_babado", "inimigo_do_traidor"
    for trait_ids, reaction in TRAIT_RULES:
        for trait_id in trait_ids:
            if _has_trait(witness_info, trait_id):
                trait = _manager("TRAIT").get(trait_id)
                return reaction, "traço {}".format(getattr(trait, "__name__", trait_id))
    return DEFAULT_REACTION, "padrão"


def _push_reaction(witness, cheater_sim):
    from interactions.context import InteractionContext, QueueInsertStrategy
    from interactions.priority import Priority
    affordance = _tuning("INTERACTION", REACTION_INTERACTION)
    if affordance is None:
        return "interação de reação não carregou"
    context = InteractionContext(witness, InteractionContext.SOURCE_SCRIPT, Priority.High,
                                 insert_strategy=QueueInsertStrategy.NEXT)
    result = witness.push_super_affordance(affordance, cheater_sim, context)
    return "ok" if result else "recusado: {}".format(getattr(result, "reason", result))


def react(witness, dist, same_room, cheater_sim, partner_ids, level, name):
    """Aplica buff + reação em uma testemunha. Retorna a descrição para o log."""
    info, cheater_info = witness.sim_info, cheater_sim.sim_info
    now = time.monotonic()
    last = _last_reaction.get(info.sim_id)
    if last is not None and now - last < COOLDOWN_S:
        return "{} {:.1f}m em_espera".format(name(witness), dist)
    if not same_room:
        return "{} {:.1f}m outro_comodo".format(name(witness), dist)

    reaction, why = choose_reaction(info, cheater_info)
    friend_of_betrayed = any(_has_any_bit(info, pid, FRIEND_BITS) for pid in partner_ids)

    buff_result = "?"
    try:
        buff = _tuning("BUFF", BUFF_NAMES[reaction])
        if buff is None:
            buff_result = "buff não carregou"
        else:
            info.Buffs.add_buff_from_op(buff, None)
            buff_result = "ok"
    except Exception:
        buff_result = "erro"
        log_exception("add_buff {}".format(reaction))

    try:
        push_result = _push_reaction(witness, cheater_sim)
    except Exception:
        push_result = "erro"
        log_exception("push reação")
    if push_result != "ok":
        stats["falhas_push"] += 1

    _last_reaction[info.sim_id] = now
    stats["reacoes"] += 1
    log("REACAO nivel={} testemunha={} traidor={} reacao={} motivo={} amigo_do_traido={} "
        "buff={} animacao={} dist={:.1f}m".format(
            level, name(witness), name(cheater_sim), reaction, why, friend_of_betrayed,
            buff_result, push_result, dist), "TESTE")
    return "{} {:.1f}m {}".format(name(witness), dist, reaction)
