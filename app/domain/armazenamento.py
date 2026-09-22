"""Armazenamento estruturado das apólices processadas — tarefa C.1.

SQLite, e não um serviço de banco: o enunciado pede "armazenamento estruturado" e
menciona SQL ou NoSQL, mas um MVP que exige subir um Postgres para ser demonstrado
é um MVP pior. O arquivo acompanha o repositório, a demonstração roda em qualquer
máquina, e a pergunta que o relatório responde não é "qual banco" e sim "por que
este basta para este problema".

Sem ORM, pelo mesmo motivo: são duas tabelas e meia dúzia de consultas.

O que justifica haver banco, e não só processar e comparar na memória:

* **Reprocessar sai caro.** Extrair uma apólice custa ~37 mil tokens; relê-la a
  cada comparação queimaria cota à toa.
* **A rastreabilidade tem de sobreviver.** Guardar só o valor extraído perderia a
  página e o trecho de origem, que é o que torna a extração auditável.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR
from ..schemas import ApoliceExtraida, CampoExtraido

CAMINHO_PADRAO = DATA_DIR / "apolices.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS apolices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    documento     TEXT NOT NULL,
    seguradora    TEXT,
    modelo_usado  TEXT,
    processada_em TEXT NOT NULL,
    UNIQUE (documento)
);

CREATE TABLE IF NOT EXISTS campos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    apolice_id        INTEGER NOT NULL REFERENCES apolices(id) ON DELETE CASCADE,
    campo_id          TEXT NOT NULL,
    valor             TEXT,
    trecho_origem     TEXT,
    pagina            INTEGER,
    paginas_possiveis TEXT NOT NULL DEFAULT '[]',
    observacao        TEXT,
    UNIQUE (apolice_id, campo_id)
);

CREATE INDEX IF NOT EXISTS idx_campos_apolice ON campos(apolice_id);
CREATE INDEX IF NOT EXISTS idx_campos_campo   ON campos(campo_id);
"""


class Banco:
    """Acesso ao armazenamento das apólices processadas."""

    def __init__(self, caminho: Path | str | None = None) -> None:
        self.em_memoria = str(caminho) == ":memory:"
        self.caminho = ":memory:" if self.em_memoria else Path(caminho or CAMINHO_PADRAO)

        # Um banco em memória vive enquanto a conexão viver: abrir e fechar a cada
        # operação, como fazemos com arquivo, descartaria os dados junto com o
        # esquema. Nesse modo a conexão fica aberta pela instância inteira.
        self._persistente: sqlite3.Connection | None = None
        if self.em_memoria:
            self._persistente = self._nova_conexao()
        else:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)

        self._criar_esquema()

    def _nova_conexao(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        # o SQLite não aplica chave estrangeira sem isto, e o ON DELETE CASCADE
        # dos campos depende disso para valer
        conexao.execute("PRAGMA foreign_keys = ON")
        return conexao

    @contextmanager
    def _conectar(self):
        conexao = self._persistente or self._nova_conexao()
        try:
            yield conexao
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        finally:
            if self._persistente is None:
                conexao.close()

    def fechar(self) -> None:
        """Encerra a conexão persistente do modo em memória."""
        if self._persistente is not None:
            self._persistente.close()
            self._persistente = None

    def _criar_esquema(self) -> None:
        with self._conectar() as c:
            c.executescript(ESQUEMA)

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def salvar(self, apolice: ApoliceExtraida) -> int:
        """Grava a apólice e devolve seu id.

        Regravar o mesmo documento substitui a extração anterior em vez de
        duplicar: reprocessar depois de melhorar o prompt é rotina, e acumular
        versões faria a comparação escolher uma ao acaso.
        """
        with self._conectar() as c:
            cursor = c.execute(
                """
                INSERT INTO apolices (documento, seguradora, modelo_usado, processada_em)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(documento) DO UPDATE SET
                    seguradora    = excluded.seguradora,
                    modelo_usado  = excluded.modelo_usado,
                    processada_em = excluded.processada_em
                """,
                (
                    apolice.documento,
                    apolice.seguradora,
                    apolice.modelo_usado,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            apolice_id = cursor.lastrowid or c.execute(
                "SELECT id FROM apolices WHERE documento = ?", (apolice.documento,)
            ).fetchone()["id"]

            c.execute("DELETE FROM campos WHERE apolice_id = ?", (apolice_id,))
            c.executemany(
                """
                INSERT INTO campos
                    (apolice_id, campo_id, valor, trecho_origem, pagina,
                     paginas_possiveis, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        apolice_id, campo.campo_id, campo.valor, campo.trecho_origem,
                        campo.pagina, json.dumps(campo.paginas_possiveis), campo.observacao,
                    )
                    for campo in apolice.campos
                ],
            )
            return apolice_id

    def apagar(self, documento: str) -> bool:
        with self._conectar() as c:
            cursor = c.execute("DELETE FROM apolices WHERE documento = ?", (documento,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def carregar(self, documento: str) -> ApoliceExtraida | None:
        """A apólice processada, com a rastreabilidade intacta."""
        with self._conectar() as c:
            linha = c.execute(
                "SELECT * FROM apolices WHERE documento = ?", (documento,)
            ).fetchone()
            if linha is None:
                return None

            campos = c.execute(
                "SELECT * FROM campos WHERE apolice_id = ? ORDER BY id", (linha["id"],)
            ).fetchall()

        return ApoliceExtraida(
            documento=linha["documento"],
            seguradora=linha["seguradora"],
            modelo_usado=linha["modelo_usado"],
            campos=[
                CampoExtraido(
                    campo_id=k["campo_id"],
                    valor=k["valor"],
                    trecho_origem=k["trecho_origem"],
                    pagina=k["pagina"],
                    paginas_possiveis=json.loads(k["paginas_possiveis"]),
                    observacao=k["observacao"],
                )
                for k in campos
            ],
        )

    def listar(self) -> list[dict]:
        """Resumo das apólices guardadas, para a interface montar o seletor."""
        with self._conectar() as c:
            linhas = c.execute(
                """
                SELECT a.documento, a.seguradora, a.modelo_usado, a.processada_em,
                       COUNT(k.id) AS total_campos,
                       SUM(CASE WHEN k.valor IS NOT NULL AND k.valor != ''
                                THEN 1 ELSE 0 END) AS encontrados
                FROM apolices a
                LEFT JOIN campos k ON k.apolice_id = a.id
                GROUP BY a.id
                ORDER BY a.processada_em DESC
                """
            ).fetchall()
        return [dict(l) for l in linhas]

    def carregar_varias(self, documentos: list[str]) -> list[ApoliceExtraida]:
        """Carrega as apólices pedidas, ignorando as que não estiverem guardadas."""
        carregadas = (self.carregar(d) for d in documentos)
        return [a for a in carregadas if a is not None]

    def tem(self, documento: str) -> bool:
        with self._conectar() as c:
            return c.execute(
                "SELECT 1 FROM apolices WHERE documento = ?", (documento,)
            ).fetchone() is not None
