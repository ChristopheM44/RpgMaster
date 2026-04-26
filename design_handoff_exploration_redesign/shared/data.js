// Données simulées partagées entre les variations
window.PARTY = [
  {
    id: 'thorvald',
    name: 'Thorvald',
    initial: 'T',
    char_class: 'Fighter',
    species: 'Human',
    level: 1,
    hp_current: 12, hp_max: 12, hp_temp: 0,
    ac: 16, init: 2, speed: 30,
    is_ai: false, is_self: true,
    abilities: { FOR: { v: 16, m: '+3' }, DEX: { v: 14, m: '+2' }, CON: { v: 15, m: '+2' }, INT: { v: 9, m: '-1' }, SAG: { v: 11, m: '+0' }, CHA: { v: 13, m: '+1' } },
    equipped: 'Épée longue',
    spells_left: null,
    conditions: [],
    accent: 'ember',
  },
  {
    id: 'oaken',
    name: 'Oaken',
    initial: 'O',
    char_class: 'Druid',
    species: 'Half-elf',
    level: 1,
    hp_current: 9, hp_max: 10, hp_temp: 0,
    ac: 13, init: 1, speed: 30,
    is_ai: true, is_self: false,
    abilities: { FOR: { v: 11, m: '+0' }, DEX: { v: 13, m: '+1' }, CON: { v: 14, m: '+2' }, INT: { v: 12, m: '+1' }, SAG: { v: 16, m: '+3' }, CHA: { v: 10, m: '+0' } },
    equipped: 'Bâton de chêne',
    spells_left: '3 / 4',
    conditions: [],
    accent: 'green',
  },
  {
    id: 'sunwing',
    name: 'Sunwing',
    initial: 'S',
    char_class: 'Rogue',
    species: 'Halfling',
    level: 1,
    hp_current: 8, hp_max: 9, hp_temp: 0,
    ac: 14, init: 4, speed: 25,
    is_ai: true, is_self: false,
    abilities: { FOR: { v: 8, m: '-1' }, DEX: { v: 17, m: '+3' }, CON: { v: 12, m: '+1' }, INT: { v: 13, m: '+1' }, SAG: { v: 11, m: '+0' }, CHA: { v: 14, m: '+2' } },
    equipped: 'Dague + arc court',
    spells_left: null,
    conditions: [],
    accent: 'gold',
  },
  {
    id: 'vael',
    name: 'Vael',
    initial: 'V',
    char_class: 'Ranger',
    species: 'Elf',
    level: 1,
    hp_current: 11, hp_max: 11, hp_temp: 0,
    ac: 15, init: 3, speed: 30,
    is_ai: true, is_self: false,
    abilities: { FOR: { v: 13, m: '+1' }, DEX: { v: 16, m: '+3' }, CON: { v: 13, m: '+1' }, INT: { v: 11, m: '+0' }, SAG: { v: 14, m: '+2' }, CHA: { v: 10, m: '+0' } },
    equipped: 'Arc long + cimeterre',
    spells_left: '2 / 2',
    conditions: [],
    accent: 'arcane',
  },
];

window.NARRATIVE = [
  { type: 'gm-recap', text: "…répète qu'aux oreilles dignes de confiance. » Son regard se pose sur les cicatrices de l'armure de Thorvald avec une approbation silencieuse. La chaleur du feu caresse le visage du guerrier tandis que les rumeurs s'installent dans son esprit comme des graines prêtes à germer. Autour de lui, Oaken sirote sa bière en observant les flammes, Sunwing garde un œil sur la porte, et Vael semble déjà réfléchir aux possibilités que ces nouvelles ouvrent. La nuit à Phandalin ne fait que commencer, et avec elle, les choix qui façonneront leur prochaine aventure." },
  { type: 'player', who: 'Oaken', text: "Oaken se penche vers Toben, ses yeux verts s'illuminant d'intérêt. « Des lumières froides dans les collines ? Cela sonne comme une menace qui mérite qu'on s'y intéresse. » Il pose se chope sur la table, le visage déterminé. « Si des gens ont besoin d'aide, nous ne les laisserons pas seuls face à l'obscurité. »" },
  { type: 'player', who: 'Sunwing', text: "Sunwing penche se chope vers Thorvald, un éclat d'intérêt dans le regard. « Des cryptes au nord… ou des lumières anciennes dans les collines. » Il prend une gorgée de bière, pensif. « Peu importe laquelle de ces pistes nous mène au danger, je serai en première ligne. Mais choisissons sagement — les pistes humaines sont une menace plus immédiate pour les voyageurs. »" },
  { type: 'player', who: 'Vael', text: "Vael penche la tête en sirotant sa bière, ses yeux s'illuminant d'intérêt. « Des bandits organisés et des lumières étranges… » Il pose sa chope avec détermination. « Thorvald, si ces menaces approchent de Phandalin, nous devrions enquêter. Un vrai guerrier ne laisse pas les innocents sans protection. »" },
  { type: 'player', who: 'Thorvald', text: "Après une bonne nuit de sommeil il vous propose compagnon que nous allions voir ce qu'il en est de ces bandits qu'on pense ?" },
  { type: 'gm', text: "Les premiers rayons du soleil filtrent à travers les volets de bois de l'auberge Stonehill, chassant les dernières ombres de la nuit. L'odeur du pain frais et de lard grillé monte des cuisines, se mêlant au parfum de paille propre des chambres où Thorvald et ses compagnons ont trouvé un repos bien mérité. Les muscles du guerrier ne sont plus qu'un lointain souvenir, et l'armure rangée près du lit semble presque légère ce matin." },
];

window.QUESTS = [
  { id: 'main', kind: 'principale', title: "Les lumières de Tresendar", desc: "Toben mentionne d'étranges lueurs dans les collines au nord. Enquêter avant la nuit prochaine.", progress: 1, steps: 3, due: 'Avant la nuit' },
  { id: 'side', kind: 'secondaire', title: "Embuscade sur la route", desc: "Des bandits opèrent sur la route de Neverwinter. Les marchands sont en danger.", progress: 0, steps: 2 },
  { id: 'rumor', kind: 'rumeur', title: "Cryptes anciennes", desc: "Des cryptes au nord, oubliées depuis des générations.", progress: 0, steps: null },
];

window.MEMORY = [
  { kind: 'PNJ', name: 'Toben', detail: 'Vieil habitué de l\'auberge — source des rumeurs', tag: 'allié' },
  { kind: 'Lieu', name: 'Auberge Stonehill', detail: 'Phandalin, cœur du village', tag: 'sûr' },
  { kind: 'Lieu', name: 'Collines de Tresendar', detail: 'Lueurs étranges signalées la nuit', tag: 'à explorer' },
  { kind: 'PNJ', name: 'Halia Thornton', detail: 'Maîtresse de la guilde des miniers', tag: 'neutre' },
  { kind: 'Lieu', name: 'Route de Neverwinter', detail: 'Bandits actifs récemment', tag: 'danger' },
];

window.SUGGESTIONS = [
  { icon: '🗣', label: 'Parler à Toben', hint: 'PNJ présent' },
  { icon: '🔍', label: 'Fouiller la salle commune', hint: 'Perception' },
  { icon: '🥾', label: 'Partir vers les collines', hint: 'Voyage' },
  { icon: '📜', label: 'Consulter une rumeur', hint: 'Histoire' },
];
