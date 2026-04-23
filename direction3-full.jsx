// Direction 3 — FULL APP (Lobby, GameSession, CharacterSheet)
// Audacieuse / éditoriale, appliquée à l'ensemble des vues principales.

const { useState: useStateD3F } = React;

const D3 = {
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

// ═══════════════════════════════════════════════════════════════════════
// Shared chrome : AppShell with top bar
// ═══════════════════════════════════════════════════════════════════════

function AppShellD3({ title, crumbs, right, children, noPadding }) {
  return (
    <div style={{
      width: 1440, height: 900,
      background: `radial-gradient(ellipse at top, #1a1630 0%, ${D3.bg} 60%)`,
      color: D3.text,
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: 14, display: "flex", flexDirection: "column",
      overflow: "hidden", position: "relative",
    }}>
      {/* grid overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)",
        backgroundSize: "24px 24px",
      }} />

      {/* Top bar */}
      <header style={{
        height: 56, display: "flex", alignItems: "center",
        padding: "0 24px",
        borderBottom: `1px solid ${D3.border}`,
        background: `linear-gradient(180deg, ${D3.bgElev}, transparent)`,
        backdropFilter: "blur(8px)",
        gap: 18, position: "relative", zIndex: 2, flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
            color: D3.bg,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, fontWeight: 700,
            boxShadow: `0 0 20px rgba(255, 130, 71, 0.3)`,
          }}>⚔</div>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 15, fontWeight: 700, letterSpacing: 1 }}>RPGMASTER</div>
        </div>

        {crumbs && (
          <>
            <span style={{ color: D3.textDim, fontSize: 13 }}>/</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: D3.textMuted }}>
              {crumbs.map((c, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span style={{ color: D3.textDim }}>›</span>}
                  <span style={{
                    color: i === crumbs.length - 1 ? D3.gold : D3.textMuted,
                    letterSpacing: 0.5, fontWeight: i === crumbs.length - 1 ? 600 : 400,
                  }}>{c}</span>
                </React.Fragment>
              ))}
            </div>
          </>
        )}

        <div style={{ flex: 1 }} />

        {right}
      </header>

      {/* Body */}
      <div style={{ flex: 1, minHeight: 0, position: "relative", zIndex: 1, display: "flex", flexDirection: "column" }}>
        {children}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// LOBBY VIEW
// ═══════════════════════════════════════════════════════════════════════

const MOCK_SESSIONS = [
  { id: "s1", name: "Les Brumes du Hinterland", status: "exploration", updated: "22/04/26 11:12", chars: 5, chapter: "Chapitre I — Au cœur de la taverne" },
  { id: "s2", name: "La Tour d'Ébène", status: "combat", updated: "21/04/26 22:40", chars: 4, chapter: "Chapitre III — L'ascension" },
  { id: "s3", name: "Le Trône de Cendres", status: "level_up", updated: "19/04/26 18:05", chars: 3, chapter: "Chapitre II — Le serment brisé" },
  { id: "s4", name: "Échos d'Aldoria", status: "lobby", updated: "18/04/26 09:30", chars: 0, chapter: "Création en cours" },
  { id: "s5", name: "Le Sang des Anciens", status: "session_end", updated: "05/04/26 23:15", chars: 6, chapter: "Épilogue" },
];

const STATUS_META = {
  lobby: { label: "En attente", color: D3.textMuted, bg: "rgba(247,236,208,0.05)" },
  character_creation: { label: "Création", color: D3.arcane, bg: "rgba(192,144,255,0.10)" },
  exploration: { label: "Exploration", color: D3.green, bg: "rgba(111,217,111,0.10)" },
  combat: { label: "Combat", color: D3.blood, bg: "rgba(232,69,69,0.12)" },
  level_up: { label: "Montée", color: D3.gold, bg: "rgba(240,199,100,0.12)" },
  session_end: { label: "Terminée", color: D3.textDim, bg: "rgba(247,236,208,0.03)" },
};

function LobbyD3() {
  const [selectedId, setSelectedId] = useStateD3F("s1");
  const [draftName, setDraftName] = useStateD3F("");

  return (
    <AppShellD3
      crumbs={["Lobby"]}
      right={
        <>
          <NavPill label="Lobby" active />
          <NavPill label="Campagnes" />
          <NavPill label="Admin" />
          <div style={{ width: 1, height: 22, background: D3.border, margin: "0 4px" }} />
          <div style={{
            display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: D3.textMuted,
          }}>
            <span style={{ width: 7, height: 7, borderRadius: 4, background: D3.green, boxShadow: `0 0 8px ${D3.green}` }} />
            EN LIGNE
          </div>
        </>
      }
    >
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Left: hero + sessions list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "36px 56px 40px", minWidth: 0 }}>
          {/* Hero */}
          <div style={{ marginBottom: 32 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: 3, color: D3.ember,
              textTransform: "uppercase", marginBottom: 6,
            }}>
              ✦ Vos aventures
            </div>
            <h1 style={{
              fontFamily: "'Cinzel', serif", fontSize: 44, fontWeight: 700,
              color: D3.text, margin: "0 0 10px", letterSpacing: 1, lineHeight: 1.1,
            }}>
              Lobby
            </h1>
            <p style={{ fontSize: 15, color: D3.textSoft, margin: 0, fontFamily: "'Fraunces', Georgia, serif", maxWidth: 540 }}>
              Reprenez une partie en cours, ou forgez une nouvelle légende. Votre Maître du Jeu IA vous y attend.
            </p>
          </div>

          {/* New session card */}
          <div style={{
            marginBottom: 32,
            padding: "20px 24px",
            background: `linear-gradient(135deg, rgba(255,130,71,0.08), rgba(240,199,100,0.04))`,
            border: `1px solid ${D3.borderStrong}`,
            borderRadius: 14,
            display: "flex", alignItems: "center", gap: 16,
            position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", top: -60, right: -30,
              width: 180, height: 180, borderRadius: 90,
              background: `radial-gradient(circle, ${D3.ember}20, transparent 70%)`,
              pointerEvents: "none",
            }} />
            <div style={{
              width: 48, height: 48, borderRadius: 10,
              background: `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22, color: D3.bg, flexShrink: 0,
              boxShadow: `0 0 24px rgba(255,130,71,0.3)`,
            }}>✦</div>
            <div style={{ flex: 1, position: "relative" }}>
              <div style={{ fontFamily: "'Cinzel', serif", fontSize: 18, fontWeight: 700, color: D3.text, marginBottom: 2 }}>
                Nouvelle Partie
              </div>
              <div style={{ fontSize: 12, color: D3.textMuted }}>
                Donnez un nom à votre campagne. Le MJ se chargera du reste.
              </div>
            </div>
            <input
              value={draftName}
              onChange={e => setDraftName(e.target.value)}
              placeholder="Nom de la campagne…"
              style={{
                width: 260, padding: "11px 14px",
                background: "rgba(0,0,0,0.35)",
                border: `1px solid ${D3.borderStrong}`,
                borderRadius: 8,
                color: D3.text, fontSize: 14,
                outline: "none", fontFamily: "'Fraunces', Georgia, serif",
                position: "relative",
              }}
            />
            <button style={{
              padding: "11px 22px",
              background: `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
              color: D3.bg, border: "none", borderRadius: 8,
              fontSize: 12, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
              cursor: "pointer",
              boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
              position: "relative",
            }}>Forger ⚔</button>
          </div>

          {/* Section title */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 16 }}>
            <h2 style={{
              fontFamily: "'Cinzel', serif", fontSize: 18, fontWeight: 700,
              color: D3.text, margin: 0, letterSpacing: 2, textTransform: "uppercase",
            }}>Sessions sauvegardées</h2>
            <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${D3.borderStrong}, transparent)` }} />
            <span style={{ fontSize: 11, color: D3.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
              {MOCK_SESSIONS.length} campagnes
            </span>
          </div>

          {/* Sessions list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {MOCK_SESSIONS.map(s => (
              <SessionCard
                key={s.id} session={s}
                selected={selectedId === s.id}
                onSelect={() => setSelectedId(s.id)}
              />
            ))}
          </div>
        </div>

        {/* Right: Session detail panel */}
        <aside style={{
          width: 380, borderLeft: `1px solid ${D3.border}`,
          background: D3.bgElev, padding: 24,
          overflowY: "auto", flexShrink: 0,
        }}>
          <SessionDetail session={MOCK_SESSIONS.find(s => s.id === selectedId) || MOCK_SESSIONS[0]} />
        </aside>
      </div>
    </AppShellD3>
  );
}

function NavPill({ label, active }) {
  return (
    <button style={{
      padding: "6px 14px",
      background: active ? "rgba(240,199,100,0.10)" : "transparent",
      border: `1px solid ${active ? "rgba(240,199,100,0.30)" : "transparent"}`,
      borderRadius: 999,
      color: active ? D3.gold : D3.textMuted,
      fontSize: 12, fontWeight: 600, letterSpacing: 0.5,
      cursor: "pointer",
    }}>{label}</button>
  );
}

function SessionCard({ session, selected, onSelect }) {
  const meta = STATUS_META[session.status] || STATUS_META.lobby;
  return (
    <div onClick={onSelect} style={{
      display: "flex", alignItems: "center", gap: 18,
      padding: "14px 18px",
      background: selected ? `linear-gradient(90deg, rgba(255,130,71,0.10), ${D3.surface})` : D3.surface,
      border: `1px solid ${selected ? D3.ember : D3.border}`,
      borderRadius: 10, cursor: "pointer",
      boxShadow: selected ? `0 0 20px rgba(255,130,71,0.12)` : "none",
    }}>
      {/* Status dot */}
      <div style={{
        width: 10, height: 10, borderRadius: 5,
        background: meta.color,
        boxShadow: session.status === "combat" || session.status === "exploration" ? `0 0 8px ${meta.color}` : "none",
        flexShrink: 0,
      }} />

      {/* Name + chapter */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Cinzel', serif", fontSize: 16, fontWeight: 700, color: D3.text, letterSpacing: 0.5 }}>
          {session.name}
        </div>
        <div style={{ fontSize: 12, color: D3.textMuted, fontStyle: "italic", fontFamily: "'Fraunces', Georgia, serif" }}>
          {session.chapter}
        </div>
      </div>

      {/* Chars */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: D3.textMuted }}>
        <span style={{ color: D3.textDim }}>✦</span>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: D3.textSoft }}>{session.chars}</span>
        <span>perso.</span>
      </div>

      {/* Status chip */}
      <div style={{
        padding: "4px 10px",
        background: meta.bg,
        border: `1px solid ${meta.color}40`,
        borderRadius: 4,
        fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
        color: meta.color, flexShrink: 0, width: 90, textAlign: "center",
      }}>{meta.label}</div>

      {/* Date */}
      <div style={{ fontSize: 10, color: D3.textDim, fontFamily: "'JetBrains Mono', monospace", width: 100, textAlign: "right" }}>
        {session.updated}
      </div>

      {/* CTA */}
      <button style={{
        padding: "7px 16px",
        background: selected ? `linear-gradient(135deg, ${D3.ember}, ${D3.gold})` : "transparent",
        border: selected ? "none" : `1px solid ${D3.borderStrong}`,
        borderRadius: 6,
        color: selected ? D3.bg : D3.gold,
        fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
        cursor: "pointer", flexShrink: 0,
      }}>Rejoindre →</button>
    </div>
  );
}

function SessionDetail({ session }) {
  const meta = STATUS_META[session.status] || STATUS_META.lobby;
  const party = MOCK.characters.slice(0, Math.min(session.chars, MOCK.characters.length));
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 3, color: D3.ember, textTransform: "uppercase", marginBottom: 6 }}>
        ✦ Aperçu
      </div>
      <h2 style={{
        fontFamily: "'Cinzel', serif", fontSize: 24, fontWeight: 700, color: D3.text,
        margin: "0 0 4px", lineHeight: 1.1, letterSpacing: 0.5,
      }}>{session.name}</h2>
      <p style={{
        fontFamily: "'Fraunces', Georgia, serif", fontSize: 14,
        color: D3.textSoft, margin: "0 0 16px", fontStyle: "italic",
      }}>{session.chapter}</p>

      <div style={{
        padding: 12, background: D3.surface, borderRadius: 8, border: `1px solid ${D3.border}`,
        marginBottom: 18,
      }}>
        <InfoRow label="Statut" value={<span style={{ color: meta.color, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, fontSize: 11 }}>{meta.label}</span>} />
        <InfoRow label="Dernière modif." value={session.updated} mono />
        <InfoRow label="Personnages" value={session.chars} mono last />
      </div>

      {/* Party */}
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: D3.textMuted, textTransform: "uppercase", marginBottom: 10 }}>
        Groupe
      </div>
      {party.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {party.map(ch => <MiniCharRow key={ch.id} ch={ch} />)}
        </div>
      ) : (
        <div style={{ padding: 16, textAlign: "center", color: D3.textMuted, fontSize: 12, border: `1px dashed ${D3.border}`, borderRadius: 8 }}>
          Aucun personnage encore
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 8 }}>
        <button style={{
          padding: "12px 0",
          background: `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
          color: D3.bg, border: "none", borderRadius: 8,
          fontSize: 12, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase",
          cursor: "pointer",
          boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
        }}>Rejoindre la partie</button>
        <div style={{ display: "flex", gap: 6 }}>
          <button style={secondaryBtn}>+ Personnage</button>
          <button style={secondaryBtn}>Exporter</button>
        </div>
        <button style={{
          padding: "8px 0",
          background: "transparent",
          border: `1px solid rgba(232,69,69,0.25)`,
          borderRadius: 6,
          color: "rgba(232,69,69,0.7)",
          fontSize: 11, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase",
          cursor: "pointer", marginTop: 4,
        }}>Supprimer la session</button>
      </div>
    </div>
  );
}

const secondaryBtn = {
  flex: 1, padding: "8px 0",
  background: "transparent",
  border: `1px solid ${D3.borderStrong}`,
  borderRadius: 6,
  color: D3.gold,
  fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
  cursor: "pointer",
};

function InfoRow({ label, value, mono, last }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "7px 0", borderBottom: last ? "none" : `1px solid ${D3.border}`,
      fontSize: 12,
    }}>
      <span style={{ color: D3.textMuted }}>{label}</span>
      <span style={{
        color: D3.text, fontWeight: 600,
        fontFamily: mono ? "'JetBrains Mono', monospace" : "inherit",
      }}>{value}</span>
    </div>
  );
}

function MiniCharRow({ ch }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 10px",
      background: D3.surface,
      border: `1px solid ${D3.border}`,
      borderRadius: 6,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6,
        background: ch.ai ? `linear-gradient(135deg, ${D3.arcane}, #7050b0)` : `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: D3.bg, fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 13,
        flexShrink: 0,
      }}>{ch.name[0]}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: D3.text, fontWeight: 600, fontFamily: "'Cinzel', serif" }}>
          {ch.name}
          {ch.ai && <span style={{ marginLeft: 6, fontSize: 8, color: D3.arcane, fontWeight: 700, letterSpacing: 1 }}>IA</span>}
        </div>
        <div style={{ fontSize: 10, color: D3.textMuted }}>Niv. {ch.level} · {ch.class}</div>
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: D3.textMuted }}>
        {ch.hp}/{ch.hpMax}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// CHARACTER SHEET VIEW
// ═══════════════════════════════════════════════════════════════════════

const ABILITY_FR = {
  FOR: { full: "Force", save: 0 },
  DEX: { full: "Dextérité", save: 3 },
  CON: { full: "Constitution", save: 1 },
  INT: { full: "Intelligence", save: 1 },
  SAG: { full: "Sagesse", save: 2 },
  CHA: { full: "Charisme", save: -1 },
};

const SKILLS_D3 = [
  { id: "acro", name: "Acrobaties", ability: "DEX", prof: true, bonus: 5 },
  { id: "ath", name: "Athlétisme", ability: "FOR", prof: false, bonus: 0 },
  { id: "disc", name: "Discrétion", ability: "DEX", prof: true, bonus: 5 },
  { id: "esc", name: "Escamotage", ability: "DEX", prof: false, bonus: 3 },
  { id: "sur", name: "Survie", ability: "SAG", prof: true, bonus: 4 },
  { id: "per", name: "Perception", ability: "SAG", prof: true, bonus: 4 },
  { id: "nat", name: "Nature", ability: "INT", prof: true, bonus: 3 },
  { id: "int", name: "Intuition", ability: "SAG", prof: false, bonus: 2 },
  { id: "dre", name: "Dressage", ability: "SAG", prof: false, bonus: 2 },
];

const EQUIP_D3 = [
  { id: 1, name: "Arc long elfique", category: "Arme distance", equipped: true, detail: "1d8+3 perforants · 45m" },
  { id: 2, name: "Épée courte", category: "Arme légère", equipped: true, detail: "1d6+3 perforants" },
  { id: 3, name: "Armure de cuir", category: "Armure légère", equipped: true, detail: "CA 11 + DEX" },
  { id: 4, name: "Carquois", category: "Équipement", equipped: false, detail: "20 flèches" },
  { id: 5, name: "Paquetage d'explorateur", category: "Équipement", equipped: false, detail: "Sac, outils, vivres" },
  { id: 6, name: "Potion de soin", category: "Consommable", equipped: false, detail: "Rend 2d4+2 PV", qty: 2 },
];

function CharacterSheetD3() {
  const ch = MOCK.characters.find(c => c.id === "vael");
  return (
    <AppShellD3
      crumbs={["Lobby", "Les Brumes du Hinterland", "Vael"]}
      right={
        <>
          <button style={{
            padding: "6px 12px",
            background: "transparent",
            border: `1px solid ${D3.borderStrong}`,
            borderRadius: 6, color: D3.textSoft,
            fontSize: 11, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase",
            cursor: "pointer",
          }}>← Retour session</button>
        </>
      }
    >
      {/* Hero header */}
      <div style={{
        padding: "28px 56px 24px",
        borderBottom: `1px solid ${D3.border}`,
        background: `linear-gradient(180deg, rgba(255,130,71,0.04), transparent)`,
        position: "relative", overflow: "hidden", flexShrink: 0,
      }}>
        <div style={{
          position: "absolute", top: -100, right: -50,
          width: 280, height: 280, borderRadius: 140,
          background: `radial-gradient(circle, ${D3.ember}25, transparent 70%)`,
          pointerEvents: "none",
        }} />

        <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{
            width: 88, height: 88, borderRadius: 14,
            background: `linear-gradient(135deg, ${D3.ember}, ${D3.gold})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 44,
            color: D3.bg,
            boxShadow: `0 0 0 3px ${D3.bgElev}, 0 0 0 4px ${D3.ember}, 0 0 40px rgba(255,130,71,0.4)`,
            flexShrink: 0,
          }}>{ch.name[0]}</div>

          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 3, color: D3.ember, textTransform: "uppercase", marginBottom: 4 }}>
              ✦ Fiche de personnage
            </div>
            <h1 style={{
              fontFamily: "'Cinzel', serif", fontSize: 40, fontWeight: 700,
              color: D3.text, margin: "0 0 4px", lineHeight: 1, letterSpacing: 1,
            }}>{ch.name}</h1>
            <div style={{ fontSize: 15, color: D3.textSoft, fontFamily: "'Fraunces', Georgia, serif" }}>
              Niv. {ch.level} · {ch.class} · {ch.species}
              <span style={{ margin: "0 10px", color: D3.textDim }}>·</span>
              <span style={{ color: D3.textMuted }}>Historique : Héros du peuple</span>
            </div>
          </div>

          {/* Header stats */}
          <div style={{ display: "flex", gap: 10 }}>
            <HeroStat label="Classe d'armure" value={ch.ac} tone={D3.teal} />
            <HeroStat label="Initiative" value="+3" tone={D3.gold} />
            <HeroStat label="Vitesse" value="9m" tone={D3.text} />
            <HeroStat label="Maîtrise" value="+2" tone={D3.ember} />
          </div>
        </div>

        {/* HP bar big */}
        <div style={{ position: "relative", marginTop: 20, maxWidth: 700 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: D3.textMuted, textTransform: "uppercase" }}>
              Points de vie
            </span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: D3.green }}>
              {ch.hp} <span style={{ color: D3.textDim }}>/ {ch.hpMax}</span>
            </span>
          </div>
          <HpBar3 cur={ch.hp} max={ch.hpMax} height={12} glow />
        </div>
      </div>

      {/* Body : 3 columns */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 56px 32px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 320px", gap: 20 }}>

          {/* LEFT : Abilities + saves */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Section title="Caractéristiques">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {Object.entries(ch.scores).map(([k, v]) => {
                  const mod = Math.floor((v - 10) / 2);
                  return (
                    <div key={k} style={{
                      padding: 10,
                      background: D3.surface,
                      border: `1px solid ${D3.border}`,
                      borderRadius: 8,
                      textAlign: "center",
                    }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, color: D3.textDim }}>{k}</div>
                      <div style={{ fontFamily: "'Cinzel', serif", fontSize: 24, fontWeight: 700, color: D3.text, lineHeight: 1.1, margin: "2px 0" }}>
                        {v}
                      </div>
                      <div style={{
                        display: "inline-block", padding: "2px 8px",
                        background: mod >= 0 ? "rgba(111,217,111,0.12)" : "rgba(232,69,69,0.12)",
                        borderRadius: 4,
                        fontSize: 11, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                        color: mod >= 0 ? D3.green : D3.blood,
                      }}>{mod >= 0 ? `+${mod}` : mod}</div>
                      <div style={{ fontSize: 9, color: D3.textDim, marginTop: 3 }}>{ABILITY_FR[k]?.full}</div>
                    </div>
                  );
                })}
              </div>
            </Section>

            <Section title="Jets de sauvegarde">
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {Object.entries(ABILITY_FR).map(([k, v]) => {
                  const prof = k === "DEX" || k === "SAG";
                  const bonus = v.save + (prof ? 2 : 0);
                  return (
                    <div key={k} style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "5px 10px",
                      background: prof ? "rgba(240,199,100,0.04)" : "transparent",
                      borderRadius: 5,
                    }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: 5,
                        background: prof ? D3.gold : "transparent",
                        border: `1px solid ${prof ? D3.gold : D3.borderStrong}`,
                        flexShrink: 0,
                      }} />
                      <span style={{ flex: 1, fontSize: 12, color: D3.textSoft }}>{v.full}</span>
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700,
                        color: bonus >= 0 ? D3.green : D3.blood, width: 28, textAlign: "right",
                      }}>{bonus >= 0 ? `+${bonus}` : bonus}</span>
                    </div>
                  );
                })}
              </div>
            </Section>
          </div>

          {/* CENTER : Skills + features */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Section title="Compétences" subtitle="Disque plein = maîtrise">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                {SKILLS_D3.map(sk => (
                  <div key={sk.id} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "5px 8px",
                    background: sk.prof ? "rgba(240,199,100,0.05)" : "transparent",
                    borderRadius: 4,
                  }}>
                    <div style={{
                      width: 9, height: 9, borderRadius: 5,
                      background: sk.prof ? D3.gold : "transparent",
                      border: `1px solid ${sk.prof ? D3.gold : D3.borderStrong}`,
                      flexShrink: 0,
                    }} />
                    <span style={{ flex: 1, fontSize: 12, color: D3.textSoft }}>{sk.name}</span>
                    <span style={{ fontSize: 9, fontWeight: 700, color: D3.textDim, letterSpacing: 1 }}>{sk.ability}</span>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700,
                      color: sk.bonus >= 0 ? D3.green : D3.blood, width: 22, textAlign: "right",
                    }}>{sk.bonus >= 0 ? `+${sk.bonus}` : sk.bonus}</span>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Aptitudes de classe" tone={D3.ember}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <FeatureCard name="Ennemi juré" desc="Avantage aux jets de Sagesse (Survie) pour pister les gobelinoïdes et aux jets d'Intelligence pour se souvenir d'eux." />
                <FeatureCard name="Explorateur né" desc="Avantage aux jets d'Intelligence (Nature) en terrain familier. Vous n'êtes pas ralenti par les terrains difficiles en nature." />
                <FeatureCard name="Style de combat" desc="Tir à l'arc. +2 aux jets d'attaque avec les armes à distance." />
              </div>
            </Section>

            <Section title="Personnalité" tone={D3.arcane}>
              <div style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 13, color: D3.textSoft, lineHeight: 1.6 }}>
                <p style={{ margin: "0 0 8px" }}>
                  <span style={{ color: D3.arcane, fontWeight: 700 }}>Trait · </span>
                  Je parle peu, mais mes mots portent. Je préfère écouter la forêt que les hommes.
                </p>
                <p style={{ margin: "0 0 8px" }}>
                  <span style={{ color: D3.arcane, fontWeight: 700 }}>Lien · </span>
                  Ma sœur jumelle a disparu dans les Brumes. Je ne reviendrai pas sans elle.
                </p>
                <p style={{ margin: 0 }}>
                  <span style={{ color: D3.arcane, fontWeight: 700 }}>Défaut · </span>
                  Je ne fais confiance qu'aux animaux et à mon arc.
                </p>
              </div>
            </Section>
          </div>

          {/* RIGHT : Equipment + conditions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Section title="Équipement">
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {EQUIP_D3.map(item => (
                  <div key={item.id} style={{
                    padding: "8px 10px",
                    background: item.equipped ? "rgba(240,199,100,0.06)" : D3.surface,
                    border: `1px solid ${item.equipped ? "rgba(240,199,100,0.25)" : D3.border}`,
                    borderRadius: 6,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 11, color: item.equipped ? D3.gold : D3.textDim }}>
                        {item.equipped ? "⚔" : "○"}
                      </span>
                      <span style={{
                        flex: 1, fontSize: 13, fontWeight: 600,
                        color: item.equipped ? D3.text : D3.textSoft,
                        fontFamily: "'Cinzel', serif",
                      }}>{item.name}</span>
                      {item.qty && (
                        <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: D3.textMuted }}>
                          ×{item.qty}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 10, color: D3.textMuted, marginTop: 2, paddingLeft: 17 }}>
                      {item.detail}
                    </div>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="État" tone={D3.blood}>
              <div style={{ padding: 10, textAlign: "center", color: D3.textMuted, fontSize: 12, fontStyle: "italic", fontFamily: "'Fraunces', serif" }}>
                Aucune condition active
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <button style={smallOutlineBtn}>+ Condition</button>
                <button style={smallOutlineBtn}>+ Ajuster PV</button>
              </div>
            </Section>

            <Section title="Actions rapides">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                <button style={quickBtn(D3.blood)}>⚔ Attaquer</button>
                <button style={quickBtn(D3.teal)}>◈ Objet</button>
                <button style={quickBtn(D3.arcane)}>✦ Sort</button>
                <button style={quickBtn(D3.green)}>☽ Repos</button>
              </div>
            </Section>
          </div>
        </div>
      </div>
    </AppShellD3>
  );
}

function HeroStat({ label, value, tone }) {
  return (
    <div style={{
      padding: "10px 16px", minWidth: 90,
      background: "rgba(0,0,0,0.3)",
      border: `1px solid ${D3.border}`,
      borderRadius: 8,
      textAlign: "center",
    }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: D3.textDim, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontFamily: "'Cinzel', serif", fontSize: 24, fontWeight: 700, color: tone, marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

function Section({ title, subtitle, tone, children }) {
  const borderColor = tone ? `${tone}40` : D3.border;
  return (
    <div style={{
      background: D3.bgElev, border: `1px solid ${borderColor}`,
      borderRadius: 12, padding: 14,
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
        <span style={{ color: tone || D3.ember, fontSize: 10 }}>✦</span>
        <h3 style={{
          fontFamily: "'Cinzel', serif", fontSize: 11, fontWeight: 700,
          color: tone || D3.text, margin: 0, letterSpacing: 2, textTransform: "uppercase",
        }}>{title}</h3>
        {subtitle && <span style={{ fontSize: 10, color: D3.textDim, fontStyle: "italic" }}>— {subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function FeatureCard({ name, desc }) {
  return (
    <div style={{
      padding: 10, background: D3.surface,
      border: `1px solid ${D3.border}`, borderRadius: 6,
    }}>
      <div style={{ fontFamily: "'Cinzel', serif", fontSize: 12, fontWeight: 700, color: D3.ember, marginBottom: 3 }}>
        {name}
      </div>
      <div style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 12, color: D3.textSoft, lineHeight: 1.45 }}>
        {desc}
      </div>
    </div>
  );
}

const smallOutlineBtn = {
  flex: 1, padding: "6px 0",
  background: "transparent",
  border: `1px solid ${D3.border}`,
  borderRadius: 5, color: D3.textSoft,
  fontSize: 10, fontWeight: 600, letterSpacing: 0.5,
  cursor: "pointer",
};

function quickBtn(color) {
  return {
    padding: "10px 0",
    background: `${color}14`,
    border: `1px solid ${color}40`,
    borderRadius: 6, color,
    fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
    cursor: "pointer",
  };
}

// ═══════════════════════════════════════════════════════════════════════
// HP Bar (shared)
// ═══════════════════════════════════════════════════════════════════════

function HpBar3({ cur, max, height = 6, glow }) {
  const pct = Math.max(0, (cur / max) * 100);
  const color = pct > 50 ? D3.green : pct > 25 ? "#e5b93a" : D3.blood;
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

// ═══════════════════════════════════════════════════════════════════════
// Export
// ═══════════════════════════════════════════════════════════════════════

window.LobbyD3 = LobbyD3;
window.CharacterSheetD3 = CharacterSheetD3;
