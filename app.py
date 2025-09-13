
import os, re, json
import pandas as pd
import streamlit as st

# ==== Config ====
EXCEL_PATH = st.secrets.get("excel_path", "/mnt/data/Stock_Zapatillas_Enzo.xlsx")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="GPT de Stock (Excel) – Avanzado", layout="wide")
st.title("GPT de Stock – Zapatillas (Avanzado)")

@st.cache_data(ttl=30)
def load_data(path):
    df = pd.read_excel(path, sheet_name="Stock")
    return df

df = load_data(EXCEL_PATH)

MODEL_MAP = {
    "blanca": "Air Max Blanca",
    "blanca airmax": "Air Max Blanca",
    "air max blanca": "Air Max Blanca",
    "negra": "Air Max Negra",
    "negra airmax": "Air Max Negra",
    "air max negra": "Air Max Negra",
    "gris": "Gris tela",
    "gris tela": "Gris tela",
    "roja": "Roja",
    "combinada": "Combinada",
}

# ==== KPIs ====
c1,c2,c3,c4 = st.columns(4)
with c1: st.metric("Total pares", len(df))
with c2: st.metric("En stock", int((df["Estado"]=="En stock").sum()))
with c3: st.metric("Vendidos", int((df["Estado"]=="Vendido").sum()))
with c4: st.metric("Ganancia neta", f'$ {int(df["Ganancia"].fillna(0).sum()):,}'.replace(",", "."))

st.divider()

# ==== Filtros rápidos ====
with st.expander("Filtros rápidos", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    modelos = ["(todos)"] + sorted(df["Modelo/Zapatilla"].dropna().unique().tolist())
    estados = ["(todos)"] + sorted(df["Estado"].dropna().unique().tolist())
    vendedores = ["(todos)"] + sorted([v for v in df.get("Vendedor", pd.Series(dtype=str)).dropna().unique().tolist()])
    with c1:
        m_sel = st.selectbox("Modelo", modelos)
    with c2:
        t_sel = st.multiselect("Talles", sorted(df["Talle"].dropna().unique().tolist()))
    with c3:
        e_sel = st.selectbox("Estado", estados, index=0)
    with c4:
        v_sel = st.selectbox("Vendedor", vendedores, index=0)

    dff = df.copy()
    if m_sel != "(todos)":
        dff = dff[dff["Modelo/Zapatilla"] == m_sel]
    if t_sel:
        dff = dff[dff["Talle"].isin(t_sel)]
    if e_sel != "(todos)":
        dff = dff[dff["Estado"] == e_sel]
    if v_sel != "(todos)":
        dff = dff[dff.get("Vendedor","") == v_sel]

    st.dataframe(dff, use_container_width=True)

# ==== Preguntas en lenguaje natural ====
st.subheader("Preguntas en lenguaje natural")
mode = st.radio("Modo de interpretación", ["Básico (sin IA)", "Avanzado (OpenAI)"], index=0, horizontal=True)

q = st.text_input("Ejemplos: '¿Cuántas blancas 41 me quedan?', '¿Qué vendió Tefi esta semana?', 'Total por modelo'")

def answer_basic(q):
    if not q: return ""
    ql = q.lower()
    # Detecta modelo
    model = None
    for k in MODEL_MAP.keys():
        if k in ql:
            model = MODEL_MAP[k]
            break
    # Detecta talle
    size_match = re.search(r"\b(3[5-9]|4[0-4])\b", ql)
    size = int(size_match.group(0)) if size_match else None
    # Detecta vendedor
    vendedor = None
    for v in ["enzo","tefi","laura"]:
        if v in ql:
            vendedor = v.capitalize()
            break

    # Intención
    want_vendidos = "vendid" in ql or "vendí" in ql
    want_total = "total" in ql

    dff = df.copy()
    if model: dff = dff[dff["Modelo/Zapatilla"] == model]
    if size: dff = dff[dff["Talle"] == size]
    if vendedor: dff = dff[dff.get("Vendedor","") == vendedor]

    if want_vendidos:
        dff = dff[dff["Estado"]=="Vendido"]
    elif not want_total:
        dff = dff[dff["Estado"]=="En stock"]

    n = len(dff)
    money = int(dff["Ganancia"].fillna(0).sum())
    money_txt = f'$ {money:,}'.replace(",", ".")

    return f"Coincidencias: {n} par(es). Ganancia acumulada: {money_txt}."

def answer_openai(q):
    # Usa OpenAI para extraer filtros estructurados
    try:
        from openai import OpenAI
        if not OPENAI_API_KEY:
            return "Falta OPENAI_API_KEY en secrets."
        client = OpenAI(api_key=OPENAI_API_KEY)

        system = """Sos un asistente que traduce preguntas sobre stock de zapatillas a filtros estructurados en JSON.
Campos válidos: modelo (Air Max Blanca/Air Max Negra/Gris tela/Roja/Combinada), talle (entero), estado (En stock/Vendido), vendedor (Enzo/Tefi/Laura).
Incluir 'agregacion': uno de ["conteo","suma_ganancia","tabla_por_modelo","tabla_por_talle"]. Responder SOLO JSON."""
        user = f"Pregunta: {q}"
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0
        )
        js = completion.choices[0].message.content.strip()
        # limpiar fences si vinieran
        js = js.strip("`")
        js = js.replace("json\n","").replace("```","").strip()
        spec = json.loads(js)
    except Exception as e:
        return f"Error interpretando la pregunta: {e}"

    dff = df.copy()
    if spec.get("modelo"): dff = dff[dff["Modelo/Zapatilla"]==spec["modelo"]]
    if spec.get("talle"): dff = dff[dff["Talle"]==int(spec["talle"])]
    if spec.get("estado"): dff = dff[dff["Estado"]==spec["estado"]]
    if spec.get("vendedor"): dff = dff[dff.get("Vendedor","")==spec["vendedor"]]

    agg = spec.get("agregacion","conteo")
    if agg=="conteo":
        return f"Resultado: {len(dff)} par(es)."
    if agg=="suma_ganancia":
        return f"Ganancia acumulada: $ {int(dff['Ganancia'].fillna(0).sum()):,}".replace(",", ".")
    if agg=="tabla_por_modelo":
        table = dff.groupby(["Modelo/Zapatilla","Estado"]).size().unstack(fill_value=0)
        st.write(table)
        return "Tabla por modelo mostrada arriba."
    if agg=="tabla_por_talle":
        table = dff.groupby(["Talle","Estado"]).size().unstack(fill_value=0)
        st.write(table)
        return "Tabla por talle mostrada arriba."
    return f"Coincidencias: {len(dff)} par(es)."

if st.button("Responder", type="primary"):
    if mode == "Básico (sin IA)":
        st.info(answer_basic(q))
    else:
        st.info(answer_openai(q))
        st.caption("Modo avanzado activo con OpenAI ✅")

st.divider()
st.write(f"📄 Excel conectado: {EXCEL_PATH}")
st.code("Para subir a Streamlit Cloud, agregá en Secrets:\nexcel_path='/app/Stock_Zapatillas_Enzo.xlsx'\nOPENAI_API_KEY='TU_API_KEY'")
