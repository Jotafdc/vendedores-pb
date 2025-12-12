import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Dashboard Print PB", layout="wide")

# --- FUNÇÃO DE LIMPEZA DE VALORES ---
def limpar_moeda(valor):
    """Converte '1.200,50' ou 'R$ 1200.50' para float puro"""
    if pd.isna(valor) or str(valor).strip() == '':
        return 0.0
    
    s = str(valor).strip().upper()
    if isinstance(valor, (int, float)):
        return float(valor)
    
    s = s.replace('R$', '').replace(' ', '')
    
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') 
    elif ',' in s:
        s = s.replace(',', '.')
    
    try:
        return float(s)
    except:
        return 0.0

# --- CARREGAMENTO BLINDADO ---
@st.cache_data
def carregar_dados_csv(arquivo):
    arquivo.seek(0)
    try:
        df = pd.read_csv(arquivo, sep=None, engine='python', header=None)
    except:
        arquivo.seek(0)
        df = pd.read_csv(arquivo, header=None)

    header_idx = -1
    for idx, row in df.head(15).iterrows():
        txt = row.astype(str).str.cat(sep=' ').upper()
        if 'AGO' in txt and ('MOISÉS' in txt or 'MOISES' in txt):
            header_idx = idx
            break
            
    if header_idx == -1:
        st.error("Não achei a linha de cabeçalho. Verifique se o CSV tem 'Moisés AGO'.")
        return None

    df.columns = df.iloc[header_idx] 
    df = df[header_idx+1:].reset_index(drop=True) 
    
    col_ago_idx = -1
    for i, col in enumerate(df.columns):
        if 'AGO' in str(col).upper():
            col_ago_idx = i
            break
            
    if col_ago_idx == -1:
        st.error("Coluna de Agosto não encontrada.")
        return None
        
    col_cidade_idx = col_ago_idx - 1
    
    df_clean = pd.DataFrame()
    df_clean['Cidade'] = df.iloc[:, col_cidade_idx]
    df_clean['Ago'] = df.iloc[:, col_ago_idx]
    df_clean['Set'] = df.iloc[:, col_ago_idx + 1]
    df_clean['Out'] = df.iloc[:, col_ago_idx + 2]
    df_clean['Media'] = df.iloc[:, col_ago_idx + 3]
    df_clean['Nov'] = df.iloc[:, col_ago_idx + 4]

    df_clean = df_clean.dropna(subset=['Cidade'])
    df_clean = df_clean[~df_clean['Cidade'].astype(str).str.upper().str.contains('TOTAL')]
    
    for col in ['Ago', 'Set', 'Out', 'Nov', 'Media']:
        df_clean[col] = df_clean[col].apply(limpar_moeda)

    return df_clean

# --- DASHBOARD ---
st.title("📊 Dashboard Gerencial: Print PB")
st.markdown("Análise de Transição: **Moisés (Ago-Out)** vs **Edinaldo (Nov)**")

f_upload = st.file_uploader("Arraste o CSV aqui", type=['csv'])

if f_upload:
    df = carregar_dados_csv(f_upload)
    
    if df is not None:
        df['Variacao_$'] = df['Nov'] - df['Media']
        
        df['Variacao_%'] = 0.0
        mask = df['Media'] > 0
        df.loc[mask, 'Variacao_%'] = (df.loc[mask, 'Variacao_$'] / df.loc[mask, 'Media']) * 100
        
        total_hist = df['Media'].sum()
        total_atual = df['Nov'].sum()
        delta = total_atual - total_hist
        delta_pct = (delta / total_hist) * 100 if total_hist > 0 else 0

        # KPIS
        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Média Histórica (3M)", f"R$ {total_hist:,.2f}")
        k2.metric("Edinaldo (Nov)", f"R$ {total_atual:,.2f}", delta=f"{delta_pct:.1f}%")
        
        up = len(df[df['Variacao_$'] > 0])
        down = len(df[df['Variacao_$'] < 0])
        k3.metric("Cidades em Alta", f"{up}", delta="Crescimento", delta_color="normal")
        k4.metric("Cidades em Baixa", f"{down}", delta="Queda", delta_color="inverse")

        st.divider()

        # VISUALIZAÇÃO
        c_left, c_right = st.columns([1, 2])
        
        with c_left:
            st.subheader("🚨 Alerta de Risco (Churn)")
            st.caption("Cidades com queda > 30% no faturamento.")
            
            churn = df[(df['Variacao_%'] < -30) & (df['Media'] > 100)].sort_values('Variacao_%')
            
            if not churn.empty:
                # --- CORREÇÃO DO ERRO AQUI (TRY/EXCEPT) ---
                tabela_churn = churn[['Cidade', 'Media', 'Nov', 'Variacao_%']]
                try:
                    # Tenta colorir (precisa de matplotlib)
                    st.dataframe(tabela_churn.style.format({
                        'Media': 'R$ {:,.2f}', 'Nov': 'R$ {:,.2f}', 'Variacao_%': '{:.1f}%'
                    }).background_gradient(subset=['Variacao_%'], cmap='Reds_r'), use_container_width=True)
                except ImportError:
                    # Se falhar, mostra sem cor
                    st.warning("Para ver as cores, instale 'matplotlib'. Mostrando tabela simples.")
                    st.dataframe(tabela_churn, use_container_width=True)
            else:
                st.success("Nenhuma cidade em situação crítica.")

        with c_right:
            st.subheader("Comparativo Lado a Lado")
            
            df_melt = df.melt(id_vars=['Cidade'], value_vars=['Media', 'Nov'], var_name='Periodo', value_name='Valor')
            df_melt['Periodo'] = df_melt['Periodo'].replace({'Media': 'Média Histórica', 'Nov': 'Edinaldo (Nov)'})
            
            fig = px.bar(df_melt, x='Cidade', y='Valor', color='Periodo', barmode='group',
                         color_discrete_map={'Média Histórica': '#A6A6A6', 'Edinaldo (Nov)': '#0068C9'})
            st.plotly_chart(fig, use_container_width=True)

        # TABELA COMPLETA
        st.divider()
        st.subheader("📋 Detalhamento da Carteira")
        
        # --- CORREÇÃO DO ERRO TAMBÉM NA TABELA FINAL ---
        try:
            st.dataframe(df.style.format({
                'Ago': 'R$ {:,.2f}', 'Set': 'R$ {:,.2f}', 'Out': 'R$ {:,.2f}',
                'Media': 'R$ {:,.2f}', 'Nov': 'R$ {:,.2f}',
                'Variacao_%': '{:+.1f}%', 'Variacao_$': 'R$ {:+,.2f}'
            }).background_gradient(subset=['Variacao_$'], cmap='RdYlGn', vmin=-5000, vmax=5000), use_container_width=True)
        except ImportError:
             st.dataframe(df, use_container_width=True)