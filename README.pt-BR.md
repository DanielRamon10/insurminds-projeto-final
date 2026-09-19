# Plataforma Inteligente para Análise e Comparação de Apólices D&O

*[Read in English](README.md)*

**Projeto Final — Curso InsurMinds · Instituto de Inteligência Artificial Aplicada (I2A2)**

Protótipo (MVP) que lê apólices de seguro D&O (*Directors and Officers*) em PDF ou
imagem, extrai automaticamente as informações relevantes — coberturas, exclusões,
franquias, limites de responsabilidade —, armazena de forma estruturada e compara
duas ou mais apólices, apontando as diferenças que importam para a decisão.

Comparar apólices D&O é hoje trabalho de especialista e leva horas: são documentos
longos, em linguagem jurídica, cujas cláusulas equivalentes aparecem com nomes e em
lugares diferentes em cada seguradora. A proposta é automatizar a maior parte dessa
leitura sem esconder de onde cada informação veio.

Licenciado sob a **licença MIT** (ver [LICENSE](LICENSE)).

---

## Grupo

| Integrante | Frente |
| --- | --- |
| Daniel Ramon | Ingestão e OCR · Armazenamento e comparação · Documentação |
| Paulo Henrique | Campos e cláusulas D&O (regras de negócio) |
| Nicole Paes | Extração das cláusulas com IA Generativa |
| Paulo Roberto | Interface, demonstração e apresentação |
| Juliana Catarina | Representante do grupo |

---

## Estado do projeto

Em desenvolvimento. O roteiro com as frentes de trabalho e as tarefas está em
[`docs/`](docs/).

**Prazo de entrega: 06/10/2026 às 23h59.**

---

## Instalação

Requer **Python 3.10 ou superior**.

```bash
git clone https://github.com/DanielRamon10/insurminds-projeto-final.git
cd insurminds-projeto-final

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

### Configuração da chave de API

```bash
copy .env.example .env           # Windows
# cp .env.example .env             # Linux / macOS
```

Abra o `.env` e preencha a chave do provedor escolhido. O arquivo `.env` está no
`.gitignore` e **nunca deve ser versionado** — nenhuma credencial aparece no
código-fonte.

---

## Execução

*A ser preenchido conforme as frentes forem entregando.*

---

## Tecnologias utilizadas

*A ser preenchido conforme as decisões da Fase 0 forem tomadas.*

---

## Estrutura de pastas

| Caminho | Conteúdo |
| --- | --- |
| `app/clients/` | Integração com serviços externos (OCR, modelos de linguagem) |
| `app/domain/` | Extração de cláusulas, estruturação e comparação entre apólices |
| `app/agents/` | Agentes especializados e orquestrador |
| `data/` | Apólices de exemplo e dados estruturados |
| `docs/` | Roteiro do projeto e relatório técnico |
| `scripts/` | Demonstração por linha de comando e utilitários |
| `tests/` | Testes automatizados |
| `Projeto_Final_Artefatos/` | Pitch deck, vídeo e demais artefatos exigidos na entrega |

---

## Observações

Nenhuma integração com sistemas reais de seguradoras. As apólices utilizadas são
documentos públicos, e suas fontes estão citadas no relatório técnico.
