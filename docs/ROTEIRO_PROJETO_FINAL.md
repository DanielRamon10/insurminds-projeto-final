# Roteiro do Projeto Final — Plataforma de Análise e Comparação de Apólices D&O

**Grupo Insurminds · Curso InsurMinds / I2A2**
**Prazo: 06/10/2026 às 23h59** — este documento foi escrito em 14/09/2026, restam **22 dias**.

---

## O que muda em relação ao Desafio 5

Três coisas novas, e as três pesam:

| Novidade | Por que exige atenção |
| --- | --- |
| **Pitch deck** (`InsurMinds_Projeto_Final.pptx`) | Nome de arquivo obrigatório e literal. Não é slide de apoio: é entregável avaliado |
| **Vídeo de até 5 minutos** (`InsurMinds_Projeto_Final.mp4`) | Precisa de produto funcionando para gravar. Se ficar para o fim, não existe |
| **Documento de entrada não estruturado** | No Desafio 5 a API devolvia números prontos. Aqui a entrada é PDF jurídico de dezenas de páginas |

E uma mudança de natureza: **esta é a avaliação final do curso**. Sem ela, o grupo não é
aprovado e ninguém recebe o certificado do módulo avançado.

---

## Fase 0 — Decisões antes de escrever código

Nada disso é técnico o bastante para uma pessoa decidir sozinha. São quatro decisões, e
todas travam trabalho de mais de uma frente.

### F0.1 — Quais campos comparar

**A decisão mais importante do projeto.** Uma apólice D&O tem dezenas de cláusulas; o
sistema não precisa extrair todas, precisa extrair as que mudam uma decisão.

Candidatos para a conversa: limite máximo de indenização, franquia (retenção), vigência,
âmbito geográfico, definição de segurado, exclusões principais, cobertura para custos de
defesa, retroatividade, prazo complementar.

> **Quem decide:** Paulo Henrique lidera — é corretor, e essa é exatamente a leitura que
> ele faz no trabalho. O grupo confirma o escopo.
> **Meta:** 8 a 12 campos. Menos que isso não demonstra comparação; mais vira extração
> rasa em todos.

### F0.2 — Onde conseguir as apólices

O enunciado sugere documentos públicos: modelos publicados por seguradoras, material da
SUSEP, cláusulas padrão de mercado. **Precisamos de pelo menos três apólices reais de
seguradoras diferentes** — comparar duas versões do mesmo modelo não demonstra nada.

> **Quem decide:** Paulo Henrique indica onde procurar; qualquer um baixa.
> **Atenção:** a fonte de cada documento tem de ser citada no relatório.

### F0.3 — Como ler o documento

Três caminhos, e a escolha muda a frente A inteira:

1. **PDF nativo** (texto embutido) — `pypdf` resolve, é rápido e não custa nada.
2. **PDF escaneado** — exige OCR (Tesseract local, ou serviço de nuvem).
3. **LLM multimodal** — manda a página como imagem e deixa o modelo ler.

> **Recomendação:** tentar o caminho 1 primeiro e cair no OCR só quando a página não tiver
> texto. A maioria dos modelos públicos de apólice é PDF nativo. Mas **o enunciado exige
> aceitar imagem**, então o caminho 2 precisa existir nem que seja para um documento.

### F0.4 — Onde guardar o que foi extraído

O enunciado pede "armazenamento estruturado" e cita SQL ou NoSQL. Para um MVP, SQLite
resolve e não exige subir serviço nenhum.

> **Recomendação:** SQLite. A pergunta a responder no relatório não é "qual banco", é
> "por que este banco basta para o problema".

---

## As cinco frentes

### Frente A — Ingestão e extração de texto

Transformar o arquivo que chega em texto confiável, sabendo de qual página veio cada
trecho — sem isso a rastreabilidade da frente B morre.

| Tarefa | O que entrega |
| --- | --- |
| **A.1** | Recepção do documento: aceita PDF e imagem, rejeita o resto com mensagem clara |
| **A.2** | Extração de PDF nativo, preservando número de página |
| **A.3** | OCR para páginas sem texto embutido |
| **A.4** | Tolerância a falha: documento corrompido ou página ilegível não derruba o lote |

**Pronto quando:** as três apólices escolhidas em F0.2 viram texto, e cada trecho sabe
dizer de que página saiu.

### Frente B — Extração das cláusulas (o coração do projeto)

É aqui que a IA Generativa entra de verdade, e é o que o enunciado avalia como "correta
utilização de IA Generativa".

| Tarefa | O que entrega |
| --- | --- |
| **B.1** | Dicionário dos campos de F0.1: nome, o que significa, como costuma aparecer no texto |
| **B.2** | Agente extrator com LLM: recebe o texto, devolve os campos estruturados |
| **B.3** | **Rastreabilidade**: cada campo extraído guarda a página e o trecho de origem |
| **B.4** | Validação: campo ausente é `null` explícito, nunca inventado |

**Pronto quando:** rodando sobre as três apólices, sai uma estrutura preenchida e é
possível apontar, para qualquer campo, onde ele estava no documento.

> **A lição do Desafio 5 aplicada aqui:** lá, o guardrail impedia o modelo de citar número
> que a previsão não tinha. Aqui o risco é maior — um limite de indenização inventado é
> pior que uma mensagem errada. **B.3 não é enfeite: é o que separa o projeto de um
> chute bem formatado.**

### Frente C — Armazenamento e comparação

| Tarefa | O que entrega |
| --- | --- |
| **C.1** | Esquema do banco e gravação das apólices processadas |
| **C.2** | Motor de comparação: campo a campo, entre duas ou mais apólices |
| **C.3** | Classificação da diferença: igual, diferente, ausente numa delas |
| **C.4** | Relatório comparativo em texto, gerado por LLM a partir das diferenças |

**Pronto quando:** dadas duas apólices, sai uma tabela de diferenças e um resumo que
explica o que elas significam para quem contrata.

> **Cuidado com a fronteira:** C.2 decide *o que* é diferente (determinístico, testável);
> C.4 explica *por que importa* (LLM). Misturar os dois foi o erro que custou um PR de
> consolidação no Desafio 5.

### Frente D — Interface e demonstração

| Tarefa | O que entrega |
| --- | --- |
| **D.1** | Upload de apólices pela interface |
| **D.2** | Visualização lado a lado das diferenças |
| **D.3** | Rastreabilidade na tela: clicar num campo e ver de onde ele veio |
| **D.4** | Demonstração por linha de comando, para o vídeo não depender da interface |

**Pronto quando:** dá para subir duas apólices e ver a comparação sem tocar no terminal.

### Frente E — Documentação, pitch e vídeo

Maior que no Desafio 5, e com dois entregáveis que não são texto.

| Tarefa | O que entrega |
| --- | --- |
| **E.1** | README com os **seis** itens obrigatórios do enunciado |
| **E.2** | Relatório técnico com **sete** seções (duas novas: limitações conhecidas e evolução futura) |
| **E.3** | `InsurMinds_Projeto_Final.pptx` — pitch deck |
| **E.4** | `InsurMinds_Projeto_Final.mp4` — vídeo de até 5 minutos |
| **E.5** | ZIP do código e organização da pasta `Projeto_Final_Artefatos` |

---

## Divisão sugerida

Baseada no que cada um demonstrou no Desafio 5. **A Juliana está viajando**, então a
frente E foi repartida entre os quatro — ela permanece como representante, responsável
pelo envio, e reassume o que fizer sentido quando voltar.

| Integrante | Frente | Por quê |
| --- | --- | --- |
| **Paulo Henrique** | F0.1, F0.2, B.1 + conteúdo de negócio do pitch | É o corretor. O dicionário de campos D&O é o `regras.yaml` deste projeto — a peça que deu ao Desafio 5 seu melhor argumento. E o problema do pitch é a dor que ele vive: horas de especialista comparando cláusulas |
| **Nicole Paes** | Frente B (B.2 a B.4) | Entregou os agentes e achou o bug do LLM que se disfarçava de fallback correto |
| **Daniel Ramon** | Frentes A e C + E.1, E.5 + consolidação do relatório | Coleta e motor de regras foram suas no Desafio 5, e o README e o empacotamento também |
| **Paulo Roberto** | Frente D + **E.3 (pitch)** + **E.4 (vídeo)** | Fez a interface e a demonstração; é quem melhor sabe mostrar o sistema funcionando |
| **Juliana Catarina** | Envio da entrega | Representante do grupo — a submissão sai obrigatoriamente do e-mail dela |

### O relatório técnico sem a Juliana

E.2 é a maior peça órfã. Em vez de um dono só, **cada frente escreve a seção que lhe
corresponde** e o Daniel consolida:

| Seção do relatório | Quem escreve |
| --- | --- |
| Arquitetura da solução | Daniel |
| Tecnologias utilizadas | Daniel |
| Descrição dos agentes | Nicole (frente B) e Paulo Roberto (frente D) |
| Fluxo de processamento | Daniel |
| Justificativa das decisões arquiteturais | quem tomou cada decisão, em uma frase |
| Limitações conhecidas | todos — cada um sabe onde a própria frente é frágil |
| Possibilidades de evolução futura | todos |

> **Quando a Juliana voltar**, o caminho natural é devolver a ela a revisão e a formatação
> final do relatório — foi o que ela fez bem no Desafio 5, e é trabalho de fim de ciclo.
> Se voltar a tempo, o pitch também pode ir para ela, liberando o Paulo Roberto para
> focar no vídeo. Reavaliar por volta de **27/09**.

> **Por que o vídeo fica com o Paulo Roberto:** gravar exige a aplicação rodando na mão de
> quem a construiu. Ele monta o pitch e grava; o Paulo Henrique dá o conteúdo do problema
> de negócio, que é a primeira parte do deck.

---

## Calendário sugerido

| Até | O que precisa estar pronto |
| --- | --- |
| **17/09** | Fase 0 fechada. Apólices baixadas, campos definidos, stack escolhida |
| **22/09** | Frentes A e B funcionando: documento entra, campos saem estruturados |
| **27/09** | Frente C: comparação entre duas apólices gerando saída. **Reavaliar o que devolver à Juliana** |
| **30/09** | Frente D: interface demonstrável. **Congelamento de funcionalidades** |
| **02/10** | Vídeo gravado e pitch pronto |
| **04/10** | Relatório final e ZIP. Revisão do grupo |
| **06/10** | Entrega — **não deixar para este dia** |

O congelamento em 30/09 não é burocracia: **sem produto estável não há vídeo**, e o
vídeo é o entregável mais fácil de perder por falta de tempo.

---

## Riscos conhecidos

1. **O vídeo ficar para o fim.** É o item mais provável de atrasar. Por isso tem dono e
   data próprios.
2. **Extração alucinada.** Um limite de indenização inventado passa despercebido numa
   demonstração e destrói a credibilidade numa pergunta. B.3 e B.4 existem contra isso.
3. **Cota do LLM.** Já aconteceu no Desafio 4 e no 5. Processar uma apólice inteira gasta
   muito mais token que gerar uma mensagem de SMS — **testar o consumo cedo**.
4. **Apólices difíceis.** Se os três documentos forem escaneados e ilegíveis, a frente A
   vira o gargalo. Por isso F0.2 vem antes de tudo.
5. **Quatro pessoas em vez de cinco.** Com a Juliana viajando, a frente E está repartida
   e o relatório não tem um dono único. O risco não é a escrita — é ninguém reparar que
   uma seção ficou sem autor. A tabela de seções acima existe para isso; conferir na
   revisão de 04/10, e **não contar com o retorno dela** para que a entrega aconteça.
