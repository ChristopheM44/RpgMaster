import random
from typing import Any

BIOMES = {
    "taverne": {
        "name_fr": "Taverne animée",
        "scene_theme": "city",
        "places": [
            "l'Auberge de la Chope Fêlée",
            "la Taverne du Gobelin Borgne",
            "le Relais des Voyageurs",
            "un cabaret souterrain mal famé",
        ],
        "weather_options": [
            "Calme",
            "Pluie battante dehors",
            "Orage violent dehors",
            "Nuit noire dehors",
        ],
        "prologues": [
            "Après des semaines de voyage éprouvant à travers des contrées sauvages, vous avez enfin trouvé refuge dans ce relais. Alors que vous partagiez un repas chaud et quelques pichets de bière en discutant de vos projets, l'agitation habituelle de la salle s'est soudainement tue pour laisser place à une tension palpable...",
            "Vous vous êtes tous retrouvés à la même table, réunis par un intermédiaire qui vous avait promis un travail gracieusement payé. Mais l'intermédiaire ne s'est jamais présenté, et vous venez de découvrir qu'une étrange marque noire a été discrètement gravée sur le bois de votre table sous vos chopines...",
        ],
    },
    "dungeon": {
        "name_fr": "Donjon / Crypte",
        "scene_theme": "dungeon",
        "places": [
            "les catacombes oubliées d'un culte éteint",
            "les geôles humides d'une forteresse en ruine",
            "la crypte ancestrale d'une lignée maudite",
            "les couloirs de pierre d'un ancien sanctuaire",
        ],
        "weather_options": [
            "Air stagnant",
            "Froid glacial souterrain",
            "Humidité suintante",
            "Obscurité totale",
        ],
        "prologues": [
            "Le sol s'est dérobé sous vos pieds alors que vous exploriez les ruines de surface, vous précipitant dans ce dédale de pierre oublié de tous. Blessés mais vivants, vos torches faiblissantes révèlent des gravures ancestrales sur les murs, et le seul chemin de retour semble être de vous enfoncer plus profondément...",
            "Capturés dans votre sommeil par des pilleurs de tombes ou des fanatiques, vous avez été jetés dans ces profondeurs pour servir de sacrifices ou de main d'œuvre. Vous avez réussi à briser vos chaînes et à éliminer vos gardes dans l'ombre, mais vous êtes désormais perdus dans l'obscurité moite de ces galeries...",
        ],
    },
    "forest": {
        "name_fr": "Forêt mystérieuse",
        "scene_theme": "forest",
        "places": [
            "une clairière d'arbres millénaires",
            "un bosquet entouré de ronces géantes",
            "les sentiers d'une forêt de pins étouffante",
            "une croisée de chemins forestiers balayée par le vent",
        ],
        "weather_options": [
            "Calme",
            "Brouillard épais",
            "Pluie battante",
            "Tempétueux",
            "Nuit noire",
            "Éclipse lunaire",
        ],
        "prologues": [
            "Vous suiviez une ancienne piste de marchands à travers les bois lorsqu'un brouillard surnaturel et soudain a effacé tout repère. Les arbres semblent avoir bougé autour de vous, refermant leurs branches comme des griffes. Vous réalisez que vous tournez en rond depuis des heures et que les bruits de la faune ont totalement cessé...",
            "Engagés pour traquer une bête enragée ou retrouver un enfant égaré, vous vous êtes enfoncés loin sous la canopée sombre. Vos provisions s'amenuisent et une étrange mélodie portée par le vent semble vous attirer vers le cœur de ce bois dense...",
        ],
    },
    "swamp": {
        "name_fr": "Marécage fétide",
        "scene_theme": "swamp",
        "places": [
            "les rives de sédiments d'un marais putride",
            "une cabane sur pilotis abandonnée au milieu des roseaux",
            "un chemin de planches pourries traversant une tourbière",
            "une mangrove aux eaux stagnantes et sombres",
        ],
        "weather_options": [
            "Brouillard toxique vert",
            "Brume dense",
            "Pluie lourde et acide",
            "Chaleur moite étouffante",
        ],
        "prologues": [
            "Votre guide local a été happé en silence au milieu de la nuit par une créature tapie sous les eaux noires. Sans sa lanterne et sa carte, vous avez erré à l'aveugle, enfonçant vos bottes dans la vase fétide, poursuivis par des feux follets dansants à la lisière de votre vision...",
            "Fuyant la colère d'un seigneur local ou d'une horde de mercenaires, vous n'avez eu d'autre choix que de vous jeter dans ces marais réputés maudits. Vos poursuivants ont rebroussé chemin, terrifiés par les légendes locales, vous laissant seuls face à la brume verte et étouffante...",
        ],
    },
    "desert": {
        "name_fr": "Désert aride",
        "scene_theme": "desert",
        "places": [
            "le sommet d'une dune de sable brûlant",
            "les ruines à demi ensablées d'une oasis asséchée",
            "un canyon de roche rouge aride",
            "les abords d'un squelette de titan pétrifié",
        ],
        "weather_options": [
            "Chaleur écrasante",
            "Vent de sable violent",
            "Soleil de plomb",
            "Nuit polaire désertique",
        ],
        "prologues": [
            "La dernière tempête de sable a complètement balayé votre campement et enseveli votre chameau de bât contenant vos réserves d'eau. La gorge sèche et les yeux irrités par la poussière de verre, vous marchez depuis l'aube en cherchant désespérément une silhouette à l'horizon, jusqu'à ce que vos pas butent contre...",
            "Poursuivant la légende d'une cité d'or engloutie sous les sables, vous avez bravé la chaleur mortelle des dunes. Vos gourdes sont presque vides, mais les reflets métalliques d'anciennes structures émergeant du sable raniment votre espoir...",
        ],
    },
    "mountain": {
        "name_fr": "Montagne escarpée",
        "scene_theme": "mountain",
        "places": [
            "un col rocheux exposé aux vents",
            "le flanc d'une falaise abrupte",
            "le surplomb de gorges profondes",
            "les ruines d'un guetteur de pierre d'altitude",
        ],
        "weather_options": [
            "Vent violent",
            "Froid glacial",
            "Blizzard mordant",
            "Brouillard d'altitude opaque",
        ],
        "prologues": [
            "Le sentier escarpé s'est effondré dans un fracas de tonnerre juste derrière vous, manquant de vous emporter dans l'abîme. Le vent hurle et la température chute rapidement alors que le soleil décline. Vous êtes bloqués sur cette corniche rocheuse avec pour seule option de continuer vers les cimes...",
            "Vous escaladiez ce massif à la recherche d'un monastère reclus abritant des secrets anciens. La météo a brutalement tourné en un orage violent de grêle et d'éclairs, vous obligeant à vous abriter à la hâte dans ces ruines de pierre suspendues au-dessus du vide...",
        ],
    },
    "coastal": {
        "name_fr": "Rivage sauvage",
        "scene_theme": "coastal",
        "places": [
            "une crique de galets noirs entourée de falaises",
            "la carcasse échouée d'un drakkar",
            "un promontoire rocheux surplombant une mer démontée",
            "une plage de sable gris battue par l'écume",
        ],
        "weather_options": [
            "Tempétueux",
            "Brume marine dense",
            "Pluie battante et vent marin",
            "Calme et ensoleillé",
        ],
        "prologues": [
            "Votre navire a sombré corps et biens après avoir heurté un récif acéré dissimulé par la brume marine. Ballottés par les vagues glaciales, vous avez lutté toute la nuit pour ne pas couler. Vous reprenez conscience ce matin, trempés et épuisés, échoués sur ce rivage hostile jonché de débris...",
            "Vous avez navigué jusqu'à cette île isolée à bord d'une petite barque de pêche afin d'élucider le mystère d'un phare éteint. Mais à peine aviez-vous posé le pied sur le rivage qu'une vague scélérate a emporté votre embarcation, vous coupant tout moyen de retour...",
        ],
    },
    "cave": {
        "name_fr": "Grotte naturelle",
        "scene_theme": "cave",
        "places": [
            "une caverne de stalactites étincelantes",
            "une faille souterraine où gronde une cascade",
            "une grotte côtière inondée à marée haute",
            "un réseau de galeries étroites et humides",
        ],
        "weather_options": [
            "Air stagnant",
            "Courant d'air siffleur",
            "Humidité glaciale",
            "Obscurité totale",
        ],
        "prologues": [
            "Réfugiés dans cette caverne pour échapper à un prédateur aérien ou à un éboulement de falaise, vous vous êtes enfoncés plus profondément pour trouver une sortie alternative. Vos pas résonnent étrangement dans ces galeries calcaires humides et vous commencez à percevoir un souffle régulier et lourd venant des profondeurs...",
            "À la recherche d'une veine de cristaux magiques ou fuyant des brigands, vous avez rampé à travers des boyaux étroits. Vous débouchez enfin dans cette grande salle souterraine, mais vos torches éclairent des ossements disposés en cercle par une main intelligente...",
        ],
    },
    "plains": {
        "name_fr": "Plaines herbeuses",
        "scene_theme": "plains",
        "places": [
            "une colline herbeuse surplombant la vallée",
            "le milieu d'une prairie de hautes herbes",
            "les abords d'un tumulus de pierres anciennes",
            "une route de terre battue traversant des champs abandonnés",
        ],
        "weather_options": [
            "Calme",
            "Vent vif",
            "Orage menaçant à l'horizon",
            "Brume matinale",
            "Soleil radieux",
        ],
        "prologues": [
            "Votre caravane marchande a été pillée et incendiée sous vos yeux par des cavaliers nomades. Laissés pour morts au milieu de ces plaines herbeuses immenses, vous vous relevez péniblement. Le vent fait onduler les herbes hautes comme une mer verte, et vous devez rapidement trouver de l'aide avant la nuit...",
            "Vous escortiez un messager important à travers les plaines lorsque celui-ci a été abattu d'une flèche noire tirée depuis les herbes hautes. Avant de mourir, il vous a confié une sacoche scellée de cire rouge en vous suppliant de la mener à destination. Vous vous retrouvez seuls au milieu du chemin...",
        ],
    },
}

GENERIC_HOOKS = [
    "Le groupe vient d'échapper de justesse à une patrouille hostile et doit trouver refuge.",
    "Une rumeur tenace indique qu'un artefact puissant ou un trésor précieux est caché tout près.",
    "Un message cryptique sur un morceau de parchemin ensanglanté vous a menés jusqu'à ce point précis.",
    "Le guide qui vous accompagnait a disparu durant la nuit, vous laissant seuls face à l'inconnu.",
    "Des bruits étranges et des vibrations sous le sol font craindre un danger imminent dans la zone.",
    "Une étrange anomalie magique semble perturber vos sens et déformer la boussole.",
]

PRESETS = {
    "pangee_romain": {
        "name_fr": "Pangée & Empire Romain (Grimdark)",
        "tone": "sombre et politique",
        "scene_theme": "rocky",
        "weather": "Pluie de cendres froides sous un ciel de plomb",
        "location_place": "les ruines d'un majestueux aqueduc de l'ancien Empire",
        "location_region": "les marches frontalières de Pangée",
        "description": "Un avant-poste minéral marqué par la rigueur impériale romaine.",
        "prologues": [
            "Enrôlés comme mercenaires et éclaireurs par le centurion Marcus de la Troisième Légion, vous escortiez un convoi de ravitaillement militaire à travers les Marches Frontalières de Pangée. Mais au milieu de la nuit, une attaque éclair d'insurgés locaux a décimé l'arrière-garde et dispersé les chevaux. Séparés de la colonne impériale, vous vous retrouvez seuls, à court de provisions, au pied de ces pierres centenaires...",
            "À la recherche des secrets perdus de la magie de l'Ancien Empire, vous avez arpenté les anciennes voies pavées romaines en ruine. Une carte cryptique achetée à un mendiant de la capitale vous a guidés jusqu'ici. Après des jours de marche sous une pluie de cendres étouffante, le tracé s'arrête net devant ces structures impériales déchues...",
        ],
        "opening_brief_template": (
            "HISTORIQUE ET PROLOGUE DE DÉPART (D'où on vient, pourquoi on est là) :\n"
            "{prologue}\n\n"
            "DÉCOR ET AMBIANCE : L'atmosphère est mature, sombre et 'grimdark' (Pangée). "
            "Le décor est marqué par une esthétique romaine impériale (ruines de thermes en marbre fêlé, "
            "aqueducs déchus, voies pavées rectilignes, garnisons austères). La magie y est rare et redoutée.\n"
            "DIRECTIVES DE NARRATION :\n"
            "- Exploite richement l'historique fourni ci-dessus pour donner du poids et du sens à l'arrivée du groupe dans la scène.\n"
            "- Mets en avant les dilemmes éthiques sérieux, la décadence politique et l'usure du monde.\n"
            "- Ne commence JAMAIS dans une taverne classique ou autour d'un feu de camp en forêt.\n"
            "- Sois assertif et affirmatif : improvise le cadre sans poser de questions hors-jeu de conception."
        ),
    },
    "jungle_dinos": {
        "name_fr": "Jungle & Ruines Oubliées (Exploration & Dinos)",
        "tone": "survie et exploration sauvage",
        "scene_theme": "swamp",
        "weather": "Chaleur moite écrasante sous une pluie tropicale battante",
        "location_place": "les ruines d'un temple de pierre dévoré par les lianes",
        "location_region": "la péninsule oubliée des dieux serpents",
        "description": "Une jungle tropicale étouffante peuplée de bêtes préhistoriques.",
        "prologues": [
            "Votre navire d'exploration, le 'Dauphin de Nacre', a été pris dans une tempête tropicale d'une violence surnaturelle et s'est fracassé contre les récifs coralliens de la péninsule. Seuls survivants du naufrage, vos corps meurtris et trempés ont été rejetés par les vagues sur une plage de sable noir. N'ayant plus aucun équipement de navigation, vous n'avez d'autre choix que de vous enfoncer dans cette jungle étouffante d'où s'élèvent des cris bestiaux préhistoriques...",
            "Engagés par un érudit de l'université pour retrouver la trace d'une expédition archéologique disparue, vous avez pénétré les territoires sauvages des dieux serpents. Après des jours de marche épuisante à vous frayer un chemin à la machette sous une chaleur de plomb et une humidité suffocante, vous découvrez enfin des traces d'activité humaine...",
        ],
        "opening_brief_template": (
            "HISTORIQUE ET PROLOGUE DE DÉPART (D'où on vient, pourquoi on est là) :\n"
            "{prologue}\n\n"
            "DÉCOR ET AMBIANCE : Une jungle primitive, moite et suffocante. Les arbres géants bloquent le ciel. "
            "Des bêtes préhistoriques (dinosaures du SRD comme des raptors ou des ptéranodons) rôdent. "
            "Des ruines de civilisations de serpents (Yuan-ti) émergent de la boue.\n"
            "DIRECTIVES DE NARRATION :\n"
            "- Exploite richement l'historique fourni ci-dessus pour donner du poids et du sens à l'arrivée du groupe dans la scène.\n"
            "- Insiste sur la survie face à une nature impitoyable (déshydratation, prédateurs géants, maladies).\n"
            "- Décris les bruits primitifs, les lianes étouffantes, l'odeur d'humus et de chair en décomposition.\n"
            "- Propose immédiatement des affordances d'exploration (un nid géant, des pistes fraîches de dinosaures, "
            "des ruines gravées de glyphes serpentins)."
        ),
    },
    "toundra_gelee": {
        "name_fr": "Toundra des Glaces Éternelles (Survie Polaire)",
        "tone": "survie extrême et isolement",
        "scene_theme": "mountain",
        "weather": "Froid glacial et blizzard mordant sous une nuit polaire éternelle",
        "location_place": "un abri de pierre précaire entouré de pics gelés",
        "location_region": "la Toundra des Glaces Éternelles",
        "description": "Une étendue gelée désolée où le vent hurle sans fin.",
        "prologues": [
            "Voyageant à bord d'un grand traîneau à chiens à travers le désert blanc, vous avez été surpris par un blizzard d'une violence inouïe. Les bêtes de trait, paniquées par le hurlement des loups arctiques, ont brisé leurs liens et se sont enfuies dans la tempête, emportant la majeure partie de vos rations. La nuit polaire s'est installée, et le froid commence à geler vos doigts alors que vous apercevez un abri précaire...",
            "Les légendes parlent d'une veine d'argent magique cachée sous les glaciers du grand nord. Poussés par l'espoir de faire fortune, vous avez gravi le col. Mais une avalanche soudaine a bloqué la gorge derrière vous, vous coupant de toute retraite et vous laissant isolés dans la toundra blanche avec pour seul espoir de continuer vers l'inconnu...",
        ],
        "opening_brief_template": (
            "HISTORIQUE ET PROLOGUE DE DÉPART (D'où on vient, pourquoi on est là) :\n"
            "{prologue}\n\n"
            "DÉCOR ET AMBIANCE : Un grand nord glacial et hostile. La nuit polaire y est éternelle. "
            "La neige et la glace recouvrent tout. Les rares communautés se regroupent frileusement "
            "autour de braseros. Des monstres du froid du SRD (yétis, géants du givre, loups arctiques) rôdent.\n"
            "DIRECTIVES DE NARRATION :\n"
            "- Exploite richement l'historique fourni ci-dessus pour donner du poids et du sens à l'arrivée du groupe dans la scène.\n"
            "- Insiste sur la morsure implacable du gel, l'isolement extrême et le silence étouffant de la neige.\n"
            "- Les personnages doivent ressentir l'engourdissement de leurs membres et la buée gelant sur leurs cils.\n"
            "- Ne tolère aucune taverne chaleureuse : le départ se fait dans le froid vif avec une urgence de feu ou d'abri."
        ),
    },
    "brume_gothique": {
        "name_fr": "Domaine de la Brume Éternelle (Horreur Gothique)",
        "tone": "angoisse, mystère et horreur gothique",
        "scene_theme": "forest",
        "weather": "Brouillard épais et glacial limitant la visibilité à quelques mètres",
        "location_place": "un vieux cimetière abandonné aux grilles rouillées",
        "location_region": "le Domaine de la Brume",
        "description": "Une contrée maudite plongée dans une nuit brumeuse perpétuelle.",
        "prologues": [
            "Alors que vous traversiez en diligence le col de montagne menant à une province isolée, un brouillard anormalement dense et glacial s'est levé. Les chevaux, terrifiés par des ombres mouvantes dans la brume, ont fait une embardée, projetant la voiture dans le ravin. Sortant miraculeusement vivants des débris de bois, vous réalisez que le cocher a disparu et que des hurlements de loups se rapprochent à travers le brouillard...",
            "Chassés de votre précédente contrée par une foule en colère ou fuyant une épidémie mortelle, vous avez marché pendant des jours sans vous arrêter. Le chemin est progressivement devenu sombre, les arbres squelettiques, et une brume glaciale rampante vous a enveloppés, vous faisant perdre tout repère géographique et temporel. Les grilles rouillées de ce vieux cimetière se dessinent devant vous...",
        ],
        "opening_brief_template": (
            "HISTORIQUE ET PROLOGUE DE DÉPART (D'où on vient, pourquoi on est là) :\n"
            "{prologue}\n\n"
            "DÉCOR ET AMBIANCE : Atmosphère d'épouvante classique et d'horreur gothique. Le brouillard "
            "suinte partout, déformant les formes et étouffant les sons. Les forêts sont composées d'arbres "
            "morts noirs comme du charbon. Des créatures maudites (vampires, goules, fantômes, loups-garous) y règnent.\n"
            "DIRECTIVES DE NARRATION :\n"
            "- Exploite richement l'historique fourni ci-dessus pour donner du poids et du sens à l'arrivée du groupe dans la scène.\n"
            "- Crée une tension psychologique lourde. Parle de paranoïa, de superstitions et de malédiction.\n"
            "- Décris les branches squelettiques qui griffent le ciel, les hurlements de loups au loin, "
            "l'impression constante d'être observé par des yeux invisibles.\n"
            "- Offre des affordances d'angoisse immédiate : des tombes fraîches anonymes, un corbeau au regard humain, "
            "un sentier s'enfonçant dans les brumes impénétrables."
        ),
    },
}


def generate_adventure_context(
    preset_id: str | None = None,
    biome_id: str | None = None,
    weather: str | None = None,
    tone: str | None = None,
) -> dict[str, Any]:
    """Compile un contexte d'aventure cohérent et varié à partir de presets ou de tirages aléatoires.

    Retourne un dictionnaire avec toutes les variables physiques et narratives nécessaires au GM.
    """
    # 1. Traitement si Preset d'Univers demandé
    if preset_id and preset_id in PRESETS:
        preset = PRESETS[preset_id]

        # Sélection aléatoire d'un prologue d'univers
        prologue = random.choice(preset["prologues"])

        # Surcharge éventuelle par des choix directs
        final_theme = (
            biome_id
            if (biome_id and biome_id in [b["scene_theme"] for b in BIOMES.values()])
            else preset["scene_theme"]
        )
        final_weather = weather if (weather and weather != "random") else preset["weather"]
        final_tone = tone if (tone and tone != "random") else preset["tone"]

        # Compilation du template
        opening_brief = preset["opening_brief_template"].format(prologue=prologue)

        return {
            "preset_id": preset_id,
            "location_place": preset["location_place"],
            "location_region": preset["location_region"],
            "weather": final_weather,
            "scene_theme": final_theme,
            "tone": final_tone,
            "opening_brief": opening_brief,
        }

    # 2. Traitement Aléatoire / Classique
    # Choix du Biome
    if not biome_id or biome_id == "random":
        chosen_biome_key = random.choice(list(BIOMES.keys()))
    else:
        chosen_biome_key = biome_id if biome_id in BIOMES else "forest"

    biome = BIOMES[chosen_biome_key]

    # Choix du lieu dans le biome
    place = random.choice(biome["places"])

    # Choix de la météo
    if not weather or weather == "random":
        chosen_weather = random.choice(biome["weather_options"])
    else:
        chosen_weather = weather

    # Choix du ton
    if not tone or tone == "random":
        chosen_tone = random.choice(
            ["exploration calme", "mystérieuse et tendue", "héroïque et active", "survie immédiate"]
        )
    else:
        chosen_tone = tone

    # Sélection de l'historique/prologue générique pour le biome
    prologue = random.choice(biome["prologues"])

    # Sélection de l'accroche
    hook = random.choice(GENERIC_HOOKS)

    # Compilation du brief pour le LLM
    brief_text = (
        f"HISTORIQUE ET PROLOGUE DE DÉPART (D'où on vient, pourquoi on est là) :\n"
        f"{prologue}\n\n"
        f"DÉCOR ET AMBIANCE : Scène d'ouverture dans un décor de type {biome['name_fr']}. "
        f"Le lieu exact est {place}. Le climat ou l'atmosphère est : {chosen_weather}.\n"
        f"DIRECTIVES DE NARRATION :\n"
        f"- Le ton de l'aventure est : {chosen_tone}.\n"
        f"- Accroche initiale : {hook}\n"
        f"- Exploite richement l'historique fourni ci-dessus pour donner du poids et du sens à l'arrivée du groupe dans la scène.\n"
        f"- Sois immersif et sensoriel (bruits, odeurs, météo). Sépare bien le contexte (mission) de la perception immédiate (le décor visible).\n"
        f"- Propose au moins trois opportunités immédiates d'interaction (un obstacle physique, un indice mystérieux, une piste)."
    )

    return {
        "preset_id": "classique",
        "location_place": place,
        "location_region": f"les terres sauvages ({chosen_tone})",
        "weather": chosen_weather,
        "scene_theme": biome["scene_theme"],
        "tone": chosen_tone,
        "opening_brief": brief_text,
    }
