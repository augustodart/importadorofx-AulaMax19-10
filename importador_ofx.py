import os
import tkinter as tk
from tkinter import filedialog, messagebox
from decimal import Decimal

import psycopg2
from ofxparse import OfxParser


DATABASE_URL = "postgresql://neondb_owner:npg_VwIrJ81TvUhB@ep-jolly-pond-aep70w52-pooler.c-2.us-east-2.aws.neon.tech/ofx?sslmode=require&channel_binding=require"

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS movimentacoes (
    id SERIAL PRIMARY KEY,
    data_movimentacao DATE NOT NULL,
    valor NUMERIC(15,2) NOT NULL,
    descricao VARCHAR(255) NOT NULL DEFAULT ''
);
"""

SQL_INDICE_UNICO = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_movimentacao_unica
ON movimentacoes (
    data_movimentacao,
    valor,
    (COALESCE(descricao, ''))
);
"""

SQL_INSERIR = """
INSERT INTO movimentacoes (
    data_movimentacao,
    valor,
    descricao
)
VALUES (%s, %s, %s)
ON CONFLICT DO NOTHING;
"""


def obter_data_transacao(transacao):
    """
    Obtém a data da transação, considerando
    os nomes de atributos usados pelo ofxparse.
    """
    data = getattr(transacao, "dtposted", None)

    if data is None:
        data = getattr(transacao, "date", None)

    if data is None:
        raise ValueError(
            f"Transação sem data reconhecida: {vars(transacao)}"
        )

    # 
    if hasattr(data, "date"):
        data = data.date()

    return data


def importar_ofx():
    arquivo_ofx = filedialog.askopenfilename(
        title="Selecione o arquivo OFX",
        filetypes=[
            ("Arquivos OFX", "*.ofx"),
            ("Todos os arquivos", "*.*")
        ]
    )

    if not arquivo_ofx:
        return

    if not DATABASE_URL:
        messagebox.showerror(
            "Erro de configuração",
            "A variável de ambiente DATABASE_URL não foi configurada."
        )
        return

    try:
        with open(arquivo_ofx, "rb") as arquivo:
            ofx = OfxParser.parse(arquivo)

        transacoes = ofx.account.statement.transactions

        entradas = Decimal("0.00")
        saidas = Decimal("0.00")
        inseridas = 0
        duplicadas = 0

        with psycopg2.connect(
            DATABASE_URL,
            sslmode="require",
            connect_timeout=15
        ) as conexao:

            with conexao.cursor() as cursor:
                cursor.execute(SQL_CRIAR_TABELA)
                cursor.execute(SQL_INDICE_UNICO)

                for t in transacoes:
                    valor = Decimal(str(t.amount)).quantize(
                        Decimal("0.01")
                    )

                    data_movimentacao = obter_data_transacao(t)

                    descricao = (
                        getattr(t, "memo", None)
                        or getattr(t, "payee", None)
                        or ""
                    )

                    descricao = str(descricao)[:255]

                    cursor.execute(
                        SQL_INSERIR,
                        (
                            data_movimentacao,
                            valor,
                            descricao
                        )
                    )

                    if cursor.rowcount == 1:
                        inseridas += 1
                    else:
                        duplicadas += 1

                    if valor > 0:
                        entradas += valor
                    elif valor < 0:
                        saidas += valor

        saldo = entradas + saidas

        resultado = (
            f"Arquivo: {os.path.basename(arquivo_ofx)}\n\n"
            f"Transações lidas: {len(transacoes)}\n"
            f"Movimentações inseridas: {inseridas}\n"
            f"Duplicadas ignoradas: {duplicadas}\n\n"
            f"Entradas: R$ {entradas:.2f}\n"
            f"Saídas: R$ {saidas:.2f}\n"
            f"Saldo: R$ {saldo:.2f}\n\n"
            "Importação concluída!"
        )

        messagebox.showinfo(
            "Resultado da importação",
            resultado
        )

    except Exception as erro:
        messagebox.showerror(
            "Erro na importação",
            f"Não foi possível importar o arquivo:\n{erro}"
        )


# Interface gráfica
janela = tk.Tk()
janela.title("Importador de Extrato OFX")
janela.geometry("420x230")
janela.resizable(False, False)

titulo = tk.Label(
    janela,
    text="Importação de Extrato Bancário",
    font=("Arial", 14, "bold")
)
titulo.pack(pady=20)

descricao = tk.Label(
    janela,
    text=(
        "Selecione um arquivo OFX para importar\n"
        "as movimentações para o PostgreSQL."
    )
)
descricao.pack(pady=10)

botao = tk.Button(
    janela,
    text="Selecionar arquivo OFX",
    command=importar_ofx,
    font=("Arial", 11),
    width=25,
    height=2
)
botao.pack(pady=15)

janela.mainloop()