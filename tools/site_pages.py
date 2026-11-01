#!/usr/bin/env python3
"""Writes the KÖLJA TV site's pages (public/**/index.html) from one header, one footer and each page's body.
The grade, the player and the subtitles stay where they are; the pages only read them (assets/site.js, tv/tv.js).
usage: python3 tools/site_pages.py"""
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public')
V = '5'  # bump when assets/site.css, assets/site.js or tv/tv.js change
SITE = 'https://tv.kolja.com.br/'
MAIL = 'contato@kolja.com.br'

NAV = [('', 'Início'), ('programacao/', 'Programação'), ('ao-vivo/', 'Ao vivo'), ('emissora/', 'A emissora'), ('anuncie/', 'Anuncie'), ('retrotv/', 'Retrotv')]


def head(path, title, desc, base):
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="KÖLJA TV">
<meta property="og:locale" content="pt_BR">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}img/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b0a09">
<link rel="icon" href="{base}img/tv.svg" type="image/svg+xml">
<link rel="preload" href="{base}fonts/jost.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{base}fonts/barlowc-700.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{base}tv/tv.css?v={V}">
<link rel="stylesheet" href="{base}assets/site.css?v={V}">
</head>'''


def top(path, base):
    links = ''.join(f'<a href="{base}{p}"{" aria-current=page" if p == path else ""}>{n}</a>' for p, n in NAV if p != 'ao-vivo/')
    sheet = ''.join(f'<a href="{base}{p}"{" aria-current=page" if p == path else ""}>{n}</a>' for p, n in NAV)
    return f'''<a class="skip" href="#main">Pular para o conteúdo</a>
<header class="top"><div class="wrap">
  <a class="logo" href="{base}" aria-label="KÖLJA TV, início"><img src="{base}img/logo.svg" alt="KÖLJA TV" width="128" height="54"></a>
  <nav aria-label="Principal">{links}</nav>
  <a class="onair" href="{base}ao-vivo/"{" aria-current=page" if path == 'ao-vivo/' else ""}><span class="dot"></span>AO VIVO</a>
  <button class="menu" type="button" aria-label="Menu" aria-expanded="false" aria-controls="sheet"><svg viewBox="0 0 24 24"><path class="b" d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/><path class="x" d="M5.6 4.2 12 10.6l6.4-6.4 1.4 1.4-6.4 6.4 6.4 6.4-1.4 1.4-6.4-6.4-6.4 6.4-1.4-1.4 6.4-6.4-6.4-6.4z"/></svg></button>
</div></header>
<div class="sheet" id="sheet">{sheet}<p>Horário de Brasília. A grade se atualiza sozinha.</p></div>'''


def ticker(base):
    return f'<div class="ticker" id="ticker" hidden><div class="wrap"><a href="{base}ao-vivo/"></a></div></div>'


def foot(base):
    return f'''<footer class="foot"><div class="wrap">
  <div class="cols">
    <div class="brand"><img src="{base}img/logo.svg" alt="KÖLJA TV" width="142" height="60"><p>Clássicos do cinema, desenhos, seriados e madrugada de terror. No ar 24 horas, no horário de Brasília.</p></div>
    <div><h2>Assistir</h2><ul><li><a href="{base}ao-vivo/">Ao vivo</a></li><li><a href="{base}programacao/">Programação</a></li><li><a href="{base}retrotv/">Retrotv</a></li></ul></div>
    <div><h2>A emissora</h2><ul><li><a href="{base}emissora/">Sobre a KÖLJA TV</a></li><li><a href="{base}anuncie/">Anuncie</a></li><li><a href="mailto:{MAIL}">Contato</a></li></ul></div>
    <div><h2>Kölja</h2><ul><li><a href="https://kolja.com.br/">kolja.com.br</a></li><li><a href="https://kolja.com.br/store/">Loja</a></li></ul></div>
  </div>
  <div class="fine"><span>© 2026 Kölja</span><span>KÖLJA TV · Canal 1</span></div>
</div></footer>'''


def page(path, title, desc, body, has_ticker=True, player=False, name=''):
    base = '../' * path.count('/')
    scripts = (f'<script src="{base}tv/tv.js?v={V}"></script>\n' if player else '') + f'<script src="{base}assets/site.js?v={V}"></script>'
    html = f'''{head(path, title, desc, base)}
<body data-base="{base}" data-page="{name}">
{top(path, base)}
{ticker(base) if has_ticker else ''}
<main id="main">
{body.replace('{B}', base).replace('{MAIL}', MAIL)}
</main>
{foot(base)}
{scripts}
</body>
</html>
'''
    out = os.path.join(ROOT, path, 'index.html') if path else os.path.join(ROOT, 'index.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w').write(html)
    print('wrote', os.path.relpath(out, ROOT))


LIVE = '''<section class="live-hero%s"><div class="wrap grid">
  <div class="player"><div id="ktv" data-base="{B}"></div></div>
  <div class="side">
    <section class="ktv-info" id="ktv-info" aria-live="polite"></section>
    <div class="upnext" id="upnext"></div>
    %s
  </div>
</div></section>'''

HOME = (LIVE % ('', '<div class="acts"><a class="btn" href="{B}programacao/">Programação de hoje</a><a class="btn ghost" href="{B}ao-vivo/">Abrir o ao vivo</a></div>')) + '''
<section class="band" id="tonightbox" hidden><div class="wrap">
  <div class="h-sec"><h2 id="tonighth">Hoje à noite</h2><a href="{B}programacao/?faixa=3">A noite toda</a></div>
  <div id="tonight"></div>
</div></section>
<section class="band"><div class="wrap">
  <div class="h-sec"><h2>Hoje na KÖLJA TV</h2><a href="{B}programacao/">Grade completa</a></div>
  <div class="parts" id="parts"></div>
</div></section>
<section class="band"><div class="wrap">
  <div class="h-sec"><h2>Os filmes de hoje</h2><a href="{B}programacao/">Programação</a></div>
  <div class="rail r4" id="films"></div>
</div></section>
<section class="promo" id="novela" data-until="2026-11-15" hidden><div class="wrap">
  <div>
    <div class="kicker">Novela da casa · Prévia do capítulo 1</div>
    <h2>Segredos da Serra</h2>
    <p>Noite de tempestade na mansão dos Albuquerque, no alto da serra de Petrópolis. Três da manhã, a geladeira aberta, e comendo o pudim da família está um homem que foi enterrado há cinco anos.</p>
    <p>A prévia passa nos intervalos dos filmes da noite e da madrugada. Ou assista aqui.</p>
    <div class="fine">Nos intervalos até 15 de novembro</div>
  </div>
  <div class="media"><img src="{B}img/novela-escada.jpg" alt="Segredos da Serra: Rodrigo, de roupão vinho, no alto da escada da mansão" loading="lazy"><button type="button" aria-label="Assistir à prévia de Segredos da Serra"><i></i></button></div>
</div></section>
<section class="band" id="legbox" hidden><div class="wrap">
  <div class="h-sec"><h2>Com legenda em português</h2><a href="{B}programacao/?leg=1">Todos com LEG</a></div>
  <p style="color:var(--fg2);margin:-6px 0 22px;max-width:60ch">As legendas são feitas aqui, em português e em inglês. Na grade, esses filmes aparecem com o selo <span class="badge leg">LEG</span>.</p>
  <div class="rail r4" id="legrail"></div>
</div></section>
<section class="band"><div class="wrap duo">
  <a class="tease" href="{B}retrotv/"><div><div class="kicker">Retrotv</div><h3>A KÖLJA TV também cabe no bolso</h3><p>O nosso aplicativo de TV para Android, com a KÖLJA TV no canal 1. Ainda não está disponível para download.</p><span class="btn ghost">Conhecer</span></div><img src="{B}img/retrotv.jpg" alt="A Retrotv no celular, passando um filme com legenda" loading="lazy" width="120" height="267"></a>
  <a class="tease" href="{B}anuncie/"><div><div class="kicker">Anuncie</div><h3>Seu comercial no intervalo dos clássicos</h3><p>Os filmes têm intervalo, como na TV aberta. Conte o que você quer anunciar e a gente combina.</p><span class="btn ghost">Como funciona</span></div></a>
</div></section>'''

AOVIVO = (LIVE % (' big', '<p style="color:var(--fg3);font-size:15px;margin-top:22px;max-width:48ch">Legendas: o botão <b style="color:var(--fg)">PT</b> no player troca para EN ou desliga. Os filmes com legenda têm o selo <span class="badge leg">LEG</span>. Dois toques na imagem abrem a tela cheia.</p>')) + '''
<section class="band"><div class="wrap">
  <div class="h-sec"><h2>Ainda hoje</h2><a href="{B}programacao/">Programação completa</a></div>
  <div class="grade" id="hoje"></div>
</div></section>'''

PROG = '''<div class="wrap page-head"><div class="kicker">Horário de Brasília</div><h1>Programação</h1>
  <p>A grade da KÖLJA TV para hoje e os próximos dias. Escolha um programa para ver a sinopse e quando ele passa de novo.</p></div>
<div class="filters"><div class="wrap"><div class="chips days" id="days" role="group" aria-label="Dia"></div><div class="chips" id="faixas" role="group" aria-label="Faixa do dia e legenda"></div></div></div>
<div class="wrap"><div class="grade" id="grade" aria-live="polite"><p class="empty">Carregando a grade…</p></div></div>'''

TITULO = '<div id="titulo"><div class="wrap page-head"><p class="empty">Carregando…</p></div></div>'

MOSAIC = ''.join(f'<img src="{{B}}arte/{i}.jpg" alt="" loading="lazy">' for i in
                 ['nosferatu-1922', 'caligari-1920', 'phantom-opera-1925', 'jekyll-1920', 'hunchback-1923', 'the-sea-beast-1926', 'the-virginian-1929', 'notld-1968'])
EMISSORA = f'''<section class="inst-hero"><div class="mosaic" aria-hidden="true">{MOSAIC}</div><div class="wrap">
  <div class="kicker">A emissora</div><h1>Uma TV de verdade, no ar o dia inteiro.</h1>
  <p>A KÖLJA TV tem grade, horário e intervalo. Ligou, pegou o que está no ar, na mesma hora que todo mundo.</p>
</div></section>
<section class="band"><div class="wrap two">
  <div class="prose"><h2>O que passa</h2>
    <p>De manhã até o começo da tarde, desenhos clássicos. À tarde vem a matinê, com comédia muda, seriados, comédia e faroeste. À noite, os grandes filmes, aventura e depois o noir. De madrugada tem Sessão Terror, ficção científica, a Madrugada Cult e as séries clássicas.</p>
    <p>É um canal só, o canal 1. Não tem catálogo para escolher nem botão de voltar: o filme começa na hora marcada, e se você chegou no meio, pegou do meio. Por isso a grade importa, e ela está sempre na <a href="{{B}}programacao/">Programação</a>.</p>
    <p>No ar desde 31 de outubro de 2026.</p></div>
  <div><div class="h-sec"><h2>Hoje, hora a hora</h2></div><ul class="schedule-key" id="daymap"></ul></div>
</div></section>
<section class="band"><div class="wrap two">
  <div class="prose"><h2>Legendas feitas aqui</h2>
    <p>Parte dos filmes tem legenda em português e em inglês, feita por nós, e estamos fazendo mais. Na programação esses filmes levam o selo <span class="badge leg">LEG</span>. No player, o botão PT troca para EN ou desliga.</p></div>
  <div class="prose"><h2>Onde assistir</h2>
    <p>Aqui no site, no <a href="{{B}}ao-vivo/">Ao vivo</a>, em qualquer navegador, no celular ou no computador. A KÖLJA TV também é o canal 1 da <a href="{{B}}retrotv/">Retrotv</a>, o nosso aplicativo de TV para Android, que ainda não está disponível para download.</p></div>
</div></section>
<section class="band"><div class="wrap">
  <div class="h-sec"><h2>As vinhetas</h2></div>
  <p style="color:var(--fg2);max-width:60ch;margin:-6px 0 22px">Cada faixa tem a sua vinheta, e todas são feitas pela casa.</p>
  <div class="idents">{''.join(f'<img src="{{B}}img/vinheta-{v}.jpg" alt="Vinheta {n}" loading="lazy">' for v, n in [('classicos', 'Grandes Clássicos'), ('noir', 'Noir'), ('terror', 'Sessão Terror'), ('ficcao', 'Ficção Científica')])}</div>
</div></section>
<section class="band"><div class="wrap prose">
  <h2>Contato</h2><p>Sugestão de filme, problema no player, imprensa ou qualquer outro assunto:</p>
  <a class="mail" href="mailto:{{MAIL}}">{{MAIL}}</a>
</div></section>'''

ANUNCIE = '''<section class="inst-hero"><div class="mosaic" aria-hidden="true"><img src="{B}arte/the-virginian-1929.jpg" alt=""><img src="{B}arte/caligari-1920.jpg" alt=""><img src="{B}arte/the-sea-beast-1926.jpg" alt=""><img src="{B}arte/phantom-opera-1925.jpg" alt=""></div><div class="wrap">
  <div class="kicker">Anuncie</div><h1>Seu comercial no intervalo dos clássicos.</h1>
  <p>Os filmes da KÖLJA TV têm intervalo, como na TV aberta. É ali que entra o seu comercial, para quem estiver assistindo naquela hora.</p>
</div></section>
<section class="band"><div class="wrap">
  <div class="h-sec"><h2>Como funciona</h2></div>
  <ol class="steps">
    <li><b>Conte o que quer anunciar</b><p>Mande um e-mail com o produto, o vídeo (ou a ideia dele) e o período em que você quer aparecer.</p></li>
    <li><b>Escolha as faixas</b><p>Os filmes da noite, o Noir, a Sessão Terror, a matinê: você diz em quais faixas o comercial entra e quantas vezes por dia.</p></li>
    <li><b>Vai ao ar</b><p>O comercial passa nos intervalos dos filmes, nunca em dois intervalos seguidos, e sai do ar sozinho no último dia combinado.</p></li>
  </ol>
</div></section>
<section class="band"><div class="wrap prose">
  <h2>Preço e formato</h2><p>A gente combina por e-mail, de acordo com as faixas e o período. Escreva para:</p>
  <a class="mail" href="mailto:{MAIL}?subject=Anunciar%20na%20K%C3%96LJA%20TV">{MAIL}</a>
</div></section>'''

RETROTV = '''<section class="band"><div class="wrap two top-align">
  <div class="prose">
    <div class="kicker" style="margin-bottom:14px">Retrotv</div>
    <h1 style="font-size:clamp(40px,6.4vw,84px);line-height:.95;letter-spacing:-.03em;margin:0 0 22px">A KÖLJA TV também cabe no bolso.</h1>
    <p>A Retrotv é o nosso aplicativo de TV para Android. Ela tem cara de televisor, com botão de ligar, volume, seletor de canal e tela cheia. E a KÖLJA TV está no canal 1.</p>
    <p>No app a grade é a mesma do site, na mesma hora. As legendas também estão lá, e o botão MENU liga e desliga.</p>
    <p><strong>A Retrotv ainda não está disponível para download.</strong> Enquanto isso, a KÖLJA TV passa inteira aqui no site.</p>
    <p style="margin-top:26px"><a class="btn" href="{B}ao-vivo/" style="text-decoration:none">Assistir ao vivo</a></p>
  </div>
  <div style="display:grid;place-items:center"><img class="phone-shot" src="{B}img/retrotv.jpg" alt="A Retrotv no celular: o televisor desenhado no app, sintonizado no canal 1, KÖLJA TV, passando um filme com legenda em português" width="540" height="1200"></div>
</div></section>'''

NOTFOUND = '''<div class="wrap page-head" style="padding-bottom:96px"><div class="kicker">Fora do ar</div><h1>Esta página saiu da grade.</h1>
  <p>Mas o canal continua no ar. <a href="/">Volte para o início</a>, veja a <a href="/programacao/">programação</a> ou vá direto para o <a href="/ao-vivo/">ao vivo</a>.</p></div>'''

DESC = 'KÖLJA TV ao vivo: clássicos do cinema, desenhos, seriados e madrugada de terror, 24 horas por dia. Assista no site ou na Retrotv.'
page('', 'KÖLJA TV · Canal 1 · Ao vivo 24 horas', DESC, HOME, has_ticker=False, player=True, name='home')
page('ao-vivo/', 'Ao vivo · KÖLJA TV', 'Assista à KÖLJA TV ao vivo: o que está passando agora, com legenda em português nos filmes marcados com LEG.', AOVIVO, has_ticker=False, player=True, name='aovivo')
page('programacao/', 'Programação · KÖLJA TV', 'A grade da KÖLJA TV para hoje e os próximos dias, no horário de Brasília: desenhos, matinê, os grandes filmes e a madrugada.', PROG, name='programacao')
page('programa/', 'Programa · KÖLJA TV', 'Sinopse, ficha e horários deste programa na KÖLJA TV.', TITULO, name='programa')
page('emissora/', 'A emissora · KÖLJA TV', 'A KÖLJA TV é um canal linear, no ar 24 horas: desenhos de manhã, matinê à tarde, os grandes filmes à noite e terror de madrugada.', EMISSORA, name='emissora')
page('anuncie/', 'Anuncie · KÖLJA TV', 'Coloque o seu comercial nos intervalos dos filmes da KÖLJA TV. Fale com a gente por e-mail.', ANUNCIE, name='anuncie')
page('retrotv/', 'Retrotv · KÖLJA TV', 'A Retrotv é o aplicativo de TV da Kölja para Android, com a KÖLJA TV no canal 1.', RETROTV, name='retrotv')
# GitHub Pages serves /404.html for any missing page: absolute links there
html = None
base404 = '/'
p = os.path.join(ROOT, '404.html')
page('__404__/', 'Fora do ar · KÖLJA TV', 'Esta página não existe.', NOTFOUND, name='404')
src = os.path.join(ROOT, '__404__', 'index.html')
open(p, 'w').write(open(src).read().replace('"../', '"/'))
os.remove(src); os.rmdir(os.path.dirname(src))
print('wrote 404.html')
