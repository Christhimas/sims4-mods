# sims4-mods

Mods de gameplay para The Sims 4, com temas brasileiros e tradução PT-BR completa
desde o lançamento. Mods gratuitos e não comerciais, conforme a política da EA.
Projeto independente, sem afiliação nem endosso da Electronic Arts.

## Estrutura

```
sims4mods.json            versão do Python do jogo + criador
sims4pack/                ferramentas de build (só stdlib)
tests/                    testes das ferramentas + build do mod de exemplo
mods/<id>/
  mod.json                id, título, versão, nomes do pacote/script
  tuning/*.xml            tuning com placeholders (veja abaixo)
  strings/en_us.json      obrigatório: fallback de todos os idiomas
  strings/pt_br.json      obrigatório completo no release
  scripts/<pacote>/       código Python do .ts4script
reference/                (ignorado) código EA descompilado, só para consulta
```

## Placeholders no tuning

| Placeholder | Vira |
|---|---|
| `s="{{id}}"` | ID da instância: FNV64 do `n=` com bit alto ligado |
| `{{tuning:Nome}}` | ID de outro tuning do mesmo mod |
| `{{str:chave}}` | `0xHASH<!--texto EN-->` da string `chave` |

Os scripts recebem `_generated.py` com `TUNING_IDS` e `STRING_KEYS`; não use IDs
na mão.

## Build

Requer Python 3.8+ para as ferramentas e **Python 3.7** (versão do jogo) para
compilar os scripts. Aponte a variável `SIMS4_PYTHON` para o interpretador 3.7.

```bash
python -m unittest discover -s tests -t .
python -m sims4pack build novela_fofoca              # build/<pacote>/
python -m sims4pack build novela_fofoca --install    # + copia para Mods/<pacote>/
python -m sims4pack build novela_fofoca --release    # checagens estritas + dist/*.zip
python -m sims4pack build novela_fofoca --no-scripts # só .package (dev)
python -m sims4pack inspect build/<pacote>/<pacote>.package
python -m sims4pack lastexc                          # lastException*.txt + logs dos mods
```

A pasta Mods padrão é `~/Documents/Electronic Arts/The Sims 4/Mods`; mude com
`SIMS4_MODS_DIR` ou `--mods-dir`.

O release bloqueia se houver `VALIDAR`/`TODO` no tuning ou nos scripts, se faltar
tradução PT-BR, ou se os `.pyc` não forem de Python 3.7.

## Fluxo Mac ↔ Windows

- **Mac**: desenvolvimento, build e testes rápidos.
- **Windows**: Sims 4 Studio / s4pe (clonar tuning da EA, conferir pacotes) e
  teste final numa pasta Mods limpa. Só faz `git pull` + build, nunca edita direto.

## Confirmar a versão do Python do jogo

Instale o mod e use o comando de trapaça `fofoca.info` (Ctrl+Shift+C). Ele mostra
a versão do Python. O log `cristhian_novela_fofoca.log` fica ao lado do `.ts4script`.
Se não for 3.7, ajuste `game_python` em `sims4mods.json`.

## Checklist de release

- [ ] `--release` passa; testado no Windows em Mods limpa (sem outros mods)
- [ ] Sem `lastException*.txt` novo após carregar um save e usar a interação
- [ ] Post no Patreon com a **data pública** (14 dias padrão, máx. 30)
- [ ] Nada de logos EA/The Sims/Plumbob; nada de doação/anúncio dentro do mod
- [ ] Correções de compatibilidade com patch: públicas e imediatas
