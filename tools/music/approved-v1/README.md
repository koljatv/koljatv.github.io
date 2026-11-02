> ARCHIVED REVIEW — Rejected on 2026-11-02 at 11:31. The earlier 10:17 approval does not approve this expanded suite. Source and masters are preserved; active media was restored to the previous versions. GarageBand replacement previews require fresh acceptance before expansion or publication.

# Suíte musical KÖLJA TV — direção aprovada

20 composições originais: previsão do tempo de 72s, 14 vinhetas de programação e 5 identificações/transições. A direção de trompa e violas amostradas com baixo/pulso eletrônicos foi aprovada em 02/11/2026.

## Produção reproduzível

Requer Python3 com NumPy, FFmpeg/FFprobe e macOS para o binário portátil sfizz1.2.3 incluído no manifesto de dependências. A biblioteca é fixada por SHA-256; nenhum plugin é instalado no sistema.

```sh
python3 tools/music/approved-v1/prepare_assets.py
python3 tools/music/approved-v1/verify.py --score-only
python3 tools/music/approved-v1/render.py
# Apenas a previsão:
python3 tools/music/approved-v1/render.py --only previsao
```

Saída: `media/trilhas-review/approved-v1/`. Cada peça tem master WAV24/48kHz, AAC192kbps, partitura JSON, MIDI por papel, stems e medidas de masterização. `score.py` define escrita, andamentos, harmonias, expressões CC11, hierarquia e intenção por quadro. `render.py` faz render offline e ganho linear; não usa limiter ou compressor. `prepare_assets.py` verifica oito samples CC0 e o engine. Veja [créditos e licenças](CREDITS.md).

A reprodução dos hashes da entrega exige as mesmas versões dos encoders; a fonte musical e as dependências ficam registradas mesmo se um encoder futuro produzir bytes diferentes.

## Verificação e imagens

```sh
python3 tools/music/approved-v1/verify.py \
  --originals media/ours \
  --forecast-video state/tempo/previsao-tempo.mp4
```

O comando requer os vídeos originais disponíveis localmente. Compara duração e hash dos streams de imagem, faz remux sem recodificação e decodifica integralmente WAV/M4A/MP4. Verifica limites de tempo das notas, cobertura exata dos samples, vozes internas, ausência de valores não finitos/clipping, bordas suaves e pico verdadeiro inferior a −2dBTP. O manifesto de preservação da sessão, quando disponível, também é verificado. `verification-summary.json` registra a entrega original; números não constituem aprovação perceptiva.

## Linguagens e forma

| Peça | BPM | Direção |
|---|---:|---|
| Previsão |100|30 compassos/5seções: chamada aprovada, mapa com respostas espaçadas, desenvolvimento, retorno variado, fechamento. Não é loop estendido.|
| Terror |84|Ré menor, semitom descendente, baixo espaçado, intensidade contida.|
| Cinema mudo |92|Cordas à frente e resposta curta de trompa, sem ragtime caricatural.|
| Desenhos |116|Graus conjuntos e pulso leve, sem pizzicato/xilofone.|
| Ficção |90|Abertura menor, acordes espaçosos, linha rarefeita.|
| Noir |88|Descida em ré menor, anacruse interna, resolução cromática.|
| Cult |94|Arco de cordas sobre mi, poucos ataques e chegada discreta.|
| Séries |108|Chamada descendente e resposta ascendente, pulso regular.|
| Comédia |112|Frase conversada, pausas claras e harmonia luminosa.|
| Clássicos |96|Frase ampla cerimonial, dominante explícita.|
| Aventura |120|Arco triádico ascendente, pulso ativo e chegada firme.|
| Faroeste |92|Frase ampla com repousos e abertura plagal.|
| Seriados |116|Impulso em si menor e conclusão maior.|
| Documentários |86|Cordas contemplativas, resposta de trompa e espaço de leitura.|
| Domingo |98|Densidade intermediária e motivo aparentado à marca.|
| Identificação barras |112|Assinatura breve, ascensão e chegada em ré.|
| Identificação tubo |110|Cordas à frente, resposta descendente suave.|
| Apresenta |120|Quatro notas com resolução breve.|
| Intervalo |104|Chegada na dominante, deixando a frase aberta.|
| Voltamos |116|Resposta ao intervalo com resolução em ré.|

Todos usam 4/4. As peças variam entre −23,54 e −19,81LUFS-I no AAC desta entrega; a diferença acompanha a função de cada quadro. A hierarquia muda nas peças conduzidas por cordas, sem acrescentar timbres caricaturais.

## Integração e reversão

`release-manifest.json` mapeia os 19 vídeos para nomes versionados `*_musica_20261102.mp4`; duração, frames e imagem permanecem iguais aos originais. Publicar em release preservando os arquivos anteriores. A reversão usa os nomes e hashes originais do manifesto, além do histórico Git para o gerador da previsão.

**Previsão:** integrar `previsao.m4a` como `tools/meteo/trilha.m4a` e executar o pipeline meteorológico com dados atuais. O `previsao.mp4` desta pasta é apenas uma referência de revisão com imagens preservadas de uma previsão anterior; não deve ser publicado como previsão vigente. O cache do pipeline deve considerar o hash da trilha.

Os scripts não modificam catálogo, grade, player ou Estúdio e não publicam. A música não altera os créditos Open-Meteo/IBGE presentes nas imagens.
