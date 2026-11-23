# Instruções para o Claude

- Responder em PT-BR.
- Mods gratuitos (política EA): nada de transação, anúncio ou pedido de doação dentro
  do mod; sem logos EA/The Sims/Plumbob; sem sugerir afiliação.
- Nunca comitar código/assets da EA. Código descompilado fica em `reference/` (ignorado).
- Nunca modificar a instalação do jogo; só escrever na pasta Mods.
- `.ts4script` só com `.pyc` da versão do jogo (`sims4mods.json` → `game_python`).
- Ferramentas em `sims4pack/` usam só stdlib e devem rodar em Python 3.7+.
- Toda string visível vai para `strings/en_us.json` + `strings/pt_br.json` via
  `{{str:chave}}`; nunca texto fixo no tuning.
- Rodar `python -m unittest discover -s tests -t .` após mudar `sims4pack/`.
- Depois de testar no jogo: `python -m sims4pack lastexc`.
