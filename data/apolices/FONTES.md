# Apólices utilizadas — fontes

O enunciado exige que a origem de cada documento seja citada. Todas são **condições
gerais públicas**, publicadas pelas próprias seguradoras para consulta aberta. Nenhum
documento contém dado de cliente.

Reunidas por **Paulo Henrique** (corretor de seguros do grupo) em 21/09/2026.

| Arquivo | Seguradora | Origem | Baixado em |
| --- | --- | --- | --- |
| `chubb_do_capital_fechado.pdf` | Chubb | [Condições gerais D&O capital fechado](https://www.chubb.com/content/dam/chubb-sites/chubb-com/br-pt/condicoes-gerais/diretores-e-administradores/capital-fechado-processo-susep-15414-900832-2017-90-versao-a-partir-de-16-12-2025.pdf) — processo SUSEP 15414.900832/2017-90 | 21/09/2026 |
| `aig_do.pdf` | AIG | [Condições gerais D&O](https://www.aig.com.br/content/dam/aig/lac/brazil/pl-29/condi%C3%A7%C3%B5es-gerais/do_aiggo.pdf.coredownload.pdf) | 21/09/2026 |

## Pendente: terceira seguradora

A Allianz publica as condições gerais em
<https://www.allianz.com.br/content/dam/onemarketing/iberolatam/allianz-br/doc-para-links/CG_RCDO_1225.pdf>,
mas o site está atrás de Cloudflare e recusa download automatizado (devolve a página
"Just a moment..."). **Precisa ser baixado manualmente pelo navegador** e colocado aqui
como `allianz_do.pdf`.

Duas apólices já satisfazem o requisito mínimo do enunciado ("comparar pelo menos duas
apólices"); a terceira é reforço para a demonstração.

## Nota sobre a SUSEP

Não existe repositório público de condições gerais no site da SUSEP fácil de navegar,
e não é necessário: as condições gerais das seguradoras **já são registradas na SUSEP**,
e o número do processo aparece no próprio documento — o da Chubb é
`15414.900832/2017-90`. Os arquivos acima são, portanto, documentos com registro
regulatório.

## Características técnicas (medidas em 21/09/2026)

| Arquivo | Páginas | Texto embutido | Tokens aprox. |
| --- | --- | --- | --- |
| `chubb_do_capital_fechado.pdf` | 70 | sim (PDF nativo) | ~36.000 |
| `aig_do.pdf` | 72 | sim (PDF nativo) | ~39.000 |

Os dois são **PDFs nativos**: `pypdf` extrai o texto sem OCR. O caminho de OCR da
frente A continua sendo necessário para atender o requisito de aceitar imagem, mas não
é o caminho principal.
