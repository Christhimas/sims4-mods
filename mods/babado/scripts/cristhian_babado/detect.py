"""M1: detecta traição em interações românticas e registra no log (sem efeitos no jogo).

Referências conferidas no jogo 1.129 (só IDs/nomes, nada copiado da EA):
- Tags: Social_Flirty (flerte, beijo, amasso), Interaction_Kiss (beijos),
  Social_Woohoo (WooHoo e Tentar ter Bebê).
- Bits de compromisso: romantic-Significant_Other 15825, romantic-Engaged 15816,
  romantic-Married 15822.
- APIs: Interaction.get_category_tags(), _trigger_interaction_start_event(self),
  RelationshipTracker.target_sim_gen()/has_any_bits(target_sim_id, bits),
  SimInfoManager.instanced_sims_gen(), Sim.level, ClientObjectMixin.position,
  RelationshipExpectationsTuning.RELATIONSHIP_EXPECTATIONS (Lovestruck).
"""

import services
import sims4.resources

from .log import log, log_exception

TAG_FLIRT = "Social_Flirty"
TAG_KISS = "Interaction_Kiss"
TAG_WOOHOO = "Social_Woohoo"
ROMANCE_TAGS = frozenset((TAG_FLIRT, TAG_KISS, TAG_WOOHOO))

COMMITTED_BIT_IDS = {15825: "namorando", 15816: "noivo(a)", 15822: "casado(a)"}

# Raio (metros) para listar possíveis testemunhas no M1. No M2 vira linha de visão.
WITNESS_RADIUS = 12.0

# Configurável por comando (babado.flerte).
settings = {"flerte_conta": True}

stats = {"interacoes_rastreadas": 0, "traicoes": 0, "ignoradas": 0}

_committed_bits = None


# ---------------------------------------------------------------- utilidades

def _tag_names(affordance):
    try:
        return {getattr(t, "name", str(t)) for t in affordance.get_category_tags()}
    except Exception:
        return set()


def _info(sim_or_info):
    return getattr(sim_or_info, "sim_info", sim_or_info)


def _name(sim_or_info):
    info = _info(sim_or_info)
    if info is None:
        return "-"
    try:
        return "{} {}".format(info.first_name, info.last_name).strip() or "?"
    except Exception:
        return repr(info)


def _is_sim(obj):
    try:
        return bool(obj is not None and obj.is_sim)
    except Exception:
        return False


def _is_adult_enough(info):
    """Jovem adulto ou mais velho."""
    from sims.sim_info_types import Age
    try:
        return info.age >= Age.YOUNGADULT
    except Exception:
        return False


def _get_committed_bits():
    global _committed_bits
    if _committed_bits is None:
        manager = services.get_instance_manager(sims4.resources.Types.RELATIONSHIP_BIT)
        bits = {}
        for bit_id, label in COMMITTED_BIT_IDS.items():
            bit = manager.get(bit_id)
            if bit is None:
                log("bit de compromisso {} ({}) não encontrado".format(bit_id, label), "AVISO")
            else:
                bits[bit] = label
        if not bits:
            return {}  # gerenciador ainda não carregou; tenta de novo depois
        _committed_bits = bits
    return _committed_bits


def committed_partners(info):
    """[(sim_id, rótulo)] com quem o Sim tem namoro, noivado ou casamento."""
    tracker = getattr(info, "relationship_tracker", None)
    if tracker is None:
        return []
    bits = _get_committed_bits()
    out = []
    for target in tracker.target_sim_gen():
        target_id = target if isinstance(target, int) else getattr(target, "sim_id", None)
        if target_id is None:
            continue
        for bit, label in bits.items():
            if tracker.has_bit(target_id, bit):
                out.append((target_id, label))
                break
    return out


def expectations(info):
    """Expectativas de relacionamento (Lovestruck). {} se o pacote não existir."""
    try:
        from sims.relationship_expectations_tuning import RelationshipExpectationsTuning
        mapping = RelationshipExpectationsTuning.RELATIONSHIP_EXPECTATIONS
    except Exception:
        return {}
    out = {}
    try:
        tracker = info.trait_tracker
        for exp_type, data in mapping.items():
            name = getattr(exp_type, "name", str(exp_type))
            if data.yes_trait is not None and tracker.has_trait(data.yes_trait):
                out[name] = "sim"
            elif data.no_trait is not None and tracker.has_trait(data.no_trait):
                out[name] = "nao"
    except Exception:
        log_exception("expectations")
    return out


def _sim_info_by_id(sim_id):
    return services.sim_info_manager().get(sim_id)


def nearby_sims(center, exclude_ids):
    """Sims instanciados perto do ator (mesmo andar), com distância em metros."""
    out = []
    try:
        pos = center.position
        level = getattr(center, "level", None)
        for sim in services.sim_info_manager().instanced_sims_gen():
            info = sim.sim_info
            if info.sim_id in exclude_ids:
                continue
            if level is not None and getattr(sim, "level", level) != level:
                continue
            p = sim.position
            dist = ((p.x - pos.x) ** 2 + (p.z - pos.z) ** 2) ** 0.5
            if dist <= WITNESS_RADIUS:
                out.append((sim, dist))
    except Exception:
        log_exception("nearby_sims")
    return sorted(out, key=lambda x: x[1])


# ---------------------------------------------------------------- avaliação

def level_for(tags):
    if TAG_WOOHOO in tags:
        return "ESCANDALO"
    if TAG_KISS in tags:
        return "TRAICAO"
    if TAG_FLIRT in tags:
        return "SUSPEITA"
    return None


def evaluate(interaction):
    """Chamado quando uma interação romântica rastreada começa."""
    affordance = type(interaction)
    tags = _tag_names(affordance)
    level = level_for(tags)
    actor = interaction.sim
    target = interaction.target
    base = "interacao={} nivel={} ator={} alvo={}".format(
        affordance.__name__, level, _name(actor), _name(target) if _is_sim(target) else repr(target))

    def ignore(reason):
        stats["ignoradas"] += 1
        log("IGNORADO motivo={} {}".format(reason, base), "TESTE")

    if level == "SUSPEITA" and not settings["flerte_conta"]:
        return ignore("flerte_desligado")
    if not _is_sim(target):
        return ignore("alvo_nao_e_sim")

    actor_info, target_info = _info(actor), _info(target)
    if not (_is_adult_enough(actor_info) and _is_adult_enough(target_info)):
        return ignore("idade")

    # Os dois lados podem estar traindo: ator e alvo.
    cheaters = []
    for who, other in ((actor_info, target_info), (target_info, actor_info)):
        partners = [(pid, label) for pid, label in committed_partners(who) if pid != other.sim_id]
        if partners:
            cheaters.append((who, other, partners))
    if not cheaters:
        return ignore("sem_compromisso_com_terceiros")

    stats["traicoes"] += 1
    exclude = {actor_info.sim_id, target_info.sim_id}
    near = nearby_sims(actor, exclude)
    for who, other, partners in cheaters:
        partner_desc = []
        partner_ids = set()
        for pid, label in partners:
            pinfo = _sim_info_by_id(pid)
            partner_ids.add(pid)
            partner_desc.append("{} [{}{}]".format(
                _name(pinfo), label,
                " expectativas={}".format(expectations(pinfo)) if pinfo else ""))
        witnesses = []
        for sim, dist in near:
            role = "PARCEIRO_TRAIDO" if sim.sim_info.sim_id in partner_ids else (
                "testemunha" if _is_adult_enough(sim.sim_info) else "crianca/adolescente")
            witnesses.append("{} {:.1f}m {}".format(_name(sim), dist, role))
        log("TRAICAO nivel={} traidor={} com={} parceiro(s)={} perto={} interacao={}".format(
            level, _name(who), _name(other), partner_desc, witnesses or "[]", affordance.__name__), "TESTE")


# ---------------------------------------------------------------- ganchos

def _wrap_start(affordance):
    if "_babado_wrapped" in affordance.__dict__:
        return False
    original = affordance._trigger_interaction_start_event

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            evaluate(self)
        except Exception:
            log_exception("evaluate {}".format(type(self).__name__))
        return result

    wrapper.__name__ = "_trigger_interaction_start_event"
    affordance._trigger_interaction_start_event = wrapper
    affordance._babado_wrapped = True
    return True


def install_hooks():
    manager = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    counts = {tag: 0 for tag in ROMANCE_TAGS}
    wrapped = 0
    types = manager.types() if callable(manager.types) else manager.types
    for affordance in list(types.values()):
        tags = _tag_names(affordance) & ROMANCE_TAGS
        if not tags:
            continue
        for tag in tags:
            counts[tag] += 1
        if _wrap_start(affordance):
            wrapped += 1
    stats["interacoes_rastreadas"] = wrapped
    log("Ganchos instalados em {} interações românticas; por tag: {}".format(wrapped, counts))
    missing = [bid for bid in COMMITTED_BIT_IDS if bid not in
               {getattr(b, "guid64", None) for b in _get_committed_bits()}]
    if missing:
        log("Bits de compromisso ausentes: {}".format(missing), "AVISO")
