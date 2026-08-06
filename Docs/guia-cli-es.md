# Movies Recommender — Guía del gestor CLI

Esta guía explica las opciones disponibles en el gestor interactivo incluido en `manage.pyz`.

El gestor permite configurar la instalación, generar el dataset, construir los modelos de recomendación y controlar el Backend y el Frontend mediante Docker.

## 1. Requisitos

El equipo debe tener instalado:

- Python 3.
- Docker.
- Docker Compose.
- Conexión a Internet para descargar las imágenes Docker, MovieLens, los datos de TMDB y los pósteres.
- Un token bearer de TMDB para generar el dataset.

No es necesario instalar dependencias adicionales de Python.

## 2. Archivos necesarios

`manage.pyz` y `compose.yaml` deben permanecer en el mismo directorio:

```text
MoviesRecommender/
├── manage.pyz
└── compose.yaml
```

El gestor creará en ese mismo directorio:

```text
.env
data/
```

El archivo `.env` guarda la configuración de la instalación. El directorio `data/` guarda el dataset, los pósteres, los modelos y los registros.

## 3. Ejecutar el gestor

Abre una terminal dentro del directorio que contiene `manage.pyz` y `compose.yaml`.

En Linux:

```bash
python3 manage.pyz
```

En Windows:

```powershell
py manage.pyz
```

## 4. Primera configuración

La primera vez que se ejecute el gestor se solicitarán los siguientes valores.

### Nombre del proyecto de Compose

Identifica la instalación dentro de Docker Compose.

Puede aceptarse el valor mostrado entre corchetes o escribirse otro nombre usando minúsculas, números, guiones y guiones bajos.

### Directorio de datos

Indica dónde se almacenarán el dataset, los modelos, los pósteres y los registros.

Puede usarse:

```text
./data
```

o una ruta absoluta.

### Puerto del Backend

Es el puerto externo en el que estará disponible la API.

El valor mostrado entre corchetes es el predeterminado, pero puede introducirse cualquier otro puerto libre.

### Puerto del Frontend

Es el puerto externo en el que estará disponible la aplicación web.

Debe ser diferente del puerto del Backend. Aunque solo vaya a utilizarse el Backend, el gestor solicita este valor como parte de la configuración general.

### Acceso de red

El gestor ofrece dos opciones:

- **Solo este equipo:** el Backend y el Frontend solo serán accesibles desde el ordenador en el que se ejecutan.
- **Otros equipos de la red:** permite que Unity, unas gafas VR u otros equipos de la red local se conecten a la aplicación.

### Token bearer de TMDB

Se utiliza durante el enriquecimiento del dataset para obtener información de las películas.

Es necesario para generar un dataset nuevo o repetir el enriquecimiento de TMDB.

Después de mostrar el resumen, el gestor solicita confirmación antes de guardar `.env`.

## 5. Menú principal

El menú principal contiene:

```text
1. Aplicación
2. Dataset
3. Configuración
0. Salir
```

### Aplicación

Permite controlar los servicios y gestionar los modelos de recomendación.

### Dataset

Permite generar, reconstruir, reanudar, validar y consultar el dataset offline.

### Configuración

Esta opción está reservada para una ampliación posterior del gestor. La configuración inicial se guarda actualmente en `.env`.

## 6. Opciones del Dataset

Ruta:

```text
Dataset
```

### Generar o reconstruir dataset offline

Contiene tres operaciones.

#### Generar un dataset nuevo

Ejecuta la pipeline completa desde el principio y genera un nuevo dataset offline.

Si ya existe un dataset final, el gestor solicita confirmación antes de reemplazarlo.

#### Reconstruir usando datos existentes

Vuelve a ejecutar la generación reutilizando los archivos de MovieLens que ya estén disponibles en el directorio de datos.

#### Reanudar una generación interrumpida

Detecta los resultados intermedios existentes y continúa desde la primera etapa pendiente.

### Origen de MovieLens

Durante la generación pueden aparecer estas opciones:

- **Descargar MovieLens automáticamente:** descarga el dataset MovieLens 32M.
- **Usar archivos de MovieLens ya extraídos:** reutiliza los archivos existentes en `data/`.
- **Usar un archivo ZIP de MovieLens:** importa un ZIP local proporcionado por el usuario.

### Configuración del dataset

#### Recomendada

Aplica la configuración preparada para la instalación estándar:

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

#### Personalizada

Permite configurar manualmente:

- Máximo de películas candidatas.
- Mínimo de valoraciones por candidata.
- Año mínimo y máximo de candidatas.
- Mínimo de etiquetas distintas.
- Máximo de etiquetas almacenadas por película.
- Límite del catálogo público.
- Límite del núcleo colaborativo.
- Mínimo de valoraciones del catálogo.
- Año mínimo del catálogo público.
- Año mínimo del catálogo colaborativo.
- Idioma de visualización.
- Política de audiencia.

Los valores mostrados entre corchetes son los valores iniciales. Pulsar Intro conserva el valor mostrado.

### Enriquecimiento de TMDB

- **Reanudar y reutilizar datos existentes:** conserva el trabajo de TMDB completado previamente y continúa desde el último punto guardado.
- **Repetir el enriquecimiento:** vuelve a consultar TMDB desde el principio.

### Descargar los pósteres que falten

Descarga y guarda localmente los pósteres utilizados por la aplicación.

Los pósteres existentes se reutilizan.

### Ejecutar la auditoría del dataset

Genera archivos de diagnóstico para analizar la calidad y la composición del dataset.

La auditoría no es necesaria para ejecutar la aplicación.

### Limpiar archivos temporales

Elimina los archivos de MovieLens descargados y la caché intermedia que ya no son necesarios después de una generación correcta.

Conserva el dataset final y los pósteres necesarios para ejecutar la aplicación.

### Reconfigurar dataset offline existente

Permite cambiar la política de audiencia del catálogo público sin repetir toda la descarga y el enriquecimiento del dataset.

Los modelos no se reconstruyen automáticamente después de cambiar el dataset.

### Validar dataset offline

Comprueba que existen y son válidos los archivos necesarios para utilizar el dataset.

### Ver información del dataset

Muestra la ubicación, los recuentos principales, la política aplicada y la compatibilidad con los modelos existentes.

### Limpiar archivos temporales

Permite eliminar posteriormente los directorios temporales conocidos sin borrar el dataset final.

## 7. Modelos de recomendación

Ruta:

```text
Aplicación
→ Modelos de recomendación
```

### Ver modelos existentes

Muestra los modelos encontrados, las variantes activas y su compatibilidad con el dataset.

### Validar modelos y compatibilidad

Comprueba que existen todos los artefactos obligatorios y que fueron generados para el dataset actual.

### Reconstruir y entrenar modelos

Construye los modelos utilizados por la API:

- TF-IDF.
- Popularidad.
- Item KNN.
- User KNN.
- Biased Matrix Factorization.

La generación del dataset no reconstruye automáticamente estos modelos. Deben reconstruirse después de generar o modificar el dataset.

### Ejecutar auditoría

Ejecuta la comparación y evaluación de los modelos compatibles.

No es necesaria para iniciar el Backend.

### Ver logs de la última ejecución

Muestra el registro guardado durante la última reconstrucción de modelos.

## 8. Control de los servicios

Dentro de `Aplicación` pueden gestionarse:

- Backend.
- Frontend.
- Backend y Frontend conjuntamente.

Cada servicio ofrece:

- **Iniciar:** crea e inicia los contenedores necesarios.
- **Detener:** detiene los contenedores.
- **Reiniciar:** reinicia los contenedores existentes.
- **Actualizar:** descarga la imagen publicada más reciente y recrea los servicios.
- **Ver estado:** muestra el estado, los puertos publicados y la salud del servicio.
- **Ver registros:** muestra los logs del servicio.

La opción **Estado general** muestra conjuntamente el estado del Backend y del Frontend.

## 9. Dirección del Backend

Cuando se ha seleccionado acceso solo desde el mismo equipo:

```text
http://localhost:<puerto-del-backend>
```

Cuando se ha permitido acceso desde la red:

```text
http://<IP-del-equipo>:<puerto-del-backend>
```

El puerto utilizado es el elegido durante la primera configuración.

La ruta principal de recomendaciones es:

```text
POST /recommendations
```
