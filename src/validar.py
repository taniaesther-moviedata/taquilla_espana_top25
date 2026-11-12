"""Comprueba el histórico después de cada carga.

Uso:
    python src/validar.py

Errores (el script termina con código 1): hay que corregirlos antes de
generar el boletín. Avisos: datos raros del propio PDF que se anotan en el
README pero no bloquean.
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
HISTORICO = RAIZ / "data" / "processed" / "top25_historico.csv"
TOTALES = RAIZ / "data" / "processed" / "totales_pdf.csv"

CLAVE_PELICULA = ["titulo_original", "distribuidora"]
MARGEN_VARIACION = 0.03  # 3 puntos: el % del PDF viene redondeado a entero


def comprobar_estructura(h, errores):
    for finde, grupo in h.groupby("finde_inicio"):
        if len(grupo) != 25:
            errores.append(f"{finde}: {len(grupo)} filas en vez de 25")
        if sorted(grupo["rank"]) != list(range(1, 26)):
            errores.append(f"{finde}: el rank no va de 1 a 25 sin repetir")
        if grupo.duplicated(CLAVE_PELICULA).any():
            errores.append(f"{finde}: hay películas repetidas")
    if h.groupby("archivo_origen")["finde_inicio"].nunique().gt(1).any():
        errores.append("Un mismo PDF aparece con dos fines de semana distintos")


def comprobar_continuidad(h, errores):
    fechas = pd.to_datetime(sorted(h["finde_inicio"].unique()))
    saltos = fechas.to_series().diff().dt.days.dropna()
    for fecha, dias in saltos.items():
        if dias != 7:
            errores.append(f"Falta algún fin de semana antes de {fecha.date()} ({int(dias)} días)")


def comprobar_totales(h, errores):
    if not TOTALES.exists():
        errores.append("No existe totales_pdf.csv: ejecuta antes extraer_pdf.py")
        return
    tot = pd.read_csv(TOTALES).set_index("finde_inicio")
    sumas = h.groupby("finde_inicio")[["recaudacion_eur", "espectadores"]].sum()
    for finde, fila in sumas.iterrows():
        if finde not in tot.index:
            errores.append(f"{finde}: falta la fila TOTAL del PDF")
            continue
        for col in ("recaudacion_eur", "espectadores"):
            if abs(fila[col] - tot.loc[finde, col]) > 1:
                errores.append(
                    f"{finde}: la suma de {col} ({fila[col]:,.0f}) "
                    f"no coincide con el TOTAL del PDF ({tot.loc[finde, col]:,.0f})"
                )


def comprobar_variaciones(h, avisos):
    """Compara la variación calculada con el histórico con la del PDF."""
    h = h.sort_values("finde_inicio")
    fechas = sorted(h["finde_inicio"].unique())
    anterior = dict(zip(fechas[1:], fechas[:-1]))
    previo = h[CLAVE_PELICULA + ["finde_inicio", "recaudacion_eur"]].copy()
    previo["finde_inicio"] = previo["finde_inicio"].map({v: k for k, v in anterior.items()})
    cruce = h.merge(previo.dropna(), on=CLAVE_PELICULA + ["finde_inicio"], suffixes=("", "_ant"))
    cruce["var_calc"] = cruce["recaudacion_eur"] / cruce["recaudacion_eur_ant"] - 1
    dif = (cruce["var_calc"] - cruce["var_recaudacion_pdf"]).abs()
    for _, f in cruce[dif > MARGEN_VARIACION].iterrows():
        avisos.append(
            f"{f.finde_inicio} · {f.titulo}: variación calculada {f.var_calc:+.0%}, "
            f"en el PDF {f.var_recaudacion_pdf:+.0%}"
        )


def comprobar_rarezas_pdf(h, avisos):
    raro = h[h["recaudacion_acum_eur"] < h["recaudacion_eur"]]
    for _, f in raro.iterrows():
        avisos.append(
            f"{f.finde_inicio} · {f.titulo}: acumulado ({f.recaudacion_acum_eur:,.0f} €) "
            f"menor que el fin de semana ({f.recaudacion_eur:,.0f} €) en el PDF"
        )
    dif = (h["var_recaudacion_pdf"] - h["var_espectadores_pdf"]).abs()
    for _, f in h[dif > 0.15].iterrows():
        avisos.append(
            f"{f.finde_inicio} · {f.titulo}: recaudación {f.var_recaudacion_pdf:+.0%} "
            f"y espectadores {f.var_espectadores_pdf:+.0%} en el PDF"
        )


def main():
    h = pd.read_csv(HISTORICO)
    errores, avisos = [], []
    comprobar_estructura(h, errores)
    comprobar_continuidad(h, errores)
    comprobar_totales(h, errores)
    comprobar_variaciones(h, avisos)
    comprobar_rarezas_pdf(h, avisos)

    findes = sorted(h["finde_inicio"].unique())
    print(f"Histórico: {len(findes)} fines de semana, del {findes[0]} al {findes[-1]}")
    for e in errores:
        print(f"ERROR  {e}")
    for a in avisos:
        print(f"AVISO  {a}")
    if not errores:
        print("Validación correcta.")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
