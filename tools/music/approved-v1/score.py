"""Original written scores for approved KÖLJA ensemble, no GM/rejected score reuse."""
CHORDS = {
 'D':(38,[54,57,62]), 'G':(43,[55,59,62]), 'A7':(45,[55,57,61]),
 'Asus':(45,[55,57,62]), 'Bm':(47,[54,57,62]), 'Em7':(40,[55,59,62]),
 'Dm7':(38,[57,60,62]), 'Gm':(43,[55,58,62]),
 'C':(36,[55,60]), 'F':(41,[57,60]), 'Bb':(34,[58,62]),
}
# Chord thirds omitted by the deliberately limited viola range are supplied by horn.
# Every pitch stays within the same official SFZ regions used by the approved preview.
def chord_events(names, beats, end, velocity=55):
 out=[]
 for i,(name,start) in enumerate(zip(names,beats)):
  stop=beats[i+1] if i+1<len(beats) else end
  root,voices=CHORDS[name]
  out.append([start,stop-start-.16,voices,velocity,name,root])
 return out

def make(name,duration,bpm,lufs,harmony,melody,role,intensity,description,pulse_stride=1):
 end=min(8.0,(duration-1.0-.08)*bpm/60)
 # Two bars with harmonic rhythm 2+2+2+2 and deliberately early final arrival.
 starts=[0,2,4,6]
 if end<=6.3: starts=[0,1.5,3,4.5]
 scale=starts[-1]/6
 notes=[[b*scale,d*scale,n,v] for b,d,n,v in melody]
 harmonies=chord_events(harmony,starts,end,52 if intensity<.7 else 57)
 bass=[]; pulse=[]
 for b in range(int(end)):
  root=CHORDS[harmony[max(i for i,x in enumerate(starts) if b>=x)]][0]
  if b<starts[-1]+.5 and (intensity>.5 or b%2==0):
   bass.append([b,.48 if b<starts[-1] else .85,root,[74,52,62,50][b%4]])
  if b<starts[-1] and b%pulse_stride==0:
   pulse.append([b,.14,0,[55,30,42,30][b%4]])
 if role=='strings':
  # Horn is an answering voice; bowed ensemble has the foreground.
  notes=notes[-3:]
 return {'name':name,'duration':duration,'bpm':bpm,'meter':'4/4','lufs_target':lufs,
  'role':role,'intensity':intensity,'description':description,'horn':notes,
  'harmonies':harmonies,'strings':[[b,d,n,v] for b,d,ns,v,_,_ in harmonies for n in ns],
  'bass':bass,'pulse':pulse,'sections':[[0,end,'frase e chegada']],
  'expression':{'horn':[[0,82],[1,100],[3,86],[4,95],[6,92],[end,66]],
                'strings':[[0,72],[1.3,87],[3.8,76],[5.5,85],[end,64]]}}

# Event tuple: beat, duration in beats, C4=60 MIDI pitch, velocity.
PROFILES=[
 ('terror',7,84,-23,['Dm7','Gm','A7','Dm7'],[(0,1.5,65,69),(2,.7,64,67),(3,.6,61,70),(4,1.6,64,72),(6,1.7,65,68)],'horn',.45,'Ré menor: semitom descendente e dominante contida; baixo em mínimas, sem impacto ou ruído de susto.',2),
 ('muda',7,92,-22.5,['D','Bm','Asus','D'],[(0,.8,62,70),(1,.6,66,72),(2,1.5,69,73),(4,1.4,64,69),(6,1.5,66,68)],'strings',.55,'Cordas em primeiro plano, arco ascendente sustentado e resposta curta de trompa; sem ragtime caricatural.',2),
 ('desenhos',6.4,116,-20.5,['D','G','A7','D'],[(0,.65,66,79),(1,.65,67,78),(2,.65,69,81),(3,.6,67,76),(4,.8,64,75),(5,.55,61,74),(6,1.4,62,76)],'horn',.88,'Energia leve em graus conjuntos; resposta descendente, sem xilofone, pizzicato ou saltos cômicos.',1),
 ('ficcao',7,90,-23,['Bm','Em7','Asus','D'],[(0,1.7,66,72),(2,1.6,67,70),(4,1.5,64,72),(6,1.6,62,69)],'strings',.48,'Abertura em si menor, intervalos largos na harmonia e frase rarefeita; pulso a cada dois tempos.',2),
 ('noir',7,88,-23,['Dm7','Gm','A7','Dm7'],[(.5,1.2,69,73),(2,1.2,67,71),(3.5,.4,65,69),(4,1.5,61,74),(6,1.6,62,70)],'horn',.52,'Linha descendente em ré menor, anacruse interna e resolução cromática; sem simulação de sax/escovas.',2),
 ('cult',7,94,-23.5,['Em7','G','Asus','D'],[(0,1.6,64,68),(2,1.5,67,70),(4,1.3,69,71),(6,1.6,66,68)],'strings',.42,'Harmonia aberta sobre mi, arco de cordas e resposta suspensa; poucos ataques, resolução maior discreta.',2),
 ('series',7,108,-21,['D','Bm','A7','D'],[(0,.8,69,77),(1,.7,66,75),(2,1.4,62,73),(4,.8,64,75),(5,.6,61,74),(6,1.5,62,76)],'horn',.8,'Chamada descendente e resposta ascendente; pulso regular, chegada firme para a faixa de séries.',1),
 ('comedia',7,112,-21.5,['G','D','A7','D'],[(0,.65,67,75),(1,.7,66,73),(2,1.3,62,72),(4,.65,64,74),(5,.65,66,75),(6,1.4,62,72)],'horn',.74,'Frase conversada em registro médio com pausas claras; luminosidade harmônica sem instrumento caricatural.',1),
 ('classicos',7,96,-20.5,['D','G','A7','D'],[(0,1.6,62,76),(2,1.5,67,79),(4,.85,64,77),(5,.65,61,78),(6,1.6,66,76)],'horn',.92,'Frase ampla e cerimonial, abertura em ré e preparação dominante explícita; cordas sustentam três vozes.',1),
 ('aventura',7,120,-19.8,['D','Bm','A7','D'],[(0,.7,62,82),(1,.65,66,80),(2,.65,69,84),(3,.65,66,79),(4,.7,64,78),(5,.65,61,80),(6,1.6,62,81)],'horn',1,'Movimento ascendente triádico com resposta em graus conjuntos; pulso mais ativo e cadência nítida.',1),
 ('faroeste',7,92,-21.5,['G','D','Asus','D'],[(0,1.5,67,76),(2,.8,66,74),(3,.65,62,72),(4,1.5,64,74),(6,1.6,62,73)],'horn',.68,'Horizonte amplo, repousos longos e resposta plagal inicial; sem clichê de banjo ou assobio.',2),
 ('seriados',7,116,-20.2,['Bm','G','A7','D'],[(0,.7,66,79),(1,.65,69,81),(2,.7,67,78),(3,.65,62,75),(4,.8,64,78),(5,.65,61,79),(6,1.5,62,78)],'horn',.95,'Impulso de aventura seriada em si menor com conclusão maior; contorno em zigue-zague controlado.',1),
 ('docs',7,86,-23,['G','Em7','Asus','D'],[(0,1.7,67,69),(2,1.6,64,68),(4,1.5,62,70),(6,1.5,66,68)],'strings',.4,'Cordas contemplativas, trompa em resposta; espaço para título e chegada luminosa sem grandiloquência.',2),
 ('domingo',7,98,-21.8,['D','G','Asus','D'],[(0,1.2,66,74),(1.5,.4,69,73),(2,1.5,67,72),(4,1.5,64,71),(6,1.6,62,70)],'horn',.65,'Acolhimento diurno, motivo aparentado à marca e harmonia suspensa; densidade intermediária.',2),
]

def forecast():
 s=make('previsao',72,100,-22.5,['D','G','A7','D'],[], 'horn',.6,'30 compassos: chamada, mapa, desenvolvimento, retorno e fechamento.',1)
 names=['D','G','Asus','D','Bm','G','D','A7','Em7','G','Asus','D','G','D','Em7','A7','Bm','G','Em7','A7','D','G','D','A7','Bm','G','Em7','Asus','A7','D']
 harmonies=[]
 for i,name in enumerate(names):
  v=55 if i<4 or 20<=i<24 else 48
  harmonies+=chord_events([name],[i*4],i*4+(3.1 if i==29 else 4),v)
 # At bar3 the suspended dominant resolves on beats3–4, as in the approved motif.
 harmonies[2]=[8,1.7,[55,57,62],53,'Asus',45]
 harmonies.insert(3,[10,1.7,[55,57,61],55,'A7',45])
 horn=[(0,1.4,66,80),(1.5,.42,69,78),(2,.9,64,75),(3,.72,62,70),
  (4,1.4,67,75),(5.5,.42,66,73),(6,.9,64,71),(7,.7,62,68),
  (8,1.7,64,73),(10,1.7,61,76),(12,2.45,62,72),
  (20,1.5,67,68),(22,1.5,66,67),(28,1.7,64,69),(30,1.5,61,70),
  (36,2.4,67,68),(40,1.7,64,69),(44,2.5,62,67),
  (48,1.5,67,72),(50,1.5,69,74),(52,1.5,66,71),(54,1.5,62,69),
  (56,2.5,64,71),(60,1.5,64,72),(62,1.5,61,73),
  (68,1.4,67,70),(70,1.4,66,68),(72,2.4,64,69),(76,2.3,61,72),
  (80,1.4,66,76),(81.5,.42,69,74),(82,.9,64,73),(83,.72,62,70),
  (84,1.4,67,73),(86,1.4,66,71),(88,2.4,62,70),(92,1.5,64,72),(94,1.5,61,73),
  (100,2.4,67,69),(104,2.4,64,68),(108,2.6,62,69),(112,1.5,64,71),(114,1.5,61,73),(116,2.5,62,70)]
 bass=[];pulse=[]
 for b in range(118):
  root=CHORDS[names[b//4]][0]
  if b<16 or 48<=b<64 or 80<=b<96 or b%2==0:
   bass.append([b,.48 if b<116 else .85,root,[73,51,62,49][b%4]])
  if b<116 and (b<12 or 48<=b<64 or 80<=b<96 or b%2==0):
   pulse.append([b,.14,0,[54,28,40,28][b%4]])
 s.update(horn=horn,harmonies=harmonies,strings=[[b,d,n,v] for b,d,ns,v,_,_ in harmonies for n in ns],bass=bass,pulse=pulse,
  sections=[[0,16,'chamada aprovada e chegada'],[16,48,'mapa: respiro e respostas espaçadas'],[48,80,'desenvolvimento em arcos'],[80,104,'retorno variado'],[104,120,'fechamento e espaço de leitura']],
  expression={'horn':[[0,92],[1,104],[4,88],[7.8,78],[10,91],[12,92],[15,70],[16,67],[47,72],[48,84],[63,89],[64,74],[79,82],[80,91],[95,78],[104,71],[114,86],[116,80],[119,58]],
  'strings':[[0,70],[1,82],[12,76],[16,63],[47,66],[48,76],[63,82],[64,69],[80,78],[96,67],[112,72],[116,73],[119,54]]})
 return s

def scores():
 result=[forecast()]
 for row in PROFILES:
  n,d,b,l,h,m,r,i,desc,stride=row
  result.append(make('vinheta_'+n,d,b,l,h,m,r,i,desc,stride))
 for args in [
  ('ident_barras',5.8,112,-21,['D','G','A7','D'],[(0,.6,66,77),(1,.5,69,76),(2,1.2,67,74),(4,.7,64,75),(5,.5,61,74),(6,1.3,62,75)],'horn',.8,'Assinatura de marca clara, abertura ascendente e chegada em ré.',1),
  ('ident_tubo',5,110,-22,['Bm','G','Asus','D'],[(0,1.3,66,73),(2,1.3,67,72),(4,1.4,64,71),(6,1.3,62,70)],'strings',.55,'Entrada de cordas, trompa responde em queda; identidade suave.',2),
  ('apresenta',3.6,120,-22,['D','G','A7','D'],[(0,.75,66,74),(2,.7,67,73),(4,.65,61,72),(6,1.1,62,72)],'horn',.62,'Miniatura de apresentação: quatro notas e resolução breve, sem arrasto.',2),
  ('intervalo',6,104,-22,['D','Bm','Asus','A7'],[(0,1.3,66,73),(2,1.3,62,71),(4,1.3,64,72),(6,1.2,61,70)],'horn',.65,'Frase abre em ré e termina na dominante: pausa deliberada antes do intervalo.',2),
  ('voltamos',4.48,116,-21.5,['Asus','A7','D','D'],[(0,1.1,64,74),(2,.8,61,75),(4,.8,66,73),(6,1.1,62,72)],'horn',.72,'Resposta ao intervalo: dominante resolve em ré, pulso encerra cedo.',1),
 ]: result.append(make(*args))
 return result
