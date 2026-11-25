
document.addEventListener('DOMContentLoaded', async () => {
    const grade = document.querySelector('.grade');
    const svg = grade?.querySelector('svg.setas');

    if (!grade || !svg) return;

    // Comeca sem nenhuma seta
    svg.replaceChildren();
    svg.style.zIndex = '0';
    svg.style.pointerEvents = 'none';
    svg.style.overflow = 'visible';

    // Identifica a disciplina selecionada
    const parametros = new URLSearchParams(window.location.search);

    const foco = (
        parametros.get('foco') || ''
    ).trim().toUpperCase();

    // A visão inicial deve mostrar todos os períodos, não só o trecho à esquerda.
    // Manter o tamanho original, sem alterar a escala ao abrir ou selecionar.
    const quadroCurso = grade.closest('.quadro');
    document.getElementById('ver-curso-completo')?.addEventListener('click', () => {
        if (foco) { window.location.search = ''; return; }
        grade.classList.add('mostrar-todas');
        quadroCurso?.scrollTo({left: 0, top: 0, behavior: 'smooth'});
    });

    const url = document.querySelector(
        'script[data-grafo-url]'
    )?.dataset.grafoUrl || '/fluxograma/grafo/';

    try {
        // Busca os requisitos no Django
        const resposta = await fetch(url, {
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json'
            }
        });

        if (!resposta.ok) {
            throw new Error(
                `Rota do grafo retornou ${resposta.status}`
            );
        }

        const dados = await resposta.json();
        const grafo = dados.grafo || {};

        if (foco && !Object.prototype.hasOwnProperty.call(grafo, foco)) {
            console.warn(
                'Fluxa: disciplina nao encontrada no grafo:',
                foco
            );
            return;
        }

        // Identifica os cartoes pelo codigo da disciplina
        const cartas = new Map();

        grade.querySelectorAll('a.carta').forEach(carta => {
            const codigo = carta.dataset.codigo
                || carta.id.replace(/^c-/, '')
                    .replace(/-P\d+-\d+$/, '');

            if (!codigo) return;

            if (!cartas.has(codigo)) {
                cartas.set(codigo, []);
            }

            cartas.get(codigo).push(carta);
        });

        function periodoDaCarta(carta) {
            const periodo = Number(carta.dataset.periodo);

            if (periodo >= 1 && periodo <= 10) {
                return periodo;
            }

            return Math.round(
                (carta.offsetLeft - 20) / 340
            ) + 1;
        }

        // Algumas optativas aparecem em mais de um periodo
        function escolherCarta(codigo, periodoMaximo = Infinity) {
            const opcoes = cartas.get(codigo) || [];

            if (!opcoes.length) return null;

            const anteriores = opcoes.filter(
                carta => periodoDaCarta(carta) <= periodoMaximo
            );

            const candidatas = anteriores.length
                ? anteriores
                : opcoes;

            return candidatas.reduce((a, b) =>
                periodoDaCarta(b) > periodoDaCarta(a) ? b : a
            );
        }

        // Descobrir exatamente qual cartao foi selecionado
        const periodoSelecionado = Number(
            parametros.get('periodo')
        );

        const alvo = (cartas.get(foco) || []).find(
            carta =>
                periodoSelecionado >= 1
                && periodoDaCarta(carta) === periodoSelecionado
        ) || escolherCarta(foco);

        if (foco && !alvo) {
            console.warn(
                'Fluxa: cartao nao encontrado para',
                foco
            );
            return;
        }

        // Percorrer todos os pre-requisitos:
        // requisitos diretos e requisitos dos requisitos
        const pendentes = foco ? [foco] : [...cartas.keys()];
        const visitados = new Set(pendentes);

        const ligacoes = [];
        const chaves = new Set();

        while (pendentes.length) {
            const atual = pendentes.pop();
            const grupos = grafo[atual] || [];

            for (const requisito of dados.co_requisitos?.[atual] || []) {
                const chave = `co:${requisito}>${atual}`;
                if (requisito !== atual && !chaves.has(chave)) {
                    chaves.add(chave);
                    ligacoes.push({de: requisito, para: atual, co: true});
                }
                if (!visitados.has(requisito)) {
                    visitados.add(requisito);
                    pendentes.push(requisito);
                }
            }

            for (const grupo of grupos) {
                if (!Array.isArray(grupo)) continue;

                for (const requisito of grupo) {
                    if (
                        !Object.prototype.hasOwnProperty.call(
                            grafo, requisito
                        )
                    ) {
                        continue;
                    }

                    if (
                        requisito === atual ||
                        requisito === foco
                    ) {
                        continue;
                    }

                    const chave = `${requisito}>${atual}`;

                    if (!chaves.has(chave)) {
                        chaves.add(chave);

                        ligacoes.push({
                            de: requisito,
                            para: atual,
                            alternativo: grupos.length > 1
                        });
                    }

                    if (!visitados.has(requisito)) {
                        visitados.add(requisito);
                        pendentes.push(requisito);
                    }
                }
            }
        }

        // Destacar todas as disciplinas da cadeia
        visitados.forEach(codigo => {
            if (!foco) return;
            (cartas.get(codigo) || []).forEach(carta => {
                carta.classList.add(
                    codigo === foco ? 'alvo' : 'cadeia'
                );
            });
        });

        // Criar elementos SVG
        const namespace = 'http://www.w3.org/2000/svg';

        function elemento(tag, atributos) {
            const el = document.createElementNS(
                namespace, tag
            );

            Object.entries(atributos).forEach(
                ([chave, valor]) => {
                    el.setAttribute(chave, String(valor));
                }
            );

            return el;
        }

        // Criar as pontas das setas
        const defs = elemento('defs', {});

        for (const [id, cor] of [
            ['ponta-pre-fluxa', '#7d8ca3'],
            ['ponta-co-fluxa', '#4679ef']
        ]) {
            const marcador = elemento('marker', {
                id: id,
                viewBox: '0 0 10 10',
                refX: 9,
                refY: 5,
                markerWidth: 7,
                markerHeight: 7,
                orient: 'auto'
            });

            marcador.appendChild(
                elemento('path', {
                    d: 'M0 0 L10 5 L0 10 z',
                    style: `fill:${cor};stroke:none`
                })
            );

            defs.appendChild(marcador);
        }

        svg.appendChild(defs);

        // Desenhar uma seta entre duas disciplinas
        function desenhar(
            origem,
            destino,
            cor,
            marcador,
            tracejada = false
        ) {
            if (
                !origem ||
                !destino ||
                origem === destino
            ) {
                return;
            }

            const x1 =
                origem.offsetLeft + origem.offsetWidth;

            const y1 =
                origem.offsetTop + origem.offsetHeight / 2;

            const x2 = destino.offsetLeft - 4;

            const y2 =
                destino.offsetTop + destino.offsetHeight / 2;

            let caminho;

            if (x2 > x1 + 20) {
                const meio = (x1 + x2) / 2;

                caminho =
                    `M${x1},${y1} ` +
                    `C${meio},${y1} ` +
                    `${meio},${y2} ${x2},${y2}`;
            } else {
                const xFim = destino.offsetLeft + destino.offsetWidth + 4;
                const desvio = Math.max(x1, xFim) + 55;

                caminho =
                    `M${x1},${y1} ` +
                    `C${desvio},${y1} ` +
                    `${desvio},${y2} ${xFim},${y2}`;
            }

            const linha = elemento('path', {
                d: caminho,
                style: (
                    `fill:none;stroke:${cor};stroke-width:2.3`
                ),
                'marker-end': `url(#${marcador})`
            });

            if (tracejada) {
                linha.setAttribute(
                    'stroke-dasharray', '7 5'
                );
            }

            svg.appendChild(linha);
        }

        // Setas dos pre-requisitos diretos e indiretos
        for (const ligacao of ligacoes) {
            const destino = ligacao.para === foco
                ? alvo
                : escolherCarta(ligacao.para);

            const origem = escolherCarta(
                ligacao.de,
                destino
                    ? periodoDaCarta(destino)
                    : Infinity
            );

            desenhar(
                origem,
                destino,
                ligacao.co ? '#4679ef' : '#7d8ca3',
                ligacao.co ? 'ponta-co-fluxa' : 'ponta-pre-fluxa',
                ligacao.co || ligacao.alternativo
            );
        }

        console.info(
            `Fluxa: ${ligacoes.length} conexoes encontradas para ${foco}`
        );

        document.getElementById('ver-cadeia-completa')?.addEventListener('click', () => {
            grade.classList.remove('mostrar-todas');
            quadroCurso?.scrollTo({left: 0, top: 0, behavior: 'smooth'});
        });

        if (dados.faltantes?.[foco]?.length) {
            console.warn(
                'Requisitos nao presentes na grade:',
                dados.faltantes[foco]
            );
        }

    } catch (erro) {
        console.error(
            'Fluxa: nao foi possivel desenhar as setas.',
            erro
        );
    }
});
