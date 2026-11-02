"""Regenera static/icons/icon-192.png e icon-512.png con la marca de la Unidad (sol naciente sobre surcos).

Uso (solo cuando cambie la marca; requiere Pillow, que no es dependencia del proyecto):

    python tools/generar_iconos_pwa.py

Los PNG se guardan en RGB de 8 bits sin transparencia: lo exige test_estaticos. La geometría replica
la del símbolo `marca` de templates/components/iconos.html y de static/icons/marca.svg (cuadrícula de 48).
"""

from pathlib import Path

from PIL import Image, ImageDraw

TRIGO, ARENA, NARANJA, LADRILLO = "#FEF2A0", "#F3CD97", "#E98B50", "#BC4F4F"
UNIDADES = 48
SUPERMUESTREO = 4


def dibujar(lado):
    escala = lado * SUPERMUESTREO / UNIDADES
    imagen = Image.new("RGB", (lado * SUPERMUESTREO,) * 2, LADRILLO)
    lienzo = ImageDraw.Draw(imagen)

    def p(x, y):
        return (x * escala, y * escala)

    # Rayos del sol (líneas de 3 unidades con puntas redondeadas).
    grosor = 3 * escala
    for (x1, y1), (x2, y2) in (
        ((24, 21), (24, 15)), ((31, 22.9), (34, 17.7)), ((36.1, 28), (41.3, 25)),
        ((17, 22.9), (14, 17.7)), ((11.9, 28), (6.7, 25)),
    ):
        lienzo.line([p(x1, y1), p(x2, y2)], fill=TRIGO, width=round(grosor))
        for extremo in ((x1, y1), (x2, y2)):
            cx, cy = p(*extremo)
            lienzo.ellipse([cx - grosor / 2, cy - grosor / 2, cx + grosor / 2, cy + grosor / 2], fill=TRIGO)

    # Mitad superior del sol, apoyada en el horizonte (y = 35).
    lienzo.pieslice([*p(14, 25), *p(34, 45)], 180, 360, fill=TRIGO)
    # Campo y surcos que convergen en el horizonte.
    lienzo.rectangle([*p(0, 35), *p(48, 48)], fill=NARANJA)
    for triangulo in (((24, 35), (0, 48), (10, 48)), ((24, 35), (19, 48), (29, 48)), ((24, 35), (38, 48), (48, 48))):
        lienzo.polygon([p(*punto) for punto in triangulo], fill=ARENA)

    return imagen.resize((lado, lado), Image.LANCZOS)


def main():
    destino = Path(__file__).resolve().parents[1] / "static" / "icons"
    for lado in (192, 512):
        dibujar(lado).save(destino / f"icon-{lado}.png", format="PNG")
        print(f"icon-{lado}.png generado")


if __name__ == "__main__":
    main()
