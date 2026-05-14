// ─── Données simulées — Sorts & Monstres (SRD 5.2) ───

window.SPELL_SCHOOLS = ['Abjuration','Conjuration','Divination','Enchantement','Évocation','Illusion','Nécromancie','Transmutation'];
window.SPELL_CLASSES = ['Barde','Clerc','Druide','Ensorceleur','Magicien','Occultiste','Paladin','Rôdeur'];
window.MONSTER_TYPES  = ['Aberration','Bête','Céleste','Constructe','Dragon','Élémentaire','Fée','Fiélon','Géant','Humanoïde','Monstruosité','Mort-vivant','Plante','Vase'];
window.MONSTER_SIZES  = ['Très petit','Petit','Moyen','Grand','Très grand','Gigantesque'];

window.SCHOOL_COLORS = {
  'Abjuration':'#4fd8c0','Conjuration':'#6fd96f','Divination':'#f0c764','Enchantement':'#c090ff',
  'Évocation':'#ff8247','Illusion':'#7eb8ff','Nécromancie':'#e84545','Transmutation':'#b88a2a',
};
window.TYPE_COLORS = {
  'Aberration':'#c090ff','Bête':'#6fd96f','Céleste':'#f0c764','Constructe':'#6b6580',
  'Dragon':'#ff8247','Élémentaire':'#4fd8c0','Fée':'#c090ff','Fiélon':'#e84545',
  'Géant':'#b88a2a','Humanoïde':'#f7ecd0','Monstruosité':'#ff8247','Mort-vivant':'#e84545',
  'Plante':'#6fd96f','Vase':'#4fd8c0',
};

window.SPELLS = [
  {
    id:'trait-de-feu', name:'Trait de feu', level:0, school:'Évocation',
    casting_time:'1 action', range:'36 m',
    components:{V:true,S:true,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Vous projetez un trait enflammé vers une créature ou un objet à portée. Effectuez une attaque à distance avec un sort. En cas de réussite, la cible subit 1d10 dégâts de feu. Un objet inflammable non porté s'embrase.",
    higher_levels:"Les dégâts augmentent de 1d10 aux niveaux 5 (2d10), 11 (3d10) et 17 (4d10).",
    classes:['Ensorceleur','Magicien'], damage_type:'Feu', source:'SRD 5.2'
  },
  {
    id:'lumiere', name:'Lumière', level:0, school:'Évocation',
    casting_time:'1 action', range:'Contact',
    components:{V:true,S:false,M:'une luciole ou de la mousse phosphorescente'},
    duration:'1 heure', concentration:false, ritual:false,
    description:"Vous touchez un objet de taille M ou inférieure. Il émet une lumière vive dans un rayon de 6 m et une lumière faible sur 6 m supplémentaires. La lumière peut prendre la couleur de votre choix.",
    higher_levels:null,
    classes:['Barde','Clerc','Ensorceleur','Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'prestidigitation', name:'Prestidigitation', level:0, school:'Transmutation',
    casting_time:'1 action', range:'3 m',
    components:{V:true,S:true,M:null},
    duration:'Jusqu\'à 1 heure', concentration:false, ritual:false,
    description:"Un tour de magie mineur que les lanceurs de sorts novices utilisent pour s\'exercer. Vous créez un petit effet sensoriel inoffensif : étincelles, brise, notes de musique, ou odeur étrange.",
    higher_levels:null,
    classes:['Barde','Ensorceleur','Magicien','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'rayon-de-givre', name:'Rayon de givre', level:0, school:'Évocation',
    casting_time:'1 action', range:'18 m',
    components:{V:true,S:true,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Un rayon de lumière blanche et glaciale fonce vers une créature à portée. Effectuez une attaque à distance avec un sort. En cas de réussite, elle subit 1d8 dégâts de froid et sa vitesse est réduite de 3 m jusqu\'à votre prochain tour.",
    higher_levels:"Les dégâts augmentent de 1d8 aux niveaux 5 (2d8), 11 (3d8) et 17 (4d8).",
    classes:['Ensorceleur','Magicien'], damage_type:'Froid', source:'SRD 5.2'
  },
  {
    id:'bouclier', name:'Bouclier', level:1, school:'Abjuration',
    casting_time:'1 réaction', range:'Personnel',
    components:{V:true,S:true,M:null},
    duration:'1 round', concentration:false, ritual:false,
    description:"Une barrière de force invisible vous protège. Jusqu\'au début de votre prochain tour, vous gagnez un bonus de +5 à la CA, y compris contre l\'attaque qui a déclenché ce sort. Vous ne subissez aucun dégât du sort projectile magique.",
    higher_levels:null,
    classes:['Ensorceleur','Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'projectile-magique', name:'Projectile magique', level:1, school:'Évocation',
    casting_time:'1 action', range:'36 m',
    components:{V:true,S:true,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Vous créez trois fléchettes de force magique. Chaque fléchette touche automatiquement une créature visible à portée et inflige 1d4+1 dégâts de force. Les fléchettes frappent simultanément et peuvent cibler une ou plusieurs créatures.",
    higher_levels:"Chaque emplacement au-dessus du 1er crée une fléchette supplémentaire.",
    classes:['Ensorceleur','Magicien'], damage_type:'Force', source:'SRD 5.2'
  },
  {
    id:'soins', name:'Soins', level:1, school:'Évocation',
    casting_time:'1 action', range:'Contact',
    components:{V:true,S:true,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Une créature que vous touchez récupère un nombre de points de vie égal à 1d8 + votre modificateur de caractéristique d\'incantation. Ce sort n\'a aucun effet sur les morts-vivants et les constructs.",
    higher_levels:"Les soins augmentent de 1d8 par emplacement au-dessus du 1er.",
    classes:['Barde','Clerc','Druide','Paladin','Rôdeur'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'detection-magie', name:'Détection de la magie', level:1, school:'Divination',
    casting_time:'1 action', range:'Personnel',
    components:{V:true,S:true,M:null},
    duration:'Jusqu\'à 10 minutes', concentration:true, ritual:true,
    description:"Pendant la durée, vous percevez la présence de magie dans un rayon de 9 m. Si vous percevez de la magie, vous pouvez utiliser votre action pour discerner une faible aura autour de tout objet ou créature magique visible, et en déterminer l\'école.",
    higher_levels:null,
    classes:['Barde','Clerc','Druide','Ensorceleur','Magicien','Paladin','Rôdeur'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'armure-mage', name:'Armure du mage', level:1, school:'Abjuration',
    casting_time:'1 action', range:'Contact',
    components:{V:true,S:true,M:'un morceau de cuir tanné'},
    duration:'8 heures', concentration:false, ritual:false,
    description:"Vous touchez une créature consentante qui ne porte pas d\'armure. Une force magique protectrice l\'entoure jusqu\'à la fin du sort. La CA de base de la cible devient 13 + son modificateur de Dextérité.",
    higher_levels:null,
    classes:['Ensorceleur','Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'sommeil', name:'Sommeil', level:1, school:'Enchantement',
    casting_time:'1 action', range:'27 m',
    components:{V:true,S:true,M:'une pincée de sable fin ou de pétales de rose'},
    duration:'1 minute', concentration:false, ritual:false,
    description:"Ce sort plonge les créatures dans un sommeil magique. Lancez 5d8 ; le total est le nombre de points de vie de créatures que ce sort peut affecter, en commençant par la créature ayant le moins de PV actuels.",
    higher_levels:"Lancez 2d8 supplémentaires par emplacement au-dessus du 1er.",
    classes:['Barde','Ensorceleur','Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'immobilisation-personne', name:'Immobilisation de personne', level:2, school:'Enchantement',
    casting_time:'1 action', range:'18 m',
    components:{V:true,S:true,M:'un petit morceau de fer droit'},
    duration:'Jusqu\'à 1 minute', concentration:true, ritual:false,
    description:"Choisissez un humanoïde visible à portée. La cible doit réussir un jet de sauvegarde de Sagesse sous peine d\'être paralysée. À la fin de chacun de ses tours, la cible peut retenter le jet de sauvegarde.",
    higher_levels:"Vous ciblez un humanoïde supplémentaire par emplacement au-dessus du 2e.",
    classes:['Barde','Clerc','Druide','Ensorceleur','Magicien','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'tenebres', name:'Ténèbres', level:2, school:'Évocation',
    casting_time:'1 action', range:'18 m',
    components:{V:true,S:false,M:'de la fourrure de chauve-souris et du goudron'},
    duration:'Jusqu\'à 10 minutes', concentration:true, ritual:false,
    description:"Des ténèbres magiques se répandent depuis un point à portée, remplissant une sphère de 4,50 m de rayon. Les créatures avec la vision dans le noir ne voient pas à travers. Une lumière non magique ne peut pas illuminer la zone.",
    higher_levels:null,
    classes:['Ensorceleur','Magicien','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'invisibilite', name:'Invisibilité', level:2, school:'Illusion',
    casting_time:'1 action', range:'Contact',
    components:{V:true,S:true,M:'un cil dans de la gomme arabique'},
    duration:'Jusqu\'à 1 heure', concentration:true, ritual:false,
    description:"Une créature que vous touchez devient invisible jusqu\'à la fin du sort. Tout ce qu\'elle porte ou transporte devient invisible tant qu\'elle le garde sur elle. Le sort prend fin si la cible attaque ou lance un sort.",
    higher_levels:"Vous ciblez une créature supplémentaire par emplacement au-dessus du 2e.",
    classes:['Barde','Ensorceleur','Magicien','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'boule-de-feu', name:'Boule de feu', level:3, school:'Évocation',
    casting_time:'1 action', range:'45 m',
    components:{V:true,S:true,M:'une petite boule de guano de chauve-souris et du soufre'},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Un point lumineux jaillit de votre doigt et explose en un embrasement dans un rayon de 6 m. Chaque créature dans la zone doit réussir un jet de sauvegarde de Dextérité ou subir 8d6 dégâts de feu (moitié en cas de réussite). Le feu contourne les angles et enflamme les objets inflammables non portés.",
    higher_levels:"Les dégâts augmentent de 1d6 par emplacement au-dessus du 3e.",
    classes:['Ensorceleur','Magicien'], damage_type:'Feu', source:'SRD 5.2'
  },
  {
    id:'dissipation-magie', name:'Dissipation de la magie', level:3, school:'Abjuration',
    casting_time:'1 action', range:'36 m',
    components:{V:true,S:true,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Choisissez une créature, un objet ou un effet magique à portée. Tout sort de niveau 3 ou inférieur prend fin. Pour les sorts de niveau supérieur, effectuez un test de caractéristique d\'incantation (DD = 10 + niveau du sort).",
    higher_levels:"Le sort dissipé automatiquement monte au niveau de l'emplacement utilisé.",
    classes:['Barde','Clerc','Druide','Magicien','Paladin','Ensorceleur','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'vol', name:'Vol', level:3, school:'Transmutation',
    casting_time:'1 action', range:'Contact',
    components:{V:true,S:true,M:'une plume d\'aile d\'oiseau'},
    duration:'Jusqu\'à 10 minutes', concentration:true, ritual:false,
    description:"Vous touchez une créature consentante qui gagne une vitesse de vol de 18 m. Si la cible est en l\'air quand le sort prend fin, elle descend de 18 m par round jusqu\'à toucher le sol.",
    higher_levels:"Vous ciblez une créature supplémentaire par emplacement au-dessus du 3e.",
    classes:['Ensorceleur','Magicien','Occultiste'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'animation-morts', name:'Animation des morts', level:3, school:'Nécromancie',
    casting_time:'1 minute', range:'3 m',
    components:{V:true,S:true,M:'une goutte de sang, un morceau de chair et une pincée de poussière d\'os'},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Ce sort crée un serviteur mort-vivant. Choisissez un tas d\'os ou le cadavre d\'un humanoïde de taille M ou P à portée. Le sort l\'anime en squelette ou en zombie qui obéit à vos ordres verbaux.",
    higher_levels:"Vous animez ou réaffirmez le contrôle de 2 morts-vivants supplémentaires par emplacement au-dessus du 3e.",
    classes:['Clerc','Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'mur-de-feu', name:'Mur de feu', level:4, school:'Évocation',
    casting_time:'1 action', range:'36 m',
    components:{V:true,S:true,M:'un petit morceau de phosphore'},
    duration:'Jusqu\'à 1 minute', concentration:true, ritual:false,
    description:"Vous créez un mur de feu sur une surface solide à portée. Le mur fait 18 m de long, 6 m de haut et 30 cm d\'épaisseur (ou annulaire, 6 m de diamètre, 6 m de haut). Le côté que vous choisissez inflige 5d8 dégâts de feu aux créatures à moins de 3 m.",
    higher_levels:"Les dégâts augmentent de 1d8 par emplacement au-dessus du 4e.",
    classes:['Druide','Ensorceleur','Magicien'], damage_type:'Feu', source:'SRD 5.2'
  },
  {
    id:'porte-dimensionnelle', name:'Porte dimensionnelle', level:4, school:'Conjuration',
    casting_time:'1 action', range:'150 m',
    components:{V:true,S:false,M:null},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Vous vous téléportez vers un emplacement que vous voyez, visualisez ou décrivez. Vous pouvez emmener un objet ou une créature consentante de taille M ou inférieure qui se trouve à votre portée.",
    higher_levels:null,
    classes:['Barde','Ensorceleur','Magicien','Occultiste','Paladin'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'mur-de-force', name:'Mur de force', level:5, school:'Évocation',
    casting_time:'1 action', range:'36 m',
    components:{V:true,S:true,M:'une pincée de poudre de gemme transparente'},
    duration:'Jusqu\'à 10 minutes', concentration:true, ritual:false,
    description:"Un mur de force invisible apparaît à un endroit de votre choix. Le mur est imperméable à tout : objets, créatures, sorts, même la téléportation. Seul le sort désintégration peut le détruire instantanément.",
    higher_levels:null,
    classes:['Magicien'], damage_type:null, source:'SRD 5.2'
  },
  {
    id:'desintegration', name:'Désintégration', level:6, school:'Transmutation',
    casting_time:'1 action', range:'18 m',
    components:{V:true,S:true,M:'un aimant et une pincée de poussière'},
    duration:'Instantanée', concentration:false, ritual:false,
    description:"Un mince rayon de lumière verte jaillit de votre doigt vers une cible visible à portée. La cible subit 10d6+40 dégâts de force. Si ces dégâts réduisent la cible à 0 PV, elle est désintégrée et réduite en fine poussière grise.",
    higher_levels:"Les dégâts augmentent de 3d6 par emplacement au-dessus du 6e.",
    classes:['Ensorceleur','Magicien'], damage_type:'Force', source:'SRD 5.2'
  },
];

// ─── Monstres ───

window.MONSTERS = [
  {
    id:'gobelin', name:'Gobelin', size:'Petit', type:'Humanoïde', subtype:'gobelinoïde',
    alignment:'Neutre Mauvais',
    ac:15, ac_type:'armure de cuir, bouclier', hp:7, hp_dice:'2d6',
    speed:{marche:'9 m'},
    abilities:{ FOR:{v:8,m:'-1'}, DEX:{v:14,m:'+2'}, CON:{v:10,m:'+0'}, INT:{v:10,m:'+0'}, SAG:{v:8,m:'-1'}, CHA:{v:8,m:'-1'} },
    saving_throws:null, skills:{'Discrétion':'+6'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 9',
    languages:'Commun, gobelin', challenge:'1/4', xp:50,
    traits:[{name:'Fuite agile',desc:'Le gobelin peut Se désengager ou Se cacher comme action bonus à chacun de ses tours.'}],
    actions:[
      {name:'Cimeterre',desc:'Corps à corps : +4 pour toucher, allonge 1,50 m, une cible. Dégâts : 5 (1d6+2) tranchants.'},
      {name:'Arc court',desc:'À distance : +4 pour toucher, portée 24/96 m, une cible. Dégâts : 5 (1d6+2) perforants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Forêt','Collines','Souterrain'], source:'SRD 5.2'
  },
  {
    id:'squelette', name:'Squelette', size:'Moyen', type:'Mort-vivant', subtype:null,
    alignment:'Loyal Mauvais',
    ac:13, ac_type:'vestiges d\'armure', hp:13, hp_dice:'2d8+4',
    speed:{marche:'9 m'},
    abilities:{ FOR:{v:10,m:'+0'}, DEX:{v:14,m:'+2'}, CON:{v:15,m:'+2'}, INT:{v:6,m:'-2'}, SAG:{v:8,m:'-1'}, CHA:{v:5,m:'-3'} },
    saving_throws:null, skills:null,
    damage_resistances:[], damage_immunities:['Poison'], condition_immunities:['Empoisonné','Épuisement'],
    senses:'Vision dans le noir 18 m, Perception passive 9',
    languages:'comprend les langues qu\'il parlait de son vivant mais ne peut pas parler', challenge:'1/4', xp:50,
    traits:[{name:'Vulnérabilité au contondant',desc:'Le squelette est vulnérable aux dégâts contondants.'}],
    actions:[
      {name:'Épée courte',desc:'Corps à corps : +4 pour toucher, allonge 1,50 m, une cible. Dégâts : 5 (1d6+2) perforants.'},
      {name:'Arc court',desc:'À distance : +4 pour toucher, portée 24/96 m, une cible. Dégâts : 5 (1d6+2) perforants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Souterrain','Ruines'], source:'SRD 5.2'
  },
  {
    id:'loup', name:'Loup', size:'Moyen', type:'Bête', subtype:null,
    alignment:'Non-aligné',
    ac:13, ac_type:'armure naturelle', hp:11, hp_dice:'2d8+2',
    speed:{marche:'12 m'},
    abilities:{ FOR:{v:12,m:'+1'}, DEX:{v:15,m:'+2'}, CON:{v:12,m:'+1'}, INT:{v:3,m:'-4'}, SAG:{v:12,m:'+1'}, CHA:{v:6,m:'-2'} },
    saving_throws:null, skills:{'Perception':'+3','Discrétion':'+4'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Perception passive 13',
    languages:'—', challenge:'1/4', xp:50,
    traits:[
      {name:'Odorat aiguisé',desc:'Le loup a l\'avantage aux tests de Sagesse (Perception) basés sur l\'odorat.'},
      {name:'Tactique de meute',desc:'Le loup a l\'avantage aux jets d\'attaque contre une créature si au moins un allié non neutralisé se trouve à 1,50 m de la cible.'},
    ],
    actions:[
      {name:'Morsure',desc:'Corps à corps : +4 pour toucher, allonge 1,50 m, une cible. Dégâts : 7 (2d4+2) perforants. La cible doit réussir un jet de sauvegarde de Force DD 11 ou tomber à terre.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Forêt','Collines','Plaines'], source:'SRD 5.2'
  },
  {
    id:'orc', name:'Orc', size:'Moyen', type:'Humanoïde', subtype:'orc',
    alignment:'Chaotique Mauvais',
    ac:13, ac_type:'armure de peaux', hp:15, hp_dice:'2d8+6',
    speed:{marche:'9 m'},
    abilities:{ FOR:{v:16,m:'+3'}, DEX:{v:12,m:'+1'}, CON:{v:16,m:'+3'}, INT:{v:7,m:'-2'}, SAG:{v:11,m:'+0'}, CHA:{v:10,m:'+0'} },
    saving_throws:null, skills:{'Intimidation':'+2'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 10',
    languages:'Commun, orc', challenge:'1/2', xp:100,
    traits:[{name:'Agressif',desc:'Par une action bonus, l\'orc peut se déplacer d\'une distance égale à sa vitesse vers une créature hostile qu\'il peut voir.'}],
    actions:[
      {name:'Hache à deux mains',desc:'Corps à corps : +5 pour toucher, allonge 1,50 m, une cible. Dégâts : 9 (1d12+3) tranchants.'},
      {name:'Javeline',desc:'Corps à corps ou à distance : +5 pour toucher, allonge 1,50 m ou portée 9/36 m, une cible. Dégâts : 6 (1d6+3) perforants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Plaines','Forêt','Montagne','Souterrain'], source:'SRD 5.2'
  },
  {
    id:'araignee-geante', name:'Araignée géante', size:'Grand', type:'Bête', subtype:null,
    alignment:'Non-aligné',
    ac:14, ac_type:'armure naturelle', hp:26, hp_dice:'4d10+4',
    speed:{marche:'9 m',escalade:'9 m'},
    abilities:{ FOR:{v:14,m:'+2'}, DEX:{v:16,m:'+3'}, CON:{v:12,m:'+1'}, INT:{v:2,m:'-4'}, SAG:{v:11,m:'+0'}, CHA:{v:4,m:'-3'} },
    saving_throws:null, skills:{'Discrétion':'+7'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 10',
    languages:'—', challenge:'1', xp:200,
    traits:[
      {name:'Pattes d\'araignée',desc:'L\'araignée peut escalader les surfaces difficiles, y compris les plafonds, sans test de caractéristique.'},
      {name:'Sens de la toile',desc:'En contact avec une toile, l\'araignée connaît la position exacte de toute créature en contact avec cette même toile.'},
      {name:'Marche dans les toiles',desc:'L\'araignée ignore les restrictions de mouvement causées par les toiles.'},
    ],
    actions:[
      {name:'Morsure',desc:'Corps à corps : +5 pour toucher, allonge 1,50 m, une cible. Dégâts : 7 (1d8+3) perforants, plus 9 (2d8) dégâts de poison. Jet de sauvegarde de Constitution DD 11 pour réduire les dégâts de poison de moitié.'},
      {name:'Toile (recharge 5-6)',desc:'À distance : +5 pour toucher, portée 9/18 m, une créature. La cible est entravée. Elle peut se libérer avec un test de Force DD 12.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Forêt','Souterrain'], source:'SRD 5.2'
  },
  {
    id:'ours-hibou', name:'Ours-hibou', size:'Grand', type:'Monstruosité', subtype:null,
    alignment:'Non-aligné',
    ac:13, ac_type:'armure naturelle', hp:59, hp_dice:'7d10+21',
    speed:{marche:'12 m'},
    abilities:{ FOR:{v:20,m:'+5'}, DEX:{v:12,m:'+1'}, CON:{v:17,m:'+3'}, INT:{v:3,m:'-4'}, SAG:{v:12,m:'+1'}, CHA:{v:7,m:'-2'} },
    saving_throws:null, skills:{'Perception':'+3'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 13',
    languages:'—', challenge:'3', xp:700,
    traits:[{name:'Vue et odorat aiguisés',desc:'L\'ours-hibou a l\'avantage aux tests de Sagesse (Perception) basés sur la vue ou l\'odorat.'}],
    actions:[
      {name:'Attaques multiples',desc:'L\'ours-hibou effectue deux attaques : une de bec et une de griffes.'},
      {name:'Bec',desc:'Corps à corps : +7 pour toucher, allonge 1,50 m, une cible. Dégâts : 10 (1d10+5) perforants.'},
      {name:'Griffes',desc:'Corps à corps : +7 pour toucher, allonge 1,50 m, une cible. Dégâts : 14 (2d8+5) tranchants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Forêt'], source:'SRD 5.2'
  },
  {
    id:'minotaure', name:'Minotaure', size:'Grand', type:'Monstruosité', subtype:null,
    alignment:'Chaotique Mauvais',
    ac:14, ac_type:'armure naturelle', hp:76, hp_dice:'9d10+27',
    speed:{marche:'12 m'},
    abilities:{ FOR:{v:18,m:'+4'}, DEX:{v:11,m:'+0'}, CON:{v:16,m:'+3'}, INT:{v:6,m:'-2'}, SAG:{v:16,m:'+3'}, CHA:{v:9,m:'-1'} },
    saving_throws:null, skills:{'Perception':'+7'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 17',
    languages:'Abyssal', challenge:'3', xp:700,
    traits:[
      {name:'Charge',desc:'Si le minotaure se déplace d\'au moins 3 m en ligne droite puis touche avec ses cornes, la cible subit 9 (2d8) dégâts perforants supplémentaires. Jet de sauvegarde de Force DD 14 ou tomber à terre.'},
      {name:'Mémoire des labyrinthes',desc:'Le minotaure se rappelle parfaitement de chaque chemin emprunté.'},
      {name:'Téméraire',desc:'Au début de son tour, le minotaure peut avoir l\'avantage sur tous ses jets d\'attaque au corps à corps, mais les attaques contre lui ont aussi l\'avantage jusqu\'au début de son prochain tour.'},
    ],
    actions:[
      {name:'Hache à deux mains',desc:'Corps à corps : +6 pour toucher, allonge 1,50 m, une cible. Dégâts : 17 (2d12+4) tranchants.'},
      {name:'Cornes',desc:'Corps à corps : +6 pour toucher, allonge 1,50 m, une cible. Dégâts : 13 (2d8+4) perforants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Souterrain'], source:'SRD 5.2'
  },
  {
    id:'troll', name:'Troll', size:'Grand', type:'Géant', subtype:null,
    alignment:'Chaotique Mauvais',
    ac:15, ac_type:'armure naturelle', hp:84, hp_dice:'8d10+40',
    speed:{marche:'9 m'},
    abilities:{ FOR:{v:18,m:'+4'}, DEX:{v:13,m:'+1'}, CON:{v:20,m:'+5'}, INT:{v:7,m:'-2'}, SAG:{v:9,m:'-1'}, CHA:{v:7,m:'-2'} },
    saving_throws:null, skills:{'Perception':'+2'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 12',
    languages:'Géant', challenge:'5', xp:1800,
    traits:[
      {name:'Odorat aiguisé',desc:'Le troll a l\'avantage aux tests de Sagesse (Perception) basés sur l\'odorat.'},
      {name:'Régénération',desc:'Le troll récupère 10 PV au début de chacun de ses tours. S\'il subit des dégâts d\'acide ou de feu, ce trait ne fonctionne pas au début de son prochain tour. Le troll ne meurt que s\'il commence son tour à 0 PV et ne se régénère pas.'},
    ],
    actions:[
      {name:'Attaques multiples',desc:'Le troll effectue trois attaques : une de morsure et deux de griffes.'},
      {name:'Morsure',desc:'Corps à corps : +7 pour toucher, allonge 1,50 m, une cible. Dégâts : 7 (1d6+4) perforants.'},
      {name:'Griffes',desc:'Corps à corps : +7 pour toucher, allonge 1,50 m, une cible. Dégâts : 11 (2d6+4) tranchants.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Forêt','Montagne','Marécage','Souterrain'], source:'SRD 5.2'
  },
  {
    id:'elementaire-feu', name:'Élémentaire de feu', size:'Grand', type:'Élémentaire', subtype:null,
    alignment:'Neutre',
    ac:13, ac_type:null, hp:102, hp_dice:'12d10+36',
    speed:{marche:'15 m'},
    abilities:{ FOR:{v:10,m:'+0'}, DEX:{v:17,m:'+3'}, CON:{v:16,m:'+3'}, INT:{v:6,m:'-2'}, SAG:{v:10,m:'+0'}, CHA:{v:7,m:'-2'} },
    saving_throws:null, skills:null,
    damage_resistances:['Contondant, perforant et tranchant non magiques'], damage_immunities:['Feu','Poison'], condition_immunities:['Agrippé','Empoisonné','Épuisement','Inconscient','Paralysé','Pétrifié','À terre'],
    senses:'Vision dans le noir 18 m, Perception passive 10',
    languages:'Igné', challenge:'5', xp:1800,
    traits:[
      {name:'Forme de feu',desc:'L\'élémentaire peut se faufiler dans un espace de 2,5 cm sans se comprimer. Une créature qui le touche ou le frappe au corps à corps subit 5 (1d10) dégâts de feu.'},
      {name:'Illumination',desc:'L\'élémentaire émet une lumière vive sur 9 m et une lumière faible sur 9 m supplémentaires.'},
      {name:'Sensibilité à l\'eau',desc:'Pour chaque 1,50 m parcouru dans l\'eau, l\'élémentaire subit 1 dégât de froid.'},
    ],
    actions:[
      {name:'Attaques multiples',desc:'L\'élémentaire effectue deux attaques de contact.'},
      {name:'Contact',desc:'Corps à corps : +6 pour toucher, allonge 1,50 m, une cible. Dégâts : 10 (2d6+3) de feu. Si la cible est inflammable, elle prend feu et subit 5 (1d10) dégâts de feu au début de chacun de ses tours.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Volcan','Plan élémentaire du Feu'], source:'SRD 5.2'
  },
  {
    id:'wyverne', name:'Wyverne', size:'Grand', type:'Dragon', subtype:null,
    alignment:'Non-aligné',
    ac:13, ac_type:'armure naturelle', hp:110, hp_dice:'13d10+39',
    speed:{marche:'6 m',vol:'24 m'},
    abilities:{ FOR:{v:19,m:'+4'}, DEX:{v:10,m:'+0'}, CON:{v:16,m:'+3'}, INT:{v:5,m:'-3'}, SAG:{v:12,m:'+1'}, CHA:{v:6,m:'-2'} },
    saving_throws:null, skills:{'Perception':'+4'},
    damage_resistances:[], damage_immunities:[], condition_immunities:[],
    senses:'Vision dans le noir 18 m, Perception passive 14',
    languages:'—', challenge:'6', xp:2300,
    traits:[],
    actions:[
      {name:'Attaques multiples',desc:'La wyverne effectue deux attaques : une de morsure et une avec son dard. En vol, elle peut remplacer la morsure par une attaque de griffes.'},
      {name:'Morsure',desc:'Corps à corps : +7 pour toucher, allonge 3 m, une cible. Dégâts : 11 (2d6+4) perforants.'},
      {name:'Griffes',desc:'Corps à corps : +7 pour toucher, allonge 1,50 m, une cible. Dégâts : 13 (2d8+4) tranchants.'},
      {name:'Dard',desc:'Corps à corps : +7 pour toucher, allonge 3 m, une cible. Dégâts : 11 (2d6+4) perforants. La cible doit réussir un jet de sauvegarde de Constitution DD 15 ou subir 24 (7d6) dégâts de poison, moitié en cas de réussite.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Montagne','Collines','Côte'], source:'SRD 5.2'
  },
  {
    id:'jeune-dragon-rouge', name:'Jeune dragon rouge', size:'Grand', type:'Dragon', subtype:null,
    alignment:'Chaotique Mauvais',
    ac:18, ac_type:'armure naturelle', hp:178, hp_dice:'17d10+85',
    speed:{marche:'12 m',escalade:'12 m',vol:'24 m'},
    abilities:{ FOR:{v:23,m:'+6'}, DEX:{v:10,m:'+0'}, CON:{v:21,m:'+5'}, INT:{v:14,m:'+2'}, SAG:{v:11,m:'+0'}, CHA:{v:19,m:'+4'} },
    saving_throws:{'DEX':'+4','CON':'+9','SAG':'+4','CHA':'+8'},
    skills:{'Discrétion':'+4','Perception':'+8'},
    damage_resistances:[], damage_immunities:['Feu'], condition_immunities:[],
    senses:'Vision aveugle 9 m, vision dans le noir 36 m, Perception passive 18',
    languages:'Commun, draconique', challenge:'10', xp:5900,
    traits:[],
    actions:[
      {name:'Attaques multiples',desc:'Le dragon effectue trois attaques : une de morsure et deux de griffes.'},
      {name:'Morsure',desc:'Corps à corps : +10 pour toucher, allonge 3 m, une cible. Dégâts : 17 (2d10+6) perforants, plus 3 (1d6) de feu.'},
      {name:'Griffes',desc:'Corps à corps : +10 pour toucher, allonge 1,50 m, une cible. Dégâts : 13 (2d6+6) tranchants.'},
      {name:'Souffle de feu (recharge 5–6)',desc:'Le dragon souffle du feu dans un cône de 9 m. Chaque créature doit réussir un jet de sauvegarde de Dextérité DD 17 ou subir 56 (16d6) dégâts de feu, moitié en cas de réussite.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Montagne','Souterrain','Volcan'], source:'SRD 5.2'
  },
  {
    id:'momie', name:'Momie', size:'Moyen', type:'Mort-vivant', subtype:null,
    alignment:'Loyal Mauvais',
    ac:11, ac_type:'armure naturelle', hp:58, hp_dice:'9d8+18',
    speed:{marche:'6 m'},
    abilities:{ FOR:{v:16,m:'+3'}, DEX:{v:8,m:'-1'}, CON:{v:15,m:'+2'}, INT:{v:6,m:'-2'}, SAG:{v:10,m:'+0'}, CHA:{v:12,m:'+1'} },
    saving_throws:{'SAG':'+2'},
    skills:null,
    damage_resistances:['Contondant, perforant et tranchant non magiques'],
    damage_immunities:['Nécrotique','Poison'],
    condition_immunities:['Charmé','Empoisonné','Épuisement','Effrayé','Paralysé'],
    senses:'Vision dans le noir 18 m, Perception passive 10',
    languages:'les langues qu\'elle parlait de son vivant', challenge:'3', xp:700,
    traits:[],
    actions:[
      {name:'Attaques multiples',desc:'La momie peut utiliser son Regard effroyable et effectuer une attaque de poing putréfié.'},
      {name:'Poing putréfié',desc:'Corps à corps : +5 pour toucher, allonge 1,50 m, une cible. Dégâts : 10 (2d6+3) contondants, plus 10 (3d6) nécrotiques. Jet de sauvegarde de Constitution DD 12 ou maudite par la putréfaction de momie.'},
      {name:'Regard effroyable',desc:'La momie cible une créature à 18 m. Celle-ci doit réussir un jet de sauvegarde de Sagesse DD 11 ou être effrayée jusqu\'à la fin du prochain tour de la momie. En cas d\'échec de 5 ou plus, la cible est aussi paralysée.'},
    ],
    reactions:null, legendary_actions:null,
    environment:['Désert','Ruines','Souterrain'], source:'SRD 5.2'
  },
];
