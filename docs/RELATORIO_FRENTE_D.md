# Relatório técnico — seções da frente D

Texto pronto para colar, escrito por **Paulo Roberto**. O roteiro pede que cada
frente escreva a seção que lhe corresponde e que o Daniel consolide; este arquivo
existe para que a contribuição não se perca no meio da conversa.

---

## Descrição dos agentes e da interface (frente D)

A interface é a última camada da plataforma e não decide nada por conta própria:
ela lê o que as frentes anteriores produziram e apresenta. Essa escolha é
deliberada. O protótipo tem quatro etapas — ingestão (A), extração (B),
armazenamento e comparação (C) e apresentação (D) — e cada uma conversa com a
seguinte apenas por meio dos modelos de `app/schemas.py`. A interface conhece
`DocumentoExtraido`, `ApoliceExtraida` e `CampoExtraido`; não conhece pypdf, não
conhece prompt, não conhece SQL.

Na prática, a tela executa três passos:

1. **Seleção e leitura.** A lista de apólices vem do banco SQLite (`Banco.listar`)
   e as escolhidas são carregadas inteiras, com a rastreabilidade preservada.
2. **Comparação.** O motor determinístico recebe as apólices e o dicionário de
   campos e devolve um resultado por campo, com veredito, valores e páginas de
   origem. A interface não recalcula nada: os números do topo da tela são a
   contagem do motor, e há teste automatizado garantindo que continuem sendo.
3. **Apresentação.** Um módulo sem dependência de Streamlit (`apresentacao.py`)
   traduz o vocabulário do motor — `ausente_em_alguma`, `redacao_divergente` — para
   o vocabulário de quem contrata seguro: "ausente em uma delas", "redação
   divergente", "igual nas duas". A tradução vive em um lugar só, o que mantém a
   tela, a demonstração por linha de comando e o relatório dizendo a mesma coisa.

**Sobre os agentes de IA generativa vistos pela interface.** A extração com modelo
de linguagem (frente B) é tratada como um serviço que pode ou não estar
disponível: a interface procura em `app.agents` uma função de extração (contrato
documentado em `apresentacao.encontrar_extrator`) e, quando ela não existe,
declara isso na tela em vez de exibir campos vazios. Campo vazio seria lido como
"a apólice não trata do assunto" — a conclusão mais danosa possível, porque é
exatamente a que o motor de comparação classifica como a diferença mais relevante.

## Justificativa das decisões arquiteturais

Uma frase por decisão, como o roteiro pede:

* **Streamlit** — permite demonstrar um fluxo interativo completo (upload,
  comparação, rastreabilidade clicável) sem escrever front-end, e já estava em
  `requirements.txt`.
* **Regras de apresentação fora do Streamlit** (`apresentacao.py`) — porque um
  aplicativo Streamlit só existe durante a execução dele, o que tornaria
  intestável justamente a parte que precisa permanecer estável entre a
  demonstração e a entrega.
* **Um vocabulário único de vereditos** — o mesmo rótulo na tela, no CSV e na
  demonstração por linha de comando; sem isso, três superfícies contariam a mesma
  história com palavras diferentes.
* **Rastreabilidade como elemento de interface, não como rodapé** — a página de
  origem de cada valor é acessível com um clique, e a página do PDF é renderizada
  ao lado do trecho, porque a pergunta que a banca fará é "de onde saiu esse
  número".
* **Nenhum dado fabricado sem aviso** — as extrações de exemplo aparecem marcadas
  no banner, no cartão de cada apólice e no rodapé da demonstração; o custo de
  dizê-lo é uma linha de texto, e o custo de omiti-lo seria a credibilidade do
  projeto.
* **CSV com separador `;` e BOM** — a saída é para ser aberta no Excel em
  português por quem trabalha com apólices, não por quem programa.
* **A proporção antes do número** — a barra de composição substituiu a fileira de
  KPIs porque "1, 0, 8, 1, 5" só vira informação depois que alguém soma; a barra
  mostra o peso de cada situação e a legenda mantém o número exato, e as duas
  saem do mesmo mapa de cores do selo do veredito, de modo que a mesma situação
  tem a mesma cor em toda a tela por construção.
* **A arte do cabeçalho é SVG escrito no código, não imagem no repositório** —
  pesa menos de 1 KB, fica nítida em qualquer zoom (inclusive no vídeo
  comprimido) e acompanha a paleta; um PNG não faria nenhum dos três, e o
  enunciado não pede identidade visual própria.
* **Pitch deck gerado por script** (`scripts/gerar_pitch.py`) — o nome do arquivo
  é exigido literalmente pelo enunciado e os números do deck saem do próprio
  código; gerado à mão, o texto envelheceria em silêncio. Há teste que confere os
  números do deck contra o motor de comparação.
* **Os prints do deck saem do próprio gerador** — o slide de demonstração cola os
  recortes de `Projeto_Final_Artefatos/prints/` sozinho, com a legenda embaixo de
  cada tela. Sem os arquivos, o mesmo slide desenha a caixa com "print N — colar
  aqui" e a execução diz quais faltam: um clone recém-baixado mostra o que falta
  em vez de um slide quebrado, e não existe o estado intermediário de uma tela
  colada ao lado de duas caixas vazias.
* **Demonstração por linha de comando (D.4)** — o vídeo é o entregável mais fácil
  de perder; se o navegador ou o Streamlit falharem na máquina de quem grava,
  existe um caminho alternativo que mostra o sistema inteiro sem interface.

## Fluxo de processamento (contribuição da frente D)

Da perspectiva de quem usa:

1. o corretor escolhe duas apólices já processadas — ou envia uma nova, que passa
   pela ingestão e é lida página a página;
2. a tela chama o motor de comparação com essas apólices e o dicionário do
   especialista;
3. para cada campo, o motor decide entre igual, diferente, redação divergente,
   ausente em uma das apólices ou fora das duas;
4. a tela agrupa o que difere por tipo de diferença, coloca os valores lado a lado
   e mostra, abaixo do par de valores, a frase do especialista explicando por que
   aquela diferença importa;
5. qualquer valor encontrado pode ser aberto até o trecho e a página do documento;
6. a comparação inteira pode ser baixada em CSV.

## Limitações conhecidas (frente D)

* **A demonstração roda sobre extrações de exemplo.** A extração com LLM está
  publicada (`extrair_apolice`, em `app.agents`) e funciona: nos documentos
  comparados ela devolve 9 dos 15 campos na AIG e 10 na Chubb, todos com página e
  trecho. Os que faltam são numéricos — LMI, franquia, vigência, retroatividade e
  sublimites — e não faltam por falha: as condições gerais definem cada um como "o
  valor indicado na Especificação da Apólice", e é a especificação que traz o
  número. A extração acha a cláusula, cita a página e registra a ressalva. Como não
  há número para comparar, os valores da demonstração continuam sendo dados escritos
  à mão em `app/domain/exemplos.py`. Ingestão, banco, comparação, rastreabilidade e
  interface são reais; os campos, não. O relatório precisa dizer isso onde citar
  números da demonstração.
* **Ausência e "valor em outro documento" já se distinguem na tela.** Quando o
  campo não tem valor, a interface consulta a prova que o extrator deixou: havendo
  ressalva ou trecho de origem, mostra a ressalva — "— valor não está neste
  documento —" com o texto do extrator — e **continua oferecendo o botão *De onde
  veio***; sem nenhuma das duas, mostra "não trata do assunto". Antes disso a tela
  escrevia "não trata do assunto" nos cinco campos numéricos e descartava a página e
  o trecho registrados, ou seja, apagava rastreabilidade justamente onde a cláusula
  remete a outro documento. `tests/test_interface.py` guarda os dois lados,
  inclusive contra a extração real de `data/extracoes/`.
* **Uma comparação por vez na tela.** Comparar três ou mais apólices funciona no
  motor e é testado, mas o layout lado a lado fica estreito; a tela assume o caso
  de uso real, que é comparar duas propostas.
* **Sem edição e sem anotação.** A tela não permite que o especialista corrija um
  valor extraído nem registre uma observação; nesta versão, corrigir significa
  reprocessar ou editar o banco.
* **Não há como remover uma apólice pela tela.** O banco sabe apagar
  (`Banco.apagar`), mas a interface não oferece o botão — excluir é operação sem
  volta e ficou fora do escopo desta versão.
* **Enviar um arquivo com nome de apólice já processada substitui a extração
  guardada.** O banco mantém uma versão por documento, e a última extração é a que
  vale; a tela avisa quando isso acontece, mas não guarda histórico.
* **Página renderizada não destaca o trecho.** A imagem da página aparece
  inteira, sem realce no trecho citado — a conferência é visual, não automática.
* **A conferência visual exige o arquivo.** O botão *De onde veio* renderiza a
  página do PDF apenas quando o documento está na máquina; enviado por upload, ele
  fica em um diretório temporário da sessão e some ao encerrar.
* **Sem autenticação.** Qualquer pessoa com acesso à máquina vê todas as apólices
  gravadas; para um protótipo acadêmico com documentos públicos isso é aceitável,
  para uso real não seria.
* **O tema depende do arquivo de configuração.** Sem `.streamlit/config.toml` no
  pacote, a interface perde a identidade visual e volta ao tema padrão.

## Possibilidades de evolução futura (frente D)

* **Destacar o trecho na página renderizada** — hoje a interface mostra a página; o
  próximo passo é desenhar sobre ela o retângulo exato de onde o valor saiu, o que
  exige que o extrator devolva a posição do trecho no texto, não só a página.
* **Correção assistida pelo especialista** — permitir editar um campo na tela e
  registrar a correção como revisão, fechando o ciclo entre o corretor e o
  extrator.
* **Comparação de três ou mais apólices com layout próprio** — matriz de
  diferenças com as apólices nas colunas e destaque do que é exclusivo de cada uma.
* **Modo apresentação** — trilha guiada que conduz da apólice bruta à diferença
  final, útil em demonstrações comerciais.
* **Histórico de versões da mesma apólice** — comparar a renovação do ano com a do
  ano anterior e mostrar apenas o que mudou, que é a pergunta que o corretor faz de
  verdade.
* **Exportação no formato de trabalho do corretor** — além do CSV, um documento
  comparativo com o texto do relatório (C.4) já redigido.