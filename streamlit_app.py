import streamlit as st
import pandas as pd

# URL de tu Google Sheet (convertida a CSV)
sheet_url = "https://docs.google.com/spreadsheets/d/15QqUqo84F8eaMcwttiZP8Fc7h5x4QIb7nHrfLRqdcrg/edit?usp=drivesdk"

@st.cache_data
def load_data():
    return pd.read_csv(sheet_url)

df = load_data()

st.title("📊 Control de Stock Zapatillas")

# Resumen rápido
st.metric("En stock", df[df["Estado"]=="En stock"].shape[0])
st.metric("Vendidos", df[df["Estado"]=="Vendido"].shape[0])
st.metric("Ganancia neta", df[df["Estado"]=="Vendido"]["Ganancia"].sum())

# Tabla filtrable
st.subheader("Filtrar stock")
modelo = st.selectbox("Modelo", ["Todos"] + df["Modelo"].unique().tolist())
if modelo != "Todos":
    df = df[df["Modelo"] == modelo]

st.dataframe(df)
