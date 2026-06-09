import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    ConfusionMatrixDisplay
)


# =====================================================
# CONFIGURAÇÃO
# =====================================================

# Inicialização
if "processado" not in st.session_state:
    st.session_state.processado = False


st.set_page_config(
    page_title="Random Forest",
    layout="wide"
)

# CSS da aplicação
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color:#c85162;
}
</style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([4,1,2])

with col1:
    st.title("Aplicação de Modelo de Machine Learning na Predição de Risco para Câncer Cervical")
    st.markdown(
            """<span style="
                    color:gray;
                    font-size:20px;
                    font-weight:bold;
                ">
                   Algoritmo: Random Forest Classifier (Scikit-Learn)
                </span>
                """,
                unsafe_allow_html=True)
with col3:
    st.write("")
    st.write("")
    st.image("logo_white.png", width=400)

st.divider()

# =====================================================
# CARREGAR MODELO
# =====================================================

modelo = joblib.load(
    "modelo_random_forest.pkl"
)

threshold = joblib.load(
    "threshold.pkl"
)

rf = modelo.named_steps["classificador"]

importancias = rf.feature_importances_

preprocessador = modelo.named_steps["preprocessamento"]

nomes_variaveis = (
    preprocessador.get_feature_names_out()
)

df_importancia = pd.DataFrame({
    "variavel": nomes_variaveis,
    "importancia": importancias
})

df_importancia = df_importancia.sort_values(
    by="importancia",
    ascending=False
)

# =====================================================
# CARREGAR CONJUNTO TESTE
# =====================================================

df = pd.read_csv(
    "data_test_colo.csv",
    sep=";",
    encoding="utf-8-sig"
)

col1,col2 =st.columns([1,4])
with col1:
    st.markdown(
            f"""<span style="
                    color:gray;
                    font-size:20px;
                    font-weight:bold;
                ">Conjunto de Dados para Predição
                </span>
                Quantidade de registros: {len(df)}
                """,
                unsafe_allow_html=True)

st.caption("Informações provenientes de Sistemas de Informação em Saúde")

styled_df = (
    df.head()
      .style
      .format({"idade": "{:.0f}"})
      .set_properties(**{
          "background-color": "#ffffff",
          "color": "black"
      })
)


st.dataframe(styled_df, hide_index=True)


#with st.expander("Configuração da Simulação",expanded = True):
with st.sidebar:
    st.header("Configuração da Simulação")

    col1, col2 = st.columns([2,1])

    with col1:

        percentual = st.number_input(
            "Percentual (%)",
            min_value=1,
            max_value=100,
            value=100
        )

    with col2:

        qtd_registros = round(
            len(df) * percentual / 100
        )

        st.metric(
            "Registros",
            qtd_registros
        )

    # col1, col2, col3 = st.columns([1,4,1])

    # with col2:

    st.markdown("""
    <style>
    div.stButton > button {
        background-color: #954535;
        color: white;
        border-radius: 8px;
    }

    div.stButton > button:hover {
        background-color: #B7410E;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

    if "processado" not in st.session_state:
        st.session_state.processado = False

    if st.button("Processar Modelo", use_container_width=True):

        barra = st.progress(0)

        barra.progress(20)

        st.session_state.processado = True
        df_amostra = df.sample(frac=percentual / 100, random_state=None)

        barra.progress(40)

        X = df_amostra.drop(columns=["risco_alto"])
        y = df_amostra["risco_alto"]

        barra.progress(60)

        y_prob = modelo.predict_proba(X)[:, 1]

        barra.progress(80)

        y_pred = (y_prob >= threshold).astype(int)

        barra.progress(100)

        barra.empty()

        st.session_state.y = y
        st.session_state.y_pred = y_pred
        st.session_state.y_prob = y_prob
        st.session_state.df_amostra = df_amostra

if st.session_state.processado:

    df_amostra = st.session_state.df_amostra

    X = df_amostra.drop(columns=["risco_alto"])

    y = st.session_state.y

    y_prob = st.session_state.y_prob

    y_pred = st.session_state.y_pred

    cm = confusion_matrix(y, y_pred)


    # =====================================================
    # MÉTRICAS
    # =====================================================
    with st.expander("Desempenho do Modelo",expanded=False):
        st.subheader("Resultados")

        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([2,1,2,1,2,1,2,1,2,1])

        with col1:
            st.metric(
                "Accuracy",
                f"{accuracy_score(y, y_pred):.4f}",
                border=True
            )
            st.caption("Proporção total de acertos")

        with col3:
            st.metric(
                "Precision",
                f"{precision_score(y, y_pred):.4f}",
                border=True
            )
            st.caption("Positivos previstos corretamente")

        with col5:
            st.metric(
                "Recall",
                f"{recall_score(y, y_pred):.4f}",
                border=True
            )
            st.caption("Positivos reais identificados")

        with col7:
            st.metric(
                "F1-Score",
                f"{f1_score(y, y_pred):.4f}",
                border=True
            )
            st.caption("Equilíbrio entre Precision e Recall")

        with col9:
            st.metric(
                "ROC AUC",
                f"{roc_auc_score(y, y_prob):.4f}",
                border=True
            )
            st.caption("Capacidade de separar classes")

        # =====================================================
        # RESULTADOS
        # =====================================================

        resultado = X.copy()

        resultado["classe_real"] = y.values

        resultado["probabilidade"] = y_prob

        resultado["classe_prevista"] = y_pred

        # =====================================================
        # RESULTADOS COMPLETOS
        # =====================================================

        # =====================================================
        # GRÁFICOS DISTRIBUIÇÃO
        # =====================================================

        st.subheader("Distribuição da Variável Alvo")

        # contagem valores reais
        real_counts = y.value_counts().sort_index()

        # contagem valores previstos
        pred_counts = pd.Series(y_pred).value_counts().sort_index()

        # criar colunas
        col1, col2, col3 = st.columns(3)

        # =====================================================
        # GRÁFICO VALORES REAIS
        # =====================================================

        with col1:

            fig1, ax1 = plt.subplots()

            fig1.set_facecolor("#e6e3dc")
            ax1.set_facecolor("#e6e3dc")

            barras1 = ax1.bar(
                ["Risco Baixo", "Risco Alto"],
                real_counts.values,
                color="#e4d1be"
            )

            # adicionar valores nas barras
            ax1.bar_label(
                barras1,
                padding=1
            )

            ax1.set_title("Valores Reais")

            ax1.set_ylabel("Quantidade")

            st.pyplot(fig1)

        # =====================================================
        # GRÁFICO PREDIÇÕES
        # =====================================================

        with col2:

            # totais previstos
            negativos_previstos = (y_pred == 0).sum()

            positivos_previstos = (y_pred == 1).sum()

            # acertos negativos
            negativos_corretos = (
                (y == 0) &
                (y_pred == 0)
            ).sum()

            # acertos positivos
            positivos_corretos = (
                (y == 1) &
                (y_pred == 1)
            ).sum()

            categorias = ["Risco Baixo", "Risco Alto"]

            totais = [
                negativos_previstos,
                positivos_previstos
            ]

            corretos = [
                negativos_corretos,
                positivos_corretos
            ]

            x = np.arange(len(categorias))

            largura = 0.35

            fig2, ax2 = plt.subplots()

            fig2.set_facecolor("#e6e3dc")

            ax2.set_facecolor("#e6e3dc")

            barras_total = ax2.bar(
                x - largura/2,
                totais,
                largura,
                label="Previstos",
                color="#e4d1be"
            )

            barras_corretos = ax2.bar(
                x + largura/2,
                corretos,
                largura,
                label="Acertos",
                color="#954535"
            )

            # valores nas barras
            ax2.bar_label(
                barras_total,
                padding=1
            )

            ax2.bar_label(
                barras_corretos,
                padding=1
            )

            ax2.set_xticks(x)

            ax2.set_xticklabels(categorias)

            ax2.set_title("Valores Preditos")

            ax2.set_ylabel("Quantidade")

            ax2.legend()

            st.pyplot(fig2)

        with col3:

            cm = confusion_matrix(y, y_pred)

            fig_cm, ax_cm = plt.subplots()

            fig_cm.set_facecolor("#e6e3dc")

            disp = ConfusionMatrixDisplay(
                confusion_matrix=cm,
                display_labels=["Risco Baixo", "Risco Alto"]
            )

            disp.plot(ax=ax_cm, cmap="Oranges", colorbar=False)

            ax_cm.set_title(
                "Matriz de Confusão"
            )

            st.pyplot(fig_cm)


    # =====================================================
    # IMPORTANCIA DAS VARIÁVEIS
    # =====================================================
    with st.expander("Análise de Variáveis",expanded=False):

        # criar colunas
        col1, col2, col3 = st.columns([1,3,1])

        with col2:
            #st.subheader("Resultados")
            top10 = df_importancia.head(5)

            fig, ax = plt.subplots(figsize=(7, 4))

            ax.barh(
                top10["variavel"],
                top10["importancia"] * 100,
                color="#954535"
            )

            ax.set_xlabel("Importância (%)")

            ax.set_title(
                "Importância das Variáveis"
            )

            ax.invert_yaxis()

            st.pyplot(fig)

    # =====================================================
    # ACERTOS
    # =====================================================
    


    with st.expander("Registros Corretamente Classificados",expanded=False):
        acertos = resultado[
            resultado["classe_real"]
            ==
            resultado["classe_prevista"]
        ]

        st.markdown("**Predições Corretas**")


        st.write(
            f"Quantidade de acertos: {len(acertos)}"
        )
        acertos_df = (
            acertos
            .style
            .format({"idade": "{:.0f}"})
            .set_properties(**{
                "background-color": "#ffffff",
                "color": "black"
            })
        )
        st.dataframe(acertos_df, hide_index=True, on_select="rerun", selection_mode="single-row")

    # =====================================================
    # ERROS
    # =====================================================

    with st.expander("Registros Incorretamente Classificados",expanded=False):
        erros = resultado[
            resultado["classe_real"]
            !=
            resultado["classe_prevista"]
        ]

        st.markdown("**Predições Incorretas**")

        st.write(
            f"Quantidade de erros: {len(erros)}"
        )

        erros_df = (
            erros
            .style
            .format({"idade": "{:.0f}"})
            .set_properties(**{
                "background-color": "#ffffff",
                "color": "black"
            })
        )

        st.dataframe(erros_df, hide_index=True, on_select="rerun", selection_mode="single-row")

#streamlit run ml_colo_web.py