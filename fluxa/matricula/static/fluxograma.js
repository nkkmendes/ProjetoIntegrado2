
// Linhas do fluxograma: usa os pré/co-requisitos já cadastrados no Django.
document.addEventListener('DOMContentLoaded', () => {
  const grade = document.getElementById('grade-fluxograma');
  const svg = document.getElementById('conexoes-fluxa');
  if (!grade || !svg) return;

  const materias = [...grade.querySelectorAll('.materia[data-codigo]')];
  const porCodigo = new Map(materias.map(el => [el.dataset.codigo, el]));
  const ligacoes = [];
  const ns = 'http://www.w3.org/2000/svg';
  let selecionada = null;

  function codigos(valor) {
    return (valor || '').split(',').map(s => s.trim()).filter(Boolean);
  }

  materias.forEach(destino => {
    for (const codigo of codigos(destino.dataset.pre)) {
      const origem = porCodigo.get(codigo);
      if (origem) ligacoes.push({ origem, destino, tipo: 'pre' });
    }

    for (const codigo of codigos(destino.dataset.co)) {
      const origem = porCodigo.get(codigo);

      if (origem && !ligacoes.some(l => l.tipo === 'co' &&
          ((l.origem === origem && l.destino === destino) ||
           (l.origem === destino && l.destino === origem)))) {
        ligacoes.push({ origem, destino, tipo: 'co' });
      }
    }
  });

  for (const ligacao of ligacoes) {
    const path = document.createElementNS(ns, 'path');

    if (ligacao.tipo === 'co') {
      path.classList.add('co-requisito');
    }

    svg.appendChild(path);
    ligacao.path = path;
  }

  function desenhar() {
    const largura = grade.scrollWidth;
    const altura = grade.scrollHeight;

    svg.setAttribute('width', largura);
    svg.setAttribute('height', altura);
    svg.setAttribute('viewBox', `0 0 ${largura} ${altura}`);

    for (const l of ligacoes) {
      const a = l.origem;
      const b = l.destino;

      const ax = a.parentElement.offsetLeft + a.offsetLeft;
      const ay = a.parentElement.offsetTop + a.offsetTop;
      const bx = b.parentElement.offsetLeft + b.offsetLeft;
      const by = b.parentElement.offsetTop + b.offsetTop;

      const paraDireita = bx >= ax;

      const x1 = paraDireita ? ax + a.offsetWidth : ax;
      const x2 = paraDireita ? bx : bx + b.offsetWidth;

      const y1 = ay + a.querySelector('summary').offsetHeight / 2;
      const y2 = by + b.querySelector('summary').offsetHeight / 2;

      const delta = Math.max(28, Math.abs(x2 - x1) * .45);

      const controle1 = x1 + (paraDireita ? delta : -delta);
      const controle2 = x2 + (paraDireita ? -delta : delta);

      l.path.setAttribute(
        'd',
        `M ${x1} ${y1} C ${controle1} ${y1}, ${controle2} ${y2}, ${x2} ${y2}`
      );
    }
  }

  function destacar(codigo) {
    selecionada = codigo;

    const ativo = codigo && porCodigo.get(codigo);

    grade.classList.toggle('com-destaque', Boolean(ativo));

    materias.forEach(m => {
      m.classList.toggle('selecionada', Boolean(ativo && m === ativo));
      m.classList.remove('ligada');
    });

    ligacoes.forEach(l => {
      const ligada = Boolean(
        ativo && (l.origem === ativo || l.destino === ativo)
      );

      l.path.classList.toggle('destacada', ligada);

      if (ligada) {
        l.origem.classList.add('ligada');
        l.destino.classList.add('ligada');
      }
    });

    if (ativo) ativo.classList.remove('ligada');
  }

  materias.forEach(m => {
    m.addEventListener('mouseenter', () => destacar(m.dataset.codigo));
    m.addEventListener('mouseleave', () => destacar(null));
    m.addEventListener('focusin', () => destacar(m.dataset.codigo));

    m.addEventListener('focusout', e => {
      if (!m.contains(e.relatedTarget)) destacar(null);
    });

    m.addEventListener('toggle', () => requestAnimationFrame(desenhar));
  });

  document.querySelectorAll('input[name="zoom"]').forEach(el => {
    el.addEventListener('change', () => requestAnimationFrame(desenhar));
  });

  const form = grade.closest('form');

  if (form) {
    form.addEventListener('reset', () => {
      destacar(null);
      requestAnimationFrame(() => requestAnimationFrame(desenhar));
    });
  }

  window.addEventListener('resize', () => requestAnimationFrame(desenhar));

  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(
      () => requestAnimationFrame(desenhar)
    );

    observer.observe(grade);
    materias.forEach(m => observer.observe(m));
  }

  desenhar();
});
