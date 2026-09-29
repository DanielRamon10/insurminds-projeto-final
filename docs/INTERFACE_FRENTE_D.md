# Frente D — interface e demonstração

Documentação das tarefas D.1 a D.4, mais o que a frente D entrega de documentação
e apresentação. Quem trabalhou nisto: **Paulo Roberto**.

## Como rodar

```bash
pip install -r requirements.txt

# a interface (o navegador abre sozinho, com o tema do .streamlit/config.toml)
streamlit run app/interface/app.py

# a mesma coisa sem abrir navegador — teste, servidor, script
streamlit run app/interface/app.py --server.headless true

# a demonstração sem navegador (tarefa D.4 — é o plano B do vídeo)
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

1. os testes exercitam a apresentação sem subir a aplicação (54 testes, um deles
   sobe a tela de verdade com `AppTest`);
2. o console (`demo_frente_d.py`) e a tela usam as **mesmas** regras: não é
   possível um dizer "ausente em uma delas" e o outro dizer outra coisa;
3. trocar de framework de interface mais adiante não custa reescrever regra.

## O visual — onde a folha de estilo se ancora

`estilo.css` é o único lugar do projeto que depende do HTML que o Streamlit
gera, então é o único que pode quebrar sem nenhum teste de Python perceber.

A primeira versão ancorava os cartões em `div[data-testid="stVerticalBlockBorderWrapper"]`.
No Streamlit 1.64 esse `data-testid` **não existe mais**: medido no Chrome, a
regra casava zero elementos e os cartões saíam com `background: rgba(0,0,0,0)`,
`border-radius: 8px` e `box-shadow: none` — sem fundo, sem raio e sem sombra, e
sem nenhum aviso. A âncora agora é `[class*="st-key-cartao"]`, a classe que o
próprio Streamlit gera a partir do `key=` do container e que é documentada como
API pública ("CSS class name prefixed with `st-key-`"). Por isso todo
`st.container(border=True)` de `app.py` carrega um `key="cartao-..."`:
sem o `key`, não há classe, e o cartão volta a sair transparente.
`tests/test_interface.py` guarda as duas pontas — a chave em `app.py` e a regra
que precisa alcançá-la.

O outro ajuste da mesma família: as colunas de um cartão crescem independentes,
então o valor de duas linhas empurrava o rodapé 21px abaixo do vizinho (medido:
AIG 65px contra Chubb 44px). `.valor` e `.valor-ausente` passaram a ter
`min-height: 66px` — duas linhas. Um valor de três linhas ainda fica mais alto
que um de duas; igualar isso exigiria encadear `display: flex` em containers
internos do Streamlit, que é exatamente a dependência que deixou a regra do
cartão morta. Não vale o risco por 1 cartão em 9.

### A passada de acabamento

Quatro acréscimos, todos construídos sobre as mesmas duas âncoras públicas
(`st-key-` e SVG escrito à mão) — nenhum deles volta a depender de `data-testid`:

- **A arte do cabeçalho** (`ARTE_DO_CABECALHO`): dois documentos e o escudo da
  conferência, em SVG de ~1 KB, escrito no `app.py`. É SVG e não PNG porque fica
  nítido em qualquer zoom (inclusive no vídeo comprimido), acompanha a paleta e
  não engorda o repositório. **O `<div>` em volta não é enfeite:** o markdown do
  Streamlit reconhece `<div>` como bloco, mas não reconhece `<svg>` — e o que
  não reconhece, ele embrulha num `<p>`. Com o `<p>` no meio, a arte deixava de
  ser filha direta do flex `.hero-topo` e caía para baixo do texto.
- **A barra de composição** substituiu a fileira de `st.metric`. Cinco números
  soltos ("1, 0, 8, 1, 5") só viram informação depois que alguém soma; a barra
  mostra a proporção de cada situação e a legenda mantém o número exato. As
  cores saem do mesmo mapa que pinta o selo do veredito, então a mesma situação
  tem a mesma cor nos dois lugares **por construção**, não por coincidência. A
  fatia de quantidade zero recebe `flex: 0` e some, em vez de virar um traço de
  3px.
- **O ícone do campo** vem de `ICONE_DO_CAMPO`, casado com o dicionário: um
  teste falha se a frente de negócio acrescentar um campo sem ícone, e outro
  falha se sobrar ícone de campo que não existe mais. O `font-family` do
  Material Symbols é restaurado por uma regra própria, porque a folha alcança
  todo elemento do Streamlit e a ligadura do ícone depende da fonte.
- **A miniatura da página 1** do PDF, na aba *Apólices*: `st.image` não aceita
  classe própria, então a moldura se ancora em `st-key-miniatura-*`, a mesma API
  pública do cartão. Só aparece quando o arquivo original está na máquina.

### A armadilha do markdown, que custou um print

O cabeçalho chegou a exibir as tags `</div>` **escritas na tela**, dentro de um
retângulo branco, logo abaixo dos selos. Não era CSS: o markdown do Streamlit lê
a string antes de o navegador vê-la, e linha com quatro espaços ou mais vira
bloco de código. Com o HTML do cabeçalho recuado dentro da função, as tags de
fechamento deixaram de ser HTML.

Desrecuar depois com `textwrap.dedent` **não** resolve — o SVG interpolado já
está na coluna zero, então não há prefixo comum para tirar e o recuo continua
lá. O molde ficou como constante de módulo (`_MOLDE_DO_CABECALHO`), na coluna
zero, e é montado com `.format()`. A regra que o teste guarda: a **primeira**
linha do bloco decide se ele é HTML ou código, e uma linha em branco **encerra**
o bloco — o recuo de dentro (`<div>` aninhado) não é problema, o de fora é.
Os outros blocos de HTML do `app.py` já nasciam na coluna zero, por concatenação
de f-strings, e não passaram por isso.

## Contrato com a frente B (extração com LLM)

A extração das cláusulas **já está publicada**: `extrair_apolice`, em
`app.agents`, é a função que a frente D consome — e o contrato escrito antes
dela valeu, porque a interface passou a usá-la sem uma linha alterada. O que
ainda depende do ambiente é a **chave de modelo**: sem `GOOGLE_API_KEY`,
`GROQ_API_KEY` ou `OPENROUTER_API_KEY` no `.env`, a extração não roda.

* `apresentacao.encontrar_extrator(modulo)` procura, em `app.agents`, uma função
  com um destes nomes: `extrair_apolice`, `extrair_apolices`, `extrair`,
  `extrair_campos`. Ela recebe um `DocumentoExtraido` e devolve uma
  `ApoliceExtraida` (ver `app/schemas.py`);
* a aba de envio tem **três** estados, e não dois: extração ausente (a frente B
  não publicou), extração publicada **sem chave configurada**, e extração
  pronta. O estado do meio é o que importa — anunciar a extração com o `.env`
  vazio é a mentira mais cara possível neste projeto: o documento entra, é lido,
  e para. A tela diz isso com todas as letras;
* com a chave configurada, o upload grava as extrações no banco e a comparação
  usa os dados reais, sem uma linha de interface alterada.

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
| Valores dos campos extraídos | reais quando as extrações de `data/extracoes/` estão no banco (`python -m scripts.carregar_extracoes`); `exemplos.py` é o plano B, e cada tela onde ele aparece diz que é exemplo |

## Um valor pode faltar por dois motivos

`ValorNaTela` distingue três desfechos, e não dois:

| Desfecho | Quando | O que a tela escreve |
| --- | --- | --- |
| valor encontrado | o extrator devolveu valor | o valor, com página e trecho |
| valor em outro documento | não há valor, **mas** há ressalva do extrator ou trecho de origem | a ressalva do extrator — "— valor não está neste documento —" — e o botão *De onde veio* continua disponível |
| ausência | não há valor, nem ressalva, nem trecho | "— não trata do assunto —" |

O caso do meio é real e não é falha: as condições gerais de D&O definem LMI,
franquia, vigência, retroatividade e sublimites como "o valor indicado na
Especificação da Apólice", e é a especificação que traz o número. A extração acha
a cláusula e cita a página. Antes desta distinção a tela escrevia "não trata do
assunto" nesses cinco campos e **descartava a página e o trecho** — apagava o D.3
justamente onde a cláusula remete a outro documento.

Sem ressalva e sem trecho a distinção seria invenção, e aí a tela volta a dizer
ausência: é o que impede a regra de virar desculpa para campo faltando. A matriz
da aba *Tabela completa* e o CSV usam a mesma regra, por isso `matriz_comparativa`
e `exportar_csv` recebem `apolices` — a diferença mora no `CampoExtraido`, e o
motor devolve só o texto do valor.

## Pendências de integração com outras frentes

Nada disto bloqueia a frente D, mas precisa acontecer antes da entrega:

1. **`gerar_entrega.py` não empacotava `.streamlit/`** — *resolvido*:
   `".streamlit"` entrou na lista `INCLUIR` do script. Sem o `config.toml` o tema
   se perdia no ZIP e a interface abria com a cara padrão do Streamlit.
2. **README, seção "Execução"** — o item E.1 é do Daniel. A linha da interface é
   `streamlit run app/interface/app.py` e a da demonstração é
   `python -m scripts.demo_frente_d`.
3. **`python-pptx` entrou no `requirements.txt`** (seção "Apresentação"), porque o
   `scripts/gerar_pitch.py` depende dele para gerar o `.pptx`.
4. **Conferir o próprio roteiro** — o roteiro em `docs/` prevê reavaliar em 27/09
   se o pitch passa para a Juliana; se passar, o `CONTEUDO` do gerador continua
   sendo a fonte do texto.

## O que ainda falta na frente D

* ~~os três prints da interface no slide de demonstração do deck~~ — *resolvido*:
  os recortes estão em `Projeto_Final_Artefatos/prints/` e o `gerar_pitch.py` os
  cola sozinho no slide 8, com a legenda embaixo de cada um. Sem os arquivos o
  slide volta a desenhar a caixa com "print N — colar aqui", então um clone
  recém-baixado não fica com um slide quebrado. As regiões de cada recorte e as
  duas armadilhas da captura estão no fim de [`ROTEIRO_VIDEO.md`](ROTEIRO_VIDEO.md);
* a gravação do vídeo — roteiro cronometrado em [`ROTEIRO_VIDEO.md`](ROTEIRO_VIDEO.md);
* revisão do resultado com o grupo, agora com a frente B entregue, para trocar os
  números de exemplo pelos números da extração real. A tela se atualiza sozinha
  porque lê o banco; o deck **não** — `tests/test_pitch.py` ainda confere os
  números do slide contra `exemplos.py`, então trocar o texto sem trocar o teste
  deixa a suíte vermelha, e deixar os dois como estão mantém no slide números que
  já não são os da extração real. Os três prints seguem a mesma regra: foram
  recortados sobre as extrações de exemplo, e a tela mostra R$ 50.000 × R$ 80.000
  de franquia — número que a extração real não produz.
