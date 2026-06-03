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


with st.expander("Configuração da Simulação",expanded = True):
    with st.container(border=True):

        st.subheader("Configuração da Simulação")

        col1, col2, col3, col4, col5 = st.columns([2,1,2,2,6])

        with col1:

            percentual = st.number_input(
                "Percentual (%)",
                min_value=1,
                max_value=100,
                value=100
            )

        with col3:

            qtd_registros = round(
                len(df) * percentual / 100
            )

            st.metric(
                "Registros",
                qtd_registros
            )

        with col4:

            st.write("")

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

            if st.button("Processar Modelo"):
                st.session_state.processado = True
                df_amostra = df.sample(frac=percentual / 100, random_state=None)

                X = df_amostra.drop(columns=["risco_alto"])
                y = df_amostra["risco_alto"]

                y_prob = modelo.predict_proba(X)[:, 1]
                y_pred = (y_prob >= threshold).astype(int)

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
            acertos.head()
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
            erros.head()
            .style
            .format({"idade": "{:.0f}"})
            .set_properties(**{
                "background-color": "#ffffff",
                "color": "black"
            })
        )

        st.dataframe(erros_df, hide_index=True, on_select="rerun", selection_mode="single-row")