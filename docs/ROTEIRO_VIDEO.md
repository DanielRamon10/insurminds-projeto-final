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
4. **Confira qual extração está na tela.** Os números narrados neste roteiro
   (3 ausentes em uma, 2 diferentes, 6 divergentes, 4 iguais, 27 com origem) são
   os das **extrações de exemplo**. Se o banco desta máquina tiver as extrações
   reais de `data/extracoes/` — as que `python -m scripts.carregar_extracoes`
   grava —, a tela mostra outros números (1 / 0 / 8 / 1, 19 com origem) e a
   narração não bate com a imagem. O botão *Recarregar as extrações de exemplo*
   **não** resolve isso: ele nunca sobrescreve extração real, de propósito. Para
   gravar sobre os exemplos, apague `data/apolices.db` e reabra o aplicativo.
5. Grave a **tela primeiro, narração depois** — é a forma mais fácil de acertar o
   tempo. Se cada integrante narra sua parte, combine o timestamp exato de entrada.
6. Ferramenta: OBS Studio (grátis) ou Xbox Game Bar (`Win` + `G`) no Windows.

## Roteiro

| Tempo | Tela | Quem fala | O que dizer |
| --- | --- | --- | --- |
| 0:00–0:30 | Slide da capa | Paulo Henrique | O problema: comparar duas apólices D&O é leitura de dezenas de páginas em linguagem jurídica, feita por especialista, e a mesma cláusula aparece com nomes diferentes em cada seguradora. Um exemplo real: duas apólices com o mesmo limite máximo podem ter franquias de R$ 50 mil e R$ 80 mil. |
| 0:30–1:15 | Slide de arquitetura | Daniel | O que foi construído: quatro etapas — ingestão que lê PDF e imagem, extração das cláusulas com IA generativa, armazenamento e comparação determinística, e a interface. Cada etapa conversa com a próxima por contratos de dados; a comparação não usa modelo de linguagem justamente para ser reprodutível. |
| 1:15–2:00 | Aba **Comparação** | Paulo Roberto | Apresente a tela aberta: duas apólices reais (Chubb e AIG), 15 campos do dicionário do especialista, e os números do topo — 3 proteções ausentes em uma delas, 2 valores diferentes, 6 redações divergentes, 4 iguais. Diga o que significa cada número. |
| 2:00–2:50 | Aba **Comparação**, rolando os cartões | Paulo Roberto | Mostre um cartão de cada tipo: a franquia (R$ 50 mil contra R$ 80 mil), sublimites ausentes na AIG, e uma exclusão com redação divergente. Leia em voz alta a frase "por que importa" de um deles — ela vem do corretor, não do modelo. |
| 2:50–3:25 | Botão **De onde veio** | Paulo Roberto | O ponto mais importante do vídeo: clique em *De onde veio*, mostre o trecho de origem, a página citada e **a página do PDF renderizada**. Diga: nenhum número aparece sem a página e o trecho de onde saiu. |
| 3:25–3:50 | Aba **Tabela completa** | Paulo Roberto | A mesma comparação em tabela, com a situação colorida e o CSV pronto para o Excel — é o que o corretor leva embora. |
| 3:50–4:15 | Aba **Apólices e envio** | Paulo Roberto | Mostre o cartão da apólice (campos encontrados, rastreabilidade) e o envio de documento. **Diga o que está pendente**: a ingestão lê o documento e devolve páginas, OCR e texto, e a extração com LLM está publicada em `app.agents` — o que falta é chave de modelo no `.env`. E explique por que os campos numéricos aparecem sem valor: as condições gerais remetem LMI, franquia, vigência, retroatividade e sublimites à Especificação da Apólice, que não está no lote — a tela mostra a ressalva do extrator com a página da cláusula, em vez de dizer que a apólice não trata do assunto. |
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
* [ ] a limitação **aparece no vídeo** — os campos numéricos não têm valor nas
      condições gerais, que remetem cada um à Especificação da Apólice, e é por isso
      que a demonstração roda sobre as extrações de exemplo; é o que sustenta a
      honestidade do resto
* [ ] a tela gravada mostra os **mesmos números** que a narração diz — ver o passo 4
      da preparação

## Depois de gravar

1. Assistir inteiro uma vez, com o roteiro na mão, marcando o que ficou confuso.
2. Rodar `python -m scripts.gerar_pitch` para o deck ficar com os números finais.
3. Conferir se o deck saiu com as três telas coladas. O gerador cola sozinho os
   recortes que estiverem em `Projeto_Final_Artefatos/prints/`; se a pasta estiver
   vazia ele desenha a caixa com "print N — colar aqui" e diz no fim da execução
   quais arquivos faltam. As regiões de cada recorte estão no fim deste roteiro.
4. Conferir o pacote: `python -m scripts.gerar_entrega` (na branch própria do
   script) precisa passar sem o modo `--parcial`.

## Os três recortes do slide de demonstração

O slide 8 do deck ("A plataforma em uso") espera três arquivos em
`Projeto_Final_Artefatos/prints/`, um por legenda, na ordem:

| arquivo | o que entra no recorte | tamanho |
| --- | --- | --- |
| `01_comparacao.png` | o título `⚠️ Valores diferentes — 2 campos` e os dois cartões abaixo dele (Franquia/Retenção e Retroatividade), do começo do título ao fim do último cartão | 1140×712 |
| `02_de_onde_veio.png` | o cartão Franquia/Retenção com o popover **De onde veio** aberto — o trecho de origem, o `📄 página 12` e a página do PDF renderizada, até a última linha do rodapé do popover. Role até o cartão ficar no meio da janela antes de capturar | 1140×1137 |
| `03_tabela_csv.png` | a aba **Tabela completa**: o título `📋 A comparação inteira, campo a campo`, a tabela com a coluna *Situação* colorida e o botão **Baixar a comparação em CSV**. Do título ao fim do botão | 1140×589 |

Como reproduzir:

1. Suba o app **sobre as extrações de exemplo** — os números do deck e da narração
   saem de `app/domain/exemplos.py`. Se o banco já tiver extrações reais, apague
   `data/apolices.db` antes: `semear_exemplos` não sobrescreve extração de verdade.
2. Janela de **1600 px de largura**. A coluna de conteúdo começa em `x = 380` e tem
   `1140 px` de largura (300 px de barra lateral + 80 px de margem de cada lado).
3. Recorte as três regiões acima, sempre com `x = 380` e `largura = 1140`.

**Ancore no elemento, não em `y` fixo.** O recorte do `01` já foi descrito com
`y` 1785 → 2515, e essa coordenada morreu na primeira vez que o layout mudou: o
cabeçalho encolheu e a fileira de KPIs virou barra de composição, e o recorte
passou a pegar o lugar errado **sem erro nenhum** — só um print torto. Meça o
retângulo de `.secao` e do último cartão no DOM e recorte entre eles:

```js
const sec = [...document.querySelectorAll('.secao')]
  .find(s => /Valores diferentes/i.test(s.innerText));
const cartoes = [...document.querySelectorAll('[class*="st-key-cartao-"]')];
const ultimo = cartoes.find(c =>
  /Retroatividade/i.test(c.querySelector('.campo-titulo')?.innerText || ''));
// recorte de sec.top - 14 até ultimo.bottom + 20, x = 380, largura = 1140
```

Vale para os três: o `02` sai do cartão da Franquia (`[class*="st-key-cartao-"]`
cujo `.campo-titulo` casa `/Franquia/i`) até o fim do
`[data-testid="stPopoverBody"]`, e o `03` do `.secao` da tabela até o fim do
`[data-testid="stDownloadButton"]`.

**Os prints envelhecem junto com a tela.** Eles são a única parte do deck que é
uma foto: mexeu no visual, o deck passa a mostrar uma tela que não existe mais.
Regerar é `python -m scripts.gerar_pitch`, que recola os três arquivos sozinho —
mas **só depois de recapturar**. Vale conferir depois de qualquer mudança de
`estilo.css` ou de `app.py`.

Duas armadilhas que custam tempo:

* **A janela precisa ser mais alta que o recorte.** O Streamlit rola um contêiner
  interno, então a página em si não cresce; um recorte que passe do fim da janela é
  cortado em silêncio e sai um PNG mutilado (o da comparação já saiu 1140×115 assim).
  Use uma janela de uns 3200 px de altura, ou role até a região antes de capturar.
  Confira as dimensões do PNG depois de cada captura e **aborte** se não baterem.
* **O popover do `02` é dinâmico.** Abra-o e espere a página do PDF renderizar antes
  de capturar — a imagem chega depois do resto do popover.
