# Movies Recommender — Configuración recomendada

Esta guía indica las opciones recomendadas para generar el dataset, construir los modelos e iniciar el Backend con una instalación limpia.

## 1. Preparar la instalación

Coloca estos dos archivos en el mismo directorio:

```text
MoviesRecommender/
├── manage.pyz
└── compose.yaml
```

Abre una terminal dentro de ese directorio.

En Linux:

```bash
python3 manage.pyz
```

En Windows:

```powershell
py manage.pyz
```

## 2. Configuración inicial recomendada

Durante la primera ejecución utiliza estos valores.

### Nombre del proyecto

Acepta el valor predeterminado:

```text
movies-recommender
```

### Directorio de datos

Acepta:

```text
./data
```

### Puerto del Backend

Utiliza:

```text
18014
```

### Puerto del Frontend

Utiliza:

```text
15173
```

### Acceso de red

Selecciona:

```text
2. Otros equipos de la red
```

Esta opción permite que Unity, las gafas VR u otro ordenador puedan conectarse al Backend desde la red local.

### Token bearer de TMDB

Introduce un token bearer válido de TMDB.

El token es necesario para descargar y enriquecer la información de las películas durante la generación.

Confirma el resumen para guardar la configuración.

## 3. Generar el dataset

Desde el menú principal sigue esta ruta:

```text
Dataset
→ Generar o reconstruir dataset offline
→ Generar un dataset nuevo
```

Como origen de los datos selecciona:

```text
Descargar MovieLens automáticamente
```

Como configuración selecciona:

```text
Recomendada
```

El preset recomendado aplica:

| Opción | Valor |
| --- | ---: |
| Máximo de películas candidatas | 15000 |
| Mínimo de valoraciones por candidata | 100 |
| Año mínimo de candidatas | 1990 |
| Año máximo de candidatas | Sin límite |
| Mínimo de etiquetas distintas | 0 |
| Máximo de etiquetas por película | 35 |
| Límite de películas públicas | Sin límite |
| Límite del núcleo colaborativo | 15000 |
| Mínimo de valoraciones del catálogo | 100 |
| Año mínimo del catálogo público | 2000 |
| Año mínimo del catálogo colaborativo | 1990 |
| Idioma | `es-ES` |
| Política de audiencia | Solo público familiar |

Después selecciona las siguientes opciones:

```text
Enriquecimiento de TMDB
→ Repetir el enriquecimiento
```

```text
¿Descargar los pósteres que falten?
→ Sí
```

```text
¿Ejecutar la auditoría del dataset?
→ No
```

```text
¿Limpiar los archivos temporales tras una ejecución correcta?
→ Sí
```

Revisa el resumen y confirma el inicio de la operación.

La generación puede tardar debido a la descarga de MovieLens, las consultas a TMDB y la descarga de los pósteres.

Al seleccionar la limpieza se eliminan los archivos descargados y la caché intermedia que ya no son necesarios. Se conservan el dataset final y los pósteres utilizados por la aplicación.

## 4. Validar el dataset

Cuando termine la generación sigue esta ruta:

```text
Dataset
→ Validar dataset offline
```

El gestor debe indicar que el dataset es válido.

## 5. Construir los modelos

La generación del dataset no construye automáticamente los modelos de recomendación.

Desde el menú principal sigue:

```text
Aplicación
→ Modelos de recomendación
→ Reconstruir y entrenar modelos
```

Confirma la reconstrucción.

El gestor construirá:

- TF-IDF.
- Popularidad.
- Item KNN.
- User KNN.
- Biased Matrix Factorization.

Cuando termine, comprueba la compatibilidad:

```text
Aplicación
→ Modelos de recomendación
→ Validar modelos y compatibilidad
```

El resultado debe indicar que los modelos son compatibles con el dataset actual.

## 6. Iniciar el Backend

Sigue esta ruta:

```text
Aplicación
→ Backend
→ Iniciar
```

Después comprueba su estado:

```text
Aplicación
→ Backend
→ Ver estado
```

El Backend debe aparecer iniciado y saludable.

No es necesario iniciar el Frontend para utilizar la API desde Unity.

## 7. Acceder al Backend

Desde el mismo ordenador:

```text
http://localhost:18014
```

Desde otro equipo de la red local:

```text
http://<IP-del-ordenador>:18014
```

La ruta de recomendaciones es:

```text
POST http://<host>:18014/recommendations
```

## 8. Resultado de la instalación

Después de completar el proceso, el directorio tendrá una estructura similar a:

```text
MoviesRecommender/
├── manage.pyz
├── compose.yaml
├── .env
└── data/
    ├── offline_dataset/
    ├── recommender_models/
    └── logs/
```

Para detener o reiniciar el Backend utiliza:

```text
Aplicación
→ Backend
→ Detener
```

o:

```text
Aplicación
→ Backend
→ Reiniciar
```
