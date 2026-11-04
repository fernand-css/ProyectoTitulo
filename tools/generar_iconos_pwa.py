"""Regenera static/icons/icon-192.png e icon-512.png con la marca de la Unidad (cruz de farmacia blanca sobre verde-azulado).

Uso (solo cuando cambie la marca; requiere Pillow, que no es dependencia del proyecto):

    python tools/generar_iconos_pwa.py

Los PNG se guardan en RGB de 8 bits sin transparencia: lo exige test_estaticos. La geometría replica
la del símbolo `marca` de templates/components/iconos.html y de static/icons/marca.svg (cuadrícula de 48),
pero a sangre completa, sin esquinas redondeadas, como pide un icono de aplicación.
"""

from pathlib import Path

from PIL import Image, ImageDraw

FONDO, CRUZ = "#1F5FAE", "#FFFFFF"
UNIDADES = 48
SUPERMUESTREO = 4


def dibujar(lado):
    escala = lado * SUPERMUESTREO / UNIDADES
    imagen = Image.new("RGB", (lado * SUPERMUESTREO,) * 2, FONDO)
    lienzo = ImageDraw.Draw(imagen)
    # Barra vertical (20–28 × 11–37) y barra horizontal (11–37 × 20–28) de la cruz.
    for x1, y1, x2, y2 in ((20, 11, 28, 37), (11, 20, 37, 28)):
        lienzo.rectangle([x1 * escala, y1 * escala, x2 * escala - 1, y2 * escala - 1], fill=CRUZ)
    return imagen.resize((lado, lado), Image.LANCZOS)


def main():
    destino = Path(__file__).resolve().parents[1] / "static" / "icons"
    for lado in (192, 512):
        dibujar(lado).save(destino / f"icon-{lado}.png", format="PNG")
        print(f"icon-{lado}.png generado")


if __name__ == "__main__":
    main()
