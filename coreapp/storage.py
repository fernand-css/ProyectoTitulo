"""Almacenamiento de estáticos que versiona las hojas de estilo y los scripts.

Sin esto, el servidor de desarrollo entrega los estáticos sin `Cache-Control` y el navegador puede seguir
usando un `.css` viejo después de un cambio (botones sin estilo, diseños a medias). Aquí cada URL de un
`.css` o `.js` lleva `?v=<fecha de modificación>`: cambia el archivo, cambia la URL y se vuelve a descargar.

Las fuentes e imágenes no se versionan: el CSS las referencia con rutas relativas y una URL distinta haría
que el navegador descargara dos veces la fuente precargada. En producción, `collectstatic` con
`ManifestStaticFilesStorage` (nombres con hash) es la alternativa completa; esto cubre el desarrollo y las
demostraciones sin cambiar el flujo.
"""

import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage

EXTENSIONES_VERSIONADAS = (".css", ".js")


class EstaticosVersionados(StaticFilesStorage):
    def url(self, name):
        url = super().url(name)
        if not name.lower().endswith(EXTENSIONES_VERSIONADAS):
            return url
        ruta = finders.find(name)
        if not ruta:
            ruta = self.path(name)
        try:
            version = int(os.stat(ruta).st_mtime)
        except (OSError, TypeError):
            return url
        return f"{url}?v={version}"
