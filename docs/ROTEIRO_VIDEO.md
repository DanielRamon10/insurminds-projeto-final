# Roteiro do vídeo — `InsurMinds_Projeto_Final.mp4`

Máximo de **5 minutos**, com quatro coisas obrigatórias: o problema, a arquitetura
da solução, a aplicação em uso e os resultados principais. Este roteiro fecha em
**4min55s**, com 5 segundos de folga para respirar.

Dono: **Paulo Roberto**. Conteúdo de negócio da abertura: **Paulo Henrique**.
Arquitetura: **Daniel**.

## Antes de gravar (10 minutos de preparação)

```bash
streamlit run app/interface/app.py
```

1. Abra no Chrome ou Edge, **janela maximizada**, zoom em 100%, tela em 1920x1080.
   Fonte maior ajuda: no Streamlit, `Ctrl` + `+` uma vez deixa o texto legível em
   vídeo comprimido.
2. Feche abas, notificações e mensageiros. Silencie o celular.
3. Confira que a barra lateral mostra **2 apólices no banco** e que as duas estão
   selecionadas. Se algo estiver estranho, clique em *Recarregar as extrações de
   exemplo*.
4. Grave a **tela primeiro, narração depois** — é a forma mais fácil de acertar o
   tempo. Se cada integrante narra sua parte, combine o timestamp exato de entrada.
5. Ferramenta: OBS Studio (grátis) ou Xbox Game Bar (`Win` + `G`) no Windows.

## Roteiro

| Tempo | Tela | Quem fala | O que dizer |
| --- | --- | --- | --- |
| 0:00–0:30 | Slide da capa | Paulo Henrique | O problema: comparar duas apólices D&O é leitura de dezenas de páginas em linguagem jurídica, feita por especialista, e a mesma cláusula aparece com nomes diferentes em cada seguradora. Um exemplo real: duas apólices com o mesmo limite máximo podem ter franquias de R$ 50 mil e R$ 80 mil. |
| 0:30–1:15 | Slide de arquitetura | Daniel | O que foi construído: quatro etapas — ingestão que lê PDF e imagem, extração das cláusulas com IA generativa, armazenamento e comparação determinística, e a interface. Cada etapa conversa com a próxima por contratos de dados; a comparação não usa modelo de linguagem justamente para ser reprodutível. |
| 1:15–2:00 | Aba **Comparação** | Paulo Roberto | Apresente a tela aberta: duas apólices reais (Chubb e AIG), 15 campos do dicionário do especialista, e os números do topo — 3 proteções ausentes em uma delas, 2 valores diferentes, 6 redações divergentes, 4 iguais. Diga o que significa cada número. |
| 2:00–2:50 | Aba **Comparação**, rolando os cartões | Paulo Roberto | Mostre um cartão de cada tipo: a franquia (R$ 50 mil contra R$ 80 mil), sublimites ausentes na AIG, e uma exclusão com redação divergente. Leia em voz alta a frase "por que importa" de um deles — ela vem do corretor, não do modelo. |
| 2:50–3:25 | Botão **De onde veio** | Paulo Roberto | O ponto mais importante do vídeo: clique em *De onde veio*, mostre o trecho de origem, a página citada e **a página do PDF renderizada**. Diga: nenhum número aparece sem a página e o trecho de onde saiu. |
| 3:25–3:50 | Aba **Tabela completa** | Paulo Roberto | A mesma comparação em tabela, com a situação colorida e o CSV pronto para o Excel — é o que o corretor leva embora. |
| 3:50–4:15 | Aba **Apólices e envio** | Paulo Roberto | Mostre o cartão da apólice (campos encontrados, rastreabilidade) e o envio de documento. **Diga o que está pendente**: a ingestão já lê o documento e devolve páginas, OCR e texto; a extração das cláusulas com LLM é a etapa em desenvolvimento — e a plataforma declara isso na tela em vez de mostrar campo vazio. |
| 4:15–4:40 | Slide de resultados e de limites | Nicole ou Daniel | Resultados e limites: 70 e 72 páginas lidas, ~37 mil tokens por apólice, 27 valores com origem registrada, 100% rastreáveis. Diga que a comparação roda hoje sobre extrações de exemplo identificadas como tal, e que o motor de regras é o mesmo que vai comparar a extração real. |
| 4:40–4:55 | Slide da equipe | Paulo Roberto | Fechamento: o que cada frente entregou e o que vem depois (redator automático, histórico de versões). "A diferença entre duas apólices deixa de ser uma leitura de horas e passa a ser uma tela com prova de origem." |

## Plano B — se o Streamlit não subir

```bash
python -m scripts.demo_frente_d
```

A demonstração por linha de comando percorre exatamente o mesmo caminho (ingestão
real, banco, comparação, rastreabilidade) com o mesmo vocabulário da tela. Aumente
a fonte do terminal antes de gravar e narre os cinco passos numerados que aparecem
na saída.

## Checklist do arquivo final

* [ ] nome exatamente `InsurMinds_Projeto_Final.mp4`
* [ ] duração **até 5 minutos** (o script do roteiro fecha em 4:55)
* [ ] arquivo **abaixo de 100 MB** — acima disso o GitHub recusa o arquivo, e o
      empacotador da entrega avisa
* [ ] salvo em `Projeto_Final_Artefatos/`
* [ ] resolução 1080p, áudio audível e sem ruído de fundo
* [ ] os quatro itens obrigatórios aparecem: problema, arquitetura, aplicação em
      uso, resultados
* [ ] a parte em que a extração com LLM ainda está em desenvolvimento **aparece no
      vídeo** — é o que sustenta a honestidade do resto

## Depois de gravar

1. Assistir inteiro uma vez, com o roteiro na mão, marcando o que ficou confuso.
2. Rodar `python -m scripts.gerar_pitch` para o deck ficar com os números finais.
3. Colar os três prints da interface no slide de demonstração.
4. Conferir o pacote: `python -m scripts.gerar_entrega` (na branch própria do
   script) precisa passar sem o modo `--parcial`.
