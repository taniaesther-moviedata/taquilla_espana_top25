"""Genera el boletín para LinkedIn como un PDF de cuatro páginas.

Uso:
    python src/generar_boletin.py                 # último fin de semana del histórico
    python src/generar_boletin.py 2026-11-06      # un fin de semana concreto (viernes)

Salida: boletines/<viernes>/boletin_<viernes>.pdf, para publicar como documento.
    Página 1: cabecera, número 1, cifras clave y top 10
    Página 2: ranking completo
    Página 3: trayectoria y entradas y salidas
    Página 4: distribuidoras (líder y cuota de cada una en el Top 25)

Las páginas son verticales 4:5 (1080 x 1350 puntos de diseño) y vectoriales.
Las métricas siguen las definiciones de las reglas del proyecto (sección 5).
"""

import math
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


def fmt_cuota(v):
    """Cuota sin decimales; por debajo del 0,5 % se escribe «<1 %» en vez de «0 %»."""
    return "<1 %" if v < 0.005 else f"{round(v * 100)} %"


def fmt_eje(v):
    """Etiqueta corta para el límite de un eje: 8 M€, 400 mil €."""
    if v >= 1e6:
        return f"{v / 1e6:g} M€".replace(".", ",")
    return f"{v / 1e3:g} mil €"


def techo_redondo(v):
    """Menor valor «redondo» (1, 1,5, 2, 2,5, 3, 4, 5, 6, 8 o 10 × 10^n) que no baja de v."""
    escala = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * escala >= v:
            return m * escala
    return 10 * escala


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
    distribuidoras: pd.DataFrame


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

    # Distribuidoras: suma de sus películas del Top 25 en el fin de semana.
    distribuidoras = (ranking.groupby("distribuidora")
                      .agg(recaudacion_eur=("recaudacion_eur", "sum"),
                           peliculas=("rank", "size"),
                           titulos=("titulo_mostrar", list))
                      .sort_values("recaudacion_eur", ascending=False)
                      .reset_index())
    distribuidoras["cuota"] = distribuidoras["recaudacion_eur"] / act["recaudacion_eur"]

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
        "dist_lider": distribuidoras.iloc[0],
    }

    # Trayectoria: cinco mejor situadas con al menos dos fines de semana en cartel.
    ultimos = findes[max(0, i - 4): i + 1]
    elegidas = ranking[ranking["semana_en_cartel"] >= 2].head(5)
    tray = h[h["finde_inicio"].isin(ultimos)].merge(
        elegidas[CLAVE + ["rank"]].rename(columns={"rank": "rank_actual"}), on=CLAVE)
    nombres = dict(zip(elegidas["rank"], elegidas["titulo_mostrar"]))
    tray["nombre"] = tray["rank_actual"].map(nombres)

    return Boletin(actual, act["finde_fin"], resumen, ranking, salidas, tray,
                   totales.loc[ultimos].reset_index(), distribuidoras)


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


_ANCHOS = {}


def ancho_texto(ax, s, tam, fuente=None, peso="normal"):
    """Ancho de un texto en puntos de diseño (con caché, porque se mide mucho)."""
    clave = (s, tam, fuente or SANS, peso)
    if clave not in _ANCHOS:
        fig = ax.figure
        obj = ax.text(0, 0, s, fontsize=tam, family=fuente or SANS, weight=peso)
        _ANCHOS[clave] = obj.get_window_extent(renderer=fig.canvas.get_renderer()).width * 100 / fig.dpi
        obj.remove()
    return _ANCHOS[clave]


_ALTOS = {}


def alto_lineas(n, tam, interlineado=1.1, fuente=None, peso="normal"):
    """Alto real de n líneas de texto en puntos de diseño, medido con el renderizador."""
    clave = (n, tam, interlineado, fuente or SANS, peso)
    if clave not in _ALTOS:
        fig = plt.figure(figsize=(ANCHO / 100, ALTO / 100), dpi=100)
        obj = fig.text(0, 0, "\n".join(["Ág"] * n), fontsize=tam, family=fuente or SANS,
                       weight=peso, linespacing=interlineado)
        _ALTOS[clave] = obj.get_window_extent(renderer=fig.canvas.get_renderer()).height
        plt.close(fig)
    return _ALTOS[clave]


def en_dos_lineas(ax, s, ancho_max, tam, fuente=None, peso="normal"):
    """Parte el texto en dos líneas lo más parecidas posible; None si no cabe."""
    palabras = s.split()
    mejor = None
    for i in range(1, len(palabras)):
        a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
        m = max(ancho_texto(ax, a, tam, fuente, peso), ancho_texto(ax, b, tam, fuente, peso))
        if m <= ancho_max and (mejor is None or m < mejor[0]):
            mejor = (m, [a, b])
    return mejor[1] if mejor else None


def ajustar(ax, s, ancho_max, tam, tam_min, lineas=2, tam_una_linea=None, fuente=None,
            peso="normal"):
    """Hace caber un texto en ancho_max sin perder legibilidad.

    Orden de preferencia, para que el título se lea entero siempre que se pueda:
    1. una línea, reduciendo la letra como mucho hasta tam_una_linea;
    2. dos líneas equilibradas, reduciendo hasta tam_min;
    3. solo si ni así cabe, dos líneas con «…» al final de la segunda.
    Devuelve (lista de líneas, tamaño de letra).
    """
    tam_una_linea = tam_una_linea or tam_min
    t = tam
    while t >= tam_una_linea - 1e-9:
        if ancho_texto(ax, s, t, fuente, peso) <= ancho_max:
            return [s], t
        t -= 0.5
    if lineas >= 2:
        t = min(tam, tam_una_linea)
        while t >= tam_min - 1e-9:
            partes = en_dos_lineas(ax, s, ancho_max, t, fuente, peso)
            if partes:
                return partes, t
            t -= 0.5
        palabras, primera = s.split(), []
        while palabras and ancho_texto(ax, " ".join(primera + palabras[:1]), tam_min, fuente,
                                       peso) <= ancho_max:
            primera.append(palabras.pop(0))
        if primera:
            return [" ".join(primera), recortar(ax, " ".join(palabras), ancho_max, tam_min,
                                                fuente, peso)], tam_min
    return [recortar(ax, s, ancho_max, tam_min, fuente, peso)], tam_min


def texto_ajustado(ax, x, y, s, ancho_max, tam, tam_min, lineas=2, tam_una_linea=None,
                   color=NEGRO, fuente=None, peso="normal", **kw):
    """Escribe un texto ajustado con ajustar() y devuelve su alto en puntos de diseño."""
    partes, t = ajustar(ax, s, ancho_max, tam, tam_min, lineas, tam_una_linea, fuente, peso)
    texto(ax, x, y, "\n".join(partes), t, color, fuente, peso, linespacing=1.1, **kw)
    return alto_lineas(len(partes), t, 1.1, fuente, peso)


def tarjeta(ax, x, y, w, h, relleno="white", borde=TAN):
    return ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=14",
                                       linewidth=1.2, edgecolor=borde, facecolor=relleno))


def cabecera(ax, b, subtitulo=None):
    texto(ax, MARGEN, 56, "Top 25 del fin de semana", 40, NEGRO, SERIF)
    texto(ax, MARGEN, 132, f"Fin de semana del {periodo_largo(b.finde_inicio, b.finde_fin)}",
          17, GRIS_TEXTO)
    if subtitulo:
        texto(ax, MARGEN, 178, subtitulo, 22, NEGRO, SERIF)


PAGINAS = 4


def pie(ax, pagina, total=PAGINAS):
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


def tabla_ranking(ax, filas, y0, alto_fila, columnas, tam=13, distribuidora_debajo=False,
                  y_max=None):
    """Dibuja filas del ranking. columnas: lista de (clave, título, x, ancho, alineación).

    Los títulos largos pasan a dos líneas y su fila crece lo justo. Si con eso la tabla
    pasara de y_max, todas las filas se acortan un poco para que siga cabiendo.
    """
    ancho_titulo = next(w for clave, _, _, w, _ in columnas if clave == "titulo")
    titulos = [ajustar(ax, f["titulo_mostrar"], ancho_titulo, tam, tam - 2.5, 2,
                       tam_una_linea=tam - 1.5, peso="medium") for _, f in filas.iterrows()]
    extra = [alto_lineas(len(p), s, 1.1, peso="medium") - alto_lineas(1, s, 1.1, peso="medium")
             for p, s in titulos]
    altos = [alto_fila + e for e in extra]
    if y_max is not None:
        disponible = y_max - (y0 + 28)
        if sum(altos) > disponible:
            base = (disponible - sum(extra)) / len(altos)
            altos = [base + e for e in extra]

    for clave, titulo, x, w, al in columnas:
        xt = x + w if al == "right" else x
        texto(ax, xt, y0, titulo.upper(), 10.5, GRIS_TEXTO, peso="semibold", ha=al)
    y = y0 + 28
    ax.plot([MARGEN, ANCHO - MARGEN], [y, y], color=TAN, lw=1.2)
    for n, (_, f) in enumerate(filas.iterrows()):
        alto_fila_n = altos[n]
        yc = y + alto_fila_n / 2
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
                # Primero se reduce un poco la letra; si no basta, dos líneas.
                partes, t = titulos[n]
                nombre = "\n".join(partes)
                if distribuidora_debajo:
                    alto_t = alto_lineas(len(partes), t, 1.1, peso="medium")
                    alto_d = alto_lineas(1, tam - 3)
                    arriba = yc - (alto_t + 4 + alto_d) / 2
                    texto(ax, x, arriba, nombre, t, NEGRO, peso="medium", linespacing=1.1)
                    texto(ax, x, arriba + alto_t + 4, recortar(ax, f["distribuidora"], w, tam - 3),
                          tam - 3, GRIS_TEXTO)
                else:
                    texto(ax, x, yc, nombre, t, NEGRO, peso="medium", va="center",
                          linespacing=1.05)
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
        y += alto_fila_n
        ax.plot([MARGEN, ANCHO - MARGEN], [y, y], color=TAN, lw=0.6, alpha=0.7)
    return y


# ---------- Páginas ----------
def pagina_1(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b)
    r = b.resumen
    lider = r["lider"]

    # Número 1: el recuadro crece si el título necesita dos líneas, y todo lo de
    # debajo baja lo mismo (dy), así nunca se recorta ni se solapa.
    alto_titulo = alto_lineas(1, 38, 1.1, SERIF)
    partes, t = ajustar(ax, lider["titulo_mostrar"], 880, 38, 24, 2, tam_una_linea=30, fuente=SERIF)
    alto_real = alto_lineas(len(partes), t, 1.1, SERIF)
    dy = max(0, alto_real - alto_titulo) + (8 if len(partes) > 1 else 0)
    tarjeta(ax, MARGEN, 186, ANCHO - 2 * MARGEN, 160 + dy, relleno=CARDO, borde=CARDO)
    texto(ax, MARGEN + 32, 208, "Nº 1 DEL FIN DE SEMANA", 12, LAVANDA_TEXTO, peso="semibold")
    texto(ax, MARGEN + 32, 230 + (alto_titulo - alto_real) / 2 if dy == 0 else 230,
          "\n".join(partes), t, NEGRO, SERIF, linespacing=1.1)
    detalle = (f"{fmt_millones(lider['recaudacion_eur'])} · {int(lider['semana_en_cartel'])}.ª semana"
               f" en cartel · {round(r['cuota_lider'] * 100)} % del Top 25 · "
               f"{fmt_entero(lider['cines'])} cines")
    texto(ax, MARGEN + 32, 302 + dy, detalle, 15, NEGRO)

    # Cifras clave: cinco tarjetas; cada texto se ajusta a su tarjeta.
    dist = r["dist_lider"]
    hueco = 14
    w = (ANCHO - 2 * MARGEN - 4 * hueco) / 5
    dentro = w - 32
    y0 = 368 + dy
    tarjetas = [
        ("Recaudación", fmt_millones(r["recaudacion"]), NEGRO,
         fmt_pct(r["var_recaudacion"]), color_signo(r["var_recaudacion"]), "vs. finde anterior"),
        ("Espectadores", fmt_entero(r["espectadores"]), NEGRO,
         fmt_pct(r["var_espectadores"]), color_signo(r["var_espectadores"]), "vs. finde anterior"),
        ("Vs. media 4 findes", fmt_pct(r["var_4"]), color_signo(r["var_4"]),
         fmt_millones(r["media_4"]), NEGRO, "media anterior"),
        ("Estrenos", str(r["estrenos"]), NEGRO,
         "", NEGRO, "películas en su primer fin de semana"),
        ("Distribuidora líder", dist["distribuidora"], NEGRO,
         f"{fmt_cuota(dist['cuota'])} del Top 25", NEGRO,
         f"{fmt_millones(dist['recaudacion_eur'])} · {dist['peliculas']} "
         f"{'película' if dist['peliculas'] == 1 else 'películas'}"),
    ]
    # Etiquetas y notas con el mismo tamaño en todas las tarjetas: el mayor que quepa en todas.
    tam_etq = min(ajustar(ax, e, dentro, 12, 10, 1, peso="semibold")[1] for e, *_ in tarjetas)
    tam_nota = min(ajustar(ax, n, dentro, 11, 9.5, 1)[1] for *_, d, _, n in tarjetas if d)
    for k, (etq, valor, color_valor, delta, color_delta, nota) in enumerate(tarjetas):
        x = MARGEN + k * (w + hueco)
        tarjeta(ax, x, y0, w, 150, relleno=CARDO if k == 4 else "white",
                borde=CARDO if k == 4 else TAN)
        texto(ax, x + 16, y0 + 16, etq, tam_etq, LAVANDA_TEXTO if k == 4 else GRIS_TEXTO,
              peso="semibold" if k == 4 else "normal")
        # Los nombres de distribuidora pueden ir en dos líneas; las cifras, siempre en una.
        if k == 4:
            partes, t = ajustar(ax, valor, dentro, 26, 14, 2, tam_una_linea=19, fuente=SERIF)
            texto(ax, x + 16, y0 + 66, "\n".join(partes), t, color_valor, SERIF,
                  va="center", linespacing=1.05)
        else:
            texto_ajustado(ax, x + 16, y0 + 42, valor, dentro, 30, 20, 1, color=color_valor,
                           fuente=SERIF)
        y_nota = y0 + 98
        if delta:
            texto_ajustado(ax, x + 16, y_nota, delta, dentro, 12.5, 10.5, 1, color=color_delta,
                           peso="semibold")
            y_nota += 22
        texto_ajustado(ax, x + 16, y_nota, nota, dentro, tam_nota, 9.5, 2 if not delta else 1,
                       color=GRIS_TEXTO)

    # Top 10
    texto(ax, MARGEN, 542 + dy, "Top 10", 22, NEGRO, SERIF)
    columnas = [
        ("rank", "Pos.", MARGEN, 40, "right"),
        ("movimiento", "Mov.", MARGEN + 62, 110, "left"),
        ("titulo", "Película", MARGEN + 186, 420, "left"),
        ("semana", "Sem.", MARGEN + 620, 50, "right"),
        ("recaudacion", "Recaudación", MARGEN + 690, 150, "right"),
        ("var", "Var.", MARGEN + 860, 92, "right"),
    ]
    tabla_ranking(ax, b.ranking.head(10), 582 + dy, 60, columnas, tam=14, distribuidora_debajo=True,
                  y_max=ALTO - 100)
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
    y = tabla_ranking(ax, b.ranking, 228, 38, columnas, tam=11.5, y_max=ALTO - 124)
    texto(ax, MARGEN, y + 12, "Var.: recaudación frente al fin de semana anterior. "
          "Reentrada: vuelve al Top 25 sin ser estreno.", 10.5, GRIS_TEXTO)
    pie(ax, 2)
    return fig


def pagina_3(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b, "Trayectoria y movimientos")

    # Trayectoria en paneles pequeños, cada uno con su propia escala
    texto(ax, MARGEN, 230, "Las cinco primeras con más de un fin de semana en cartel", 15,
          NEGRO, peso="semibold")
    texto(ax, MARGEN, 254, "Recaudación por fin de semana. Cada panel tiene su propia escala "
          "para que se vea cómo cae cada película.", 11.5, GRIS_TEXTO)
    findes = b.findes_trayectoria
    xs = list(range(len(findes)))
    etiquetas_x = [f"{pd.Timestamp(f).day} {MESES_CORTOS[pd.Timestamp(f).month - 1]}"
                   for f in findes["finde_inicio"]]
    hueco, cols = 24, 3
    w = (ANCHO - 2 * MARGEN - (cols - 1) * hueco) / cols
    h_panel, y_inicio = 226, 288
    for k, (rank, grupo) in enumerate(b.trayectoria.groupby("rank_actual")):
        fila, col = divmod(k, cols)
        x0 = MARGEN + col * (w + hueco)
        y0 = y_inicio + fila * (h_panel + 18)
        color = SERIES[k % len(SERIES)]
        tarjeta(ax, x0, y0, w, h_panel)
        texto_ajustado(ax, x0 + 16, y0 + 14, f"{rank}. {grupo['nombre'].iloc[0]}", w - 32, 12.5,
                       10, 1, color=NEGRO, peso="semibold")
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
        # Límite superior redondo, con su valor escrito sobre la línea discontinua.
        limite = techo_redondo(tope * 1.3)
        g.set_ylim(0, limite)
        g.axhline(limite, color=ACERO, lw=0.9, ls=(0, (4, 3)), clip_on=False)
        g.annotate(fmt_eje(limite), (0, 1), xycoords="axes fraction", xytext=(0, 4),
                   textcoords="offset points", ha="left", va="bottom", fontsize=9,
                   family=SANS, color=GRIS_TEXTO)
        g.set_xlim(-0.4, len(xs) - 0.6)
        g.set_xticks(xs, etiquetas_x, fontsize=9, family=SANS, color=GRIS_TEXTO)
        g.tick_params(axis="x", length=0, pad=4)
        g.set_yticks([])
        for lado in ("top", "right", "left"):
            g.spines[lado].set_visible(False)
        g.spines["bottom"].set_color(TAN)
    texto(ax, MARGEN + 2 * (w + hueco) + 8, y_inicio + h_panel + 18 + 20,
          "Importes del fin de semana\n(viernes a domingo).\nLínea discontinua: límite\nsuperior del eje del panel.\nSin punto: aún no se había\nestrenado o no estaba\nen el Top 25.",
          11, GRIS_TEXTO, linespacing=1.5)

    # Entradas y salidas
    ytit = 778
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
            alto = texto_ajustado(ax, x, y, principal, col_w - 110, 12.5, 11, 2,
                                  tam_una_linea=11.5, color=NEGRO, peso="medium")
            texto(ax, x + col_w, y, secundario, 12.5, GRIS_TEXTO, ha="right")
            y += 28 + max(0, alto - alto_lineas(1, 12.5, 1.1, peso="medium"))
        return y

    yfin = lista(MARGEN, ytit + 48, f"Estrenos ({len(estrenos)})", estrenos,
                 lambda f: (f"{int(f['rank'])}. {f['titulo_mostrar']}", fmt_millones(f["recaudacion_eur"])))
    lista(MARGEN, yfin + 14, f"Reentradas ({len(reentradas)})", reentradas,
          lambda f: (f"{int(f['rank'])}. {f['titulo_mostrar']}", fmt_millones(f["recaudacion_eur"])))
    lista(MARGEN + col_w + 40, ytit + 48, f"Salen del Top 25 ({len(b.salidas)})", b.salidas,
          lambda f: (f"{f['titulo_mostrar']}", f"era {int(f['rank'])}.ª"))
    pie(ax, 3)
    return fig


def pagina_4(b):
    fig, ax = nueva_pagina()
    cabecera(ax, b, "Distribuidoras")
    d = b.distribuidoras
    lider = d.iloc[0]

    # Distribuidora líder, con las películas que aportan su recaudación
    tarjeta(ax, MARGEN, 226, ANCHO - 2 * MARGEN, 166, relleno=CARDO, borde=CARDO)
    texto(ax, MARGEN + 32, 246, "DISTRIBUIDORA LÍDER DEL FIN DE SEMANA", 12, LAVANDA_TEXTO,
          peso="semibold")
    texto_ajustado(ax, MARGEN + 32, 268, lider["distribuidora"], 880, 34, 24, 1, fuente=SERIF)
    n = lider["peliculas"]
    detalle = (f"{fmt_cuota(lider['cuota'])} del Top 25 · {fmt_millones(lider['recaudacion_eur'])}"
               f" · {n} {'película' if n == 1 else 'películas'}: {', '.join(lider['titulos'])}")
    texto_ajustado(ax, MARGEN + 32, 338, detalle, 880, 15, 12.5, 2, tam_una_linea=13.5)

    texto(ax, MARGEN, 420, "Cuota de cada distribuidora en la recaudación del Top 25", 15,
          NEGRO, peso="semibold")
    texto(ax, MARGEN, 444, "Suma de lo que recaudaron sus películas del Top 25 en el fin de semana.",
          11.5, GRIS_TEXTO)

    # Barras horizontales: nombre a la izquierda, cuota, importe y películas a la derecha.
    y_ini, y_fin = 482, ALTO - 110
    fila = min(50, (y_fin - y_ini) / len(d))
    tam = 14 if fila >= 44 else 13 if fila >= 36 else 11.5
    x_nombre = MARGEN + 250
    etiquetas = [f"{fmt_cuota(f['cuota'])} · {fmt_millones(f['recaudacion_eur'])} · "
                 f"{f['peliculas']} {'pel.' if f['peliculas'] == 1 else 'pels.'}"
                 for _, f in d.iterrows()]
    ancho_etq = max(ancho_texto(ax, e, tam, peso="semibold") for e in etiquetas) + 14
    x_barra, x_tope = x_nombre + 14, ANCHO - MARGEN - ancho_etq
    maximo = d["cuota"].max()
    for i, (_, f) in enumerate(d.iterrows()):
        yc = y_ini + fila * (i + 0.5)
        es_lider = i == 0
        texto_ajustado(ax, x_nombre, yc, f["distribuidora"], 236, tam, tam - 2.5,
                       2 if fila >= 36 else 1, tam_una_linea=tam - 1, color=NEGRO,
                       peso="semibold" if es_lider else "normal", ha="right", va="center",
                       multialignment="right")
        largo = max(3, (x_tope - x_barra) * f["cuota"] / maximo)
        ax.add_patch(FancyBboxPatch((x_barra, yc - fila * 0.32), largo, fila * 0.64,
                                    boxstyle="round,pad=0,rounding_size=4", linewidth=0,
                                    facecolor=LAVANDA if es_lider else CARDO))
        texto(ax, x_barra + largo + 10, yc, etiquetas[i], tam, NEGRO if es_lider else GRIS_TEXTO,
              peso="semibold" if es_lider else "normal", va="center")
    pie(ax, 4)
    return fig


def main():
    viernes = sys.argv[1] if len(sys.argv) > 1 else None
    h = pd.read_csv(HISTORICO)
    b = preparar_datos(h, viernes)
    salida = DIR_BOLETINES / b.finde_inicio
    salida.mkdir(parents=True, exist_ok=True)

    paginas = [pagina_1(b), pagina_2(b), pagina_3(b), pagina_4(b)]
    ruta_pdf = salida / f"boletin_{b.finde_inicio}.pdf"
    with PdfPages(ruta_pdf, metadata={"Title": f"Top 25 del fin de semana · {periodo_largo(b.finde_inicio, b.finde_fin)}",
                                      "Author": "Tania Adrianzen Acero"}) as pdf:
        for fig in paginas:
            pdf.savefig(fig, facecolor=FONDO)
            plt.close(fig)
    print(f"Boletín generado en {salida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
