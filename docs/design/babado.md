# Babado! — documento de design (v1)

> Nome provisório. Status: **design aprovado em 2026-11-23**, implementação não iniciada.
> Pasta do mod (quando começar): `mods/babado/`, `package_name` `cristhian_Babado`,
> `script_package` `cristhian_babado`.

## 1. Ideia

Quando um Sim comprometido trai e outros Sims **presenciam**, eles reagem conforme a
personalidade e passam a **saber** do caso. Quem sabe pode **espalhar a fofoca**; a
notícia corre de boca em boca até, talvez, chegar ao parceiro traído.

### O que o jogo base já faz (e não vamos duplicar)
- Ciúme do **parceiro traído** que vê a cena: `broadcaster_Jealousy` (76132, linha de
  visão) e `broadcaster_Jealousy_WooHoo` (76434), buffs `Buff_Jealousy_*`
  (ex.: CaughtCheating 76385, CheatingDiscovered 76387) e loots
  `Loot_Buff_Jealousy_*` / `Loot_Relationship_Jealousy_Loss_Cheating` (76595).
- Reações de testemunha **por traço** já existem para brigas
  (`loot_buff_Fight_Witnessed_*`, `buff_FightWitnessed_*`) — servem de modelo.

### O que o mod acrescenta
- Reação de **terceiros** que presenciam a traição.
- **Conhecimento persistente** ("fulano sabe que X traiu com Y").
- **Propagação** da fofoca e consequência quando ela chega ao traído.

## 2. Mecânica

### 2.1 Detecção da traição
- Gancho por script no início de interações românticas (mesma técnica de
  `diag.trace_affordance`, mas por **tag/categoria** de interação em vez de uma lista
  fixa — cobre pacotes de expansão sem manutenção manual).
- É traição quando o **ator** tem vínculo romântico comprometido (namorando, noivo,
  casado) com alguém que **não** é o alvo.
- Gravidade:

| Nível | Interações | Efeito |
|---|---|---|
| Suspeita | flerte | reação leve; não cria conhecimento (configurável) |
| Traição | beijo, carícias | reação + conhecimento |
| Escândalo | WooHoo | reação forte + conhecimento + mais chance de espalhar |

- Só jovem adulto ou mais velho (ator, alvo e testemunhas).
- Respeitar relacionamento aberto/limites de ciúme do jogo (Lovestruck) quando
  presentes. **VALIDAR**: como ler essa configuração no runtime.

### 2.2 Testemunhas
- Sims com **linha de visão** do ator no momento da interação (mesmo critério do
  `broadcaster_Jealousy`), excluindo ator, alvo e o próprio parceiro traído (o jogo
  base já cuida dele).
- **VALIDAR**: implementar via broadcaster próprio injetado nas interações românticas
  vs. consulta de LOS no script. Preferir broadcaster (padrão da EA, menos custo).

### 2.3 Conhecimento (persistência)
- Relationship bit custom **unidirecional** testemunha → traidor:
  `cristhian_Babado_SabeDaTraicao` (o save do jogo persiste sozinho).
- Quem foi o cúmplice (alvo) fica num segundo bit testemunha → cúmplice
  `cristhian_Babado_SabeDoCaso`.
- Limite: um "babado" ativo por traidor por testemunha; repetir só reforça.
- Expira após N dias de jogo sem ser comentado (configurável; padrão 7).
  **VALIDAR**: timeout de relationship bit vs. limpeza por script.

### 2.4 Reação por personalidade
Push de uma reação curta (animação **existente** do jogo) + buff próprio na testemunha.
Ordem de prioridade: o primeiro traço que bater define a reação.

| Traço (jogo base) | Reação | Buff (PT-BR / EN) |
|---|---|---|
| Esquentado | bravo | Revoltado com a Traição / Outraged by Betrayal |
| Romântico | triste | Decepcionado com o Amor / Disappointed in Love |
| Malvado, Malicioso | se diverte | Que Babado! / Juicy Gossip! |
| Bonzinho, Família | indignado | Indignado / Indignant |
| Brincalhão | ri | Morrendo de Rir / Cracking Up |
| (padrão) | sem graça | Constrangido / Awkward |

Modificadores:
- Testemunha **amiga/família do traído** → reação um nível mais forte.
- Testemunha **inimiga do traidor** → tende a "se diverte".
- **VALIDAR**: IDs dos traços e de animações de reação (gasp, raiva, riso, choro)
  via `python -m sims4pack ea-tuning`.

### 2.5 Fofoca (propagação)
- Novo mixer social (Amigável): **"Contar o babado sobre {traidor}"**,
  disponível só se o ator tem `SabeDaTraicao` com alguém e o alvo **não** sabe.
- Ao ouvir: o ouvinte ganha o conhecimento e reage pela tabela 2.4.
- Se o ouvinte é o **parceiro traído**: aplicar os loots de ciúme da EA
  (`Loot_Buff_Jealousy_CheatingDiscovered` 76408 +
  `Loot_Relationship_Jealousy_Loss_Cheating` 76595) — sem recriar o sistema.
- Autonomia: Sims Malvados/Maliciosos têm mais chance de espalhar sozinhos
  (configurável, pode desligar).

### 2.6 Lado do traidor
- Buff "Com a Consciência Pesada" / "Guilty Conscience" quando sabe que foi visto.
- Mixer **"Pedir segredo"** para uma testemunha: sucesso remove a chance de ela contar
  por alguns dias; falha (ou testemunha Malvada) aumenta a chance.

### 2.7 Configurações (comandos de trapaça, nunca UI de pagamento/anúncio)
- `babado.info` — versão, build, commit, contadores, caminho do log.
- `babado.flerte on|off` — flerte conta como traição.
- `babado.autonomia on|off` e `babado.chance <0-100>`.
- `babado.limpar` — remove todo conhecimento do save (recuperação).
- Configs gravadas num JSON ao lado do `.ts4script` (fora do save).

## 3. Logs e testes (regra do projeto)
Todo evento relevante gera linha `[TESTE]` no `cristhian_babado.log`:
- `TRAICAO nivel=… ator=… alvo=… parceiro=… testemunhas=[…]`
- `REACAO testemunha=… traço=… reação=… buff=…`
- `CONHECIMENTO +bit testemunha=… traidor=…`
- `FOFOCA de=… para=… resultado=… chegou_ao_traido=…`
- `IGNORADO motivo=(relação aberta|idade|sem compromisso|sem testemunha)`

Cenários de teste no jogo (cada um com save dedicado na pasta Saves):
1. Casado beija outro Sim com 2 testemunhas de traços diferentes.
2. Mesmo caso sem compromisso → `IGNORADO`.
3. Testemunha conta para terceiro; terceiro conta para o traído → ciúme da EA.
4. Salvar, sair e recarregar → conhecimento continua.
5. Pedir segredo: sucesso e falha.
6. `babado.flerte off` → flerte não gera nada.

## 4. Fora da v1
- Reações para traços de pacotes de expansão.
- Notícia no celular / notificação "Fulano está espalhando que…".
- Integração com o tema novela; fofoca falsa (inventar babado).
- Animações novas.

## 5. Marcos

| # | Entrega | Validação no jogo |
|---|---|---|
| M1 | Detecção + log (sem efeitos) | log mostra TRAICAO/IGNORADO corretos |
| M2 | Testemunhas + reações + buffs | reações por traço nos cenários 1–2 |
| M3 | Conhecimento persistente | cenário 4 |
| M4 | Mixer "Contar o babado" + chegada ao traído | cenário 3 |
| M5 | Lado do traidor + configs | cenários 5–6 |
| M6 | PT-BR revisado, release dev, post Patreon (acesso antecipado 14 dias) | checklist de release |

## 6. Conformidade
- Sem transação, anúncio ou pedido de doação dentro do mod; créditos só no Patreon.
- Sem código/assets da EA no repo: só IDs referenciados e tuning próprio.
- Strings visíveis sempre via `strings/en_us.json` + `strings/pt_br.json`.
- Conteúdo romântico limitado a jovem adulto ou mais velho, como no jogo base.
