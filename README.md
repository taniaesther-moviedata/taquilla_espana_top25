# taquilla_espana_top25

Este proyecto produce cada semana un boletín de una página con el Top 25 de taquilla de fin de semana en los cines de España, listo para publicarse como imagen en LinkedIn.

Autora: Tania Adrianzen Acero.

## Fuente

[Taquilla y espectadores](https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html), Ministerio de Cultura, serie «Top 25». Un PDF por fin de semana (viernes a domingo). Los datos los elabora Rentrak y no son datos oficiales del ICAA.

Cita en el boletín: «Fuente: Ministerio de Cultura / ICAA, datos elaborados por Rentrak».

## Estructura

```
data/raw/                      PDFs tal como se descargan; no se editan
data/processed/
  top25_historico.csv          una fila por película y fin de semana
  totales_pdf.csv              fila TOTAL de cada PDF, para validar
data/correcciones_titulos.csv  títulos para mostrar fijados a mano
src/extraer_pdf.py             PDF -> histórico
src/validar.py                 comprobaciones tras cada carga
boletines/                     una carpeta por fin de semana: imagen + texto
```

## Rutina del jueves

1. Descargar el PDF «Top 25» del último fin de semana y subirlo a `data/raw/` con su nombre original.
2. `python src/extraer_pdf.py` añade al histórico los PDFs que falten.
3. `python src/validar.py` debe terminar en «Validación correcta». Los errores se corrigen antes de seguir; los avisos se revisan y se anotan abajo si procede.
4. Generar el boletín, redactar el post y programarlo para el viernes a las 11:00.

Instalación: `pip install -r requirements.txt`

## Notas sobre los datos

- La película se identifica entre fines de semana por `titulo_original` + `distribuidora`.
- `titulo_mostrar` pone el artículo delante («Bola negra, La» → «La bola negra»). Lo que la regla no resuelve (tildes, nombres propios) se corrige en `data/correcciones_titulos.csv`.
- **Variación semanal:** el boletín la calcula con el histórico (cifras exactas, coherentes con la comparación a 4 semanas). El `+/-%` del PDF se guarda solo como contraste: viene redondeado a entero, y el fin de semana anterior que implica es de media un 0,7 % mayor que el publicado (posibles correcciones de cifras provisionales). El validador avisa si la diferencia supera 3 puntos.
- **Acumulado:** total desde el estreno, días laborables y preestrenos incluidos. Verificado con la carga inicial: en 83 pares de fines de semana consecutivos, acumulado nuevo ≥ acumulado anterior + fin de semana, y la diferencia (lunes a jueves) es de mediana el 59 % del fin de semana anterior. En estrenos, el acumulado es igual al fin de semana (20 de 45) o mayor por preestrenos y pases especiales (21 de 45).
- **Errores de origen:** cuatro estrenos traen un acumulado menor que su propio fin de semana (Superthings −97.898 €, Karateka −13.861 €, Digger −8.314 €, El precio de la red −1.414 €). En Superthings, el % de la semana siguiente confirma la cifra del fin de semana, así que el erróneo es el acumulado. También hay variaciones de espectadores incoherentes con la recaudación (Resident Evil, 16-18 oct.). Se mantienen tal cual; el acumulado no se usa en el boletín.

## Registro

| Fin de semana | Fecha de carga | Incidencias |
| --- | --- | --- |
| 2 oct. – 8 nov. 2026 (6 fines de semana) | 2026-11-12 | Carga inicial. Validación correcta; avisos de origen anotados arriba. |
