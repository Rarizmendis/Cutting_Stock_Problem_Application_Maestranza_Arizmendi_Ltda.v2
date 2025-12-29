import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_pdf_viewer import pdf_viewer
import pytz

# -----------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Optimizador Arizmendi", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 0. SISTEMA DE SEGURIDAD (LOGIN)
# -----------------------------------------------------------------------------
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 Acceso Restringido")
    st.markdown("### Maestranza Arizmendi Ltda.")
    st.text_input("Contraseña:", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state:
        st.error("🚫 Contraseña incorrecta.")
    return False

if not check_password():
    st.stop()

# -----------------------------------------------------------------------------
# 1. LÓGICA DEL NEGOCIO
# -----------------------------------------------------------------------------
class OptimizadorCortes:
    def __init__(self, largo_comercial, espesor_sierra):
        self.largo_comercial = largo_comercial
        self.espesor_sierra = espesor_sierra
        self.requerimientos = []
        self.stock_disponible = []

    def agregar_stock(self, cantidad, largo, etiqueta_id="Retazo"):
        for _ in range(int(cantidad)):
            self.stock_disponible.append({
                'tipo': 'stock',
                'capacidad_max': largo,
                'libre': largo,
                'cortes': [],
                'id_origen': etiqueta_id
            })

    def agregar_requerimiento(self, cantidad, largo, etiqueta=""):
        if (largo + self.espesor_sierra) > self.largo_comercial:
             pass 
        for _ in range(int(cantidad)):
            self.requerimientos.append({'largo': largo, 'etiqueta': etiqueta})
        return True, "OK"

    def resolver(self):
        piezas_ordenadas = sorted(self.requerimientos, key=lambda x: x['largo'], reverse=True)
        barras_resultado = [b.copy() for b in self.stock_disponible] 

        for pieza in piezas_ordenadas:
            largo_pieza = pieza['largo']
            etiqueta_pieza = pieza['etiqueta']
            mejor_barra_idx = -1
            menor_sobrante = float('inf')
            consumo_pieza = largo_pieza + self.espesor_sierra
            
            for i, barra in enumerate(barras_resultado):
                espacio_libre = barra['libre']
                if espacio_libre >= consumo_pieza:
                    sobrante_potencial = espacio_libre - consumo_pieza
                    if sobrante_potencial < menor_sobrante:
                        menor_sobrante = sobrante_potencial
                        mejor_barra_idx = i
            
            if mejor_barra_idx != -1:
                barras_resultado[mejor_barra_idx]['cortes'].append({
                    'largo': largo_pieza, 
                    'etiqueta': etiqueta_pieza
                })
                barras_resultado[mejor_barra_idx]['libre'] -= consumo_pieza
            else:
                nueva_barra = {
                    'tipo': 'nueva',
                    'capacidad_max': self.largo_comercial,
                    'libre': self.largo_comercial - consumo_pieza,
                    'cortes': [{'largo': largo_pieza, 'etiqueta': etiqueta_pieza}],
                    'id_origen': 'Nueva'
                }
                barras_resultado.append(nueva_barra)
        
        barras_activas = [b for b in barras_resultado if len(b['cortes']) > 0]
        return barras_activas

def agrupar_patrones(barras_resultado):
    patrones = {}
    for barra in barras_resultado:
        firma = (
            barra['tipo'], 
            barra['capacidad_max'], 
            tuple((c['largo'], c['etiqueta']) for c in barra['cortes'])
        )
        if firma in patrones:
            patrones[firma]['cantidad'] += 1
        else:
            patrones[firma] = {
                'cantidad': 1,
                'tipo': barra['tipo'],
                'largo_base': barra['capacidad_max'],
                'cortes': barra['cortes'],
                'libre': barra['libre']
            }
    return patrones

def obtener_color_gradiente(largo, min_largo, max_largo):
    if min_largo == max_largo: return "#3b82f6"
    try: ratio = (largo - min_largo) / (max_largo - min_largo)
    except: ratio = 1.0
    r1, g1, b1 = 220, 53, 69
    r2, g2, b2 = 30, 136, 229
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"

# -----------------------------------------------------------------------------
# 2. GENERACIÓN DE PDF
# -----------------------------------------------------------------------------
class PDFReporte(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'MAESTRANZA ARIZMENDI LTDA.', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Reporte de cortes y optimización de material', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
        self.set_x(-50)
        try:
            chile_tz = pytz.timezone('America/Santiago')
            ahora = datetime.now(chile_tz).strftime("%d/%m/%y %H:%M")
        except:
            ahora = datetime.now().strftime("%d/%m/%y %H:%M")
        self.cell(40, 10, ahora, 0, 0, 'R')

def crear_pdf_cortes(patrones, nombre_estructura, largo_stock, kerf, metricas):
    pdf = PDFReporte(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # Info
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Proyecto:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, nombre_estructura, 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Longitud base:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 6, f"{int(largo_stock)} mm", 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Espesor de la sierra:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"{int(kerf)} mm", 0, 1)
    pdf.ln(5)
    
    # --- MÉTRICAS ---
    # Ajustamos altura según si hay peso o no
    altura_rect = 32 if metricas['kg_m'] > 0 else 32 # Mantener altura fija por estética o ajustar
    
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(10, pdf.get_y(), 190, altura_rect, 'F')
    y_start = pdf.get_y() + 3
    pdf.set_xy(10, y_start)
    
    # Columna 1
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 5, "Barras NUEVAS:", 0, 0, 'R')
    pdf.set_font("Arial", '', 9)
    pdf.cell(45, 5, f"{metricas['barras_nuevas']} un.", 0, 0)
    
    pdf.set_xy(10, y_start + 6)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 5, "Retazos REUTILIZADOS:", 0, 0, 'R')
    pdf.set_font("Arial", '', 9)
    pdf.cell(45, 5, f"{metricas['barras_stock']} un.", 0, 0)

    # Si hay peso lineal, lo mostramos en Columna 1 abajo
    if metricas['kg_m'] > 0:
        pdf.set_xy(10, y_start + 12)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(45, 5, "Peso material:", 0, 0, 'R')
        pdf.set_font("Arial", '', 9)
        pdf.cell(45, 5, f"{metricas['peso_total_kg']:.1f} kg ({metricas['kg_m']} kg/m)", 0, 0)

    # Columna 2
    pdf.set_xy(100, y_start) 
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 5, "Metros útiles:", 0, 0, 'R')
    pdf.set_font("Arial", '', 9)
    pdf.cell(45, 5, f"{metricas['util_m']:.2f} m ({metricas['util_pct']:.1f}%)", 0, 0)

    pdf.set_xy(100, y_start + 6)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 5, "Pérdida total:", 0, 0, 'R') 
    pdf.set_font("Arial", '', 9)
    pdf.cell(45, 5, f"{metricas['desperdicio_total_m']:.2f} m ({metricas['desperdicio_pct']:.1f}%)", 0, 0)

    pdf.set_xy(100, y_start + 12)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(45, 5, "Solo sobrante:", 0, 0, 'R')
    pdf.set_font("Arial", '', 9)
    pdf.cell(45, 5, f"{metricas['sobrante_m']:.2f} m ({metricas['sobrante_pct']:.1f}%)", 0, 0)

    pdf.ln(20)
    
    # Patrones
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Detalle de patrones de corte", 0, 1)
    
    ancho_pagina = 190
    altura_barra = 14
    margen_izq = 10
    idx = 1
    resumen_piezas = {} 
    resumen_material = {}

    for firma, datos in patrones.items():
        if pdf.get_y() > 230: pdf.add_page()
        
        repeticiones = datos['cantidad']
        tipo = datos['tipo']
        largo_base = datos['largo_base']
        cortes = datos['cortes']
        remanente = int(datos['libre'])
        
        for c in cortes:
            key = (c['etiqueta'], int(c['largo']))
            resumen_piezas[key] = resumen_piezas.get(key, 0) + repeticiones

        key_mat = (tipo, int(largo_base))
        if key_mat not in resumen_material:
            resumen_material[key_mat] = {'cantidad': 0, 'metros_utiles_acum': 0}
        
        resumen_material[key_mat]['cantidad'] += repeticiones
        metros_utiles_patron = sum(c['largo'] for c in cortes)
        resumen_material[key_mat]['metros_utiles_acum'] += (metros_utiles_patron * repeticiones)

        pdf.set_font("Arial", 'B', 10)
        tipo_texto = "BARRA NUEVA" if tipo == 'nueva' else f"RETAZO BODEGA ({int(largo_base)}mm)"
        
        pdf.cell(25, 6, f"Patrón #{idx}", 0, 0)
        pdf.set_font("Arial", 'B' if tipo == 'stock' else '', 10)
        if tipo == 'stock': pdf.set_text_color(200, 100, 0) 
        pdf.cell(70, 6, f"[{tipo_texto}] - Repetir {repeticiones} veces", 0, 0)
        pdf.set_text_color(0,0,0) 
        
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 6, f"Sobrante: {remanente} mm", 0, 1, 'R')
        
        x_curr = margen_izq
        y_curr = pdf.get_y() + 2
        scale = ancho_pagina / largo_stock 
        pdf.set_line_width(0.2)
        
        if tipo == 'stock':
            ancho_base_vis = largo_base * scale
            pdf.set_draw_color(150, 150, 150)
            pdf.rect(x_curr, y_curr, ancho_base_vis, altura_barra, 'D')
            pdf.set_draw_color(0,0,0)

        for corte in cortes:
            ancho_vis = corte['largo'] * scale
            largo_real = int(corte['largo'])
            etiqueta = corte['etiqueta']
            pdf.set_fill_color(255, 255, 255) 
            pdf.rect(x_curr, y_curr, ancho_vis, altura_barra, 'FD')
            
            label = f"{etiqueta}"
            sub_label = f"{largo_real}"
            width_needed = max(pdf.get_string_width(label), pdf.get_string_width(sub_label)) + 2
            
            if width_needed < ancho_vis: 
                pdf.set_font("Arial", 'B', 7)
                pdf.set_xy(x_curr, y_curr + 3)
                pdf.cell(ancho_vis, 3, label, 0, 0, 'C')
                pdf.set_font("Arial", '', 7)
                pdf.set_xy(x_curr, y_curr + 7)
                pdf.cell(ancho_vis, 3, sub_label, 0, 0, 'C')
            else: 
                center_x = x_curr + (ancho_vis / 2)
                pdf.line(center_x, y_curr + altura_barra, center_x, y_curr + altura_barra + 2) 
                pdf.set_font("Arial", 'B', 6)
                pdf.set_xy(x_curr, y_curr + altura_barra + 2)
                pdf.cell(ancho_vis, 3, label, 0, 0, 'C') 
                pdf.set_font("Arial", '', 6)
                pdf.set_xy(x_curr, y_curr + altura_barra + 5)
                pdf.cell(ancho_vis, 3, sub_label, 0, 0, 'C')
            x_curr += ancho_vis
            
            ancho_sierra_vis = kerf * scale
            pdf.set_fill_color(50, 50, 50)
            pdf.rect(x_curr, y_curr, ancho_sierra_vis, altura_barra, 'F')
            x_curr += ancho_sierra_vis

        ancho_rem_vis = remanente * scale
        if ancho_rem_vis > 0:
            pdf.set_fill_color(220, 220, 220) 
            pdf.rect(x_curr, y_curr, ancho_rem_vis, altura_barra, 'FD')
            pdf.set_font("Arial", 'I', 7)
            if pdf.get_string_width(str(remanente)) < ancho_rem_vis:
                pdf.set_xy(x_curr, y_curr + 5)
                pdf.cell(ancho_rem_vis, 4, str(remanente), 0, 0, 'C')
        pdf.ln(altura_barra + 10) 
        idx += 1
    
    # --- TABLAS RESUMEN ---
    pdf.ln(5)
    if pdf.get_y() > 240: pdf.add_page()
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Resumen de piezas cortadas", 0, 1) 
    
    ancho_col1, ancho_col2, ancho_col3 = 60, 60, 40
    ancho_total_tabla = ancho_col1 + ancho_col2 + ancho_col3
    x_centrado = (210 - ancho_total_tabla) / 2
    
    pdf.set_fill_color(200, 200, 200)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_x(x_centrado)
    pdf.cell(ancho_col1, 7, "Etiqueta", 1, 0, 'C', True)
    pdf.cell(ancho_col2, 7, "Largo (mm)", 1, 0, 'C', True)
    pdf.cell(ancho_col3, 7, "Cantidad total", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    piezas_ordenadas = sorted(resumen_piezas.items(), key=lambda x: x[0][0])
    
    for (etiqueta, largo), cantidad in piezas_ordenadas:
        pdf.set_x(x_centrado)
        pdf.cell(ancho_col1, 6, str(etiqueta), 1, 0, 'C')
        pdf.cell(ancho_col2, 6, str(largo), 1, 0, 'C')
        pdf.cell(ancho_col3, 6, str(cantidad), 1, 1, 'C')

    pdf.ln(8)
    if pdf.get_y() > 240: pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Resumen de material utilizado", 0, 1) 
    
    w1, w2, w3, w4 = 60, 30, 30, 40
    tot_w = w1 + w2 + w3 + w4
    x_cent = (210 - tot_w) / 2
    
    pdf.set_fill_color(200, 200, 200)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_x(x_cent)
    pdf.cell(w1, 7, "Tipo Material", 1, 0, 'C', True)
    pdf.cell(w2, 7, "Largo", 1, 0, 'C', True)
    pdf.cell(w3, 7, "Cant. Usada", 1, 0, 'C', True)
    pdf.cell(w4, 7, "% Aprovechamiento", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    mat_ordenado = sorted(resumen_material.items(), key=lambda x: (x[0][0], x[0][1]))
    
    for (tipo, largo), datos in mat_ordenado:
        cant = datos['cantidad']
        metros_utiles = datos['metros_utiles_acum']
        metros_totales_barras = largo * cant
        
        if metros_totales_barras > 0:
            eficiencia = (metros_utiles / metros_totales_barras) * 100
        else:
            eficiencia = 0

        tipo_str = "Barra Nueva Comercial" if tipo == 'nueva' else "Retazo de Bodega"
        
        pdf.set_x(x_cent)
        pdf.cell(w1, 6, tipo_str, 1, 0, 'L')
        pdf.cell(w2, 6, f"{largo} mm", 1, 0, 'C')
        pdf.cell(w3, 6, str(cant), 1, 0, 'C')
        pdf.cell(w4, 6, f"{eficiencia:.1f}%", 1, 1, 'C')

    return pdf

# -----------------------------------------------------------------------------
# 3. INTERFAZ GRÁFICA
# -----------------------------------------------------------------------------

st.markdown("""
<style>
    .bloque-corte { transition: transform 0.2s; cursor: default; }
    .bloque-corte:hover { transform: scale(1.05); z-index: 100; border: 1px solid #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    h1 { font-size: 2rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🏭 Optimizador de Cortes - Maestranza Arizmendi Ltda.")

with st.sidebar:
    st.header("1. Configuración")
    
    nombre_estructura = st.text_input("Nombre Proyecto", value="Estructura X")
    largo_stock = st.number_input("Largo Comercial (mm)", value=6000, step=100)
    kerf = st.number_input("Espesor Sierra (mm)", value=3.0, step=0.5)
    
    # --- NUEVA OPCIÓN: PESO LINEAL ---
    kg_m = st.number_input("Peso lineal (kg/m) [Opcional]", value=0.0, step=0.1, help="Si es 0, no se calcula el peso.")
    
    st.divider()
    
    st.markdown("### 📦 Bodega / Sobrantes")
    st.info("Ingresa aquí los retazos que quieras reutilizar.")
    
    if "df_stock" not in st.session_state:
        st.session_state.df_stock = pd.DataFrame(columns=["Cantidad", "Largo", "Ref"])

    edited_stock = st.data_editor(
        st.session_state.df_stock,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Cantidad": st.column_config.NumberColumn("Cant.", format="%d", min_value=0),
            "Largo": st.column_config.NumberColumn("Largo (mm)", format="%d", min_value=1),
            "Ref": st.column_config.TextColumn("Ref (Opc)"),
        },
        hide_index=True,
        key="stock_editor"
    )

st.subheader("2. Listado de Piezas a Cortar")

if "df_piezas" not in st.session_state:
    st.session_state.df_piezas = pd.DataFrame(columns=["Cantidad", "Largo", "Etiqueta"])

edited_df = st.data_editor(
    st.session_state.df_piezas,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Cantidad": st.column_config.NumberColumn("Cant.", format="%d", min_value=1),
        "Largo": st.column_config.NumberColumn("Largo (mm)", format="%d", min_value=1),
        "Etiqueta": st.column_config.TextColumn("Etiqueta"),
    },
    hide_index=True
)

calcular = st.button("🚀 CALCULAR PATRONES", type="primary", use_container_width=True)

st.divider()

if calcular:
    if edited_df.empty:
        st.warning("Ingresa al menos una pieza para calcular.")
    else:
        opt = OptimizadorCortes(largo_stock, kerf)
        
        for _, row in edited_stock.iterrows():
            try:
                if row['Cantidad'] > 0 and row['Largo'] > 0:
                    ref = str(row['Ref']) if pd.notna(row['Ref']) and str(row['Ref']).strip() != "" else "Retazo"
                    opt.agregar_stock(row['Cantidad'], row['Largo'], ref)
            except: pass
            
        error = False
        for _, row in edited_df.iterrows():
            try:
                if row['Cantidad'] > 0 and row['Largo'] > 0:
                    lbl = str(row['Etiqueta']) if pd.notna(row['Etiqueta']) else ""
                    ok, msg = opt.agregar_requerimiento(row['Cantidad'], row['Largo'], lbl)
                    if not ok: 
                        st.error(msg)
                        error = True
            except: pass
        
        if not error:
            resultados = opt.resolver()
            patrones = agrupar_patrones(resultados)
            
            total_barras = len(resultados)
            barras_nuevas = sum(1 for b in resultados if b['tipo'] == 'nueva')
            barras_stock = sum(1 for b in resultados if b['tipo'] == 'stock')
            
            # KPI
            util_total_mm = sum(p['largo'] for b in resultados for p in b['cortes'])
            sobrante_total_mm = sum(b['libre'] for b in resultados)
            material_usado_total_mm = sum(b['capacidad_max'] for b in resultados)
            desperdicio_total_mm = material_usado_total_mm - util_total_mm
            
            pct_util = (util_total_mm / material_usado_total_mm * 100) if material_usado_total_mm > 0 else 0
            pct_desp = (desperdicio_total_mm / material_usado_total_mm * 100) if material_usado_total_mm > 0 else 0
            pct_sobr = (sobrante_total_mm / material_usado_total_mm * 100) if material_usado_total_mm > 0 else 0

            # CÁLCULO PESO (Opcional)
            peso_total = 0.0
            if kg_m > 0:
                # El peso se calcula sobre el material total consumido (incluyendo lo que se bota)
                # O sobre el material útil? Normalmente se compra por peso total.
                peso_total = (material_usado_total_mm / 1000) * kg_m

            st.subheader("3. Resultados del Proyecto")
            
            # Columnas dinámicas (si hay peso son 6, si no 5)
            cols = st.columns(6) if kg_m > 0 else st.columns(5)
            
            cols[0].metric("Barras NUEVAS", f"{barras_nuevas} un.", help=f"Barras comerciales de {int(largo_stock/1000)}m a comprar")
            cols[1].metric("Retazos Usados", f"{barras_stock} un.", help="Material recuperado de bodega")
            cols[2].metric("Metros Útiles", f"{util_total_mm/1000:.2f} m ({pct_util:.1f}%)", help="Suma de las piezas cortadas")
            cols[3].metric("Pérdida Total", f"{desperdicio_total_mm/1000:.2f} m ({pct_desp:.1f}%)", help="Sierra + Sobrantes")
            cols[4].metric("Solo Sobrante", f"{sobrante_total_mm/1000:.2f} m", help="Material que vuelve a bodega")
            
            if kg_m > 0:
                cols[5].metric("Peso Total", f"{peso_total:.1f} kg", help=f"Basado en {kg_m} kg/m")
            
            st.divider()

            st.markdown("##### 📄 Previsualización Reporte PDF")
            
            metricas = {
                'total_barras': total_barras, 'barras_nuevas': barras_nuevas, 'barras_stock': barras_stock,
                'sobrante_m': sobrante_total_mm/1000, 'sobrante_pct': pct_sobr, 
                'desperdicio_total_m': desperdicio_total_mm/1000, 'desperdicio_pct': pct_desp,
                'util_m': util_total_mm/1000, 'util_pct': pct_util,
                'kg_m': kg_m, 'peso_total_kg': peso_total
            }
            
            pdf_obj = crear_pdf_cortes(patrones, nombre_estructura, largo_stock, kerf, metricas)
            pdf_data = pdf_obj.output() 
            
            col_dl, col_view = st.columns([1, 4])
            with col_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=bytes(pdf_data),
                    file_name=f"Cortes_{nombre_estructura}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            
            pdf_viewer(input=bytes(pdf_data), width=700)
            
            st.divider()
            
            st.markdown("### 🔍 Detalle Visual de Cortes")

            idx_patron = 1
            for firma, datos in patrones.items():
                repeticiones = datos['cantidad']
                cortes = datos['cortes']
                remanente = datos['libre']
                tipo_barra = datos['tipo']
                largo_base_barra = datos['largo_base']
                
                largos = [c['largo'] for c in cortes]
                l_min, l_max = min(largos), max(largos)

                origen_str = f"BARRA NUEVA ({int(largo_base_barra)}mm)" if tipo_barra == 'nueva' else f"RETAZO BODEGA ({int(largo_base_barra)}mm)"
                icono = "🆕" if tipo_barra == 'nueva' else "📦"
                
                st.markdown(f"**Patrón #{idx_patron}** — {icono} **{origen_str}** — Repetir: **{repeticiones}x**")
                
                divs_cortes = ""
                for corte in cortes:
                    pct = (corte['largo'] / largo_stock) * 100 
                    color = obtener_color_gradiente(corte['largo'], l_min, l_max)
                    pct_sierra = (kerf / largo_stock) * 100
                    
                    divs_cortes += f"""<div class="bloque-corte" style="width:{pct}%; background-color:{color}; height:100%; display:flex; flex-direction:column; justify-content:center; align-items:center; color:white; position:relative;" title="{corte['etiqueta']} ({int(corte['largo'])})"><span style="font-size:11px; font-weight:bold; text-shadow:1px 1px 1px #000;">{corte['etiqueta']}</span><span style="font-size:9px; text-shadow:1px 1px 1px #000;">{int(corte['largo'])}</span></div><div style="width:{pct_sierra}%; background-color:#222; height:100%;"></div>"""
                
                div_remanente = ""
                if remanente > 0:
                    pct_rem = (remanente / largo_stock) * 100
                    div_remanente = f"""<div style="width:{pct_rem}%; background-color:#eee; height:100%; border-left:2px solid #ff4b4b; display:flex; justify-content:center; align-items:center; color:#555; font-size:10px;">{int(remanente)}</div>"""

                ancho_total_visual = (largo_base_barra / largo_stock) * 100
                st.markdown(f"""<div style="width:{ancho_total_visual}%; height:60px; border:1px solid #444; border-radius:4px; display:flex; overflow:hidden; margin-bottom:25px; background-color:#fafafa;">{divs_cortes}{div_remanente}</div>""", unsafe_allow_html=True)
                
                idx_patron += 1
        else:
            st.info("Ingresa las piezas a la izquierda y presiona Calcular.")
