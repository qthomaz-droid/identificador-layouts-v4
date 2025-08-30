# Arquivo: teste_web.py

import streamlit as st

# Lista de resultados FALSOS, com links de imagens de exemplo que funcionam.
# A estrutura é a mesma que o seu 'identificador.py' deveria retornar.
resultados_falsos = [
    {
        "codigo_layout": "123",
        "banco": "Layout de Alta Confiança (Exemplo 1)",
        "pontuacao": 95.0,
        "url_previa": "https://manager.conciliadorcontabil.com.br/uploads/3/2023-04/3.jpg" # URL real da sua API
    },
    {
        "codigo_layout": "456",
        "banco": "Layout de Média Confiança (Exemplo 2)",
        "pontuacao": 75.0,
        "url_previa": "https://placehold.co/600x400/EEE/31343C/png?text=Exemplo2" # URL de placeholder
    },
    {
        "codigo_layout": "789",
        "banco": "Layout Sem Imagem (Exemplo 3)",
        "pontuacao": 90.0,
        "url_previa": None # Simula um layout sem imagem cadastrada
    }
]

st.set_page_config(page_title="Teste de Imagens", layout="wide")
st.title("🧪 Teste de Exibição de Imagens (Web)")

st.info("Abaixo estão 3 resultados de teste. As imagens devem aparecer nos dois primeiros.")

# Usamos exatamente a mesma lógica de exibição do seu app.py
for i, res in enumerate(resultados_falsos):
    rank = i + 1
    if res['pontuacao'] >= 85:
        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
    else:
        emoji = f"**{rank}º**"

    with st.container(border=True):
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if res.get("url_previa"):
                st.image(res["url_previa"], caption=f"Exemplo {res['codigo_layout']}", width=150)
            else:
                st.write("(Sem prévia)")

        with col2:
            st.markdown(f"### {emoji} {res['banco']}")
            st.markdown(f"- **Código:** `{res['codigo_layout']}`\n- **Confiança:** **{round(res['pontuacao'])}%**")