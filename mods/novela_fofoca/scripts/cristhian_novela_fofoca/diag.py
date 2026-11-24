"""Rastreamento de interações para testes: loga fila, início e fim com resultado.

Os ganchos são aplicados SÓ na classe da affordance do mod (não nas da EA).
Métodos conferidos em interactions/base/interaction.py (jogo 1.129):
  on_added_to_queue(self, *args, **kwargs)
  _trigger_interaction_start_event(self)
  _exited_pipeline(self, *args, **kwargs)
"""

from .log import log, log_exception


def _sim_name(sim):
    if sim is None:
        return "-"
    try:
        info = getattr(sim, "sim_info", sim)
        name = "{} {}".format(info.first_name, info.last_name).strip()
        return "{} (id {})".format(name or "?", getattr(info, "sim_id", "?"))
    except Exception:
        return repr(sim)


def describe(interaction):
    try:
        ctx = getattr(interaction, "context", None)
        source = getattr(ctx, "source", None)
        return "id={} actor={} alvo={} origem={}".format(
            getattr(interaction, "id", "?"),
            _sim_name(getattr(interaction, "sim", None)),
            _sim_name(getattr(interaction, "target", None)),
            getattr(source, "name", source),
        )
    except Exception:
        return repr(interaction)


def _wrap(affordance, method_name, label, after=None):
    original = getattr(affordance, method_name, None)
    if original is None:
        log("{}: método {} não existe (patch do jogo mudou?)".format(affordance.__name__, method_name), "AVISO")
        return False

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            extra = after(self) if after else ""
            log("{} {} {}".format(label, describe(self), extra).rstrip(), "TESTE")
        except Exception:
            log_exception("diag {}".format(label))
        return result

    wrapper.__name__ = method_name
    setattr(affordance, method_name, wrapper)
    return True


def _exit_details(interaction):
    parts = []
    for attr in ("global_outcome_result", "finishing_type"):
        try:
            value = getattr(interaction, attr)
            parts.append("{}={}".format(attr, getattr(value, "name", value)))
        except Exception:
            pass
    try:
        parts.append("cancelada_pelo_usuario={}".format(interaction.has_been_user_canceled))
    except Exception:
        pass
    return " ".join(parts)


def trace_affordance(affordance):
    ok = all([
        _wrap(affordance, "on_added_to_queue", "NA_FILA"),
        _wrap(affordance, "_trigger_interaction_start_event", "INICIOU"),
        _wrap(affordance, "_exited_pipeline", "TERMINOU", after=_exit_details),
    ])
    log("Rastreamento {} em {}".format("ativo" if ok else "PARCIAL", affordance.__name__))
    return ok
