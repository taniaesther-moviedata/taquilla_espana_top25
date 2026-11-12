"""Extrae la tabla del Top 25 de los PDFs del Ministerio de Cultura.

Uso:
    python src/extraer_pdf.py            # procesa los PDFs de data/raw/ que falten
    python src/extraer_pdf.py --todo     # reconstruye el histórico desde cero

Cada PDF tiene una sola página con una tabla de 25 filas y una fila TOTAL.
Las columnas no tienen separadores dibujados en el cuerpo, solo en la
cabecera, así que cada palabra se asigna a la columna cuya celda de cabecera
contiene su centro horizontal. Los límites se leen de cada PDF porque varían
unos puntos de un archivo a otro.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pdfplumber

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
HISTORICO = RAIZ / "data" / "processed" / "top25_historico.csv"

COLUMNAS_PDF = [
    "rank",
    "titulo",
    "titulo_original",
    "distribuidora",
    "semana_en_cartel",
    "cines",
    "recaudacion_eur",
    "var_recaudacion_pdf",
    "espectadores",
    "var_espectadores_pdf",
    "recaudacion_acum_eur",
    "espectadores_acum",
]

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# El pie del PDF dice, por ejemplo, "España: 30-01 Noviembre 2026".
# El mes y el año son los del domingo.
PATRON_FECHAS = re.compile(r"España:\s*(\d{1,2})-(\d{1,2})\s+([A-Za-zé]+)\s+(\d{4})")

# Artículos que el ministerio pone al final del título: "Bola negra, La".
ARTICULOS = ("El", "La", "Los", "Las", "The", "A", "An", "Il", "Le", "Les", "L'")


def leer_fechas(texto):
    """Devuelve (viernes, domingo) a partir del pie del PDF."""
    m = PATRON_FECHAS.search(texto)
    if not m:
        raise ValueError("No se encuentra el periodo en el pie del PDF")
    dia_ini, dia_fin = int(m.group(1)), int(m.group(2))
    mes_fin = MESES[m.group(3).lower()]
    anio_fin = int(m.group(4))
    domingo = date(anio_fin, mes_fin, dia_fin)
    # Si el viernes es de un mes anterior (30-01), retrocede un mes.
    if dia_ini > dia_fin:
        mes_ini = 12 if mes_fin == 1 else mes_fin - 1
        anio_ini = anio_fin - 1 if mes_fin == 1 else anio_fin
    else:
        mes_ini, anio_ini = mes_fin, anio_fin
    viernes = date(anio_ini, mes_ini, dia_ini)
    if (domingo - viernes).days != 2 or viernes.weekday() != 4:
        raise ValueError(f"Periodo inesperado: {viernes} - {domingo}")
    return viernes, domingo


def a_numero(texto):
    """'1.007.157 €' -> 1007157.0 ; '' -> None."""
    limpio = texto.replace("€", "").replace(".", "").replace(",", ".").strip()
    return float(limpio) if limpio else None


def a_porcentaje(texto):
    """'-23%' -> -0.23 ; '' -> None."""
    limpio = texto.replace("%", "").strip()
    return round(float(limpio) / 100, 4) if limpio else None


def cargar_correcciones():
    """Títulos para mostrar fijados a mano (data/correcciones_titulos.csv)."""
    ruta = RAIZ / "data" / "correcciones_titulos.csv"
    if not ruta.exists():
        return {}
    tabla = pd.read_csv(ruta)
    return dict(zip(tabla["titulo"], tabla["titulo_mostrar"]))


def titulo_para_mostrar(titulo, correcciones=None):
    """'Bola negra, La' -> 'La bola negra'.

    Mueve el artículo que el ministerio pone detrás, también cuando va antes
    de un subtítulo ('Oveja Shaun, La. Mision calabaza'). Los casos que esta
    regla no resuelve (nombres propios, tildes) se fijan en
    data/correcciones_titulos.csv, que tiene prioridad.
    """
    if correcciones and titulo in correcciones:
        return correcciones[titulo]
    # Los paréntesis finales, como "(1980) (re)", se apartan y se devuelven al final.
    m = re.match(r"^(.*?)((?:\s*\([^)]*\))*)$", titulo)
    nucleo, parentesis = m.group(1), m.group(2)
    principal, separador, subtitulo = nucleo.partition(". ")
    for art in ARTICULOS:
        sufijo = f", {art}"
        if principal.endswith(sufijo):
            resto = principal[: -len(sufijo)]
            if art in ("El", "La", "Los", "Las"):
                resto = resto[:1].lower() + resto[1:]
            return f"{art} {resto}{separador}{subtitulo}{parentesis}"
    return titulo


def limites_columnas(pagina):
    """Bordes horizontales de las 12 celdas de la cabecera."""
    tabla = pagina.find_tables()[0]
    celdas = sorted(tabla.cells, key=lambda c: c[0])
    if len(celdas) != len(COLUMNAS_PDF):
        raise ValueError(f"La cabecera tiene {len(celdas)} celdas, se esperaban 12")
    return [(c[0], c[2]) for c in celdas], tabla.bbox[3]


def extraer_filas(pagina):
    """Agrupa las palabras del cuerpo de la tabla por fila y por columna."""
    limites, fin_cabecera = limites_columnas(pagina)
    palabras = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
    cuerpo = [p for p in palabras if p["top"] > fin_cabecera]

    # Agrupa por línea con una tolerancia de 3 puntos.
    lineas = []
    for p in sorted(cuerpo, key=lambda p: (round(p["top"]), p["x0"])):
        if lineas and abs(lineas[-1][0] - p["top"]) < 3:
            lineas[-1][1].append(p)
        else:
            lineas.append([p["top"], [p]])

    filas = []
    for _, palabras_linea in lineas:
        celdas = [[] for _ in COLUMNAS_PDF]
        for p in sorted(palabras_linea, key=lambda p: p["x0"]):
            centro = (p["x0"] + p["x1"]) / 2
            for i, (x0, x1) in enumerate(limites):
                if x0 <= centro <= x1:
                    celdas[i].append(p["text"])
                    break
        filas.append([" ".join(c) for c in celdas])
    return filas


def procesar_pdf(ruta):
    """Devuelve (DataFrame con las 25 filas, dict con la fila TOTAL)."""
    with pdfplumber.open(ruta) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError(f"{ruta.name}: se esperaba 1 página")
        pagina = pdf.pages[0]
        texto = pagina.extract_text() or ""
        if "Top 25 Fin de Semana" not in texto:
            raise ValueError(f"{ruta.name}: no es un informe Top 25 de fin de semana")
        viernes, domingo = leer_fechas(texto)
        filas = extraer_filas(pagina)

    datos, total = [], None
    for celdas in filas:
        if celdas[0].isdigit():
            datos.append(celdas)
        elif celdas[0] == "TOTAL" or celdas[1].startswith("TOTAL"):
            total = celdas

    df = pd.DataFrame(datos, columns=COLUMNAS_PDF)
    for col in ("rank", "semana_en_cartel", "cines"):
        df[col] = df[col].astype(int)
    for col in ("recaudacion_eur", "espectadores", "recaudacion_acum_eur", "espectadores_acum"):
        df[col] = df[col].map(a_numero)
    for col in ("var_recaudacion_pdf", "var_espectadores_pdf"):
        df[col] = df[col].map(a_porcentaje)

    df.insert(0, "finde_fin", domingo.isoformat())
    df.insert(0, "finde_inicio", viernes.isoformat())
    correcciones = cargar_correcciones()
    df["titulo_mostrar"] = df["titulo"].map(lambda t: titulo_para_mostrar(t, correcciones))
    df["archivo_origen"] = ruta.name

    # La fila TOTAL trae, en orden: recaudación, espectadores y los dos acumulados.
    importes = re.findall(r"[\d.]+", " ".join(total or []))
    if len(importes) != 4:
        raise ValueError(f"{ruta.name}: no se puede leer la fila TOTAL")
    total_pdf = {
        "finde_inicio": viernes.isoformat(),
        "recaudacion_eur": a_numero(importes[0]),
        "espectadores": a_numero(importes[1]),
    }
    return df, total_pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--todo", action="store_true", help="reconstruir el histórico")
    args = parser.parse_args()

    existente = None
    if HISTORICO.exists() and not args.todo:
        existente = pd.read_csv(HISTORICO)
    ya_cargados = set(existente["archivo_origen"]) if existente is not None else set()

    nuevos, totales = [], []
    for ruta in sorted(DIR_RAW.glob("*.pdf")):
        if ruta.name in ya_cargados:
            continue
        df, total = procesar_pdf(ruta)
        nuevos.append(df)
        totales.append({**total, "archivo_origen": ruta.name})
        print(f"{ruta.name}: {len(df)} filas, fin de semana {df['finde_inicio'].iloc[0]}")

    if not nuevos:
        print("No hay PDFs nuevos.")
        return 0

    partes = ([existente] if existente is not None else []) + nuevos
    historico = pd.concat(partes, ignore_index=True)
    historico = historico.sort_values(["finde_inicio", "rank"]).reset_index(drop=True)
    HISTORICO.parent.mkdir(parents=True, exist_ok=True)
    historico.to_csv(HISTORICO, index=False)

    # Los totales del PDF se guardan aparte para validar sumas.
    ruta_totales = HISTORICO.with_name("totales_pdf.csv")
    tot = pd.DataFrame(totales)
    if ruta_totales.exists() and not args.todo:
        tot = pd.concat([pd.read_csv(ruta_totales), tot], ignore_index=True)
    tot.drop_duplicates("finde_inicio", keep="last").sort_values("finde_inicio").to_csv(
        ruta_totales, index=False
    )
    print(f"Histórico: {len(historico)} filas en {HISTORICO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
