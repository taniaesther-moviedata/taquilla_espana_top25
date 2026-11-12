# taquilla_espana_top25

Este proyecto, semiautomatizado con Claude, produce cada semana un boletín con el Top 25 de taquilla de fin de semana en los cines de España, listo para publicarse como imagen en LinkedIn.

Autora: Tania Adrianzen Acero.

## Fuente

[Taquilla y espectadores](https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html), Ministerio de Cultura, serie «Top 25». Un PDF por fin de semana (viernes a domingo). Los datos los elabora Rentrak y no son datos oficiales del ICAA.

Cita en el boletín: «Fuente: Ministerio de Cultura / ICAA, datos elaborados por Rentrak».

**Dashboard interactivo:** [Taquilla España · Top 25 del fin de semana](https://claude.ai/artifact/UtmKbXVYMyQ1AhRdVoYDfK). Se actualiza cada semana y el selector permite consultar los fines de semana anteriores.

## Estructura

```
taquilla_espana_top25/
├── data/
│   ├── raw/                         # PDFs del ministerio tal como se descargan; no se editan
│   ├── processed/
│   │   ├── top25_historico.csv      # una fila por película y fin de semana
│   │   └── totales_pdf.csv          # fila TOTAL de cada PDF, para validar
│   └── correcciones_titulos.csv     # títulos para mostrar fijados a mano
├── src/
│   ├── extraer_pdf.py               # PDF -> histórico
│   ├── validar.py                   # comprobaciones tras cada carga
│   ├── generar_boletin.py           # páginas del boletín (PNG) y PDF para LinkedIn
│   └── generar_animacion.py         # versión animada del boletín (MP4 4:5 y GIF)
├── dashboard/
│   └── index.html                   # copia de la página del dashboard de Claude Data
├── boletines/
│   └── AAAA-MM-DD/                  # una carpeta por fin de semana (fecha del viernes)
│       ├── pagina_1.png … pagina_3.png
│       ├── boletin_AAAA-MM-DD.pdf
│       └── animacion_AAAA-MM-DD.mp4 / .gif
├── requirements.txt
└── README.md
```

## Rutina del jueves

1. Descargar el PDF «Top 25» del último fin de semana y subirlo a `data/raw/` con su nombre original.
2. `python src/extraer_pdf.py` añade al histórico los PDFs que falten.
3. `python src/validar.py` debe terminar en «Validación correcta». Los errores se corrigen antes de seguir; los avisos se revisan y se anotan abajo si procede.
4. `python src/generar_boletin.py` crea en `boletines/<viernes>/` las tres páginas (PNG 4:5) y el PDF para publicar como documento en LinkedIn.
5. Opcional: `python src/generar_animacion.py --gif` crea la versión animada (MP4 de 12 s, 1080 × 1350, y una copia en GIF).
6. Actualizar el dashboard de Claude Data con el nuevo `top25_historico.csv`.
7. Redactar el post y programarlo para el viernes a las 11:00.

Instalación: `pip install -r requirements.txt`

## Notas sobre los datos

- La película se identifica entre fines de semana por `titulo_original` + `distribuidora`.
- `titulo_mostrar` pone el artículo delante («Bola negra, La» → «La bola negra»). Lo que la regla no resuelve (tildes, nombres propios) se corrige en `data/correcciones_titulos.csv`.
- **Variación semanal:** el boletín la calcula con el histórico (cifras exactas, coherentes con la comparación a 4 semanas). El `+/-%` del PDF se guarda solo como contraste: viene redondeado a entero, y el fin de semana anterior que implica es de media un 0,7 % mayor que el publicado (posibles correcciones de cifras provisionales). El validador avisa si la diferencia supera 3 puntos.
- **Acumulado:** total desde el estreno, días laborables y preestrenos incluidos. Verificado con la carga inicial: en 83 pares de fines de semana consecutivos, acumulado nuevo ≥ acumulado anterior + fin de semana, y la diferencia (lunes a jueves) es de mediana el 59 % del fin de semana anterior. En estrenos, el acumulado es igual al fin de semana (20 de 45) o mayor por preestrenos y pases especiales (21 de 45).
- **Errores de origen:** cuatro estrenos traen un acumulado menor que su propio fin de semana (Superthings −97.898 €, Karateka −13.861 €, Digger −8.314 €, El precio de la red −1.414 €). En Superthings, el % de la semana siguiente confirma la cifra del fin de semana, así que el erróneo es el acumulado. También hay variaciones de espectadores incoherentes con la recaudación (Resident Evil, 16-18 oct.). Se mantienen tal cual; el acumulado no se usa en el boletín.

## Paleta

Tan `#D2B997`, Lavender Purple `#946FBA`, Cool Steel `#9EA6A5`, Rose Wine `#BF4D70`, Golden Bronze `#C4972E`, Thistle `#D2C5DE`, Black `#060200`. Para texto legible se usan tonos oscurecidos de la misma paleta (bronce `#8A6A1F` para subidas, lavanda `#5E3F82` sobre Thistle, gris `#5E6463`). Subidas en bronce con ▲ o «+», bajadas en Rose Wine con ▼ o «−».

## Registro

| Fin de semana | Fecha de carga | Incidencias |
| --- | --- | --- |
| 2 oct. – 8 nov. 2026 (6 fines de semana) | 2026-11-12 | Carga inicial. Validación correcta; avisos de origen anotados arriba. |
