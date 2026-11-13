# -*- coding: utf-8 -*-
"""Camada PRATA: limpeza e tratamento. Lê data/raw/ocorrencia.csv e grava data/silver/.
Reexecutável do zero:  python src/transform.py
"""
import os
import numpy as np
import pandas as pd

from pathlib import Path
BASE = Path(__file__).resolve().parent.parent          # raiz do projeto (funciona de qualquer pasta)
RAW = BASE / "data" / "raw" / "ocorrencia.csv"
SILVER_DIR = BASE / "data" / "silver"
SILVER_CSV = SILVER_DIR / "ocorrencia_limpo.csv"
SILVER_PARQUET = SILVER_DIR / "ocorrencia_limpo.parquet"
OUTROS_LOCAIS = [BASE / "ocorrencia.csv", Path.cwd() / "ocorrencia.csv", BASE.parent / "ocorrencia.csv"]
MARCADORES_NULOS = ["***", "**", "*", "****", "*****", "NULL", "NAN", ""]
LAT_BR, LON_BR = (-34.0, 6.0), (-74.0, -33.0)          # caixa delimitadora do Brasil
LOG = []                                               # relatório de tratamento


def log(msg):
    LOG.append(msg)
    print(msg)


def extrair(caminho=RAW):
    """Lê o CSV bruto (sem alterá-lo), testando encodings."""
    if not os.path.exists(caminho):
        achado = next((c for c in OUTROS_LOCAIS if c.exists()), None)
        if achado is None:
            raise FileNotFoundError(f"Arquivo bruto não encontrado. Coloque o ocorrencia.csv em: {caminho}")
        log(f"[aviso] usando {achado} (o ideal é guardá-lo em data/raw/)")
        caminho = achado
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(caminho, sep=";", encoding=enc, dtype=str)
            log(f"[extração] {len(df)} linhas, {df.shape[1]} colunas (encoding={enc})")
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível decodificar o arquivo.")


def padronizar_texto(df):
    """trim + MAIÚSCULAS; marcadores (***, **, ...) viram NaN."""
    for c in df.columns:
        df[c] = df[c].astype("string").str.strip().str.upper().replace(MARCADORES_NULOS, pd.NA)
    return df


def remover_colunas_redundantes(df):
    """codigo_ocorrencia1..4 são cópias do código principal: só remove se forem idênticas."""
    for c in [c for c in df.columns if c.startswith("codigo_ocorrencia") and c != "codigo_ocorrencia"]:
        if df[c].equals(df["codigo_ocorrencia"]):
            df = df.drop(columns=c)
            log(f"[redundância] coluna '{c}' idêntica a codigo_ocorrencia: removida")
    return df


def tratar_duplicidades(df):
    antes = len(df)
    df = df.drop_duplicates().drop_duplicates(subset="codigo_ocorrencia", keep="first")
    log(f"[duplicidades] {antes - len(df)} registros removidos (linha completa ou código repetido)")
    return df


def converter_tipos(df):
    """Datas ISO-8601, números e booleanos (SIM/NÃO -> 1/0)."""
    df["codigo_ocorrencia"] = pd.to_numeric(df["codigo_ocorrencia"], errors="raise").astype("int64")
    df["data_ocorrencia"] = pd.to_datetime(df["ocorrencia_dia"], format="%d/%m/%Y", errors="coerce")
    df["data_publicacao"] = pd.to_datetime(df["divulgacao_dia_publicacao"], format="%Y-%m-%d", errors="coerce")  # esta coluna já vem em ISO
    hora = pd.to_datetime(df["ocorrencia_hora"], format="%H:%M:%S", errors="coerce")
    df["hora_ocorrencia"] = hora.dt.strftime("%H:%M:%S")
    df["hora_dia"] = hora.dt.hour.astype("Int64")
    for c in ["ocorrencia_latitude", "ocorrencia_longitude"]:
        # corrige sinal perdido ('?19.33' -> '-19.33'), vírgula decimal e espaços ('- 2.7')
        v = df[c].astype("string").str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
        df[c] = pd.to_numeric(v.str.replace(r"^\?", "-", regex=True), errors="coerce")
    for c in ["total_recomendacoes", "total_aeronaves_envolvidas"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    for c in ["ocorrencia_saida_pista", "investigacao_aeronave_liberada", "divulgacao_relatorio_publicado"]:
        df[c] = df[c].map({"SIM": 1, "NÃO": 0}).astype("Int64")
    df["investigacao_ativa"] = (df["investigacao_status"] == "ATIVA").astype("int64")
    return df


def tratar_ausentes(df):
    """Categóricas ausentes -> 'NÃO INFORMADO'. Coordenadas e hora ausentes ficam NULL (imputar
    seria inventar dado). Data de publicação ausente é legítima (relatório ainda não publicado)."""
    for c in ["ocorrencia_uf", "ocorrencia_cidade", "ocorrencia_aerodromo", "ocorrencia_classificacao"]:
        n = int(df[c].isna().sum())
        df[c] = df[c].fillna("NÃO INFORMADO")
        if n:
            log(f"[ausentes] {c}: {n} valores -> 'NÃO INFORMADO'")
    log(f"[ausentes] coordenadas ausentes mantidas como NULL: {int(df['ocorrencia_latitude'].isna().sum())}")
    log(f"[ausentes] hora ausente mantida como NULL: {int(df['hora_dia'].isna().sum())}")
    log(f"[ausentes] data de publicação ausente (relatório não publicado): {int(df['data_publicacao'].isna().sum())}")
    return df


def tratar_outliers(df):
    """1) Coordenadas fora do Brasil -> NULL (erro de digitação). 2) Datas futuras -> NaT.
    3) total_recomendacoes: valores reais, apenas SINALIZADOS (IQR sobre ocorrências com >=1
    recomendação). 4) 0 aeronaves envolvidas é inconsistente -> sinalizado."""
    lat, lon = df["ocorrencia_latitude"], df["ocorrencia_longitude"]
    fora = (lat.notna() | lon.notna()) & ~(lat.between(*LAT_BR) & lon.between(*LON_BR))
    df.loc[fora, ["ocorrencia_latitude", "ocorrencia_longitude"]] = np.nan
    log(f"[outliers] coordenadas fora do Brasil anuladas: {int(fora.sum())}")

    futuras = df["data_ocorrencia"] > pd.Timestamp.today()
    df.loc[futuras, "data_ocorrencia"] = pd.NaT
    log(f"[outliers] datas de ocorrência futuras anuladas: {int(futuras.sum())}")

    pos = df.loc[df["total_recomendacoes"] > 0, "total_recomendacoes"]
    q1, q3 = pos.quantile([0.25, 0.75])
    limite = q3 + 1.5 * (q3 - q1)
    df["outlier_recomendacoes"] = (df["total_recomendacoes"] > limite).astype("int64")
    log(f"[outliers] recomendações > {limite:.0f} (IQR) sinalizadas: {int(df['outlier_recomendacoes'].sum())} (valores mantidos)")

    df["aeronaves_inconsistente"] = (df["total_aeronaves_envolvidas"] < 1).astype("int64")
    log(f"[outliers] ocorrências com 0 aeronaves sinalizadas: {int(df['aeronaves_inconsistente'].sum())}")
    return df


def transformar():
    df = extrair()
    df = padronizar_texto(df)
    df = remover_colunas_redundantes(df)
    df = tratar_duplicidades(df)
    df = converter_tipos(df)
    df = tratar_ausentes(df)
    df = tratar_outliers(df)
    n = int(df["data_ocorrencia"].isna().sum())
    if n:
        df = df.dropna(subset=["data_ocorrencia"])
        log(f"[ausentes] {n} registros sem data de ocorrência válida removidos")
    colunas = ["codigo_ocorrencia", "ocorrencia_classificacao", "ocorrencia_uf", "ocorrencia_cidade",
               "ocorrencia_aerodromo", "ocorrencia_latitude", "ocorrencia_longitude", "data_ocorrencia",
               "hora_ocorrencia", "hora_dia", "ocorrencia_saida_pista", "investigacao_aeronave_liberada",
               "investigacao_status", "investigacao_ativa", "divulgacao_relatorio_numero",
               "divulgacao_relatorio_publicado", "data_publicacao", "total_recomendacoes",
               "total_aeronaves_envolvidas", "outlier_recomendacoes", "aeronaves_inconsistente"]
    df = df[colunas].sort_values("codigo_ocorrencia").reset_index(drop=True)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SILVER_CSV, index=False, encoding="utf-8", date_format="%Y-%m-%d")
    try:
        df.to_parquet(SILVER_PARQUET, index=False)
    except ImportError:
        log("[aviso] pyarrow não instalado: Parquet não gerado (CSV limpo gerado normalmente)")
    log(f"[prata] {len(df)} linhas gravadas em {SILVER_CSV}")
    with open(SILVER_DIR / "relatorio_tratamento.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    return df


if __name__ == "__main__":
    transformar()
