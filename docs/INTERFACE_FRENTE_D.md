# Frente D — interface e demonstração

Documentação das tarefas D.1 a D.4, mais o que a frente D entrega de documentação
e apresentação. Quem trabalhou nisto: **Paulo Roberto**.

## Como rodar

```bash
pip install -r requirements.txt

# a interface
streamlit run app/interface/app.py

# a mesma coisa sem navegador (tarefa D.4 — é o plano B do vídeo)
python -m scripts.demo_frente_d            # inclui a ingestão real dos PDFs
python -m scripts.demo_frente_d --rapido   # pula a ingestão
```

A interface abre com as duas apólices de exemplo já selecionadas: não é preciso
enviar arquivo nenhum para ver a comparação funcionando.

## O que cada tarefa entrega

| Tarefa | Onde está | O que faz |
| --- | --- | --- |
| D.1 upload | `app/interface/app.py` → aba *Apólices e envio* | recebe PDF ou imagem, entrega à ingestão da frente A e mostra os números medidos (páginas, páginas por OCR, tokens) |
| D.2 lado a lado | aba *Comparação* | cartões com o valor de cada apólice na mesma linha, agrupados por situação e ordenados pelo motor |
| D.3 rastreabilidade | botão *De onde veio*, em cada valor | abre o trecho de origem, a página citada e **a página do PDF renderizada** para conferência |
| D.4 linha de comando | `scripts/demo_frente_d.py` | a demonstração inteira sem navegador, para o vídeo não depender da interface |

Arquivos da frente:

```
app/interface/app.py           a aplicação Streamlit (desenho e interação)
app/interface/apresentacao.py  o que a tela mostra — sem Streamlit, testável
app/interface/estilo.css       o visual que o Streamlit não traz pronto
app/interface/__init__.py      docstring do pacote
.streamlit/config.toml         tema (cores, fonte, toolbar mínima)
scripts/demo_frente_d.py       demonstração por linha de comando (D.4)
scripts/gerar_pitch.py         gerador do pitch deck (E.3)
tests/test_interface.py        testes da apresentação e da aplicação
tests/test_pitch.py            testes do deck (arquivo e conteúdo)
docs/ROTEIRO_VIDEO.md          roteiro do vídeo, cronometrado (E.4)
docs/RELATORIO_FRENTE_D.md     seções do relatório técnico que cabem à frente D
```

## A decisão que organiza tudo

**A interface não extrai, não compara e não inventa.** Ela lê o banco da frente C,
usa o motor de comparação da frente C e desenha o resultado. As regras de
apresentação — rótulo de veredito, ordem das diferenças, texto do campo ausente,
citação de página — ficam todas em `apresentacao.py`, separadas do Streamlit.

Isso tem três consequências práticas:

1. os testes exercitam a apresentação sem subir a aplicação (38 testes, um deles
   sobe a tela de verdade com `AppTest`);
2. o console (`demo_frente_d.py`) e a tela usam as **mesmas** regras: não é
   possível um dizer "ausente em uma delas" e o outro dizer outra coisa;
3. trocar de framework de interface mais adiante não custa reescrever regra.

## Contrato com a frente B (extração com LLM)

A extração das cláusulas ainda não está pronta. A interface foi escrita para
funcionar **antes** dela e para não precisar mudar **depois** dela:

* `apresentacao.encontrar_extrator(modulo)` procura, em `app.agents`, uma função
  com um destes nomes: `extrair_apolice`, `extrair_apolices`, `extrair`,
  `extrair_campos`. Ela deve receber um `DocumentoExtraido` e devolver uma
  `ApoliceExtraida` (ver `app/schemas.py`);
* **enquanto não existir**, a tela diz que a extração está em desenvolvimento e
  não mostra campo vazio como se a apólice não tratasse do assunto — seria a
  mentira mais cara possível neste projeto;
* **quando existir**, o upload passa a gravar as extrações no banco e a
  comparação usa os dados reais, sem uma linha de interface alterada.

## Sobre as extrações de exemplo

`app/domain/exemplos.py` existe para destravar a frente D e foi escrito pelo
Daniel justamente para isso. Ele é usado na demonstração e **avisado em três
lugares**: banner no topo da tela, selo no cartão de cada apólice e nota final da
demonstração por linha de comando. Dado fabricado nunca aparece como saída do
sistema — a tabela abaixo é o que é real e o que não é:

| O que | Real na demonstração? |
| --- | --- |
| Leitura dos PDFs (frente A) | sim — roda nos dois documentos reais |
| Banco SQLite (C.1) | sim |
| Motor de comparação e vereditos (C.2, C.3) | sim |
| Rastreabilidade por página e trecho | sim, sobre os valores que existem |
| Valores dos campos extraídos | **não** — vêm de `exemplos.py`, à espera da frente B |

## Pendências de integração com outras frentes

Nada disto bloqueia a frente D, mas precisa acontecer antes da entrega:

1. **`gerar_entrega.py` não empacota `.streamlit/`** — o script do Daniel tem uma
   lista `INCLUIR` explícita e `.streamlit` ficou de fora. Sem o `config.toml`, o
   tema se perde no ZIP (a interface continua funcionando, com a cara padrão do
   Streamlit). Sugestão: acrescentar `".streamlit"` à lista.
2. **README, seção "Execução"** — o item E.1 é do Daniel. A linha da interface é
   `streamlit run app/interface/app.py` e a da demonstração é
   `python -m scripts.demo_frente_d`.
3. **`python-pptx` entrou no `requirements.txt`** (seção "Apresentação"), porque o
   `scripts/gerar_pitch.py` depende dele para gerar o `.pptx`.
4. **Conferir o próprio roteiro** — o roteiro em `docs/` prevê reavaliar em 27/09
   se o pitch passa para a Juliana; se passar, o `CONTEUDO` do gerador continua
   sendo a fonte do texto.

## O que ainda falta na frente D

* os três prints da interface no slide de demonstração do deck (o slide já tem os
  espaços marcados com o que recortar);
* a gravação do vídeo — roteiro cronometrado em [`ROTEIRO_VIDEO.md`](ROTEIRO_VIDEO.md);
* revisão do resultado com o grupo depois que a frente B entregar, para trocar os
  números de exemplo pelos números da extração real (a tela e o deck se atualizam
  sozinhos: o deck tem teste que confere os números contra o motor).
