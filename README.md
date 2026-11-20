# taquilla_espana_top25

Este proyecto, semiautomatizado con Claude, produce cada semana un boletín con el Top 25 de taquilla de fin de semana en los cines de España, listo para publicarse como imagen en LinkedIn.

Autora: Tania Adrianzen Acero.

## Fuente

[Taquilla y espectadores](https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html), Ministerio de Cultura, serie «Top 25». Un PDF por fin de semana (viernes a domingo). Los datos los elabora Rentrak y no son datos oficiales del ICAA.

Cita en el boletín: «Fuente: Ministerio de Cultura / ICAA, datos elaborados por Rentrak».

**Dashboard interactivo:** [Taquilla España · Top 25 del fin de semana](https://taniaesther-moviedata.github.io/taquilla_espana_top25/), publicado con GitHub Pages. Se actualiza solo cada vez que se carga un PDF nuevo, y el selector permite consultar los fines de semana anteriores.

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
│   ├── generar_boletin.py           # boletín para LinkedIn (PDF de cuatro páginas)
│   └── generar_animacion.py         # versión animada del boletín (MP4 4:5 y GIF)
├── dashboard/
│   └── index.html                   # dashboard; se publica en GitHub Pages junto con el histórico
├── boletines/
│   └── AAAA-MM-DD/                  # una carpeta por fin de semana (fecha del viernes)
│       ├── boletin_AAAA-MM-DD.pdf
│       └── animacion_AAAA-MM-DD.mp4 / .gif
├── requirements.txt
└── README.md
```

## Rutina del jueves

1. Descargar el PDF «Top 25» del último fin de semana y subirlo a `data/raw/` con su nombre original.
2. `python src/extraer_pdf.py` añade al histórico los PDFs que falten.
3. `python src/validar.py` debe terminar en «Validación correcta». Los errores se corrigen antes de seguir; los avisos se revisan y se anotan abajo si procede.
4. `python src/generar_boletin.py` crea en `boletines/<viernes>/` el PDF de cuatro páginas (4:5) para publicar como documento en LinkedIn: número 1, cifras clave y top 10; ranking completo; trayectoria y entradas y salidas; distribuidoras.
5. Opcional: `python src/generar_animacion.py --gif` crea la versión animada (MP4 de 12 s, 1080 × 1350, y una copia en GIF).
6. El dashboard se publica solo en GitHub Pages con el nuevo `top25_historico.csv` (ver abajo).
7. Redactar el post y programarlo para el viernes a las 11:00.

Instalación: `pip install -r requirements.txt`

### Automatización con GitHub Actions

Los pasos 2 a 5 se ejecutan solos con el flujo `.github/workflows/boletin_semanal.yml`: al subir un PDF a `data/raw/` en la rama `main`, GitHub extrae, valida, genera el boletín y la animación y guarda los resultados en el repositorio con un commit automático. Si la validación da error, el flujo se detiene y no guarda nada; el detalle aparece en la pestaña **Actions**. También se puede lanzar a mano desde **Actions → Boletín semanal → Run workflow**. Después de que termine, hay que hacer `git pull` antes de trabajar en local.

Cuando el boletín termina bien, el flujo `.github/workflows/publicar_dashboard.yml` publica en GitHub Pages `dashboard/index.html` y el histórico actualizado. También se ejecuta al cambiar el dashboard o el histórico en `main`, y a mano desde **Actions → Publicar dashboard → Run workflow**. La web solo incluye la página y el CSV, no los PDFs ni los boletines. Para ver el dashboard en local hay que servir la carpeta del repositorio (`python -m http.server` y abrir `/dashboard/`), porque el navegador no deja leer el CSV abriendo el archivo directamente.

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
| 13-15 nov. 2026 | 2026-11-20 | Primera carga con GitHub Actions. El PDF no estaba publicado el jueves a mediodía; se subió el viernes. Validación correcta, con un aviso de origen: «La odisea», +28 % de recaudación y +1 % de espectadores según el PDF. |

## Cambios en la estructura del dashboard

| Fecha | Cambio |
| --- | --- |
| 2026-11-20 | Boletín y animación: tarjeta «Distribuidora líder» en las cifras clave; el PDF suma una cuarta página, «Distribuidoras», con la líder y la cuota de cada distribuidora en barras. Los títulos largos ya no se cortan: primero se reduce un poco la letra y, si no basta, pasan a dos líneas (la fila o el recuadro crecen lo necesario); los «…» quedan solo para casos extremos. |
| 2026-11-20 | El dashboard pasa de Claude Data a GitHub Pages, con el mismo contenido, la paleta del proyecto (Lora e Inter) y modo oscuro. Los filtros quedan en la dirección de la página, así que un enlace copiado conserva la selección. |
| 2026-11-18 | Nueva tarjeta «Distribuidora líder del fin de semana» (distribuidora con más recaudación en el Top 25, su cuota, su recaudación y su número de películas) y nueva sección con la cuota de cada distribuidora en barras horizontales. Ambas siguen el selector de fin de semana, no el de distribuidora. |
