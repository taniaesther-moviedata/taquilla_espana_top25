"""Genera la pieza animada del boletín para LinkedIn (vídeo vertical 4:5).

Uso:
    python src/generar_animacion.py                  # último fin de semana, MP4
    python src/generar_animacion.py --gif            # además, una copia en GIF
    python src/generar_animacion.py --prueba 4.5 12  # solo fotogramas sueltos (PNG)
    python src/generar_animacion.py 2026-11-06       # un fin de semana concreto

Salida en boletines/<viernes>/animacion_<viernes>.mp4 (1080 x 1350, 30 fps, 12 s).

El dashboard se construye por partes: cabecera, cifras clave (con la
distribuidora líder), top 10 y
evolución de cinco fines de semana; los últimos segundos quedan fijos para
que se pueda leer. Los tamaños de letra están pensados para el móvil.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
import pandas as pd  # noqa: E402

from generar_boletin import (  # noqa: E402
    ALTO, ANCHO, BRONCE, CARDO, DIR_BOLETINES, FONDO, GRIS_TEXTO, HISTORICO,
    LAVANDA, LAVANDA_TEXTO, MARGEN, NEGRO, RAIZ, SERIF, TAN, ajustar, color_signo, etiqueta_finde,
    fmt_cuota, fmt_entero, fmt_millones, fmt_pct, nueva_pagina, periodo_largo, preparar_datos,
    tarjeta, texto,
)

FPS = 30
DURACION = 12.0        # segundos en total
FIN_MOVIMIENTO = 9.0   # a partir de aquí la imagen queda fija


def suavizar(x):
    """Curva de entrada rápida y frenada suave, entre 0 y 1."""
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def avance(t, inicio, duracion):
    return suavizar((t - inicio) / duracion)


def preparar_textos(ax, b):
    """Textos que no cambian entre fotogramas (títulos recortados, etiquetas)."""
    top10 = b.ranking.head(10)
    hueco = 16
    w = (ANCHO - 2 * MARGEN - 3 * hueco) / 4
    dist = b.resumen["dist_lider"]
    etiquetas = ["Recaudación", "Espectadores", "Vs. media 4 findes", "Distribuidora líder"]
    return {
        "top10": top10,
        # Títulos: primero letra algo menor; si no basta, dos líneas (caben en la fila de 54).
        "titulos": [ajustar(ax, f["titulo_mostrar"], 348, 17, 13.5, 2, tam_una_linea=15,
                            peso="medium") for _, f in top10.iterrows()],
        "ancho_tarjeta": w,
        # El mismo tamaño de etiqueta en las cuatro tarjetas: el mayor que quepa en todas.
        "etiquetas": etiquetas,
        "tam_etiqueta": min(ajustar(ax, e, w - 40, 14, 11, 1, peso="semibold")[1] for e in etiquetas),
        "distribuidora": ajustar(ax, dist["distribuidora"], w - 40, 34, 18, 2, tam_una_linea=24,
                                 fuente=SERIF),
        "maximo": top10["recaudacion_eur"].max(),
        "findes": b.findes_trayectoria,
    }


def fotograma(ax, b, c, t):
    """Dibuja el estado del dashboard en el segundo t."""
    ax.clear()
    ax.set_xlim(0, ANCHO)
    ax.set_ylim(ALTO, 0)
    ax.axis("off")
    r = b.resumen

    # ---- Cabecera ----
    p = avance(t, 0.0, 0.8)
    if p > 0:
        dy = (1 - p) * 14
        texto(ax, MARGEN, 50 + dy, "Top 25 del fin de semana", 44, NEGRO, SERIF, alpha=p)
        texto(ax, MARGEN, 134 + dy,
              f"Taquilla en España · {periodo_largo(b.finde_inicio, b.finde_fin)}",
              19, GRIS_TEXTO, alpha=p)

    # ---- Cifras clave ----
    hueco = 16
    w = c["ancho_tarjeta"]
    y0 = 190
    dist = r["dist_lider"]
    tarjetas = [
        (lambda q: f"{r['recaudacion'] * q / 1e6:.1f} M€".replace(".", ","),
         NEGRO, fmt_pct(r["var_recaudacion"]), color_signo(r["var_recaudacion"]), "vs. finde anterior"),
        (lambda q: fmt_entero(r["espectadores"] * q),
         NEGRO, fmt_pct(r["var_espectadores"]), color_signo(r["var_espectadores"]), "vs. finde anterior"),
        (lambda q: fmt_pct(r["var_4"] * q) or "0 %",
         color_signo(r["var_4"]), fmt_millones(r["media_4"]), NEGRO, "media anterior"),
        (None, NEGRO, fmt_cuota(dist["cuota"]), NEGRO, "del Top 25"),
    ]
    for k, (valor, color_valor, delta, color_delta, nota) in enumerate(tarjetas):
        p = avance(t, 0.6 + 0.25 * k, 0.9)
        if p <= 0:
            continue
        x = MARGEN + k * (w + hueco)
        lider = k == 3
        tarjeta(ax, x, y0, w, 152, relleno=CARDO if lider else "white",
                borde=CARDO if lider else TAN).set_alpha(p)
        texto(ax, x + 20, y0 + 16, c["etiquetas"][k], c["tam_etiqueta"],
              LAVANDA_TEXTO if lider else GRIS_TEXTO, peso="semibold" if lider else "normal",
              alpha=p)
        if lider:
            partes, tam = c["distribuidora"]
            texto(ax, x + 20, y0 + 66, "\n".join(partes), tam, NEGRO, SERIF, alpha=p,
                  va="center", linespacing=1.05)
        else:
            texto(ax, x + 20, y0 + 38, valor(p), 34, color_valor, SERIF, alpha=p)
        # Cifra de contraste y su explicación en dos líneas, para que no se monten.
        texto(ax, x + 20, y0 + 98, f"{delta}", 15, color_delta, peso="semibold", alpha=p)
        texto(ax, x + 20, y0 + 122, nota, 13, GRIS_TEXTO, alpha=p)

    # ---- Top 10 ----
    p = avance(t, 1.8, 0.6)
    if p > 0:
        texto(ax, MARGEN, 366, "Top 10 por recaudación", 24, NEGRO, SERIF, alpha=p)
        ax.add_patch(Rectangle((ANCHO - MARGEN - 268, 381), 16, 16, color=BRONCE, alpha=p, lw=0))
        texto(ax, ANCHO - MARGEN - 246, 389, "estreno", 14, GRIS_TEXTO, alpha=p, va="center")
        ax.add_patch(Rectangle((ANCHO - MARGEN - 150, 381), 16, 16, color=LAVANDA, alpha=p, lw=0))
        texto(ax, ANCHO - MARGEN - 128, 389, "ya en cartel", 14, GRIS_TEXTO, alpha=p, va="center")
    x_barra, ancho_max, alto_fila = 470, 322, 54
    for i, (_, f) in enumerate(c["top10"].iterrows()):
        p = avance(t, 2.1 + 0.28 * i, 0.8)
        if p <= 0:
            continue
        yc = 418 + alto_fila * i + alto_fila / 2
        estreno = f["semana_en_cartel"] == 1
        texto(ax, MARGEN + 30, yc, str(int(f["rank"])), 20, NEGRO, SERIF, alpha=p,
              ha="right", va="center")
        partes, tam = c["titulos"][i]
        texto(ax, MARGEN + 46, yc, "\n".join(partes), tam, NEGRO, peso="medium", alpha=p,
              va="center", linespacing=1.05)
        largo = ancho_max * f["recaudacion_eur"] / c["maximo"] * p
        ax.add_patch(Rectangle((x_barra, yc - 16), largo, 32, lw=0,
                               color=BRONCE if estreno else LAVANDA))
        etiqueta = texto(ax, x_barra + largo + 12, yc, fmt_millones(f["recaudacion_eur"] * p),
                         17, NEGRO, peso="semibold", alpha=p, va="center")
        if not estreno and p > 0.6:
            caja = etiqueta.get_window_extent(renderer=ax.figure.canvas.get_renderer())
            texto(ax, x_barra + largo + 12 + caja.width + 12, yc, fmt_pct(f["var"]), 15,
                  color_signo(f["var"]), peso="semibold", alpha=(p - 0.6) / 0.4, va="center")

    # ---- Evolución de cinco fines de semana ----
    p = avance(t, 5.5, 0.6)
    if p > 0:
        texto(ax, MARGEN, 992, "Recaudación del Top 25 · últimos cinco fines de semana",
              22, NEGRO, SERIF, alpha=p)
    findes = c["findes"]
    base, alto_max = 1214, 142
    paso = (ANCHO - 2 * MARGEN) / len(findes)
    tope = findes["recaudacion_eur"].max()
    for j, f in findes.iterrows():
        p = avance(t, 5.8 + 0.3 * j, 0.7)
        if p <= 0:
            continue
        actual = f["finde_inicio"] == b.finde_inicio
        xc = MARGEN + paso * (j + 0.5)
        h = alto_max * f["recaudacion_eur"] / tope * p
        ax.add_patch(Rectangle((xc - 62, base - h), 124, h, lw=0,
                               color=LAVANDA if actual else CARDO))
        if h > 34:
            texto(ax, xc, base - 8, fmt_millones(f["recaudacion_eur"] * p), 16,
                  "white" if actual else NEGRO, peso="semibold", alpha=p, ha="center",
                  va="bottom")
        texto(ax, xc, base + 8, etiqueta_finde(f["finde_inicio"], f["finde_fin"]), 14,
              NEGRO if actual else GRIS_TEXTO, peso="semibold" if actual else "normal",
              alpha=p, ha="center")
    p = avance(t, 7.6, 0.7)
    if p > 0 and len(findes) > 1:
        y_media = base - alto_max * r["media_4"] / tope
        x_ini = MARGEN + paso * 0.5 - 70
        x_fin = MARGEN + paso * (len(findes) - 0.5) + 70
        ax.plot([x_ini, x_ini + (x_fin - x_ini) * p], [y_media, y_media], color=NEGRO,
                lw=2, ls=(0, (5, 4)))
    p = avance(t, 8.2, 0.6)
    if p > 0 and len(findes) > 1:
        y_media = base - alto_max * r["media_4"] / tope
        marco = {"boxstyle": "round,pad=0.25", "fc": FONDO, "ec": "none", "alpha": p}
        texto(ax, ANCHO - MARGEN, y_media - 10,
              f"Media de los {r['findes_media']} anteriores: {fmt_millones(r['media_4'])}",
              14.5, NEGRO, alpha=p, ha="right", va="bottom", bbox=marco)

    # ---- Pie ----
    p = avance(t, 0.2, 0.8)
    if p > 0:
        ax.plot([MARGEN, ANCHO - MARGEN], [ALTO - 74, ALTO - 74], color=TAN, lw=1, alpha=p)
        texto(ax, MARGEN, ALTO - 62,
              "Fuente: Ministerio de Cultura / ICAA, datos elaborados por Rentrak.",
              12, GRIS_TEXTO, alpha=p)
        texto(ax, MARGEN, ALTO - 38, "Tania Adrianzen Acero", 13, NEGRO, peso="semibold", alpha=p)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("viernes", nargs="?", help="fin de semana (AAAA-MM-DD); por defecto, el último")
    parser.add_argument("--gif", action="store_true", help="crear también un GIF")
    parser.add_argument("--prueba", nargs="+", type=float, metavar="SEG",
                        help="guardar solo los fotogramas de esos segundos")
    args = parser.parse_args()

    b = preparar_datos(pd.read_csv(HISTORICO), args.viernes)
    salida = DIR_BOLETINES / b.finde_inicio
    salida.mkdir(parents=True, exist_ok=True)
    fig, ax = nueva_pagina()
    fig.canvas.draw()
    c = preparar_textos(ax, b)

    if args.prueba:
        for seg in args.prueba:
            fotograma(ax, b, c, seg)
            ruta = salida / f"prueba_{seg:05.2f}s.png"
            fig.savefig(ruta, dpi=100, facecolor=FONDO)
            print(ruta.relative_to(RAIZ))
        return 0

    final = salida / f"animacion_{b.finde_inicio}.mp4"
    temporal = salida / "animacion_en_curso.mp4"
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporal)],
        stdin=subprocess.PIPE)
    imagen = None
    for n in range(int(DURACION * FPS)):
        t = n / FPS
        if imagen is None or t <= FIN_MOVIMIENTO:
            fotograma(ax, b, c, t)
            fig.canvas.draw()
            imagen = bytes(fig.canvas.buffer_rgba())
        ffmpeg.stdin.write(imagen)
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        print("ffmpeg ha fallado; no se ha generado el vídeo")
        return 1
    temporal.replace(final)
    print(final.relative_to(RAIZ))

    if args.gif:
        gif = final.with_suffix(".gif")
        filtro = ("fps=15,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                  "[b][p]paletteuse=dither=none:diff_mode=rectangle")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vf", filtro,
                        str(gif)], check=True)
        print(gif.relative_to(RAIZ))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
