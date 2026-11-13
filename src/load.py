# -*- coding: utf-8 -*-
"""Camada OURO: cria o schema (sql/schema.sql) e carrega data/silver/ no MySQL.
Uso:  python src/load.py          (credenciais em variáveis de ambiente ou arquivo .env)
"""
import os
import re
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SILVER = os.path.join(BASE, "data", "silver", "ocorrencia_limpo.csv")
SCHEMA = os.path.join(BASE, "sql", "schema.sql")
REGIAO = {**dict.fromkeys("AC AM AP PA RO RR TO".split(), "NORTE"),
          **dict.fromkeys("AL BA CE MA PB PE PI RN SE".split(), "NORDESTE"),
          **dict.fromkeys("DF GO MS MT".split(), "CENTRO-OESTE"),
          **dict.fromkeys("ES MG RJ SP".split(), "SUDESTE"),
          **dict.fromkeys("PR RS SC".split(), "SUL")}
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def url_conexao(com_banco=True):
    """Monta a conexão a partir de DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME (ou DB_URL).
    URL.create cuida de caracteres especiais na senha (@, #, : ...)."""
    if os.getenv("DB_URL"):
        return os.environ["DB_URL"]
    return URL.create("mysql+pymysql", username=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
                      host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
                      database=os.getenv("DB_NAME", "ocorrencias_aeronauticas") if com_banco else None,
                      query={"charset": "utf8mb4"})


def executar_ddl(engine, caminho=SCHEMA):
    """Executa o script DDL (CREATE DATABASE/TABLE) comando a comando."""
    with open(caminho, encoding="utf-8") as f:
        sql = re.sub(r"--[^\n]*", "", f.read())          # remove comentários
    comandos = [c.strip() for c in sql.split(";") if c.strip()]
    with engine.connect() as conn:
        for c in comandos:
            conn.execute(text(c))
        conn.commit()
    print(f"✅ DDL executado ({len(comandos)} comandos)")


def construir_dimensoes(df):
    d = {}
    d["dim_classificacao"] = pd.DataFrame({"nome": sorted(df.ocorrencia_classificacao.unique())})
    ufs = sorted(df.ocorrencia_uf.unique())
    d["dim_uf"] = pd.DataFrame({"sigla": ufs, "regiao": [REGIAO.get(u, "NÃO INFORMADO") for u in ufs]})
    d["dim_aerodromo"] = pd.DataFrame({"codigo": sorted(df.ocorrencia_aerodromo.unique())})
    d["dim_aerodromo"]["fora_aerodromo"] = (d["dim_aerodromo"].codigo == "FAER").astype(int)
    datas = pd.to_datetime(pd.Series(sorted(df.data_ocorrencia.unique())))
    d["dim_tempo"] = pd.DataFrame({
        "id_data": datas.dt.strftime("%Y%m%d").astype(int), "data": datas.dt.date, "ano": datas.dt.year,
        "trimestre": datas.dt.quarter, "mes": datas.dt.month, "nome_mes": datas.dt.month.map(lambda m: MESES[m - 1]),
        "dia": datas.dt.day, "dia_semana": datas.dt.dayofweek, "nome_dia_semana": datas.dt.dayofweek.map(lambda i: DIAS[i])})
    return d


def carregar():
    if not os.path.exists(SILVER):
        sys.exit(f"❌ {SILVER} não encontrado. Rode antes: python src/transform.py")
    df = pd.read_csv(SILVER, encoding="utf-8", parse_dates=["data_ocorrencia", "data_publicacao"],
                     keep_default_na=False, na_values=[""])
    try:
        # 1) cria o banco e as tabelas
        executar_ddl(create_engine(url_conexao(com_banco=False)))
        engine = create_engine(url_conexao())
        dims = construir_dimensoes(df)

        # 2) carga em uma única transação: se algo falhar, nada é gravado
        with engine.begin() as conn:
            for nome in ["dim_classificacao", "dim_uf", "dim_aerodromo", "dim_tempo"]:
                dims[nome].to_sql(nome, conn, if_exists="append", index=False)
            m_uf = pd.read_sql("SELECT id_uf, sigla FROM dim_uf", conn)
            cid = df[["ocorrencia_cidade", "ocorrencia_uf"]].drop_duplicates().merge(
                m_uf, left_on="ocorrencia_uf", right_on="sigla")
            cid[["ocorrencia_cidade", "id_uf"]].rename(columns={"ocorrencia_cidade": "nome"}).to_sql(
                "dim_cidade", conn, if_exists="append", index=False)

            m_cl = pd.read_sql("SELECT id_classificacao, nome AS ocorrencia_classificacao FROM dim_classificacao", conn)
            m_ae = pd.read_sql("SELECT id_aerodromo, codigo AS ocorrencia_aerodromo FROM dim_aerodromo", conn)
            m_ci = pd.read_sql("SELECT c.id_cidade, c.nome AS ocorrencia_cidade, u.sigla AS ocorrencia_uf "
                               "FROM dim_cidade c JOIN dim_uf u ON u.id_uf = c.id_uf", conn)
            f = (df.merge(m_cl, on="ocorrencia_classificacao").merge(m_ae, on="ocorrencia_aerodromo")
                   .merge(m_ci, on=["ocorrencia_cidade", "ocorrencia_uf"]))
            f["id_data"] = f.data_ocorrencia.dt.strftime("%Y%m%d").astype(int)
            fato = f.rename(columns={
                "ocorrencia_latitude": "latitude", "ocorrencia_longitude": "longitude",
                "ocorrencia_saida_pista": "saida_pista", "investigacao_aeronave_liberada": "aeronave_liberada",
                "investigacao_status": "status_investigacao", "divulgacao_relatorio_numero": "relatorio_numero",
                "divulgacao_relatorio_publicado": "relatorio_publicado", "total_aeronaves_envolvidas": "total_aeronaves",
                "outlier_recomendacoes": "flag_outlier_recomendacoes",
                "aeronaves_inconsistente": "flag_aeronaves_inconsistente"})[[
                "codigo_ocorrencia", "id_classificacao", "id_cidade", "id_aerodromo", "id_data", "hora_ocorrencia",
                "hora_dia", "latitude", "longitude", "saida_pista", "aeronave_liberada", "status_investigacao",
                "investigacao_ativa", "relatorio_numero", "relatorio_publicado", "data_publicacao",
                "total_recomendacoes", "total_aeronaves", "flag_outlier_recomendacoes", "flag_aeronaves_inconsistente"]]
            fato.to_sql("fato_ocorrencia", conn, if_exists="append", index=False, chunksize=2000)

        # 3) validação
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM fato_ocorrencia")).scalar()
        print(f"✅ Carga concluída: {n} linhas na fato (Prata: {len(df)})")
        if n != len(df):
            sys.exit("❌ Contagem divergente entre Prata e Ouro!")
    except SQLAlchemyError as erro:
        sys.exit(f"❌ Erro de banco de dados (nada foi gravado na carga): {erro}")


if __name__ == "__main__":
    carregar()
