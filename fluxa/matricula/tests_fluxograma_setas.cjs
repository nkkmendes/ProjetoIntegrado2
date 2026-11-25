const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

async function desenhar(search) {
  const elemento = () => ({children: [], style: {}, attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(el) { this.children.push(el); },
    replaceChildren() { this.children = []; }});
  const svg = elemento();
  const cartas = ['AAA1000', 'BBB1000', 'CCC1000', 'DDD1000', 'EEE1000', 'FFF1000'].map((codigo, i) => ({
    dataset: {codigo, periodo: String(i + 1)}, offsetLeft: 20 + i * 340,
    offsetTop: 78, offsetWidth: 230, offsetHeight: 88, classList: {add() {}},
  }));
  const grade = {querySelector: () => svg, querySelectorAll: () => cartas,
    closest: () => ({scrollTo() {}}), classList: {add() {}, remove() {}}};
  let carregar;
  const document = {
    addEventListener(_nome, fn) { carregar = fn; },
    querySelector: s => s === '.grade' ? grade : {dataset: {grafoUrl: '/grafo'}},
    getElementById: () => null, createElementNS: () => elemento(),
  };
  const dados = {
    grafo: {AAA1000: [], BBB1000: [['AAA1000']], CCC1000: [['BBB1000']],
      DDD1000: [], EEE1000: [], FFF1000: [['EEE1000']]},
    co_requisitos: {BBB1000: ['DDD1000']},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/fluxograma_setas.js'), 'utf8'), {
    document, window: {location: {search}}, URLSearchParams,
    fetch: async () => ({ok: true, json: async () => dados}),
    console: {info() {}, warn() {}, error(e) { throw e; }},
  });
  await carregar();
  return svg.children.filter(e => e.attrs.d);
}

test('sem seleção desenha todas as ligações visíveis', async () => {
  const linhas = await desenhar('');
  assert.equal(linhas.length, 4);
  assert.equal(linhas.filter(l => l.attrs['stroke-dasharray']).length, 1);
});

test('seleção inclui requisitos indiretos e correquisitos da cadeia', async () => {
  const linhas = await desenhar('?foco=CCC1000&periodo=3');
  assert.equal(linhas.length, 3);
  assert.ok(linhas.every(l => l.attrs.d.includes('C')));
});
