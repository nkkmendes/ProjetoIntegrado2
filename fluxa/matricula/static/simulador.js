/* Simulador de matrícula: lista lateral de disciplinas/turmas, grade semanal e
   detecção de conflito de horário. Só mexe na tela; quem decide o que vale é o
   servidor (ele confere tudo de novo ao salvar). */
(function () {
  'use strict';

  var dadosEl = document.getElementById('dados-simulador');
  if (!dadosEl) { return; }
  var disciplinas = JSON.parse(dadosEl.textContent);
  var inicial = JSON.parse(document.getElementById('selecao-inicial').textContent);

  var DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
  var PX_HORA = 44;

  var porCodigo = {};
  disciplinas.forEach(function (d) { porCodigo[d.codigo] = d; });

  // Faixa de horas da grade: de 7h às 19h, ampliada se alguma turma sair disso.
  var horaIni = 7, horaFim = 19;
  disciplinas.forEach(function (d) {
    d.turmas.forEach(function (t) {
      t.horarios.forEach(function (h) {
        horaIni = Math.min(horaIni, Math.floor(h.inicio / 60));
        horaFim = Math.max(horaFim, Math.ceil(h.fim / 60));
      });
    });
  });

  // Seleção: código da disciplina -> id da turma.
  var sel = {};
  disciplinas.forEach(function (d) {
    d.turmas.forEach(function (t) {
      if (inicial.indexOf(t.id) !== -1) { sel[d.codigo] = t.id; }
    });
  });

  var aberto = '';
  var foco = '';

  var $lista = document.getElementById('sim-lista');
  var $busca = document.getElementById('sim-busca');
  var $contador = document.getElementById('sim-contador');
  var $nDisc = document.getElementById('sim-n-disc');
  var $nCred = document.getElementById('sim-n-cred');
  var $diasCab = document.getElementById('sim-dias');
  var $corpo = document.getElementById('sim-corpo');
  var $escolhidas = document.getElementById('sim-escolhidas');
  var $semEscolha = document.getElementById('sim-sem-escolha');
  var $campos = document.getElementById('sim-campos');
  var $limpar = document.getElementById('sim-limpar');
  var $salvar = document.getElementById('sim-salvar');

  function el(tag, classe, texto) {
    var e = document.createElement(tag);
    if (classe) { e.className = classe; }
    if (texto !== undefined && texto !== null) { e.textContent = texto; }
    return e;
  }

  function hh(min) {
    var h = Math.floor(min / 60), m = min % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
  }

  function textoHorarios(t) {
    return t.horarios.map(function (h) {
      return DIAS[h.dia] + ' ' + hh(h.inicio) + '–' + hh(h.fim);
    }).join(' · ');
  }

  function turmaEscolhida(d) {
    var id = sel[d.codigo];
    if (id === undefined) { return null; }
    for (var i = 0; i < d.turmas.length; i++) {
      if (d.turmas[i].id === id) { return d.turmas[i]; }
    }
    return null;
  }

  function sobrepoe(a, b) {
    for (var i = 0; i < a.length; i++) {
      for (var j = 0; j < b.length; j++) {
        if (a[i].dia === b[j].dia && a[i].inicio < b[j].fim && b[j].inicio < a[i].fim) {
          return a[i];
        }
      }
    }
    return null;
  }

  // Primeiro choque de uma turma com a grade atual (ignora a própria disciplina,
  // pois escolher outra turma dela substitui a atual).
  function conflitoCom(d, t) {
    var codigos = Object.keys(sel);
    for (var i = 0; i < codigos.length; i++) {
      var outra = porCodigo[codigos[i]];
      if (outra.codigo === d.codigo) { continue; }
      var escolhida = turmaEscolhida(outra);
      if (!escolhida) { continue; }
      var batida = sobrepoe(t.horarios, escolhida.horarios);
      if (batida) {
        return outra.codigo + ' (' + DIAS[batida.dia] + ' ' + hh(batida.inicio) + ')';
      }
    }
    return '';
  }

  // Co-requisitos que ainda precisam entrar na grade junto com esta disciplina.
  function faltandoJuntos(d) {
    return (d.juntos || []).filter(function (c) { return sel[c] === undefined; });
  }

  function escolher(d, t) { sel[d.codigo] = t.id; foco = d.codigo + ':' + t.id; render(); }
  function remover(d) { delete sel[d.codigo]; foco = d.codigo + ':cab'; render(); }

  function desenharLista() {
    var termo = ($busca.value || '').trim().toLowerCase();
    $lista.textContent = '';
    var mostradas = 0;
    disciplinas.forEach(function (d) {
      if (termo && (d.codigo + ' ' + d.nome).toLowerCase().indexOf(termo) === -1) { return; }
      mostradas += 1;
      var escolhida = turmaEscolhida(d);
      var abre = aberto === d.codigo;

      var cab = el('button', 'disc cor-' + d.cor + (escolhida ? ' na-grade' : ''));
      cab.type = 'button';
      cab.setAttribute('aria-expanded', abre ? 'true' : 'false');
      cab.setAttribute('data-foco', d.codigo + ':cab');
      cab.appendChild(el('span', 'cor'));
      var textos = el('span', 'textos');
      textos.appendChild(el('span', 'codigo', d.codigo + ' · ' + d.creditos + ' cr.'));
      textos.appendChild(el('span', '', d.nome));
      textos.appendChild(el('span', 'resumo-disc',
        (escolhida ? 'Na grade: turma ' + escolhida.codigo + ' · ' : '') +
        d.turmas.length + (d.turmas.length === 1 ? ' turma' : ' turmas')));
      if (d.juntos && d.juntos.length) {
        textos.appendChild(el('span', 'resumo-disc', 'Cursar junto com: ' + d.juntos.join(', ')));
      }
      cab.appendChild(textos);
      cab.appendChild(el('span', 'resumo-disc', abre ? '▾' : '▸'));
      cab.addEventListener('click', function () {
        aberto = abre ? '' : d.codigo;
        foco = d.codigo + ':cab';
        render();
      });
      $lista.appendChild(cab);

      if (!abre) { return; }
      d.turmas.forEach(function (t) {
        var naGrade = escolhida && escolhida.id === t.id;
        var choque = naGrade ? '' : conflitoCom(d, t);
        var cartao = el('div', 'turma' + (naGrade ? ' escolhida' : '') + (choque ? ' conflito' : ''));
        var topo = el('div', 'topo');
        topo.appendChild(el('strong', '', 'Turma ' + t.codigo + (naGrade ? ' · na grade' : '')));
        if (t.vagas !== null && t.vagas !== undefined) {
          topo.appendChild(el('span', 'vagas', t.vagas + (t.vagas === 1 ? ' vaga informada' : ' vagas informadas')));
        }
        cartao.appendChild(topo);
        if (t.professor) { cartao.appendChild(el('div', '', t.professor)); }
        cartao.appendChild(el('div', '', t.horarios.length ? textoHorarios(t) : 'Horário não informado'));
        var salas = [];
        t.horarios.forEach(function (h) { if (h.sala && salas.indexOf(h.sala) === -1) { salas.push(h.sala); } });
        if (salas.length) { cartao.appendChild(el('div', 'sala', 'Sala ' + salas.join(', '))); }
        if (choque) { cartao.appendChild(el('div', 'conflita', 'Conflita com ' + choque)); }

        var botao = el('button');
        botao.type = 'button';
        botao.setAttribute('data-foco', d.codigo + ':' + t.id);
        if (naGrade) {
          botao.className = 'remover'; botao.textContent = 'Remover da grade';
          botao.addEventListener('click', function () { remover(d); });
        } else if (choque) {
          botao.className = 'indisponivel'; botao.disabled = true;
          botao.textContent = 'Indisponível: conflito de horário';
        } else {
          botao.className = 'adicionar';
          botao.textContent = escolhida ? 'Trocar para esta turma' : 'Adicionar à grade';
          botao.addEventListener('click', function () { escolher(d, t); });
        }
        cartao.appendChild(botao);
        $lista.appendChild(cartao);
      });
    });
    if (!mostradas) {
      $lista.appendChild(el('p', 'vazio', 'Nenhuma disciplina encontrada.'));
    }
    $contador.textContent = mostradas + (mostradas === 1 ? ' disciplina disponível' : ' disciplinas disponíveis');
  }

  function desenharGrade() {
    var horas = horaFim - horaIni;
    $diasCab.textContent = '';
    DIAS.forEach(function (n) { $diasCab.appendChild(el('span', '', n)); });
    $corpo.textContent = '';
    $corpo.style.height = (horas * PX_HORA) + 'px';
    for (var i = 0; i < horas; i++) {
      var linha = el('div', 'grade-hora');
      linha.style.top = (i * PX_HORA) + 'px';
      $corpo.appendChild(linha);
      var rotulo = el('span', 'grade-hora-rotulo', hh((horaIni + i) * 60));
      rotulo.style.top = (i * PX_HORA - 7) + 'px';
      $corpo.appendChild(rotulo);
    }
    for (var c = 0; c <= 6; c++) {
      var col = el('div', 'grade-coluna');
      col.style.left = (c * 100 / 6) + '%';
      $corpo.appendChild(col);
    }
    Object.keys(sel).forEach(function (codigo) {
      var d = porCodigo[codigo], t = turmaEscolhida(d);
      if (!t) { return; }
      t.horarios.forEach(function (h) {
        var ev = el('div', 'evento cor-' + d.cor);
        ev.style.left = 'calc(' + (h.dia * 100 / 6) + '% + 3px)';
        ev.style.width = 'calc(' + (100 / 6) + '% - 6px)';
        ev.style.top = ((h.inicio - horaIni * 60) * PX_HORA / 60 + 2) + 'px';
        ev.style.height = ((h.fim - h.inicio) * PX_HORA / 60 - 4) + 'px';
        ev.appendChild(el('strong', '', d.codigo));
        ev.appendChild(el('span', '', 'Turma ' + t.codigo));
        if (h.sala) { ev.appendChild(document.createElement('br')); ev.appendChild(el('span', '', h.sala)); }
        $corpo.appendChild(ev);
      });
    });
  }

  function desenharEscolhidas() {
    $escolhidas.textContent = '';
    var codigos = Object.keys(sel).sort();
    var cred = 0;
    var pendencias = 0;
    codigos.forEach(function (codigo) {
      var d = porCodigo[codigo], t = turmaEscolhida(d);
      if (!t) { return; }
      cred += d.creditos;
      var item = el('li', 'escolhida-item cor-' + d.cor);
      var info = el('div', 'info');
      info.appendChild(el('span', 'cor'));
      var txt = el('div');
      txt.appendChild(el('div', 'nome', d.codigo + ' — ' + d.nome + ' · Turma ' + t.codigo));
      txt.appendChild(el('div', 'detalhe', (t.professor ? t.professor + ' · ' : '') + textoHorarios(t)));
      var falta = faltandoJuntos(d);
      if (falta.length) {
        pendencias += 1;
        txt.appendChild(el('div', 'detalhe aviso-corequisito',
          'Exige cursar junto: ' + falta.join(', ') + ' (falta escolher)'));
      }
      info.appendChild(txt);
      item.appendChild(info);
      var b = el('button', 'botao-perigo', 'Remover');
      b.type = 'button';
      b.setAttribute('aria-label', 'Remover ' + d.codigo + ' da grade');
      b.setAttribute('data-foco', d.codigo + ':grade');
      b.addEventListener('click', function () { remover(d); });
      item.appendChild(b);
      $escolhidas.appendChild(item);
    });
    $nDisc.textContent = codigos.length;
    $nCred.textContent = cred;
    $semEscolha.hidden = codigos.length > 0;
    if ($salvar) { $salvar.title = pendencias ? 'Escolha também os co-requisitos pendentes' : ''; }
  }

  function atualizarCampos() {
    $campos.textContent = '';
    Object.keys(sel).forEach(function (codigo) {
      var i = document.createElement('input');
      i.type = 'hidden'; i.name = 'turmas'; i.value = sel[codigo];
      $campos.appendChild(i);
    });
  }

  function render() {
    desenharLista();
    desenharGrade();
    desenharEscolhidas();
    atualizarCampos();
    if (foco) {
      var alvo = document.querySelector('[data-foco="' + foco + '"]');
      if (alvo && !alvo.disabled) { alvo.focus(); }
      foco = '';
    }
  }

  $busca.addEventListener('input', function () { desenharLista(); });
  $limpar.addEventListener('click', function () { sel = {}; render(); });
  render();
})();
