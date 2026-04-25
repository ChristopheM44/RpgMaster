// Direction 3 — VUE COMBAT
// Reprend l'ADN éditorial de Direction 3 (récit en mode lecture, hot-seat bar)
// + grille tactique (battlemap) + tracker d'initiative D&D 5.2 SRD
// Tout en français.

const { useState: useStateCombat } = React;

const cc = {
  bg: "#0e0d14",
  bgElev: "#181623",
  surface: "#1f1c2e",
  surfaceRaised: "#2a2640",
  border: "rgba(255, 235, 180, 0.07)",
  borderStrong: "rgba(255, 235, 180, 0.18)",
  text: "#f7ecd0",
  textSoft: "rgba(247, 236, 208, 0.75)",
  textMuted: "rgba(247, 236, 208, 0.5)",
  textDim: "rgba(247, 236, 208, 0.32)",
  gold: "#f0c764",
  goldDeep: "#b88a2a",
  ember: "#ff8247",
  blood: "#e84545",
  arcane: "#c090ff",
  teal: "#4fd8c0",
  green: "#6fd96f",
};

// ────────────────────────────────────────────────────────────────────────
// Données spécifiques au combat (mock D&D 5.2 SRD)
// ────────────────────────────────────────────────────────────────────────

// PJ : reprend MOCK.characters
// PNJ / monstres : ajoutés ici. Issus du SRD 5.2 (Goblin, Hobgoblin, Bugbear, Wolf).
const COMBAT_MONSTERS = [
  { id: "gob1", name: "Gobelin", kind: "monster", token: "G1", color: "#7fa650", species: "Gobelinoïde", cr: "1/4", hp: 5, hpMax: 7, ac: 15, init: 4, x: 8, y: 3 },
  { id: "gob2", name: "Gobelin", kind: "monster", token: "G2", color: "#7fa650", species: "Gobelinoïde", cr: "1/4", hp: 7, hpMax: 7, ac: 15, init: 2, x: 9, y: 5 },
  { id: "hob1", name: "Hobgobelin", kind: "monster", token: "H", color: "#b85a3a", species: "Gobelinoïde", cr: "1/2", hp: 9, hpMax: 11, ac: 18, init: 1, x: 10, y: 4 },
  { id: "wol1", name: "Loup", kind: "monster", token: "L", color: "#6e7488", species: "Bête", cr: "1/4", hp: 11, hpMax: 11, ac: 13, init: 5, x: 7, y: 6 },
];

// Positions des PJ sur la grille (cells)
const PC_POSITIONS = {
  thorvald: { x: 3, y: 4 },
  elara: { x: 2, y: 3 },
  solana: { x: 2, y: 5 },
  shade: { x: 3, y: 6 },
  vael: { x: 3, y: 3 },
};

const PC_INIT = {
  thorvald: 8,
  elara: 18,
  solana: 12,
  shade: 21,
  vael: 17,
};

const NARRATIVE_COMBAT = [
  { id: 1, type: "system", text: "Combat — Round 1" },
  {
    id: 2, type: "narration", speaker: "Maître du jeu",
    text: "L'arche effondrée s'embrase soudain d'une lueur bleutée. Quatre silhouettes vertes surgissent du couloir voisin, lances dressées, accompagnées d'un loup au pelage couleur de cendre. À l'arrière, un hobgobelin en armure de plate hurle un ordre dans une langue gutturale. L'écho du goutte-à-goutte s'éteint, remplacé par le grondement sourd des bottes ferrées sur la pierre.",
  },
  {
    id: 3, type: "roll", speaker: "Initiative",
    text: "Les jets d'initiative sont lancés — Shade ouvre la danse.",
    rolls: [
      { name: "Shade", value: 21, kind: "pc" },
      { name: "Elara", value: 18, kind: "pc" },
      { name: "Vael", value: 17, kind: "pc" },
      { name: "Solana", value: 12, kind: "pc" },
      { name: "Thorvald", value: 8, kind: "pc" },
      { name: "Loup", value: 5, kind: "monster" },
      { name: "Gobelin (1)", value: 4, kind: "monster" },
      { name: "Gobelin (2)", value: 2, kind: "monster" },
      { name: "Hobgobelin", value: 1, kind: "monster" },
    ],
  },
  {
    id: 4, type: "action", speaker: "Shade",
    text: "Je me glisse dans l'ombre d'une colonne, vise le gobelin le plus proche et décoche une dague.",
  },
  {
    id: 5, type: "roll", speaker: "Jet d'attaque",
    text: "Dague — attaque sournoise (Dextérité)",
    dice: [{ label: "1d20+5", value: 17, hit: true }, { label: "Dégâts", value: "1d4+3+2d6", total: 12 }],
  },
  {
    id: 6, type: "narration", speaker: "Maître du jeu",
    text: "La lame siffle dans la pénombre et se fiche entre les côtes du gobelin. Il s'effondre sur un genou, le souffle court. Un filet de sang noir coule sur sa tunique de cuir.",
  },
];

// Ordre d'initiative consolidé (pj + monstres)
function buildInitiativeOrder() {
  const pcs = MOCK.characters.map(c => ({
    id: c.id, name: c.name, kind: "pc", init: PC_INIT[c.id] ?? 10,
    hp: c.hp, hpMax: c.hpMax, ac: c.ac, ai: c.ai, class: c.class,
  }));
  const monsters = COMBAT_MONSTERS.map(m => ({
    id: m.id, name: m.name, kind: "monster", init: m.init,
    hp: m.hp, hpMax: m.hpMax, ac: m.ac, cr: m.cr, color: m.color, token: m.token,
  }));
  return [...pcs, ...monsters].sort((a, b) => b.init - a.init);
}

// ────────────────────────────────────────────────────────────────────────
// Composant principal
// ────────────────────────────────────────────────────────────────────────

function CombatViewD3() {
  const order = buildInitiativeOrder();
  const [activeId, setActiveId] = useStateCombat("shade"); // tour de Shade
  const [selectedId, setSelectedId] = useStateCombat("vael"); // sélection joueur
  const selectedPC = MOCK.characters.find(c => c.id === selectedId) || MOCK.characters[0];

  return (
    <div style={{
      width: 1440, height: 900,
      background: `radial-gradient(ellipse at top, #2a1320 0%, ${cc.bg} 60%)`,
      color: cc.text,
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: 14, display: "flex", flexDirection: "column",
      overflow: "hidden", position: "relative",
    }}>
      {/* grain dot grid */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)",
        backgroundSize: "24px 24px",
      }} />

      {/* ─── Header ─── */}
      <header style={{
        height: 60, display: "flex", alignItems: "center",
        padding: "0 24px",
        borderBottom: `1px solid ${cc.border}`,
        background: `linear-gradient(180deg, ${cc.bgElev}, transparent)`,
        backdropFilter: "blur(8px)",
        gap: 18, position: "relative", zIndex: 2, flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 8,
            background: `linear-gradient(135deg, ${cc.ember}, ${cc.gold})`,
            color: cc.bg, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 17, fontWeight: 700,
            boxShadow: `0 0 20px rgba(255, 130, 71, 0.3)`,
          }}>⚔</div>
          <div>
            <div style={{ fontFamily: "'Cinzel', serif", fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>RPGMASTER</div>
            <div style={{ fontSize: 10, color: cc.textDim, letterSpacing: 1 }}>CHAPITRE I — CORRIDOR DES BRUMES</div>
          </div>
        </div>

        <span style={{ color: cc.textDim, fontSize: 13, marginLeft: 4 }}>/</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: cc.textMuted }}>
          <span>Lobby</span>
          <span style={{ color: cc.textDim }}>›</span>
          <span>Les Brumes du Hinterland</span>
          <span style={{ color: cc.textDim }}>›</span>
          <span style={{ color: cc.gold, fontWeight: 600 }}>Combat</span>
        </div>

        <div style={{ flex: 1 }} />

        {/* Combat status chip */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "7px 14px",
          background: `linear-gradient(135deg, rgba(232,69,69,0.18), rgba(232,69,69,0.05))`,
          border: `1px solid rgba(232,69,69,0.4)`,
          borderRadius: 999, fontSize: 12,
          boxShadow: `0 0 16px rgba(232,69,69,0.15)`,
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: 4, background: cc.blood,
            boxShadow: `0 0 8px ${cc.blood}`,
          }} />
          <span style={{ color: cc.textMuted, textTransform: "uppercase", letterSpacing: 1, fontSize: 10 }}>Phase</span>
          <span style={{ fontWeight: 700, color: cc.blood, letterSpacing: 0.5, textTransform: "uppercase" }}>COMBAT</span>
          <span style={{ color: "rgba(232,69,69,0.4)" }}>·</span>
          <span style={{ color: cc.textMuted, textTransform: "uppercase", letterSpacing: 1, fontSize: 10 }}>Round</span>
          <span style={{ fontWeight: 700, color: cc.text, fontFamily: "'JetBrains Mono', monospace" }}>1</span>
          <span style={{ color: "rgba(232,69,69,0.4)" }}>·</span>
          <span style={{ color: cc.textMuted, textTransform: "uppercase", letterSpacing: 1, fontSize: 10 }}>Tour</span>
          <span style={{ fontWeight: 700, color: cc.gold }}>Shade</span>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <HeaderBtnC icon="◐" label="TOUR SUIVANT" color={cc.gold} primary />
          <HeaderBtnC icon="✕" label="FIN DE COMBAT" color="#8a8470" />
        </div>
      </header>

      {/* ─── Main ─── */}
      <div style={{ flex: 1, display: "flex", minHeight: 0, position: "relative", zIndex: 1 }}>

        {/* LEFT — Initiative tracker */}
        <aside style={{
          width: 260, display: "flex", flexDirection: "column",
          borderRight: `1px solid ${cc.border}`,
          background: cc.bgElev, flexShrink: 0,
        }}>
          <div style={{ padding: "18px 18px 10px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
              <span style={{ color: cc.ember, fontSize: 11 }}>✦</span>
              <h3 style={{
                fontFamily: "'Cinzel', serif", fontSize: 12, fontWeight: 700,
                color: cc.text, margin: 0, letterSpacing: 2, textTransform: "uppercase",
              }}>Initiative</h3>
            </div>
            <div style={{ fontSize: 10, color: cc.textDim, fontFamily: "'Fraunces', Georgia, serif", fontStyle: "italic" }}>
              Ordre des tours de ce round
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "0 12px 16px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {order.map((u, i) => (
                <InitiativeRow
                  key={u.id} unit={u} index={i + 1}
                  active={u.id === activeId}
                  selected={u.id === selectedId}
                  onClick={() => setSelectedId(u.id)}
                />
              ))}
            </div>

            {/* Round actions */}
            <div style={{
              marginTop: 16, padding: 12,
              background: cc.surface, border: `1px solid ${cc.border}`,
              borderRadius: 8,
            }}>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: cc.textMuted, textTransform: "uppercase", marginBottom: 8 }}>
                ✦ Round
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button style={smallBtnC(cc.gold)}>+ Allié</button>
                <button style={smallBtnC(cc.blood)}>+ Ennemi</button>
              </div>
              <button style={{
                width: "100%", marginTop: 6, padding: "7px 0",
                background: "transparent",
                border: `1px solid ${cc.border}`,
                borderRadius: 5, color: cc.textSoft,
                fontSize: 10, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase",
                cursor: "pointer",
              }}>↻ Relancer initiative</button>
            </div>
          </div>
        </aside>

        {/* CENTER — Récit + Battlemap */}
        <section style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

          {/* Battlemap */}
          <div style={{
            flexShrink: 0,
            borderBottom: `1px solid ${cc.borderStrong}`,
            background: `linear-gradient(180deg, #0a0810, #110d18)`,
            padding: "16px 24px",
            position: "relative",
          }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 10 }}>
              <span style={{ fontFamily: "'Cinzel', serif", color: cc.ember, fontSize: 12, letterSpacing: 3 }}>✦</span>
              <h2 style={{
                fontFamily: "'Cinzel', serif", fontSize: 14, fontWeight: 700,
                color: cc.text, margin: 0, letterSpacing: 2, textTransform: "uppercase",
              }}>Champ de bataille</h2>
              <span style={{ fontSize: 10, color: cc.textDim, fontFamily: "'Fraunces', Georgia, serif", fontStyle: "italic" }}>
                Corridor des Brumes — 1 case = 1,5m
              </span>
              <div style={{ flex: 1 }} />
              <div style={{ display: "flex", gap: 6 }}>
                <MapTool icon="✥" label="Déplacer" />
                <MapTool icon="📏" label="Mesurer" />
                <MapTool icon="⊕" label="Aire" />
                <MapTool icon="⛶" label="Plein écran" />
              </div>
            </div>

            <Battlemap
              activeId={activeId}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>

          {/* Récit */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ padding: "18px 56px 0", display: "flex", alignItems: "baseline", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <span style={{ fontFamily: "'Cinzel', serif", color: cc.ember, fontSize: 13, letterSpacing: 3 }}>✦</span>
                <h1 style={{
                  fontFamily: "'Cinzel', serif", fontSize: 22, fontWeight: 700,
                  color: cc.text, margin: 0, letterSpacing: 1,
                }}>RÉCIT</h1>
              </div>
              <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${cc.borderStrong}, transparent)` }} />
              <span style={{ fontSize: 11, color: cc.textMuted, letterSpacing: 1, textTransform: "uppercase" }}>
                Round 1 — Tour de Shade
              </span>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "16px 56px 12px" }}>
              <div style={{ maxWidth: 720, margin: "0 auto" }}>
                {NARRATIVE_COMBAT.map(entry => <CombatLogEntry key={entry.id} entry={entry} />)}
              </div>
            </div>

            {/* Composer */}
            <div style={{ padding: "10px 56px 14px", borderTop: `1px solid ${cc.border}`, background: cc.bgElev, flexShrink: 0 }}>
              <div style={{ maxWidth: 820, margin: "0 auto" }}>
                <div style={{
                  border: `1px solid ${cc.borderStrong}`,
                  borderRadius: 12, background: cc.surface,
                  boxShadow: `0 4px 24px rgba(0,0,0,0.4), 0 0 0 1px rgba(232, 69, 69, 0.04) inset`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 14px 2px" }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: 6,
                      background: `linear-gradient(135deg, ${cc.arcane}, #7050b0)`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontWeight: 700, fontSize: 11, color: cc.bg,
                      fontFamily: "'Cinzel', serif",
                    }}>S</div>
                    <span style={{ fontSize: 11, color: cc.textMuted }}>
                      Vous incarnez <strong style={{ color: cc.gold }}>Shade</strong> — c'est votre tour (Action · Mouvement · Action bonus)
                    </span>
                  </div>
                  <textarea
                    placeholder="Décrivez votre action de combat, tactique ou intention…"
                    rows={2}
                    style={{
                      width: "100%", resize: "none",
                      border: "none", outline: "none",
                      padding: "2px 14px 8px",
                      fontFamily: "'Fraunces', Georgia, serif", fontSize: 15,
                      color: cc.text, background: "transparent",
                      lineHeight: 1.5,
                    }}
                  />
                  <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "6px 10px", borderTop: `1px solid ${cc.border}` }}>
                    <ActionChip icon="⚔" label="Attaquer" color={cc.blood} />
                    <ActionChip icon="✦" label="Sort" color={cc.arcane} />
                    <ActionChip icon="💨" label="Foncer" color={cc.teal} />
                    <ActionChip icon="◈" label="Esquive" color={cc.gold} />
                    <ActionChip icon="👁" label="Préparer" color={cc.textMuted} />
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 10, color: cc.textDim, marginRight: 8 }}>
                      Action · Mouv. 9m · Bonus
                    </span>
                    <button style={{
                      padding: "7px 18px",
                      background: `linear-gradient(135deg, ${cc.ember}, ${cc.gold})`,
                      color: cc.bg, border: "none", borderRadius: 6,
                      fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
                      cursor: "pointer",
                      boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
                    }}>Lancer ⏎</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* RIGHT — Detail panel (selected token) */}
        <aside style={{
          width: 320, display: "flex", flexDirection: "column",
          borderLeft: `1px solid ${cc.border}`,
          background: cc.bgElev, flexShrink: 0,
        }}>
          <SelectedDetail selectedId={selectedId} />
        </aside>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Battlemap — grille tactique
// ────────────────────────────────────────────────────────────────────────

function Battlemap({ activeId, selectedId, onSelect }) {
  const COLS = 14;
  const ROWS = 9;
  const CELL = 42;

  const tokens = [
    ...MOCK.characters.map(c => ({
      id: c.id, kind: "pc", name: c.name, label: c.name[0],
      ai: c.ai, hp: c.hp, hpMax: c.hpMax,
      ...PC_POSITIONS[c.id],
    })),
    ...COMBAT_MONSTERS.map(m => ({
      id: m.id, kind: "monster", name: m.name, label: m.token,
      color: m.color, hp: m.hp, hpMax: m.hpMax,
      x: m.x, y: m.y,
    })),
  ];

  return (
    <div style={{
      width: COLS * CELL, height: ROWS * CELL,
      position: "relative",
      margin: "0 auto",
      borderRadius: 8,
      border: `1px solid ${cc.borderStrong}`,
      background: `
        linear-gradient(135deg, #1a1a26 0%, #0e0e16 100%)
      `,
      overflow: "hidden",
      boxShadow: `inset 0 0 60px rgba(0,0,0,0.7), 0 6px 24px rgba(0,0,0,0.5)`,
    }}>
      {/* Atmospheric background : fog patches & corridor walls */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `
          radial-gradient(ellipse 120px 60px at 20% 30%, rgba(192,144,255,0.08), transparent 70%),
          radial-gradient(ellipse 160px 80px at 75% 70%, rgba(79,216,192,0.06), transparent 70%),
          radial-gradient(ellipse 100px 50px at 60% 20%, rgba(255,130,71,0.05), transparent 70%)
        `,
      }} />

      {/* Walls (decorative) */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: CELL,
        background: `repeating-linear-gradient(90deg, rgba(40,30,30,0.6), rgba(40,30,30,0.6) 12px, rgba(70,50,50,0.4) 12px, rgba(70,50,50,0.4) 24px)`,
        borderBottom: `1px solid rgba(0,0,0,0.6)`,
      }} />
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: CELL,
        background: `repeating-linear-gradient(90deg, rgba(40,30,30,0.6), rgba(40,30,30,0.6) 12px, rgba(70,50,50,0.4) 12px, rgba(70,50,50,0.4) 24px)`,
        borderTop: `1px solid rgba(0,0,0,0.6)`,
      }} />

      {/* Grid lines */}
      <svg width={COLS * CELL} height={ROWS * CELL} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {Array.from({ length: COLS + 1 }).map((_, i) => (
          <line key={`v${i}`} x1={i * CELL} y1={0} x2={i * CELL} y2={ROWS * CELL} stroke="rgba(255,235,180,0.06)" strokeWidth={1} />
        ))}
        {Array.from({ length: ROWS + 1 }).map((_, i) => (
          <line key={`h${i}`} x1={0} y1={i * CELL} x2={COLS * CELL} y2={i * CELL} stroke="rgba(255,235,180,0.06)" strokeWidth={1} />
        ))}
      </svg>

      {/* Decorative obstacles */}
      <div style={{
        position: "absolute", left: 5 * CELL, top: 4 * CELL,
        width: CELL, height: CELL,
        background: "radial-gradient(circle, #2a2024 0%, #15101a 80%)",
        border: "1px solid rgba(0,0,0,0.6)",
        borderRadius: 4,
        boxShadow: "inset 0 0 12px rgba(0,0,0,0.7)",
      }}>
        <div style={{
          position: "absolute", inset: 0, display: "flex",
          alignItems: "center", justifyContent: "center",
          fontSize: 18, color: "rgba(255,235,180,0.2)",
        }}>▲</div>
      </div>
      <div style={{
        position: "absolute", left: 6 * CELL, top: 2 * CELL,
        width: CELL, height: CELL * 1,
        background: "radial-gradient(circle, #2a2024 0%, #15101a 80%)",
        border: "1px solid rgba(0,0,0,0.6)",
        borderRadius: 4,
      }} />

      {/* Glowing rune (objective) */}
      <div style={{
        position: "absolute",
        left: 11 * CELL + CELL * 0.2, top: 4 * CELL + CELL * 0.2,
        width: CELL * 0.6, height: CELL * 0.6,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${cc.arcane}80, ${cc.arcane}20 60%, transparent)`,
        boxShadow: `0 0 16px ${cc.arcane}, 0 0 30px ${cc.arcane}80`,
      }} />

      {/* Coords (subtle) */}
      <div style={{
        position: "absolute", top: 4, left: 4,
        fontSize: 9, color: cc.textDim,
        fontFamily: "'JetBrains Mono', monospace",
      }}>A1</div>

      {/* Tokens */}
      {tokens.map(tok => (
        <Token
          key={tok.id} token={tok} cell={CELL}
          active={tok.id === activeId}
          selected={tok.id === selectedId}
          onClick={() => onSelect(tok.id)}
        />
      ))}

      {/* Movement indicator (Shade can move 9m = 6 cases) — subtle ring */}
      <div style={{
        position: "absolute",
        left: PC_POSITIONS.shade.x * CELL + CELL / 2 - CELL * 6,
        top: PC_POSITIONS.shade.y * CELL + CELL / 2 - CELL * 6,
        width: CELL * 12, height: CELL * 12,
        borderRadius: "50%",
        border: `1px dashed ${cc.gold}40`,
        pointerEvents: "none",
        opacity: 0.6,
      }} />
    </div>
  );
}

function Token({ token, cell, active, selected, onClick }) {
  const isPC = token.kind === "pc";
  const baseColor = isPC
    ? (token.ai ? cc.arcane : cc.ember)
    : (token.color || cc.blood);

  const ring = active ? cc.gold : selected ? cc.text : "transparent";

  return (
    <div
      onClick={onClick}
      style={{
        position: "absolute",
        left: token.x * cell + 4, top: token.y * cell + 4,
        width: cell - 8, height: cell - 8,
        borderRadius: "50%",
        background: isPC
          ? `radial-gradient(circle at 30% 30%, ${baseColor}, ${baseColor}cc 60%, ${baseColor}99)`
          : `radial-gradient(circle at 30% 30%, ${baseColor}, ${baseColor}cc 60%, #20141a)`,
        border: `2px solid ${isPC ? cc.gold : "rgba(0,0,0,0.6)"}`,
        boxShadow: active
          ? `0 0 0 2px ${cc.gold}, 0 0 18px ${cc.gold}, inset 0 -6px 10px rgba(0,0,0,0.4)`
          : selected
            ? `0 0 0 2px ${cc.text}, 0 0 12px rgba(247,236,208,0.3), inset 0 -6px 10px rgba(0,0,0,0.4)`
            : `inset 0 -6px 10px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.6)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer",
        zIndex: active ? 5 : selected ? 4 : 2,
      }}
    >
      <span style={{
        fontFamily: "'Cinzel', serif", fontWeight: 700,
        fontSize: 14, color: isPC ? cc.bg : cc.text,
        textShadow: isPC ? "none" : "0 1px 2px rgba(0,0,0,0.8)",
        lineHeight: 1,
      }}>{token.label}</span>

      {/* Mini HP bar under token */}
      <div style={{
        position: "absolute", bottom: -8, left: 2, right: 2,
        height: 3, borderRadius: 2,
        background: "rgba(0,0,0,0.7)",
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%",
          width: `${(token.hp / token.hpMax) * 100}%`,
          background: token.hp / token.hpMax > 0.5 ? cc.green : token.hp / token.hpMax > 0.25 ? "#e5b93a" : cc.blood,
        }} />
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Initiative row
// ────────────────────────────────────────────────────────────────────────

function InitiativeRow({ unit, index, active, selected, onClick }) {
  const isPC = unit.kind === "pc";
  const tone = isPC ? (unit.ai ? cc.arcane : cc.ember) : cc.blood;

  return (
    <div onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "8px 10px",
      background: active
        ? `linear-gradient(90deg, rgba(240,199,100,0.18), rgba(240,199,100,0.04))`
        : selected
          ? `rgba(247,236,208,0.05)`
          : "transparent",
      border: `1px solid ${active ? cc.gold : selected ? cc.borderStrong : "transparent"}`,
      borderRadius: 6, cursor: "pointer",
      boxShadow: active ? `0 0 12px rgba(240,199,100,0.15)` : "none",
      position: "relative",
    }}>
      {/* Initiative number */}
      <div style={{
        width: 28, height: 28, borderRadius: 6,
        background: active ? cc.gold : "rgba(0,0,0,0.4)",
        border: `1px solid ${active ? cc.gold : cc.border}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700,
        color: active ? cc.bg : cc.textSoft, flexShrink: 0,
      }}>{unit.init}</div>

      {/* Token */}
      <div style={{
        width: 26, height: 26, borderRadius: "50%",
        background: isPC
          ? `linear-gradient(135deg, ${tone}, ${cc.gold})`
          : `radial-gradient(circle at 30% 30%, ${unit.color || cc.blood}, #20141a)`,
        border: `1.5px solid ${isPC ? cc.gold : "rgba(0,0,0,0.6)"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "'Cinzel', serif", fontWeight: 700,
        fontSize: 11, color: isPC ? cc.bg : cc.text, flexShrink: 0,
      }}>{isPC ? unit.name[0] : (unit.token || unit.name[0])}</div>

      {/* Name + class */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          fontFamily: "'Cinzel', serif", fontSize: 12, fontWeight: 600,
          color: active ? cc.text : cc.textSoft,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {unit.name}
          {isPC && unit.ai && <span style={{ fontSize: 8, color: cc.arcane, fontWeight: 700, letterSpacing: 0.5 }}>IA</span>}
        </div>
        <div style={{ fontSize: 9, color: cc.textDim }}>
          {isPC ? unit.class : `FP ${unit.cr || "—"}`}
        </div>
      </div>

      {/* HP bar mini */}
      <div style={{ width: 50, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
        <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: cc.textMuted }}>
          {unit.hp}/{unit.hpMax}
        </span>
        <div style={{ width: "100%", height: 3, borderRadius: 2, background: "rgba(0,0,0,0.5)", overflow: "hidden" }}>
          <div style={{
            height: "100%", width: `${(unit.hp / unit.hpMax) * 100}%`,
            background: unit.hp / unit.hpMax > 0.5 ? cc.green : unit.hp / unit.hpMax > 0.25 ? "#e5b93a" : cc.blood,
          }} />
        </div>
      </div>

      {active && (
        <div style={{
          position: "absolute", left: -1, top: 6, bottom: 6,
          width: 3, borderRadius: 2,
          background: cc.gold, boxShadow: `0 0 8px ${cc.gold}`,
        }} />
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Selected detail panel
// ────────────────────────────────────────────────────────────────────────

function SelectedDetail({ selectedId }) {
  const pc = MOCK.characters.find(c => c.id === selectedId);
  const monster = COMBAT_MONSTERS.find(m => m.id === selectedId);

  if (pc) return <PCDetail ch={pc} />;
  if (monster) return <MonsterDetail m={monster} />;
  return null;
}

function PCDetail({ ch }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: 18, borderBottom: `1px solid ${cc.border}` }}>
        <div style={{
          position: "relative",
          padding: "14px 14px 12px",
          background: `linear-gradient(180deg, ${cc.surface}, ${cc.bgElev})`,
          border: `1px solid ${cc.borderStrong}`,
          borderRadius: 12, overflow: "hidden",
        }}>
          <div style={{
            position: "absolute", top: -40, right: -40,
            width: 120, height: 120, borderRadius: 60,
            background: `radial-gradient(circle, ${cc.ember}40, transparent 70%)`,
          }} />

          <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 50, height: 50, borderRadius: 10,
              background: `linear-gradient(135deg, ${cc.ember}, ${cc.gold})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 22,
              color: cc.bg,
              boxShadow: `0 0 0 2px ${cc.bgElev}, 0 0 0 3px ${cc.ember}, 0 0 18px rgba(255,130,71,0.4)`,
            }}>{ch.name[0]}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, color: cc.ember, textTransform: "uppercase", marginBottom: 2 }}>
                ◆ Sélection
              </div>
              <div style={{ fontFamily: "'Cinzel', serif", fontSize: 20, fontWeight: 700, color: cc.text, lineHeight: 1.1 }}>
                {ch.name}
              </div>
              <div style={{ fontSize: 11, color: cc.textMuted }}>
                Niv. {ch.level} · {ch.class} · {ch.species}
              </div>
            </div>
          </div>

          <div style={{ position: "relative", marginTop: 12, display: "flex", gap: 6 }}>
            <ChipMini label="PV" value={`${ch.hp}/${ch.hpMax}`} color={cc.green} />
            <ChipMini label="CA" value={ch.ac} color={cc.teal} />
            <ChipMini label="Init." value={`+${PC_INIT[ch.id] >= 18 ? 5 : 3}`} color={cc.gold} />
            <ChipMini label="Vit." value="9m" color={cc.text} />
          </div>

          <div style={{ position: "relative", marginTop: 10 }}>
            <HpBarC cur={ch.hp} max={ch.hpMax} height={8} glow />
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: 18 }}>
        <SectionMini title="Actions">
          <ActionRow icon="⚔" name="Arc long" detail="+5 toucher · 1d8+3 perforants · 45m" tone={cc.blood} />
          <ActionRow icon="⚔" name="Épée courte" detail="+5 toucher · 1d6+3 perforants" tone={cc.blood} />
          <ActionRow icon="✦" name="Marque du chasseur" detail="Bonus · +1d6 dégâts contre la cible" tone={cc.arcane} />
          <ActionRow icon="✦" name="Soin des blessures" detail="Sort niv. 1 · 1d8+3 PV" tone={cc.green} />
        </SectionMini>

        <SectionMini title="Économie d'action">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4 }}>
            <ActionPip label="Action" used={false} />
            <ActionPip label="Bonus" used={false} />
            <ActionPip label="Réaction" used={false} />
          </div>
          <div style={{
            marginTop: 8, padding: "6px 8px",
            background: "rgba(0,0,0,0.3)",
            border: `1px solid ${cc.border}`,
            borderRadius: 5,
            display: "flex", justifyContent: "space-between", alignItems: "center",
            fontSize: 11, color: cc.textSoft,
          }}>
            <span>Mouvement</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", color: cc.gold, fontWeight: 700 }}>9m / 9m</span>
          </div>
        </SectionMini>

        <SectionMini title="Conditions" tone={cc.blood}>
          <div style={{
            padding: "10px 8px", textAlign: "center",
            color: cc.textMuted, fontSize: 11, fontStyle: "italic",
            fontFamily: "'Fraunces', serif",
            border: `1px dashed ${cc.border}`, borderRadius: 6,
          }}>
            Aucune condition active
          </div>
        </SectionMini>
      </div>
    </div>
  );
}

function MonsterDetail({ m }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: 18, borderBottom: `1px solid ${cc.border}` }}>
        <div style={{
          position: "relative",
          padding: "14px 14px 12px",
          background: `linear-gradient(180deg, ${cc.surface}, ${cc.bgElev})`,
          border: `1px solid rgba(232,69,69,0.25)`,
          borderRadius: 12, overflow: "hidden",
        }}>
          <div style={{
            position: "absolute", top: -40, right: -40,
            width: 120, height: 120, borderRadius: 60,
            background: `radial-gradient(circle, ${cc.blood}40, transparent 70%)`,
          }} />

          <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 50, height: 50, borderRadius: "50%",
              background: `radial-gradient(circle at 30% 30%, ${m.color}, #20141a)`,
              border: `2px solid rgba(0,0,0,0.6)`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 18,
              color: cc.text, textShadow: "0 1px 2px rgba(0,0,0,0.8)",
            }}>{m.token}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, color: cc.blood, textTransform: "uppercase", marginBottom: 2 }}>
                ◆ Cible verrouillée
              </div>
              <div style={{ fontFamily: "'Cinzel', serif", fontSize: 20, fontWeight: 700, color: cc.text, lineHeight: 1.1 }}>
                {m.name}
              </div>
              <div style={{ fontSize: 11, color: cc.textMuted }}>
                {m.species} · FP {m.cr}
              </div>
            </div>
          </div>

          <div style={{ position: "relative", marginTop: 12, display: "flex", gap: 6 }}>
            <ChipMini label="PV" value={`${m.hp}/${m.hpMax}`} color={cc.green} />
            <ChipMini label="CA" value={m.ac} color={cc.teal} />
            <ChipMini label="Init." value={`+${m.init}`} color={cc.gold} />
          </div>

          <div style={{ position: "relative", marginTop: 10 }}>
            <HpBarC cur={m.hp} max={m.hpMax} height={8} glow />
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: 18 }}>
        <SectionMini title="Caractéristiques">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 4 }}>
            {[["FOR", 8], ["DEX", 14], ["CON", 10], ["INT", 10], ["SAG", 8], ["CHA", 8]].map(([k, v]) => {
              const mod = Math.floor((v - 10) / 2);
              return (
                <div key={k} style={{
                  padding: "5px 0",
                  background: "rgba(0,0,0,0.3)",
                  border: `1px solid ${cc.border}`,
                  borderRadius: 4,
                  display: "flex", flexDirection: "column", alignItems: "center",
                }}>
                  <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: 1, color: cc.textDim }}>{k}</span>
                  <span style={{ fontFamily: "'Cinzel', serif", fontSize: 13, fontWeight: 700, color: cc.text, lineHeight: 1 }}>{v}</span>
                  <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: mod >= 0 ? cc.green : cc.blood, fontWeight: 700 }}>{mod >= 0 ? `+${mod}` : mod}</span>
                </div>
              );
            })}
          </div>
        </SectionMini>

        <SectionMini title="Actions" tone={cc.blood}>
          <ActionRow icon="⚔" name="Cimeterre" detail="+4 toucher · 1d6+2 tranchants" tone={cc.blood} />
          <ActionRow icon="🏹" name="Arc court" detail="+4 toucher · 1d6+2 perforants · 24m" tone={cc.blood} />
          <ActionRow icon="💨" name="Repli rusé" detail="Bonus · Se désengager ou se cacher" tone={cc.gold} />
        </SectionMini>

        <SectionMini title="Notes du MJ" tone={cc.arcane}>
          <div style={{
            fontFamily: "'Fraunces', Georgia, serif", fontSize: 12,
            color: cc.textSoft, lineHeight: 1.5, fontStyle: "italic",
          }}>
            Petite créature, mauvais. Embuscade : avantage si surprise.
            Préfère attaquer en groupe et fuir si isolé.
          </div>
        </SectionMini>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Sous-composants
// ────────────────────────────────────────────────────────────────────────

function HpBarC({ cur, max, height = 6, glow }) {
  const pct = Math.max(0, (cur / max) * 100);
  const color = pct > 50 ? cc.green : pct > 25 ? "#e5b93a" : cc.blood;
  return (
    <div style={{ position: "relative", width: "100%", height, borderRadius: height / 2, background: "rgba(0,0,0,0.5)", overflow: "hidden", border: `1px solid rgba(255,255,255,0.04)` }}>
      <div style={{
        position: "absolute", inset: 0, right: "auto",
        width: `${pct}%`, borderRadius: height / 2,
        background: `linear-gradient(90deg, ${color}cc, ${color})`,
        boxShadow: glow ? `0 0 8px ${color}80` : "none",
      }} />
    </div>
  );
}

function HeaderBtnC({ icon, label, color, primary }) {
  return (
    <button style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: "7px 14px",
      background: primary
        ? `linear-gradient(135deg, ${color}, ${cc.ember})`
        : `${color}14`,
      border: primary ? "none" : `1px solid ${color}40`,
      borderRadius: 6,
      color: primary ? cc.bg : color,
      fontSize: 10, fontWeight: 700, letterSpacing: 1,
      cursor: "pointer",
      boxShadow: primary ? `0 2px 12px rgba(255,130,71,0.3)` : "none",
    }}>
      <span style={{ fontSize: 12 }}>{icon}</span>{label}
    </button>
  );
}

function ChipMini({ label, value, color }) {
  return (
    <div style={{
      flex: 1, padding: "5px 6px",
      background: "rgba(0,0,0,0.3)",
      border: `1px solid ${color}30`,
      borderRadius: 5,
      display: "flex", flexDirection: "column", alignItems: "center",
    }}>
      <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: 1, color: cc.textDim }}>{label}</span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color }}>{value}</span>
    </div>
  );
}

function MapTool({ icon, label }) {
  return (
    <button title={label} style={{
      display: "flex", alignItems: "center", gap: 5,
      padding: "5px 9px",
      background: cc.surface,
      border: `1px solid ${cc.border}`,
      borderRadius: 5, color: cc.textSoft,
      fontSize: 10, fontWeight: 600,
      cursor: "pointer",
    }}>
      <span style={{ fontSize: 12 }}>{icon}</span>{label}
    </button>
  );
}

function smallBtnC(color) {
  return {
    flex: 1, padding: "6px 0",
    background: `${color}14`,
    border: `1px solid ${color}40`,
    borderRadius: 5, color,
    fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
    cursor: "pointer",
  };
}

function ActionChip({ icon, label, color }) {
  return (
    <button style={{
      display: "flex", alignItems: "center", gap: 5,
      padding: "5px 9px",
      background: "transparent",
      border: `1px solid ${color}30`,
      borderRadius: 5, color: color === cc.textMuted ? cc.textSoft : color,
      fontSize: 11, fontWeight: 500,
      cursor: "pointer",
    }}>
      <span>{icon}</span>{label}
    </button>
  );
}

function SectionMini({ title, tone, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 8 }}>
        <span style={{ color: tone || cc.ember, fontSize: 9 }}>✦</span>
        <h4 style={{
          fontFamily: "'Cinzel', serif", fontSize: 10, fontWeight: 700,
          color: tone || cc.text, margin: 0, letterSpacing: 2, textTransform: "uppercase",
        }}>{title}</h4>
      </div>
      {children}
    </div>
  );
}

function ActionRow({ icon, name, detail, tone }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 10px",
      background: cc.surface,
      border: `1px solid ${cc.border}`,
      borderRadius: 6,
      marginBottom: 4,
      cursor: "pointer",
    }}>
      <span style={{ color: tone, fontSize: 14 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Cinzel', serif", fontSize: 12, fontWeight: 600, color: cc.text }}>
          {name}
        </div>
        <div style={{ fontSize: 10, color: cc.textMuted, fontFamily: "'JetBrains Mono', monospace" }}>
          {detail}
        </div>
      </div>
    </div>
  );
}

function ActionPip({ label, used }) {
  return (
    <div style={{
      padding: "6px 4px",
      background: used ? "rgba(0,0,0,0.4)" : "rgba(111,217,111,0.10)",
      border: `1px solid ${used ? cc.border : "rgba(111,217,111,0.3)"}`,
      borderRadius: 5,
      display: "flex", flexDirection: "column", alignItems: "center", gap: 1,
    }}>
      <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: 1, color: cc.textDim, textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 11, color: used ? cc.textDim : cc.green, fontWeight: 700 }}>
        {used ? "✕" : "●"}
      </span>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Combat log entries
// ────────────────────────────────────────────────────────────────────────

function CombatLogEntry({ entry }) {
  if (entry.type === "system") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 14, margin: "20px 0 24px" }}>
        <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, transparent, ${cc.blood}80)` }} />
        <span style={{ fontFamily: "'Cinzel', serif", fontSize: 12, color: cc.blood, letterSpacing: 4, textTransform: "uppercase" }}>
          ⚔ {entry.text} ⚔
        </span>
        <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${cc.blood}80, transparent)` }} />
      </div>
    );
  }

  if (entry.type === "narration") {
    return (
      <div style={{ margin: "22px 0" }}>
        <div style={{
          fontFamily: "'Cinzel', serif", fontSize: 10, fontWeight: 700,
          letterSpacing: 2, textTransform: "uppercase",
          color: cc.ember, marginBottom: 8,
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <span>✦</span>{entry.speaker}
        </div>
        <p style={{
          fontFamily: "'Fraunces', Georgia, serif",
          fontSize: 16, lineHeight: 1.6,
          color: cc.text, margin: 0, textWrap: "pretty",
        }}>{entry.text}</p>
      </div>
    );
  }

  if (entry.type === "action") {
    return (
      <div style={{
        margin: "16px 0", padding: "10px 14px",
        background: "rgba(192, 144, 255, 0.06)",
        border: `1px solid rgba(192, 144, 255, 0.25)`,
        borderRadius: 8,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ color: cc.arcane, fontSize: 11 }}>▸</span>
          <span style={{ fontFamily: "'Cinzel', serif", fontSize: 12, fontWeight: 700, color: cc.arcane, letterSpacing: 0.5 }}>
            {entry.speaker}
          </span>
          <span style={{ fontSize: 9, color: cc.arcane, opacity: 0.6, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>
            Action
          </span>
        </div>
        <div style={{ fontSize: 14, color: cc.textSoft, lineHeight: 1.5, paddingLeft: 18, fontFamily: "'Fraunces', Georgia, serif", fontStyle: "italic" }}>
          « {entry.text} »
        </div>
      </div>
    );
  }

  if (entry.type === "roll" && entry.rolls) {
    return (
      <div style={{
        margin: "16px 0", padding: "12px 14px",
        background: cc.surface,
        border: `1px solid ${cc.borderStrong}`,
        borderRadius: 8,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span style={{ color: cc.gold, fontSize: 12 }}>⚄</span>
          <span style={{ fontFamily: "'Cinzel', serif", fontSize: 11, fontWeight: 700, color: cc.gold, letterSpacing: 1.5, textTransform: "uppercase" }}>
            {entry.speaker}
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: cc.textMuted, fontStyle: "italic", fontFamily: "'Fraunces', serif" }}>
            {entry.text}
          </span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {entry.rolls.map((r, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "4px 8px",
              background: "rgba(0,0,0,0.3)",
              border: `1px solid ${r.kind === "pc" ? cc.border : "rgba(232,69,69,0.2)"}`,
              borderRadius: 5,
            }}>
              <span style={{ fontSize: 10, color: r.kind === "pc" ? cc.textSoft : cc.textMuted, fontFamily: "'Cinzel', serif" }}>
                {r.name}
              </span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, color: cc.gold }}>
                {r.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (entry.type === "roll" && entry.dice) {
    return (
      <div style={{
        margin: "12px 0", padding: "10px 14px",
        background: "rgba(232, 69, 69, 0.06)",
        border: `1px solid rgba(232, 69, 69, 0.25)`,
        borderRadius: 8,
        display: "flex", alignItems: "center", gap: 14,
      }}>
        <span style={{ color: cc.blood, fontSize: 14 }}>⚔</span>
        <span style={{ fontFamily: "'Cinzel', serif", fontSize: 11, fontWeight: 700, color: cc.blood, letterSpacing: 1, textTransform: "uppercase" }}>
          {entry.speaker}
        </span>
        <span style={{ flex: 1, fontSize: 12, color: cc.textSoft, fontFamily: "'Fraunces', serif", fontStyle: "italic" }}>
          {entry.text}
        </span>
        {entry.dice.map((d, i) => (
          <div key={i} style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            padding: "4px 10px",
            background: "rgba(0,0,0,0.3)",
            border: `1px solid ${d.hit ? cc.green : cc.border}`,
            borderRadius: 5, minWidth: 56,
          }}>
            <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: 1, color: cc.textDim, textTransform: "uppercase" }}>{d.label}</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700, color: d.hit ? cc.green : cc.gold }}>
              {d.value || d.total}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return null;
}

// ────────────────────────────────────────────────────────────────────────
// Export
// ────────────────────────────────────────────────────────────────────────

window.CombatViewD3 = CombatViewD3;
