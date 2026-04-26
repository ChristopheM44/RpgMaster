// Direction 3 — CAMPAGNES (vue refondue + élargie)
// Reprend les 3 captures fournies (liste, modale, détail) et élargit
// la "Campagne" en hub : sessions, arc narratif (scénario), accès aux
// Journal de quêtes / Journal du chroniqueur / Carnet d'aventure.

const { useState: useStateD3C, useMemo: useMemoD3C } = React;

const DC3 = {
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

// ─────────────────────────────────────────────────────────────────────
// MOCK : campagnes étoffées
// ─────────────────────────────────────────────────────────────────────

const MOCK_CAMPAIGNS = [
  {
    id: "c1",
    name: "Les Brumes du Hinterland",
    tagline: "Une épopée qui traverse trois royaumes",
    description: "Aux confins du Hinterland, les disparitions se multiplient. Le groupe doit démêler la menace gobeline des lueurs étranges qui pulsent dans les anciennes mines de cristal.",
    sessions: 4,
    activeSession: 4,
    chars: 5,
    quests: { active: 7, done: 12, rumors: 4 },
    journal: { entries: 23 },
    chronicler: { npcs: 18, places: 11 },
    updated: "22/04/26 11:12",
    arc: [
      { id: "ch1", num: "I", title: "Au cœur de la taverne", state: "done", sessions: 1, summary: "Première rencontre à l'auberge Stonehill. Bram dévoile les rumeurs du Hinterland." },
      { id: "ch2", num: "II", title: "La piste des disparitions", state: "done", sessions: 1, summary: "Pierrefort, le capitaine Harlon, premiers indices d'une présence gobeline organisée." },
      { id: "ch3", num: "III", title: "Les Brumes du Nord", state: "done", sessions: 1, summary: "Traversée des marais. Embuscade. Premier contact avec un éclaireur ennemi capturé." },
      { id: "ch4", num: "IV", title: "La mine de cristal", state: "active", sessions: 1, summary: "Le groupe descend. Lueurs bleutées pulsantes. Quelque chose veille au fond." },
      { id: "ch5", num: "V", title: "Le serment brisé", state: "planned", sessions: 0, summary: "Rencontre prévue avec l'Ordre du Crépuscule. Choix narratif majeur en perspective." },
      { id: "ch6", num: "VI", title: "Le Trône de Cendres", state: "planned", sessions: 0, summary: "Climax. Le PNJ antagoniste révèle sa vraie nature." },
    ],
  },
  {
    id: "c2",
    name: "La Chute des Rois Anciens",
    tagline: "Une épopée qui traverse trois royaumes",
    description: "Forgée dans l'écho des dynasties éteintes, cette campagne suit un groupe de héros qui découvre que le sang qui coule dans leurs veines pourrait être celui des derniers Rois Anciens.",
    sessions: 2,
    activeSession: 2,
    chars: 3,
    quests: { active: 3, done: 4, rumors: 6 },
    journal: { entries: 9 },
    chronicler: { npcs: 7, places: 5 },
    updated: "21/04/26 22:40",
    arc: [
      { id: "ch1", num: "I", title: "L'héritage du sang", state: "done", sessions: 1, summary: "Le testament. La révélation. Les premiers ennemis." },
      { id: "ch2", num: "II", title: "Aldoria endormie", state: "active", sessions: 1, summary: "Exploration de la cité oubliée. Le groupe doit retrouver la Couronne d'Argent." },
      { id: "ch3", num: "III", title: "Le pacte d'Ombrebois", state: "planned", sessions: 0, summary: "Diplomatie elfique. Choix entre alliance et conquête." },
    ],
  },
  {
    id: "c3",
    name: "Test",
    tagline: "Bac à sable",
    description: "Campagne d'essai pour tester les mécaniques. Sessions courtes, narratif minimal.",
    sessions: 1,
    activeSession: 1,
    chars: 0,
    quests: { active: 0, done: 0, rumors: 0 },
    journal: { entries: 0 },
    chronicler: { npcs: 0, places: 0 },
    updated: "18/04/26 09:30",
    arc: [
      { id: "ch1", num: "I", title: "Session 1 (test)", state: "active", sessions: 1, summary: "Salon de test. Aucun fil narratif." },
    ],
  },
  {
    id: "c4",
    name: "Ma Campagne",
    tagline: "Brouillon",
    description: "Campagne en cours de préparation. Le scénario n'a pas encore été lancé.",
    sessions: 1,
    activeSession: 1,
    chars: 0,
    quests: { active: 0, done: 0, rumors: 0 },
    journal: { entries: 0 },
    chronicler: { npcs: 0, places: 0 },
    updated: "05/04/26 23:15",
    arc: [
      { id: "ch1", num: "I", title: "À écrire", state: "planned", sessions: 0, summary: "Prologue à définir." },
    ],
  },
];

const ARC_META = {
  done:    { label: "Terminé", color: DC3.textDim,  bg: "rgba(247,236,208,0.04)" },
  active:  { label: "En cours", color: DC3.ember,    bg: "rgba(255,130,71,0.10)" },
  planned: { label: "À venir",  color: DC3.arcane,   bg: "rgba(192,144,255,0.08)" },
};

// ─────────────────────────────────────────────────────────────────────
// AppShell réutilisé (style D3) — version simplifiée locale
// ─────────────────────────────────────────────────────────────────────

function CampaignShellD3({ children, crumbs, right }) {
  return (
    <div style={{
      width: 1440, height: 900,
      background: `radial-gradient(ellipse at top, #1a1630 0%, ${DC3.bg} 60%)`,
      color: DC3.text,
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: 14, display: "flex", flexDirection: "column",
      overflow: "hidden", position: "relative",
    }}>
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)",
        backgroundSize: "24px 24px",
      }} />
      <header style={{
        height: 56, display: "flex", alignItems: "center",
        padding: "0 24px",
        borderBottom: `1px solid ${DC3.border}`,
        background: `linear-gradient(180deg, ${DC3.bgElev}, transparent)`,
        backdropFilter: "blur(8px)",
        gap: 18, position: "relative", zIndex: 2, flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`,
            color: DC3.bg,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, fontWeight: 700,
            boxShadow: `0 0 20px rgba(255, 130, 71, 0.3)`,
          }}>⚔</div>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 15, fontWeight: 700, letterSpacing: 1 }}>RPGMASTER</div>
        </div>
        {crumbs && (
          <>
            <span style={{ color: DC3.textDim, fontSize: 13 }}>/</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: DC3.textMuted }}>
              {crumbs.map((c, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span style={{ color: DC3.textDim }}>›</span>}
                  <span style={{
                    color: i === crumbs.length - 1 ? DC3.gold : DC3.textMuted,
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
      <div style={{ flex: 1, minHeight: 0, position: "relative", zIndex: 1, display: "flex", flexDirection: "column" }}>
        {children}
      </div>
    </div>
  );
}

function CNavPill({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "6px 14px",
      background: active ? "rgba(240,199,100,0.10)" : "transparent",
      border: `1px solid ${active ? "rgba(240,199,100,0.30)" : "transparent"}`,
      borderRadius: 999,
      color: active ? DC3.gold : DC3.textMuted,
      fontSize: 12, fontWeight: 600, letterSpacing: 0.5,
      cursor: "pointer",
    }}>{label}</button>
  );
}

const RightOnline = () => (
  <>
    <CNavPill label="Lobby" />
    <CNavPill label="Campagnes" active />
    <CNavPill label="Admin" />
    <div style={{ width: 1, height: 22, background: DC3.border, margin: "0 4px" }} />
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: DC3.textMuted }}>
      <span style={{ width: 7, height: 7, borderRadius: 4, background: DC3.green, boxShadow: `0 0 8px ${DC3.green}` }} />
      EN LIGNE
    </div>
    <button style={{
      padding: "6px 14px", background: "transparent",
      border: `1px solid ${DC3.borderStrong}`, borderRadius: 6,
      color: DC3.textSoft, fontSize: 11, fontWeight: 600, letterSpacing: 1,
      textTransform: "uppercase", cursor: "pointer",
    }}>← Lobby</button>
  </>
);

// ─────────────────────────────────────────────────────────────────────
// PAGE TITLE — partagé
// ─────────────────────────────────────────────────────────────────────

function CampaignsHeader({ onNew }) {
  return (
    <div style={{
      padding: "32px 56px 24px",
      display: "flex", alignItems: "flex-end", gap: 24,
      position: "relative",
    }}>
      <div style={{
        position: "absolute", top: -40, left: -20,
        width: 280, height: 200, borderRadius: 140,
        background: `radial-gradient(ellipse, ${DC3.ember}15, transparent 70%)`,
        pointerEvents: "none",
      }} />
      <div style={{ flex: 1, position: "relative" }}>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: 3, color: DC3.ember,
          textTransform: "uppercase", marginBottom: 6,
        }}>
          ✦ Vos chroniques
        </div>
        <h1 style={{
          fontFamily: "'Cinzel', serif", fontSize: 44, fontWeight: 700,
          color: DC3.text, margin: "0 0 10px", letterSpacing: 1, lineHeight: 1.05,
        }}>
          Campagnes
        </h1>
        <p style={{
          fontSize: 15, color: DC3.textSoft, margin: 0,
          fontFamily: "'Fraunces', Georgia, serif", maxWidth: 620, fontStyle: "italic",
        }}>
          Enchaînez des sessions avec progression persistante. Chaque campagne tisse son propre fil — quêtes, PNJ, lieux et chroniques.
        </p>
      </div>
      <div style={{ display: "flex", gap: 10, position: "relative" }}>
        <button onClick={onNew} style={{
          padding: "10px 22px",
          background: `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`,
          color: DC3.bg, border: "none", borderRadius: 8,
          fontSize: 12, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
          cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
          boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
        }}>
          <span style={{ fontSize: 14 }}>✦</span> Forger une campagne
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// CAMPAIGN CARD — version riche
// ─────────────────────────────────────────────────────────────────────

function CampaignCard({ camp, selected, onSelect }) {
  const activeChapter = camp.arc.find(a => a.state === "active") || camp.arc[0];
  const totalChapters = camp.arc.length;
  const doneChapters = camp.arc.filter(a => a.state === "done").length;

  return (
    <div onClick={onSelect} style={{
      padding: "16px 18px",
      background: selected
        ? `linear-gradient(135deg, rgba(255,130,71,0.12), ${DC3.surface})`
        : DC3.surface,
      border: `1px solid ${selected ? DC3.ember : DC3.border}`,
      borderRadius: 10, cursor: "pointer",
      boxShadow: selected ? `0 0 24px rgba(255,130,71,0.15)` : "none",
      position: "relative", overflow: "hidden",
    }}>
      {selected && (
        <div style={{
          position: "absolute", left: 0, top: 0, bottom: 0, width: 3,
          background: `linear-gradient(180deg, ${DC3.ember}, ${DC3.gold})`,
        }} />
      )}

      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontFamily: "'Cinzel', serif", fontSize: 17, fontWeight: 700,
            color: DC3.text, letterSpacing: 0.5, lineHeight: 1.2, marginBottom: 2,
          }}>{camp.name}</div>
          <div style={{
            fontSize: 12, color: DC3.textMuted, fontStyle: "italic",
            fontFamily: "'Fraunces', Georgia, serif",
          }}>
            ✦ Chapitre {activeChapter.num} — {activeChapter.title}
          </div>
        </div>
        <button style={{
          width: 22, height: 22, borderRadius: 4,
          background: "transparent", border: "none",
          color: DC3.textDim, fontSize: 14, cursor: "pointer", flexShrink: 0,
        }}>×</button>
      </div>

      {/* Progress bar */}
      <div style={{ marginBottom: 10 }}>
        <div style={{
          height: 4, background: "rgba(0,0,0,0.4)", borderRadius: 2, overflow: "hidden",
          border: `1px solid ${DC3.border}`,
        }}>
          <div style={{
            height: "100%",
            width: `${(doneChapters / totalChapters) * 100}%`,
            background: `linear-gradient(90deg, ${DC3.goldDeep}, ${DC3.ember})`,
          }} />
        </div>
        <div style={{
          marginTop: 4, fontSize: 10, color: DC3.textDim,
          fontFamily: "'JetBrains Mono', monospace", display: "flex", justifyContent: "space-between",
        }}>
          <span>{doneChapters} / {totalChapters} chapitres</span>
          <span>{camp.updated}</span>
        </div>
      </div>

      {/* Chip row */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <CardChip icon="◆" label={`${camp.sessions} session${camp.sessions > 1 ? "s" : ""}`} />
        <CardChip icon="✦" label={`${camp.chars} perso${camp.chars > 1 ? "s" : ""}.`} />
        <CardChip icon="◷" label={`${camp.quests.active} quête${camp.quests.active > 1 ? "s" : ""}`} tone={camp.quests.active ? DC3.gold : null} />
        <CardChip icon="◉" label={`${camp.chronicler.npcs} PNJ`} />
      </div>
    </div>
  );
}

function CardChip({ icon, label, tone }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "3px 8px",
      background: "rgba(0,0,0,0.3)",
      border: `1px solid ${DC3.border}`,
      borderRadius: 4,
      fontSize: 10, color: tone || DC3.textMuted,
      fontFamily: "'JetBrains Mono', monospace", letterSpacing: 0.3,
    }}>
      <span style={{ color: tone || DC3.textDim, fontSize: 9 }}>{icon}</span>
      {label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────
// DETAIL PANEL : 3 onglets (Sessions / Scénario / Notes)
// ─────────────────────────────────────────────────────────────────────

function CampaignDetail({ camp, defaultTab }) {
  const [tab, setTab] = useStateD3C(defaultTab || "sessions");

  return (
    <aside style={{
      width: 580, borderLeft: `1px solid ${DC3.border}`,
      background: `linear-gradient(180deg, ${DC3.bgElev}, ${DC3.bg})`,
      display: "flex", flexDirection: "column", flexShrink: 0,
      minHeight: 0,
    }}>
      {/* Hero */}
      <div style={{
        padding: "24px 28px 20px", borderBottom: `1px solid ${DC3.border}`,
        position: "relative", overflow: "hidden", flexShrink: 0,
      }}>
        <div style={{
          position: "absolute", top: -60, right: -40,
          width: 220, height: 220, borderRadius: 110,
          background: `radial-gradient(circle, ${DC3.ember}25, transparent 70%)`,
          pointerEvents: "none",
        }} />
        <div style={{ position: "relative" }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 3, color: DC3.ember,
            textTransform: "uppercase", marginBottom: 6,
          }}>
            ✦ Campagne sélectionnée
          </div>
          <h2 style={{
            fontFamily: "'Cinzel', serif", fontSize: 28, fontWeight: 700,
            color: DC3.text, margin: "0 0 4px", lineHeight: 1.05, letterSpacing: 0.5,
          }}>{camp.name}</h2>
          <p style={{
            fontFamily: "'Fraunces', Georgia, serif", fontSize: 13,
            color: DC3.textSoft, margin: "0 0 14px", fontStyle: "italic", lineHeight: 1.5,
          }}>{camp.tagline}</p>

          {/* Stats row */}
          <div style={{ display: "flex", gap: 8 }}>
            <DetailStat label="Sessions" value={camp.sessions} tone={DC3.text} />
            <DetailStat label="Persos" value={camp.chars} tone={DC3.gold} />
            <DetailStat label="Quêtes" value={camp.quests.active} tone={DC3.ember} sub={`${camp.quests.done} fini`} />
            <DetailStat label="Chronique" value={camp.journal.entries} tone={DC3.arcane} sub="entrées" />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 0, padding: "0 28px",
        borderBottom: `1px solid ${DC3.border}`, flexShrink: 0,
      }}>
        {[
          { id: "sessions", label: "Sessions", icon: "◆" },
          { id: "arc", label: "Scénario", icon: "✦" },
          { id: "notes", label: "Notes du MJ", icon: "❦" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "12px 14px",
            background: "transparent",
            border: "none",
            borderBottom: `2px solid ${tab === t.id ? DC3.ember : "transparent"}`,
            color: tab === t.id ? DC3.text : DC3.textMuted,
            fontSize: 11, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
            cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
            fontFamily: "'Cinzel', serif",
          }}>
            <span style={{ color: tab === t.id ? DC3.ember : DC3.textDim, fontSize: 10 }}>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px 28px", minHeight: 0 }}>
        {tab === "sessions" && <SessionsTab camp={camp} />}
        {tab === "arc" && <ArcTab camp={camp} />}
        {tab === "notes" && <NotesTab camp={camp} />}
      </div>

      {/* Knowledge hub - always visible footer */}
      <div style={{
        padding: "14px 28px 18px",
        borderTop: `1px solid ${DC3.border}`,
        background: "rgba(0,0,0,0.25)",
        flexShrink: 0,
      }}>
        <div style={{
          fontSize: 9, fontWeight: 700, letterSpacing: 2, color: DC3.textMuted,
          textTransform: "uppercase", marginBottom: 8,
        }}>✦ Codex de la campagne</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          <CodexLink
            icon="◷" label="Journal de quêtes"
            count={camp.quests.active + camp.quests.done}
            sub={`${camp.quests.active} actives`}
            tone={DC3.gold}
          />
          <CodexLink
            icon="❦" label="Journal du chroniqueur"
            count={camp.journal.entries}
            sub="entrées"
            tone={DC3.arcane}
          />
          <CodexLink
            icon="◉" label="Carnet d'aventure"
            count={camp.chronicler.npcs + camp.chronicler.places}
            sub={`${camp.chronicler.npcs} PNJ · ${camp.chronicler.places} lieux`}
            tone={DC3.teal}
          />
        </div>
      </div>
    </aside>
  );
}

function DetailStat({ label, value, tone, sub }) {
  return (
    <div style={{
      flex: 1, padding: "8px 10px",
      background: "rgba(0,0,0,0.3)",
      border: `1px solid ${DC3.border}`, borderRadius: 6,
    }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: DC3.textDim, textTransform: "uppercase" }}>{label}</div>
      <div style={{
        fontFamily: "'Cinzel', serif", fontSize: 22, fontWeight: 700,
        color: tone, marginTop: 2, lineHeight: 1,
      }}>{value}</div>
      {sub && <div style={{ fontSize: 9, color: DC3.textDim, marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>{sub}</div>}
    </div>
  );
}

function CodexLink({ icon, label, count, sub, tone }) {
  return (
    <button style={{
      padding: "10px 12px",
      background: DC3.surface,
      border: `1px solid ${DC3.border}`,
      borderRadius: 8,
      cursor: "pointer", textAlign: "left",
      color: DC3.text, fontFamily: "inherit",
      transition: "all 0.15s",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ color: tone, fontSize: 14 }}>{icon}</span>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700,
          color: tone, lineHeight: 1,
        }}>{count}</span>
      </div>
      <div style={{
        fontFamily: "'Cinzel', serif", fontSize: 11, fontWeight: 700,
        color: DC3.text, letterSpacing: 0.5, lineHeight: 1.2,
      }}>{label}</div>
      <div style={{ fontSize: 9, color: DC3.textDim, marginTop: 2 }}>{sub}</div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 1 : SESSIONS
// ─────────────────────────────────────────────────────────────────────

function SessionsTab({ camp }) {
  const sessions = useMemoD3C(() => {
    const arr = [];
    for (let i = 1; i <= camp.sessions; i++) {
      const isActive = i === camp.activeSession;
      arr.push({
        id: `s${i}`,
        num: i,
        active: isActive,
        chapter: camp.arc[i - 1] || camp.arc[camp.arc.length - 1],
      });
    }
    return arr;
  }, [camp]);

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
        {sessions.map(s => (
          <div key={s.id} style={{
            display: "flex", alignItems: "center", gap: 12,
            padding: "12px 14px",
            background: s.active
              ? `linear-gradient(90deg, rgba(255,130,71,0.10), ${DC3.surface})`
              : DC3.surface,
            border: `1px solid ${s.active ? "rgba(255,130,71,0.30)" : DC3.border}`,
            borderRadius: 8,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 6,
              background: s.active
                ? `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`
                : "rgba(0,0,0,0.3)",
              border: s.active ? "none" : `1px solid ${DC3.border}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              color: s.active ? DC3.bg : DC3.textMuted,
              fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 14,
              flexShrink: 0,
            }}>{s.num}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  fontFamily: "'Cinzel', serif", fontSize: 13, fontWeight: 700,
                  color: DC3.text, letterSpacing: 0.5,
                }}>Session {s.num}</span>
                {s.active && (
                  <span style={{
                    padding: "1px 6px",
                    background: "rgba(255,130,71,0.18)",
                    border: `1px solid rgba(255,130,71,0.4)`,
                    borderRadius: 3,
                    fontSize: 9, fontWeight: 700, letterSpacing: 1,
                    textTransform: "uppercase", color: DC3.ember,
                  }}>active</span>
                )}
              </div>
              <div style={{
                fontSize: 11, color: DC3.textMuted, fontStyle: "italic",
                fontFamily: "'Fraunces', Georgia, serif",
              }}>
                Chap. {s.chapter.num} — {s.chapter.title}
              </div>
            </div>
            <div style={{
              fontSize: 9, color: DC3.textDim, fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: 0.3,
            }}>
              {s.id === `s${camp.activeSession}` ? "b69760c4" : `${s.id}…`}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <button style={{
        width: "100%", padding: "12px 0",
        background: `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`,
        color: DC3.bg, border: "none", borderRadius: 8,
        fontSize: 12, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase",
        cursor: "pointer", marginBottom: 8,
        boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        fontFamily: "'Cinzel', serif",
      }}>
        <span style={{ fontSize: 14 }}>▶</span> Jouer la session courante
      </button>
      <button style={{
        width: "100%", padding: "10px 0",
        background: "rgba(192,144,255,0.08)",
        color: DC3.arcane,
        border: `1px solid rgba(192,144,255,0.30)`, borderRadius: 8,
        fontSize: 11, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
        cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        fontFamily: "'Cinzel', serif",
      }}>
        <span>→</span> Session suivante (transférer personnages)
      </button>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 2 : ARC NARRATIF
// ─────────────────────────────────────────────────────────────────────

function ArcTab({ camp }) {
  return (
    <div>
      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 2, color: DC3.textMuted,
        textTransform: "uppercase", marginBottom: 12,
      }}>✦ Arc narratif — {camp.arc.length} chapitres</div>

      <div style={{ position: "relative" }}>
        {/* Vertical timeline line */}
        <div style={{
          position: "absolute", left: 13, top: 18, bottom: 18, width: 1,
          background: `linear-gradient(180deg, ${DC3.borderStrong}, ${DC3.border} 50%, transparent)`,
        }} />

        {camp.arc.map((ch, i) => {
          const meta = ARC_META[ch.state];
          return (
            <div key={ch.id} style={{
              position: "relative", display: "flex", gap: 14,
              paddingBottom: i === camp.arc.length - 1 ? 0 : 16,
            }}>
              {/* Dot / num */}
              <div style={{
                width: 28, height: 28, borderRadius: 14,
                background: ch.state === "active"
                  ? `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`
                  : ch.state === "done" ? DC3.surfaceRaised : DC3.surface,
                border: ch.state === "active" ? "none" : `1px solid ${ch.state === "done" ? DC3.borderStrong : DC3.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "'Cinzel', serif", fontWeight: 700, fontSize: 11,
                color: ch.state === "active" ? DC3.bg : ch.state === "done" ? DC3.gold : DC3.textMuted,
                flexShrink: 0, zIndex: 1, position: "relative",
                boxShadow: ch.state === "active" ? `0 0 14px rgba(255,130,71,0.5)` : "none",
              }}>{ch.num}</div>

              <div style={{
                flex: 1,
                padding: "10px 14px",
                background: ch.state === "active"
                  ? `linear-gradient(135deg, rgba(255,130,71,0.08), ${DC3.surface})`
                  : DC3.surface,
                border: `1px solid ${ch.state === "active" ? "rgba(255,130,71,0.30)" : DC3.border}`,
                borderRadius: 8,
              }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
                  <h4 style={{
                    fontFamily: "'Cinzel', serif", fontSize: 13, fontWeight: 700,
                    color: DC3.text, margin: 0, letterSpacing: 0.3, lineHeight: 1.2,
                  }}>{ch.title}</h4>
                  <span style={{
                    padding: "1px 6px",
                    background: meta.bg,
                    border: `1px solid ${meta.color}40`,
                    borderRadius: 3,
                    fontSize: 8, fontWeight: 700, letterSpacing: 1,
                    textTransform: "uppercase", color: meta.color,
                  }}>{meta.label}</span>
                  <div style={{ flex: 1 }} />
                  {ch.sessions > 0 && (
                    <span style={{
                      fontSize: 9, color: DC3.textDim,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>{ch.sessions} session{ch.sessions > 1 ? "s" : ""}</span>
                  )}
                </div>
                <p style={{
                  fontFamily: "'Fraunces', Georgia, serif", fontSize: 12,
                  color: DC3.textSoft, margin: 0, lineHeight: 1.5, textWrap: "pretty",
                }}>{ch.summary}</p>
              </div>
            </div>
          );
        })}
      </div>

      <button style={{
        width: "100%", marginTop: 16,
        padding: "10px 0",
        background: "transparent",
        color: DC3.gold,
        border: `1px dashed ${DC3.borderStrong}`, borderRadius: 8,
        fontSize: 11, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
        cursor: "pointer", fontFamily: "'Cinzel', serif",
      }}>+ Ajouter un chapitre</button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 3 : NOTES DU MJ
// ─────────────────────────────────────────────────────────────────────

function NotesTab({ camp }) {
  return (
    <div>
      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 2, color: DC3.textMuted,
        textTransform: "uppercase", marginBottom: 10,
      }}>✦ Synopsis</div>
      <div style={{
        padding: "14px 16px",
        background: DC3.surface,
        border: `1px solid ${DC3.border}`, borderRadius: 8, marginBottom: 18,
      }}>
        <p style={{
          fontFamily: "'Fraunces', Georgia, serif", fontSize: 13,
          color: DC3.textSoft, margin: 0, lineHeight: 1.6, textWrap: "pretty",
        }}>{camp.description}</p>
      </div>

      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 2, color: DC3.textMuted,
        textTransform: "uppercase", marginBottom: 10,
      }}>✦ Tonalités</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 18 }}>
        {["Dark fantasy", "Mystère", "Politique", "Exploration", "Combat tactique"].map(t => (
          <span key={t} style={{
            padding: "5px 10px",
            background: "rgba(192,144,255,0.08)",
            border: `1px solid rgba(192,144,255,0.25)`,
            borderRadius: 999, fontSize: 11, color: DC3.arcane,
            fontFamily: "'Fraunces', Georgia, serif",
          }}>{t}</span>
        ))}
      </div>

      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 2, color: DC3.textMuted,
        textTransform: "uppercase", marginBottom: 10,
      }}>✦ Mémo privé</div>
      <div style={{
        padding: "14px 16px", background: DC3.bgElev,
        border: `1px solid ${DC3.borderStrong}`, borderRadius: 8,
        fontFamily: "'Fraunces', Georgia, serif", fontSize: 13,
        color: DC3.textSoft, lineHeight: 1.6, fontStyle: "italic",
        position: "relative", marginBottom: 16,
      }}>
        <span style={{
          position: "absolute", top: 10, left: 10,
          color: DC3.gold, fontSize: 16, fontFamily: "'Cinzel', serif",
        }}>“</span>
        <div style={{ paddingLeft: 18 }}>
          Bram cache quelque chose. Il connaît l'identité du nécromancien — ne révéler qu'au chapitre V.
          La sœur de Vael est bien en vie, prisonnière dans la mine. Le Capitaine Harlon est compromis.
        </div>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button style={{
          flex: 1, padding: "9px 0",
          background: "transparent",
          border: `1px solid ${DC3.borderStrong}`, borderRadius: 6,
          color: DC3.gold, fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
          cursor: "pointer", fontFamily: "'Cinzel', serif",
        }}>Éditer</button>
        <button style={{
          flex: 1, padding: "9px 0",
          background: "transparent",
          border: `1px solid rgba(232,69,69,0.25)`, borderRadius: 6,
          color: "rgba(232,69,69,0.7)", fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
          cursor: "pointer", fontFamily: "'Cinzel', serif",
        }}>Supprimer la campagne</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// MODALE : Nouvelle campagne (refonte D3 du visuel #2)
// ─────────────────────────────────────────────────────────────────────

function NewCampaignModal({ onClose, embedded }) {
  const [name, setName] = useStateD3C("La Chute des Rois Anciens");
  const [desc, setDesc] = useStateD3C("Une épopée qui traverse trois royaumes…");

  const inner = (
    <div style={{
      width: 560,
      background: `linear-gradient(180deg, ${DC3.bgElev}, ${DC3.bg})`,
      border: `1px solid ${DC3.borderStrong}`,
      borderRadius: 14,
      padding: 28,
      position: "relative", overflow: "hidden",
      boxShadow: `0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(240,199,100,0.08)`,
    }}>
      {/* Glow */}
      <div style={{
        position: "absolute", top: -80, right: -40,
        width: 240, height: 240, borderRadius: 120,
        background: `radial-gradient(circle, ${DC3.ember}30, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative" }}>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: 3, color: DC3.ember,
          textTransform: "uppercase", marginBottom: 4,
        }}>
          ✦ Forger une nouvelle chronique
        </div>
        <h2 style={{
          fontFamily: "'Cinzel', serif", fontSize: 28, fontWeight: 700,
          color: DC3.text, margin: "0 0 20px", letterSpacing: 0.5, lineHeight: 1.1,
        }}>Nouvelle campagne</h2>

        {/* Nom */}
        <label style={{
          display: "block", fontSize: 10, fontWeight: 700,
          letterSpacing: 2, color: DC3.textMuted, textTransform: "uppercase",
          marginBottom: 6, fontFamily: "'Cinzel', serif",
        }}>Nom de la campagne</label>
        <input
          value={name} onChange={e => setName(e.target.value)}
          style={{
            width: "100%", padding: "12px 14px",
            background: "rgba(0,0,0,0.4)",
            border: `1px solid ${DC3.borderStrong}`,
            borderRadius: 8, color: DC3.text,
            fontSize: 16, fontFamily: "'Fraunces', Georgia, serif",
            outline: "none", marginBottom: 18,
          }}
        />

        {/* Description */}
        <label style={{
          display: "block", fontSize: 10, fontWeight: 700,
          letterSpacing: 2, color: DC3.textMuted, textTransform: "uppercase",
          marginBottom: 6, fontFamily: "'Cinzel', serif",
        }}>Description <span style={{ color: DC3.textDim, fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>— optionnel</span></label>
        <textarea
          value={desc} onChange={e => setDesc(e.target.value)} rows={3}
          style={{
            width: "100%", padding: "12px 14px",
            background: "rgba(0,0,0,0.4)",
            border: `1px solid ${DC3.borderStrong}`,
            borderRadius: 8, color: DC3.text,
            fontSize: 14, fontFamily: "'Fraunces', Georgia, serif",
            outline: "none", marginBottom: 18, resize: "vertical",
            lineHeight: 1.5,
          }}
        />

        {/* Tonalités quick-pick */}
        <label style={{
          display: "block", fontSize: 10, fontWeight: 700,
          letterSpacing: 2, color: DC3.textMuted, textTransform: "uppercase",
          marginBottom: 8, fontFamily: "'Cinzel', serif",
        }}>Tonalités <span style={{ color: DC3.textDim, fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>— max 3</span></label>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 24 }}>
          {[
            { l: "Dark fantasy", on: true },
            { l: "Mystère", on: true },
            { l: "Politique", on: false },
            { l: "Exploration", on: true },
            { l: "Combat tactique", on: false },
            { l: "Romance", on: false },
            { l: "Cosmique", on: false },
          ].map(t => (
            <button key={t.l} style={{
              padding: "5px 12px",
              background: t.on ? "rgba(192,144,255,0.12)" : "transparent",
              border: `1px solid ${t.on ? "rgba(192,144,255,0.4)" : DC3.border}`,
              borderRadius: 999,
              fontSize: 11, color: t.on ? DC3.arcane : DC3.textMuted,
              fontFamily: "'Fraunces', Georgia, serif",
              cursor: "pointer",
            }}>{t.l}</button>
          ))}
        </div>

        {/* Footer */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{
            padding: "11px 22px", background: "transparent",
            border: `1px solid ${DC3.borderStrong}`, borderRadius: 8,
            color: DC3.textSoft, fontSize: 12, fontWeight: 700, letterSpacing: 1.2,
            textTransform: "uppercase", cursor: "pointer", fontFamily: "'Cinzel', serif",
          }}>Annuler</button>
          <button style={{
            padding: "11px 28px",
            background: `linear-gradient(135deg, ${DC3.ember}, ${DC3.gold})`,
            color: DC3.bg, border: "none", borderRadius: 8,
            fontSize: 12, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
            cursor: "pointer", fontFamily: "'Cinzel', serif",
            boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <span style={{ fontSize: 14 }}>⚔</span> Forger
          </button>
        </div>
      </div>
    </div>
  );

  if (embedded) return inner;

  return (
    <div style={{
      position: "absolute", inset: 0,
      background: "rgba(8,6,12,0.7)", backdropFilter: "blur(6px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 100,
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()}>{inner}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// EXPORTS — 3 artboards
// ─────────────────────────────────────────────────────────────────────

// 1) Vue principale, panneau de détail visible
function CampaignsListD3() {
  const [selectedId, setSelectedId] = useStateD3C("c1");
  const camp = MOCK_CAMPAIGNS.find(c => c.id === selectedId) || MOCK_CAMPAIGNS[0];

  return (
    <CampaignShellD3 crumbs={["Lobby", "Campagnes"]} right={<RightOnline />}>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* List */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <CampaignsHeader />
          <div style={{ padding: "0 56px 28px", overflowY: "auto", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {MOCK_CAMPAIGNS.map(c => (
                <CampaignCard
                  key={c.id} camp={c}
                  selected={selectedId === c.id}
                  onSelect={() => setSelectedId(c.id)}
                />
              ))}
            </div>
          </div>
        </div>
        <CampaignDetail camp={camp} defaultTab="sessions" />
      </div>
    </CampaignShellD3>
  );
}

// 2) Vue avec onglet Scénario actif (montre l'arc narratif)
function CampaignsArcD3() {
  const camp = MOCK_CAMPAIGNS[0];
  return (
    <CampaignShellD3 crumbs={["Lobby", "Campagnes"]} right={<RightOnline />}>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <CampaignsHeader />
          <div style={{ padding: "0 56px 28px", overflowY: "auto", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {MOCK_CAMPAIGNS.map(c => (
                <CampaignCard
                  key={c.id} camp={c}
                  selected={c.id === camp.id}
                  onSelect={() => {}}
                />
              ))}
            </div>
          </div>
        </div>
        <CampaignDetail camp={camp} defaultTab="arc" />
      </div>
    </CampaignShellD3>
  );
}

// 3) Vue avec onglet Notes du MJ actif
function CampaignsNotesD3() {
  const camp = MOCK_CAMPAIGNS[0];
  return (
    <CampaignShellD3 crumbs={["Lobby", "Campagnes"]} right={<RightOnline />}>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <CampaignsHeader />
          <div style={{ padding: "0 56px 28px", overflowY: "auto", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {MOCK_CAMPAIGNS.map(c => (
                <CampaignCard
                  key={c.id} camp={c}
                  selected={c.id === camp.id}
                  onSelect={() => {}}
                />
              ))}
            </div>
          </div>
        </div>
        <CampaignDetail camp={camp} defaultTab="notes" />
      </div>
    </CampaignShellD3>
  );
}

// 4) Modale Nouvelle campagne (par-dessus la liste)
function CampaignsNewModalD3() {
  return (
    <CampaignShellD3 crumbs={["Lobby", "Campagnes"]} right={<RightOnline />}>
      <div style={{ flex: 1, display: "flex", minHeight: 0, position: "relative" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, opacity: 0.4 }}>
          <CampaignsHeader />
          <div style={{ padding: "0 56px 28px", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {MOCK_CAMPAIGNS.slice(0, 3).map(c => (
                <CampaignCard key={c.id} camp={c} selected={false} onSelect={() => {}} />
              ))}
            </div>
          </div>
        </div>
        <NewCampaignModal onClose={() => {}} />
      </div>
    </CampaignShellD3>
  );
}

window.CampaignsListD3 = CampaignsListD3;
window.CampaignsArcD3 = CampaignsArcD3;
window.CampaignsNotesD3 = CampaignsNotesD3;
window.CampaignsNewModalD3 = CampaignsNewModalD3;
