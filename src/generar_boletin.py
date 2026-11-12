"""Genera las imágenes del boletín para LinkedIn y las une en un PDF.

Uso:
    python src/generar_boletin.py                 # último fin de semana del histórico
    python src/generar_boletin.py 2026-11-06      # un fin de semana concreto (viernes)

Salida en boletines/<viernes>/:
    pagina_1.png  cabecera, número 1, cifras clave y top 10
    pagina_2.png  ranking completo
    pagina_3.png  trayectoria y entradas y salidas
    boletin_<viernes>.pdf  las tres páginas, para publicar como documento

Las páginas son verticales 4:5 (1080 x 1350 puntos de diseño). Los PNG se
guardan al doble de resolución para que el texto se vea nítido.
Las métricas siguen las definiciones de las reglas del proyecto (sección 5).
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
HISTORICO = RAIZ / "data" / "processed" / "top25_historico.csv"
DIR_BOLETINES = RAIZ / "boletines"
CLAVE = ["titulo_original", "distribuidora"]

# ---------- Paleta de Tania ----------
TAN = "#D2B997"
LAVANDA = "#946FBA"
ACERO = "#9EA6A5"
VINO = "#BF4D70"
BRONCE = "#C4972E"
CARDO = "#D2C5DE"
NEGRO = "#060200"
# Derivados de la paleta para fondo y texto legible
FONDO = "#FAF7F2"          # Tan muy aclarado
GRIS_TEXTO = "#5E6463"     # Cool Steel oscurecido, para texto secundario
BRONCE_TEXTO = "#8A6A1F"   # Golden Bronze oscurecido, para subidas en texto
LAVANDA_TEXTO = "#5E3F82"  # Lavender Purple oscurecido, para texto sobre Thistle
SERIES = [LAVANDA, VINO, BRONCE, NEGRO, ACERO]

ANCHO, ALTO = 1080, 1350   # puntos de diseño (1 punto = 1 px a 100 ppp)
MARGEN = 64

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.",
                "ago.", "sept.", "oct.", "nov.", "dic."]


# ---------- Tipografía ----------
def elegir_fuentes():
    """Lora para títulos y cifras, Inter para el texto; DejaVu si faltan."""
    disponibles = {f.name for f in font_manager.fontManager.ttflist}
    serif = "Lora" if "Lora" in disponibles else "DejaVu Serif"
    sans = "Inter" if "Inter" in disponibles else "DejaVu Sans"
    return serif, sans


SERIF, SANS = elegir_fuentes()


# ---------- Formatos ----------
def fmt_entero(v):
    return f"{v:,.0f}".replace(",", ".")


def fmt_euros(v):
    return f"{fmt_entero(v)} €"


def fmt_millones(v):
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f} M€".replace(".", ",")
    return f"{fmt_entero(round(v / 1e3))} mil €"


def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    p = round(v * 100)
    signo = "+" if p > 0 else "−" if p < 0 else ""
    return f"{signo}{abs(p)} %"


def color_signo(v):
    if v is None or pd.isna(v) or abs(v) < 0.005:
        return NEGRO
    return BRONCE_TEXTO if v > 0 else VINO


def etiqueta_finde(ini, fin):
    a, b = pd.Timestamp(ini), pd.Timestamp(fin)
    if a.month == b.month:
        return f"{a.day}-{b.day} {MESES_CORTOS[b.month - 1]}"
    return f"{a.day} {MESES_CORTOS[a.month - 1]}-{b.day} {MESES_CORTOS[b.month - 1]}"


def periodo_largo(ini, fin):
    a, b = pd.Timestamp(ini), pd.Timestamp(fin)
    if a.month == b.month:
        return f"{a.day} al {b.day} de {MESES[b.month - 1]} de {b.year}"
    return f"{a.day} de {MESES[a.month - 1]} al {b.day} de {MESES[b.month - 1]} de {b.year}"


# ---------- Datos ----------
@dataclass
class Boletin:
    finde_inicio: str
    finde_fin: str
    resumen: dict
    ranking: pd.DataFrame
    salidas: pd.DataFrame
    trayectoria: pd.DataFrame
    findes_trayectoria: pd.DataFrame


def preparar_datos(h, viernes=None):
    """Calcula las métricas del boletín para un fin de semana."""
    findes = sorted(h["finde_inicio"].unique())
    actual = viernes or findes[-1]
    if actual not in findes:
        raise ValueError(f"{actual} no está en el histórico")
    i = findes.index(actual)
    if i == 0:
        raise ValueError("Hace falta al menos un fin de semana anterior")
    anterior = findes[i - 1]

    totales = (h.groupby("finde_inicio")
               .agg(finde_fin=("finde_fin", "first"),
                    recaudacion_eur=("recaudacion_eur", "sum"),
                    espectadores=("espectadores", "sum"))
               .loc[findes[: i + 1]])
    act, ant = totales.loc[actual], totales.loc[anterior]
    cuatro = totales.loc[findes[max(0, i - 4): i]]
    media = cuatro["recaudacion_eur"].mean()

    cur = h[h["finde_inicio"] == actual].sort_values("rank")
    prev = h[h["finde_inicio"] == anterior]
    ranking = cur.merge(prev[CLAVE + ["rank", "recaudacion_eur"]], on=CLAVE,
                        how="left", suffixes=("", "_ant"))
    ranking["cambio"] = ranking["rank_ant"] - ranking["rank"]
    ranking["var"] = ranking["recaudacion_eur"] / ranking["recaudacion_eur_ant"] - 1
    ranking["por_cine"] = (ranking["recaudacion_eur"] / ranking["cines"]).round()

    def movimiento(f):
        if pd.isna(f["rank_ant"]):
            return "Estreno" if f["semana_en_cartel"] == 1 else "Reentrada"
        c = int(f["cambio"])
        return f"▲ {c}" if c > 0 else f"▼ {-c}" if c < 0 else "="

    ranking["movimiento"] = ranking.apply(movimiento, axis=1)

    salidas = prev.merge(cur[CLAVE], on=CLAVE, how="left", indicator=True)
    salidas = salidas[salidas["_merge"] == "left_only"].sort_values("rank")

    lider = ranking.iloc[0]
    resumen = {
        "recaudacion": act["recaudacion_eur"],
        "espectadores": act["espectadores"],
        "var_recaudacion": act["recaudacion_eur"] / ant["recaudacion_eur"] - 1,
        "var_espectadores": act["espectadores"] / ant["espectadores"] - 1,
        "media_4": media,
        "var_4": act["recaudacion_eur"] / media - 1,
        "findes_media": len(cuatro),
        "estrenos": int((ranking["semana_en_cartel"] == 1).sum()),
        "lider": lider,
        "cuota_lider": lider["recaudacion_eur"] / act["recaudacion_eur"],
    }

    # Trayectoria: cinco mejor situadas con al menos dos fines de semana en cartel.
    ultimos = findes[max(0, i - 4): i + 1]
    elegidas = ranking[ranking["semana_en_cartel"] >= 2].head(5)
    tray = h[h["finde_inicio"].isin(ultimos)].merge(
        elegidas[CLAVE + ["rank"]].rename(columns={"rank": "rank_actual"}), on=CLAVE)
    nombres = dict(zip(elegidas["rank"], elegidas["titulo_mostrar"]))
    tray["nombre"] = tray["rank_actual"].map(nombres)

    return Boletin(actual, act["finde_fin"], resumen, ranking, salidas, tray,
                   totales.loc[ultimos].reset_index())


# ---------- Ayudas de dibujo ----------
def nueva_pagina():
    fig = plt.figure(figsize=(ANCHO / 100, ALTO / 100), dpi=100)
    fig.patch.set_facecolor(FONDO)
    lienzo = fig.add_axes([0, 0, 1, 1])
    lienzo.set_xlim(0, ANCHO)
    lienzo.set_ylim(ALTO, 0)   # y hacia abajo, como en diseño
    lienzo.axis("off")
    return fig, lienzo


def texto(ax, x, y, s, tam=14, color=NEGRO, fuente=None, peso="normal", **kw):
    return ax.text(x, y, s, fontsize=tam, color=color, family=fuente or SANS,
                   weight=peso, va=kw.pop("va", "top"), **kw)


def recortar(ax, s, ancho_max, tam, fuente=None, peso="normal"):
    """Acorta un texto con «…» para que no pase de ancho_max puntos."""
    fig = ax.figure
    rend = fig.canvas.get_renderer()

    def ancho(t):
        obj = ax.text(0, 0, t, fontsize=tam, family=fuente or SANS, weight=peso)
        w = obj.get_window_extent(renderer=rend).width * 100 / fig.dpi
        obj.remove()
        return w

    if ancho(s) <= ancho_max:
        return s
    while len(s) > 1 and ancho(s + "…") > ancho_max:
        s = s[:-1]
    return s.rstrip() + "…"


def tarjeta(ax, x, y, w, h, relleno="white", borde=TAN):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=14",
                                linewidth=1.2, edgecolor=borde, facecolor=relleno))


def cabecera(ax, b, subtitulo=None):
    texto(ax, MARGEN, 56, "BOLETÍN SEMANAL · TAQUILLA EN ESPAÑA", 13, LAVANDA, peso="semibold")
    texto(ax, MARGEN, 84, "Top 25 del fin de semana", 40, NEGRO, SERIF)
    texto(ax, MARGEN, 160, f"Fin de semana del {periodo_largo(b.finde_inicio, b.finde_fin)}",
          17, GRIS_TEXTO)
    if subtitulo:
        texto(ax, MARGEN, 206, subtitulo, 22, NEGRO, SERIF)


def pie(ax, pagina, total=3):
    ax.plot([MARGEN, ANCHO - MARGEN], [ALTO - 82, ALTO - 82], color=TAN, lw=1)
    texto(ax, MARGEN, ALTO - 68,
          "Fuente: Ministerio de Cultura / ICAA, datos elaborados por Rentrak. "
          "Top 25 = suma de las 25 películas del informe.", 10.5, GRIS_TEXTO)
    texto(ax, MARGEN, ALTO - 46, "Tania Adrianzen Acero", 12, NEGRO, peso="semibold")
    texto(ax, ANCHO - MARGEN, ALTO - 46, f"{pagina}/{total}", 12, GRIS_TEXTO, ha="right")


def insignia(ax, x, y_centro, s, tam=11):
    """Etiqueta redondeada para «Estreno» y «Reentrada»."""
    obj = texto(ax, x + 10, y_centro, s, tam, LAVANDA_TEXTO, peso="semibold", va="center")
    rend = ax.figure.canvas.get_renderer()
    w = obj.get_window_extent(renderer=rend).width * 100 / ax.figure.dpi
    ax.add_patch(FancyBboxPatch((x, y_centro - 12), w + 20, 24,
                                boxstyle="round,pad=0,rounding_size=12",
                                linewidth=0, facecolor=CARDO, zorder=0.5))


def tabla_ranking(ax, filas, y0, alto_fila, columnas, tam=13, distribuidora_debajo=False):
    """Dibuja filas del ranking. columnas: lista de (clave, título, x, ancho, alineación)."""
    for clave, titulo, x, w, al in columnas:
        xt = x + w if al == "right" else x
        texto(ax, xt, y0, titulo.upper(), 10.5, GRIS_TEXTO, peso="semibold", ha=al)
    y = y0 + 28
    ax.plot([MARGEN, ANCHO - MARGEN], [y, y], color=TAN, lw=1.2)
    for _, f in filas.iterrows():
        yc = y + alto_fila / 2
        for clave, _, x, w, al in columnas:
            xt = x + w if al == "right" else x
            if clave == "rank":
                texto(ax, xt, yc, str(int(f["rank"])), tam + 1, NEGRO, SERIF, ha=al, va="center")
            elif clave == "movimiento":
                m = f["movimiento"]
                if m in ("Estreno", "Reentrada"):
                    insignia(ax, x, yc, m, tam - 2)
                else:
                    c = BRONCE_TEXTO if m.startswith("▲") else VINO if m.startswith("▼") else GRIS_TEXTO
                    texto(ax, xt, yc, m, tam - 1, c, peso="semibold", ha=al, va="center")
            elif clave == "titulo":
                nombre = recortar(ax, f["titulo_mostrar"], w, tam, peso="medium")
                if distribuidora_debajo:
                    texto(ax, x, yc - 3, nombre, tam, NEGRO, peso="medium", va="bottom")
                    texto(ax, x, yc + 3, recortar(ax, f["distribuidora"], w, tam - 3),
                          tam - 3, GRIS_TEXTO, va="top")
                else:
                    texto(ax, x, yc, nombre, tam, NEGRO, peso="medium", va="center")
            elif clave == "distribuidora":
                texto(ax, x, yc, recortar(ax, f["distribuidora"], w, tam - 1), tam - 1,
                      GRIS_TEXTO, va="center")
            elif clave == "semana":
                texto(ax, xt, yc, str(int(f["semana_en_cartel"])), tam, NEGRO, ha=al, va="center")
            elif clave == "cines":
                texto(ax, xt, yc, fmt_entero(f["cines"]), tam, NEGRO, ha=al, va="center")
            elif clave == "recaudacion":
                texto(ax, xt, yc, fmt_euros(f["recaudacion_eur"]), tam, NEGRO, ha=al, va="center")
            elif clave == "var":
                texto(ax, xt, yc, fmt_pct(f["var"]), tam, color_signo(f["var"]),
                      peso="semibold", ha=al, va="center")
            elif clave == "por_cine":
                texto(ax, xt, yc, fmt_euros(f["por_cine"]), tam, NEGRO, ha=al, va="center")
        y += alto_fila
        ax.plot([MARGEN, ANCHO - MARGEN], [y, y], color=TAN, lw=0.6, alpha=0.7)
    return y


# ---------- Páginas ----------
def pagina_1(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b)
    r = b.resumen
    lider = r["lider"]

    # Número 1
    tarjeta(ax, MARGEN, 214, ANCHO - 2 * MARGEN, 160, relleno=CARDO, borde=CARDO)
    texto(ax, MARGEN + 32, 236, "Nº 1 DEL FIN DE SEMANA", 12, LAVANDA_TEXTO, peso="semibold")
    texto(ax, MARGEN + 32, 258, recortar(ax, lider["titulo_mostrar"], 880, 38, SERIF), 38, NEGRO, SERIF)
    detalle = (f"{fmt_millones(lider['recaudacion_eur'])} · {int(lider['semana_en_cartel'])}.ª semana"
               f" en cartel · {round(r['cuota_lider'] * 100)} % del Top 25 · "
               f"{fmt_entero(lider['cines'])} cines")
    texto(ax, MARGEN + 32, 330, detalle, 15, NEGRO)

    # Cifras clave
    hueco = 16
    w = (ANCHO - 2 * MARGEN - 3 * hueco) / 4
    tarjetas = [
        ("Recaudación Top 25", fmt_millones(r["recaudacion"]),
         fmt_pct(r["var_recaudacion"]), "vs. finde anterior", r["var_recaudacion"]),
        ("Espectadores Top 25", fmt_entero(r["espectadores"]),
         fmt_pct(r["var_espectadores"]), "vs. finde anterior", r["var_espectadores"]),
        ("Vs. media 4 findes", fmt_pct(r["var_4"]),
         fmt_millones(r["media_4"]), "media anterior", None),
        ("Estrenos en el Top 25", str(r["estrenos"]), "", "primer fin de semana", None),
    ]
    for k, (etq, valor, delta, nota, signo) in enumerate(tarjetas):
        x = MARGEN + k * (w + hueco)
        tarjeta(ax, x, 396, w, 146)
        texto(ax, x + 20, 414, etq, 11.5, GRIS_TEXTO)
        color_valor = color_signo(r["var_4"]) if k == 2 else NEGRO
        texto(ax, x + 20, 440, valor, 30, color_valor, SERIF)
        if delta:
            t = texto(ax, x + 20, 500, delta, 12.5, color_signo(signo) if signo is not None else NEGRO,
                      peso="semibold")
            rend = fig.canvas.get_renderer()
            dw = t.get_window_extent(renderer=rend).width
            texto(ax, x + 20 + dw + 6, 500, nota, 11.5, GRIS_TEXTO)
        else:
            texto(ax, x + 20, 500, nota, 11.5, GRIS_TEXTO)

    # Top 10
    texto(ax, MARGEN, 566, "Top 10", 22, NEGRO, SERIF)
    columnas = [
        ("rank", "Pos.", MARGEN, 40, "right"),
        ("movimiento", "Mov.", MARGEN + 62, 110, "left"),
        ("titulo", "Película", MARGEN + 186, 420, "left"),
        ("semana", "Sem.", MARGEN + 620, 50, "right"),
        ("recaudacion", "Recaudación", MARGEN + 690, 150, "right"),
        ("var", "Var.", MARGEN + 860, 92, "right"),
    ]
    tabla_ranking(ax, b.ranking.head(10), 606, 60, columnas, tam=14, distribuidora_debajo=True)
    pie(ax, 1)
    return fig


def pagina_2(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b, "Ranking completo")
    columnas = [
        ("rank", "Pos.", MARGEN, 34, "right"),
        ("movimiento", "Mov.", MARGEN + 48, 96, "left"),
        ("titulo", "Película", MARGEN + 152, 300, "left"),
        ("distribuidora", "Distribuidora", MARGEN + 464, 150, "left"),
        ("semana", "Sem.", MARGEN + 616, 40, "right"),
        ("cines", "Cines", MARGEN + 664, 50, "right"),
        ("recaudacion", "Recaudación", MARGEN + 722, 112, "right"),
        ("var", "Var.", MARGEN + 840, 52, "right"),
        ("por_cine", "€/cine", MARGEN + 896, 56, "right"),
    ]
    y = tabla_ranking(ax, b.ranking, 256, 38, columnas, tam=11.5)
    texto(ax, MARGEN, y + 12, "Var.: recaudación frente al fin de semana anterior. "
          "Reentrada: vuelve al Top 25 sin ser estreno.", 10.5, GRIS_TEXTO)
    pie(ax, 2)
    return fig


def pagina_3(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b, "Trayectoria y movimientos")

    # Trayectoria en paneles pequeños, cada uno con su propia escala
    texto(ax, MARGEN, 258, "Las cinco primeras con más de un fin de semana en cartel", 15,
          NEGRO, peso="semibold")
    texto(ax, MARGEN, 282, "Recaudación por fin de semana. Cada panel tiene su propia escala "
          "para que se vea cómo cae cada película.", 11.5, GRIS_TEXTO)
    findes = b.findes_trayectoria
    xs = list(range(len(findes)))
    etiquetas_x = [f"{pd.Timestamp(f).day} {MESES_CORTOS[pd.Timestamp(f).month - 1]}"
                   for f in findes["finde_inicio"]]
    hueco, cols = 24, 3
    w = (ANCHO - 2 * MARGEN - (cols - 1) * hueco) / cols
    h_panel, y_inicio = 226, 316
    for k, (rank, grupo) in enumerate(b.trayectoria.groupby("rank_actual")):
        fila, col = divmod(k, cols)
        x0 = MARGEN + col * (w + hueco)
        y0 = y_inicio + fila * (h_panel + 18)
        color = SERIES[k % len(SERIES)]
        tarjeta(ax, x0, y0, w, h_panel)
        texto(ax, x0 + 16, y0 + 14, recortar(ax, f"{rank}. {grupo['nombre'].iloc[0]}", w - 32, 12.5,
                                             peso="semibold"), 12.5, NEGRO, peso="semibold")
        g = fig.add_axes([(x0 + 18) / ANCHO, 1 - (y0 + h_panel - 30) / ALTO,
                          (w - 36) / ANCHO, (h_panel - 96) / ALTO])
        g.set_facecolor("white")
        serie = grupo.set_index("finde_inicio")["recaudacion_eur"]
        valores = [serie.get(f, float("nan")) for f in findes["finde_inicio"]]
        g.plot(xs, valores, color=color, lw=2.4, marker="o", ms=6, mec="white", mew=1.2)
        tope = max(v for v in valores if v == v)
        for xv, v in zip(xs, valores):
            if v == v:
                g.annotate(fmt_millones(v).replace(" mil €", " mil"), (xv, v), xytext=(0, 9),
                           textcoords="offset points", ha="center", fontsize=9.5, family=SANS,
                           color=NEGRO, zorder=5,
                           bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none"})
        g.set_ylim(0, tope * 1.25)
        g.set_xlim(-0.4, len(xs) - 0.6)
        g.set_xticks(xs, etiquetas_x, fontsize=9, family=SANS, color=GRIS_TEXTO)
        g.tick_params(axis="x", length=0, pad=4)
        g.set_yticks([])
        for lado in ("top", "right", "left"):
            g.spines[lado].set_visible(False)
        g.spines["bottom"].set_color(TAN)
    texto(ax, MARGEN + 2 * (w + hueco) + 8, y_inicio + h_panel + 18 + 20,
          "Importes del fin de semana\n(viernes a domingo).\nSin punto: aún no se había\nestrenado o no estaba\nen el Top 25.",
          11, GRIS_TEXTO, linespacing=1.5)

    # Entradas y salidas
    ytit = 806
    texto(ax, MARGEN, ytit, "Entradas y salidas", 22, NEGRO, SERIF)
    col_w = (ANCHO - 2 * MARGEN - 40) / 2
    estrenos = b.ranking[b.ranking["movimiento"] == "Estreno"]
    reentradas = b.ranking[b.ranking["movimiento"] == "Reentrada"]

    def lista(x, y, titulo, filas, linea):
        texto(ax, x, y, titulo.upper(), 11, LAVANDA_TEXTO, peso="semibold")
        y += 26
        if filas.empty:
            texto(ax, x, y, "Ninguna este fin de semana", 12.5, GRIS_TEXTO)
            return y + 28
        for _, f in filas.iterrows():
            principal, secundario = linea(f)
            texto(ax, x, y, recortar(ax, principal, col_w - 110, 12.5, peso="medium"),
                      12.5, NEGRO, peso="medium")
            texto(ax, x + col_w, y, secundario, 12.5, GRIS_TEXTO, ha="right")
            y += 28
        return y

    yfin = lista(MARGEN, ytit + 48, f"Estrenos ({len(estrenos)})", estrenos,
                 lambda f: (f"{int(f['rank'])}. {f['titulo_mostrar']}", fmt_millones(f["recaudacion_eur"])))
    lista(MARGEN, yfin + 14, f"Reentradas ({len(reentradas)})", reentradas,
          lambda f: (f"{int(f['rank'])}. {f['titulo_mostrar']}", fmt_millones(f["recaudacion_eur"])))
    lista(MARGEN + col_w + 40, ytit + 48, f"Salen del Top 25 ({len(b.salidas)})", b.salidas,
          lambda f: (f"{f['titulo_mostrar']}", f"era {int(f['rank'])}.ª"))
    pie(ax, 3)
    return fig


def main():
    viernes = sys.argv[1] if len(sys.argv) > 1 else None
    h = pd.read_csv(HISTORICO)
    b = preparar_datos(h, viernes)
    salida = DIR_BOLETINES / b.finde_inicio
    salida.mkdir(parents=True, exist_ok=True)

    paginas = [pagina_1(b), pagina_2(b), pagina_3(b)]
    ruta_pdf = salida / f"boletin_{b.finde_inicio}.pdf"
    with PdfPages(ruta_pdf, metadata={"Title": f"Top 25 del fin de semana · {periodo_largo(b.finde_inicio, b.finde_fin)}",
                                      "Author": "Tania Adrianzen Acero"}) as pdf:
        for n, fig in enumerate(paginas, start=1):
            fig.savefig(salida / f"pagina_{n}.png", dpi=200, facecolor=FONDO)
            pdf.savefig(fig, facecolor=FONDO)
            plt.close(fig)
    print(f"Boletín generado en {salida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
