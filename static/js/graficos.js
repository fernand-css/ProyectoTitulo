// Ayuda de los gráficos de Recetas: un cuadro con el texto del dato que está bajo el puntero o el foco.
// Solo repite lo que ya está escrito en la página (el atributo data-tip y la tabla de datos): sin JavaScript
// todo sigue legible. El texto se escribe con textContent, nunca como HTML.
(() => {
  const SEPARACION = 12;

  const preparar = (figura) => {
    const cuadro = document.createElement('div');
    cuadro.className = 'grafico-tip';
    cuadro.setAttribute('role', 'tooltip');
    cuadro.hidden = true;
    figura.appendChild(cuadro);

    const ocultar = () => { cuadro.hidden = true; };

    const mostrar = (marca, x, y) => {
      cuadro.textContent = marca.getAttribute('data-tip');
      cuadro.hidden = false;
      const caja = figura.getBoundingClientRect();
      let izquierda = x - caja.left + SEPARACION;
      // Si no cabe a la derecha del puntero, se muestra a su izquierda.
      if (izquierda + cuadro.offsetWidth > caja.width) {
        izquierda = Math.max(0, x - caja.left - SEPARACION - cuadro.offsetWidth);
      }
      const arriba = Math.max(0, y - caja.top - cuadro.offsetHeight - SEPARACION);
      cuadro.style.left = izquierda + 'px';
      cuadro.style.top = arriba + 'px';
    };

    // Con el dedo el evento queda en el elemento donde empezó el gesto: se busca la marca bajo el punto actual.
    const marcaEn = (evento) => {
      const elemento = document.elementFromPoint(evento.clientX, evento.clientY) || evento.target;
      const marca = elemento && elemento.closest ? elemento.closest('[data-tip]') : null;
      return marca && figura.contains(marca) ? marca : null;
    };

    const mover = (evento) => {
      const marca = marcaEn(evento);
      if (marca) mostrar(marca, evento.clientX, evento.clientY);
      else ocultar();
    };

    figura.addEventListener('pointermove', mover);
    figura.addEventListener('pointerdown', mover);
    // El mouse oculta el cuadro al salir; con el dedo queda a la vista hasta tocar en otra parte.
    figura.addEventListener('pointerleave', (evento) => { if (evento.pointerType === 'mouse') ocultar(); });
    document.addEventListener('pointerdown', (evento) => { if (!figura.contains(evento.target)) ocultar(); });
    // Teclado: los segmentos de la barra son enlaces y muestran su texto al recibir el foco.
    figura.addEventListener('focusin', (evento) => {
      const marca = evento.target.closest ? evento.target.closest('[data-tip]') : null;
      if (!marca) return;
      const caja = marca.getBoundingClientRect();
      mostrar(marca, caja.left + caja.width / 2, caja.top);
    });
    figura.addEventListener('focusout', ocultar);
    document.addEventListener('keydown', (evento) => { if (evento.key === 'Escape') ocultar(); });
  };

  document.querySelectorAll('[data-grafico]').forEach(preparar);
})();
