import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

st.set_page_config(page_title="Dashboard — Segurança de voo (CENIPA)", layout="wide")
sns.set_theme(style="whitegrid")

ORDEM = ["ACIDENTE", "INCIDENTE GRAVE", "INCIDENTE"]
COR = {"ACIDENTE": "#d6342c", "INCIDENTE GRAVE": "#f2a900", "INCIDENTE": "#2f6fdb"}
GENERICOS = ["NIID", "NCAD"] 
CAMINHOS = ["ocorrencia_limpo.csv", "data/silver/ocorrencia_limpo.csv",
            "etl_ocorrencias/data/silver/ocorrencia_limpo.csv"]


@st.cache_data
def carregar():
    base = Path(__file__).resolve().parent
    for c in CAMINHOS:
        if (base / c).exists():
            df = pd.read_csv(base / c, parse_dates=["data_ocorrencia", "data_publicacao"])
            df["ano"] = df["data_ocorrencia"].dt.year
            return df
    st.error("Arquivo ocorrencia_limpo.csv não encontrado. Rode o transform.py ou coloque o CSV ao lado do app.py.")
    st.stop()


def semaforo(v, ref, tol=0.15):
    return "🟢" if v <= ref else ("🟡" if v <= ref * (1 + tol) else "🔴")


df = carregar()
REF = df["data_ocorrencia"].max()
ac = df[df["ocorrencia_classificacao"] == "ACIDENTE"]
sp = df[df["ocorrencia_saida_pista"] == 1]


with st.sidebar:
    st.title("Informações do Aluno")
    st.markdown("---")
    st.markdown("**Grupo:** Cauã Albano, Júlia Maria, Miguel David, Vinicius Veiga, Luan Felipe")
    st.markdown("**Turma:** 3B2")
    st.markdown("---")
    st.header("Filtros")
    st.caption("Valem para os gráficos e tabelas. Os KPIs do topo sempre usam a base completa.")
    a0, a1 = st.slider("Período (anos)", int(df.ano.min()), int(df.ano.max()),
                       (int(df.ano.min()), int(df.ano.max())))
    classes = st.multiselect("Classificação", ORDEM, default=["ACIDENTE", "INCIDENTE GRAVE"])
    ocultar_faer = st.checkbox("Ocultar FAER (fora de aeródromo) na tabela de aeródromos", True)

dff = df[df["ano"].between(a0, a1) & df["ocorrencia_classificacao"].isin(classes)]

def grafico_anual(d):
    t = d.groupby(["ano", "ocorrencia_classificacao"]).size().unstack(fill_value=0)
    cols = [c for c in ORDEM if c in t.columns]
    fig, ax = plt.subplots(figsize=(8, 5))
    t[cols].plot(kind="bar", stacked=True, ax=ax, color=[COR[c] for c in cols], edgecolor="white")
    ax.set_title("Ocorrências por ano", fontweight="bold")
    ax.set_xlabel("Ano (2026 parcial)")
    ax.set_ylabel("Nº de ocorrências")
    ax.legend([c.title() for c in cols], fontsize=8)
    plt.tight_layout()
    return fig


def grafico_relatorio(a0, a1):
    d = ac[ac["ano"].between(a0, a1)].copy()
    d["situacao"] = np.select(
        [d["divulgacao_relatorio_publicado"] == 1, d["investigacao_ativa"] == 1],
        ["Relatório publicado", "Investigação ativa"], default="Finalizada sem relatório")
    t = d.groupby(["ano", "situacao"]).size().unstack(fill_value=0)
    cores = {"Relatório publicado": "#1a9d5a", "Finalizada sem relatório": "#f2a900", "Investigação ativa": "#d6342c"}
    cols = [c for c in cores if c in t.columns]
    fig, ax = plt.subplots(figsize=(8, 5))
    t[cols].plot(kind="bar", stacked=True, ax=ax, color=[cores[c] for c in cols], edgecolor="white")
    ax.set_title("Acidentes: situação do relatório final", fontweight="bold")
    ax.set_xlabel("Ano")
    ax.set_ylabel("Nº de acidentes")
    ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout()
    return fig


def grafico_hora(d):
    h = d["hora_dia"].dropna().astype(int).value_counts().reindex(range(24), fill_value=0)
    s = d[d["ocorrencia_saida_pista"] == 1]["hora_dia"].dropna().astype(int).value_counts().reindex(range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(h.index, h.values, color="#2f6fdb", edgecolor="black", alpha=0.8, label="Ocorrências")
    ax.plot(s.index, s.values, color="#8a5cd6", marker="o", linewidth=2, label="Saídas de pista")
    ax.set_title("Ocorrências por hora do dia", fontweight="bold")
    ax.set_xlabel("Hora")
    ax.set_ylabel("Nº de ocorrências")
    ax.set_xticks(range(0, 24, 2))
    ax.legend()
    plt.tight_layout()
    return fig


def tabela_aerodromos(d):
    x = d[~d["ocorrencia_aerodromo"].isin(GENERICOS)]  # sem local identificado: fora do ranking
    x = x[x["ocorrencia_aerodromo"] != "FAER"] if ocultar_faer else x
    t = x.groupby("ocorrencia_aerodromo").agg(
        ocorrencias=("codigo_ocorrencia", "size"),
        acidentes=("ocorrencia_classificacao", lambda s: int((s == "ACIDENTE").sum())),
        saidas_de_pista=("ocorrencia_saida_pista", "sum"))
    t = t.sort_values(["saidas_de_pista", "ocorrencias"], ascending=False).head(10)
    t.index.name = "Aeródromo"
    return t


def tabela_uf(a0, a1):
    d = ac[ac["ano"].between(a0, a1)]
    t = d.groupby("ocorrencia_uf").agg(
        acidentes=("codigo_ocorrencia", "size"),
        pct_fora_aerodromo=("ocorrencia_aerodromo", lambda s: round((s == "FAER").mean() * 100)),
        saidas_de_pista=("ocorrencia_saida_pista", "sum"))
    t = t.sort_values("acidentes", ascending=False).head(8)
    t.index.name = "UF"
    return t

st.title("✈️ Segurança de voo no Brasil: o aprendizado está chegando a tempo?")
st.caption(f"Público: gerente de segurança operacional (aeroclubes, operadores, órgãos reguladores) · "
           f"Fonte: CENIPA, camada Prata ({len(df):,} ocorrências) · **Dados até {REF:%d/%m/%Y}** · "
           f"Atualização: carga manual do ETL (recomendado: mensal)".replace(",", "."))

u12 = int((ac["data_ocorrencia"] > REF - pd.Timedelta(days=365)).sum())
base = ac[ac["ano"].between(2019, 2024)].groupby("ano").size().mean()
ativas = ac[ac["investigacao_ativa"] == 1]
atold = int(((REF - ativas["data_ocorrencia"]).dt.days > 365).sum())
pct_old = atold / len(ativas) * 100
a3 = ac[ac["ano"].between(2023, 2025)]
pct_pub = a3["divulgacao_relatorio_publicado"].mean() * 100
spy = int((sp["ano"] == 2025).sum())
spmed = sp[sp["ano"].between(2016, 2025)].groupby("ano").size().mean()
faer = (ac["ocorrencia_aerodromo"] == "FAER").mean() * 100

tab1, tab2 = st.tabs(["Dashboard", "MVP: Briefing pré-voo"])

with tab1:
    st.error(f"**Acidentes não diminuem (~{base:.0f}/ano) e o aprendizado chega tarde: só {pct_pub:.0f}% dos "
             f"acidentes de 2023–2025 têm relatório publicado.** {atold} de {len(ativas)} investigações de acidente "
             f"abertas já passam de 12 meses.")

    st.subheader("1 · Indicadores principais")
    kpis = [
        (semaforo(u12, base), "Acidentes (últimos 12 meses)", f"{u12}",
         f"Média anual 2019–24: {base:.0f}. Vermelho: revisar causas recorrentes. Verde: manter ações."),
        ("🟢" if pct_old < 10 else "🟡" if pct_old <= 30 else "🔴", "Investigações abertas há +12 meses", f"{atold}",
         f"{pct_old:.0f}% das abertas. Ação: priorizar a fila e publicar declaração intermediária."),
        ("🟢" if pct_pub >= 80 else "🟡" if pct_pub >= 50 else "🔴", "Acidentes 2023–25 com relatório", f"{pct_pub:.0f}%",
         "Ação: operadores devem usar o histórico enquanto o relatório não sai (ver MVP)."),
        (semaforo(spy, spmed), "Saídas de pista em 2025", f"{spy}",
         f"Média 2016–25: {spmed:.0f}/ano. Ação: foco nos aeródromos reincidentes."),
        ("🟡", "Acidentes fora de aeródromo", f"{faer:.0f}%",
         "Ação: campanhas para quem opera fora de aeródromos."),
    ]
    for col, (emoji, rotulo, valor, acao) in zip(st.columns(5), kpis):
        with col:
            st.metric(f"{emoji} {rotulo}", valor)
            st.caption(acao)
    st.caption("Faixas (proposta do grupo): verde ≤ referência · amarelo até +15% · vermelho acima. "
               "Fila: verde < 10%, amarelo 10–30%, vermelho > 30%. Prazo de 12 meses inspirado no Anexo 13 da ICAO.")
    st.markdown("---")

    st.subheader("2 · Tendências")
    if dff.empty:
        st.warning("Nenhuma ocorrência para os filtros escolhidos.")
        st.stop()
    graficos = [
        {"titulo": "Evolução anual", "funcao": lambda: grafico_anual(dff),
         "analise": "Os acidentes ficam entre ~140 e ~205 por ano desde 2011, sem queda clara. Os incidentes (não graves) "
                    "disparam a partir de 2023, o que parece mudança de registro e não de risco; por isso ficam fora do filtro padrão."},
        {"titulo": "Situação do relatório (acidentes)", "funcao": lambda: grafico_relatorio(a0, a1),
         "analise": f"Até 2022 a grande maioria dos acidentes tem relatório. De 2023 em diante predomina a investigação ativa: "
                    f"apenas {pct_pub:.0f}% dos acidentes de 2023–2025 foram publicados. É o gargalo do aprendizado."},
        {"titulo": "Hora do dia", "funcao": lambda: grafico_hora(dff),
         "analise": "Há dois picos: 12–14h e 18–20h (fim de tarde). As saídas de pista seguem o mesmo padrão, "
                    "concentradas entre 10h e 20h."},
    ]
    for col, g in zip(st.columns(3), graficos):
        with col:
            st.markdown(f"**{g['titulo']}**")
            fig = g["funcao"]()
            st.pyplot(fig)
            plt.close(fig)
            with st.expander(f"Análise — {g['titulo']}", expanded=True):
                st.write(g["analise"])
    st.markdown("---")

    st.subheader("3 · Detalhamento")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Aeródromos com mais saídas de pista ({a0}–{a1})**")
        n_gen = int(dff[dff["ocorrencia_aerodromo"].isin(GENERICOS)]["ocorrencia_saida_pista"].sum())
        st.caption(f"Contagem histórica, sem ajustar pelo volume de voos. Não entram {n_gen} saídas de pista registradas "
                   f"em códigos genéricos (NIID/NCAD, local sem identificação): é um problema de qualidade do dado.")
        st.dataframe(tabela_aerodromos(dff), use_container_width=True)
    with c2:
        st.markdown(f"**Estados com mais acidentes ({a0}–{a1})**")
        st.caption("pct_fora_aerodromo = % dos acidentes registrados como FAER.")
        st.dataframe(tabela_uf(a0, a1), use_container_width=True)

    with st.expander("Qualidade dos dados e definições das métricas"):
        inc = df[df["ocorrencia_classificacao"] == "INCIDENTE"].groupby("ano").size()
        st.markdown(f"""
- **Acidente** = classificação ACIDENTE · **investigação aberta** = status ATIVA · **relatório publicado** = divulgação marcada como SIM · **saída de pista** = campo saída de pista SIM.
- Tratamento (Prata): 0 duplicidades, UFs ausentes viram "NÃO INFORMADO", coordenadas fora do Brasil anuladas, {df['ocorrencia_latitude'].isna().mean() * 100:.0f}% sem coordenadas (não imputadas).
- **Atenção:** incidentes (não graves) por ano: 2022 = {inc.get(2022)}, 2023 = {inc.get(2023)}, 2024 = {inc.get(2024)}, 2025 = {inc.get(2025)}. Parece mudança de registro; por isso os indicadores usam acidentes e incidentes graves.
- NIID e NCAD aparecem como aeródromos, mas parecem códigos genéricos (local sem identificação).
- Sem dados de movimentos de voo não é possível calcular taxas (ocorrências por 100 mil pousos).
""")

with tab2:
    st.info("**MVP:** o relatório oficial leva ~2 anos, mas o histórico já diz onde e quando ficar mais atento. "
            "Escolha o aeródromo e o horário para receber um briefing com base nas ocorrências de 2016–2025.")
    per = df[df["ano"].between(2016, 2025)]
    cont = per[~per["ocorrencia_aerodromo"].isin(["FAER"] + GENERICOS)]["ocorrencia_aerodromo"].value_counts()
    opcoes = ["FAER (fora de aeródromo)"] + list(cont[cont >= 15].index)
    esq, dir_ = st.columns([1, 2])
    with esq:
        local = st.selectbox("Aeródromo (código) ou fora de aeródromo", opcoes)
        hora = st.select_slider("Horário previsto (pouso/decolagem)", options=list(range(24)), value=14,
                                format_func=lambda h: f"{h:02d}:00")
    p = per[per["ocorrencia_aerodromo"] == ("FAER" if local.startswith("FAER") else local)]
    n, nac, nsp = len(p), int((p["ocorrencia_classificacao"] == "ACIDENTE").sum()), int(p["ocorrencia_saida_pista"].sum())
    h_ac = per[per["ocorrencia_classificacao"] == "ACIDENTE"]["hora_dia"].dropna().astype(int).value_counts().reindex(range(24), fill_value=0)
    fator = h_ac[hora] / h_ac.mean()
    nivel, msg, dica = (("ALTO", st.error, "Estude o perfil da pista (comprimento, piso, condição), calcule a distância de pouso com margem e defina um ponto de arremetida.")
                        if nsp >= 10 else
                        ("MÉDIO", st.warning, "Revise a distância de pouso/decolagem e a condição da pista; mantenha a velocidade de aproximação estável.")
                        if nsp >= 4 else
                        ("BAIXO", st.success, "Histórico sem concentração de saídas de pista; mantenha o briefing padrão."))
    with dir_:
        m = st.columns(4)
        m[0].metric("Ocorrências", n)
        m[1].metric("Acidentes", nac)
        m[2].metric("Saídas de pista", nsp)
        m[3].metric("Fator do horário", f"{fator:.1f}×")
        msg(f"**Risco histórico de saída de pista: {nivel}.** {dica}"
            + (" Fora de aeródromo não há infraestrutura de apoio: planeje área alternativa." if local.startswith("FAER") else "")
            + (" Este é um horário de pico de acidentes: redobre a atenção." if fator >= 1.3 else ""))
    st.caption("Nível: alto ≥ 10 saídas de pista no período, médio 4–9, baixo 0–3. Fator do horário = acidentes naquela hora ÷ média das 24 horas. "
               "Contagens históricas, sem ajuste pelo tráfego (aeródromos movimentados têm mais registros). "
               "Não é previsão e não substitui NOTAM, briefing meteorológico nem a avaliação do piloto.")
