/* Variation C — Carnet d'aventure (v2)
   Modifs:
   - Sections "Quêtes" et "Carnet" repliables (chevron)
   - Boutons par personnage : switch IA/Joueur + ouvrir fiche
*/

function VarC_AdventureLog({ density = 'compact' }) {
  const [openQuests, setOpenQuests] = React.useState(true);
  const [openMemory, setOpenMemory] = React.useState(true);
  const [openParty, setOpenParty] = React.useState(true);

  const CLASS_FR = {
    Fighter: 'Guerrier',
    Druid: 'Druide',
    Rogue: 'Roublard',
    Ranger: 'Rôdeur',
    Wizard: 'Magicien',
    Cleric: 'Clerc',
    Bard: 'Barde',
    Paladin: 'Paladin',
    Sorcerer: 'Ensorceleur',
    Warlock: 'Occultiste',
    Monk: 'Moine',
    Barbarian: 'Barbare',
  };
  const party = window.PARTY;
  const quests = window.QUESTS;
  const memory = window.MEMORY;

  function hpColor(c) {
    const pct = c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0;
    return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)';
  }

  const Chevron = ({ open }) => (
    <span
      className="font-mono text-[10px] transition-transform"
      style={{
        display: 'inline-block',
        transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
        color: 'var(--color-text-dim)',
        width: 10, textAlign: 'center',
      }}
    >▶</span>
  );

  return (
    <aside className="flex shrink-0 min-h-0 flex-col overflow-hidden" style={{ width: '380px', background: 'var(--color-bg-elev)' }}>
      {/* En-tête : date du jeu */}
      <div
        className="shrink-0 px-4 py-3 border-b"
        style={{
          borderColor: 'var(--color-border)',
          background: 'linear-gradient(180deg, rgba(240,199,100,0.06), transparent)',
        }}
      >
        <div className="rpg-eyebrow mb-1" style={{ color: 'var(--color-gold)' }}>✦ Carnet d'aventure</div>
        <div className="font-display text-[15px] font-bold" style={{ color: 'var(--color-parchment)' }}>
          Phandalin · Auberge Stonehill
        </div>
        <div className="mt-0.5 flex items-center gap-3 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          <span>☀ Aube</span>
          <span style={{ color: 'var(--color-text-dim)' }}>·</span>
          <span>Jour 3 — 6 du Hammer</span>
          <span style={{ color: 'var(--color-text-dim)' }}>·</span>
          <span>Doux</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Le groupe — repliable, avec boutons d'action */}
        <section className="px-4 pt-3 pb-2">
          <button
            onClick={() => setOpenParty(!openParty)}
            className="w-full flex items-center justify-between mb-2 py-0.5 hover:opacity-80 transition-opacity"
          >
            <span className="flex items-center gap-1.5">
              <Chevron open={openParty} />
              <span className="rpg-eyebrow">✦ Le groupe</span>
            </span>
            <span className="text-[9px] font-mono" style={{ color: 'var(--color-text-dim)' }}>{party.length}</span>
          </button>

          {openParty && (
            <div className="space-y-1.5">
              {party.map((c) => {
                const pct = (c.hp_current / c.hp_max) * 100;
                return (
                  <div
                    key={c.id}
                    className="rounded-md border px-2 py-1.5"
                    style={{
                      borderColor: c.is_self ? 'rgba(240,199,100,0.4)' : 'var(--color-border)',
                      background: c.is_self ? 'rgba(240,199,100,0.05)' : 'var(--color-surface)',
                    }}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md font-display text-[14px] font-bold"
                        style={{
                          background: c.is_ai
                            ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
                            : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
                          color: 'var(--color-bg)',
                        }}
                      >{c.initial}</div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate font-display text-[11px] font-semibold" style={{ color: c.is_self ? 'var(--color-gold)' : 'var(--color-parchment)' }}>{c.name}</span>
                          {c.is_ai && <span className="text-[8px] font-bold" style={{ color: 'var(--color-arcane)' }}>IA</span>}
                          <span className="text-[9px] italic" style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-serif)' }}>· {CLASS_FR[c.char_class] ?? c.char_class}</span>
                        </div>
                        <div className="relative mt-0.5 w-full overflow-hidden rounded-full" style={{ height: '2px', background: 'rgba(0,0,0,0.5)' }}>
                          <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: hpColor(c) }} />
                        </div>
                        <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[9px]" style={{ color: 'var(--color-text-dim)' }}>
                          <span style={{ color: hpColor(c) }}>{c.hp_current}/{c.hp_max}</span>
                          <span>·</span>
                          <span>CA {c.ac}</span>
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 text-[9px]" style={{ color: 'var(--color-parchment-dark)' }}>
                          <span title="Arme équipée">⚔</span>
                          <span className="truncate">{c.equipped}</span>
                          {c.spells_left && (
                            <>
                              <span style={{ color: 'var(--color-text-dim)' }}>·</span>
                              <span title="Sorts disponibles" className="font-mono shrink-0" style={{ color: 'var(--color-arcane)' }}>✦ {c.spells_left}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          title={c.is_ai ? 'Reprendre le contrôle (joueur)' : 'Confier à l\'IA'}
                          className="flex h-6 w-6 items-center justify-center rounded text-[11px] transition-all"
                          style={{
                            background: c.is_ai ? 'rgba(192,144,255,0.12)' : 'rgba(240,199,100,0.1)',
                            color: c.is_ai ? 'var(--color-arcane)' : 'var(--color-gold)',
                            border: `1px solid ${c.is_ai ? 'rgba(192,144,255,0.3)' : 'rgba(240,199,100,0.3)'}`,
                          }}
                        >{c.is_ai ? '🤖' : '👤'}</button>
                        <button
                          title="Ouvrir la fiche complète"
                          className="flex h-6 w-6 items-center justify-center rounded text-[11px] transition-all"
                          style={{
                            background: 'rgba(255,255,255,0.04)',
                            color: 'var(--color-parchment-dark)',
                            border: '1px solid var(--color-border-strong)',
                          }}
                        >📜</button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Quêtes en cours — repliable */}
        <section className="px-4 pt-3 pb-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <button
            onClick={() => setOpenQuests(!openQuests)}
            className="w-full flex items-center justify-between mb-2 py-0.5 hover:opacity-80 transition-opacity"
          >
            <span className="flex items-center gap-1.5">
              <Chevron open={openQuests} />
              <span className="rpg-eyebrow">◈ Quêtes en cours</span>
            </span>
            <span className="text-[9px] font-mono" style={{ color: 'var(--color-text-dim)' }}>{quests.length}</span>
          </button>

          {openQuests && (
            <div className="space-y-2">
              {quests.map((q) => {
                const tone = q.kind === 'principale' ? 'var(--color-ember)' : q.kind === 'secondaire' ? 'var(--color-gold)' : 'var(--color-arcane)';
                return (
                  <div key={q.id} className="border-l-2 pl-2.5 py-0.5" style={{ borderColor: tone }}>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[8px] font-bold uppercase tracking-[0.15em]" style={{ color: tone }}>{q.kind}</span>
                      {q.due && <span className="text-[8px]" style={{ color: 'var(--color-blood)' }}>⏳ {q.due}</span>}
                    </div>
                    <div className="font-display text-[12px] font-bold leading-tight" style={{ color: 'var(--color-parchment)' }}>{q.title}</div>
                    <div className="text-[10px] leading-snug mt-0.5" style={{ color: 'var(--color-parchment-dark)', fontFamily: 'var(--font-serif)' }}>« {q.desc} »</div>
                    {q.steps && (
                      <div className="mt-1 flex items-center gap-1.5">
                        {Array.from({ length: q.steps }).map((_, i) => (
                          <div key={i} className="h-1 flex-1 rounded-full" style={{ background: i < q.progress ? tone : 'rgba(255,255,255,0.08)' }} />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Carnet — PNJ & lieux — repliable */}
        <section className="px-4 pt-3 pb-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <button
            onClick={() => setOpenMemory(!openMemory)}
            className="w-full flex items-center justify-between mb-2 py-0.5 hover:opacity-80 transition-opacity"
          >
            <span className="flex items-center gap-1.5">
              <Chevron open={openMemory} />
              <span className="rpg-eyebrow">◉ Carnet du chroniqueur</span>
            </span>
            <span className="text-[9px] font-mono" style={{ color: 'var(--color-text-dim)' }}>{memory.length}</span>
          </button>

          {openMemory && (
            <div className="space-y-1">
              {memory.map((m, i) => (
                <div key={i} className="flex items-baseline gap-2 py-1" style={{ borderBottom: i < memory.length - 1 ? '1px dashed var(--color-border)' : 'none' }}>
                  <span className="font-mono text-[8px] shrink-0 uppercase tracking-[0.1em]" style={{ color: m.kind === 'PNJ' ? 'var(--color-arcane)' : 'var(--color-teal)' }}>{m.kind}</span>
                  <span className="font-display text-[11px] font-semibold" style={{ color: 'var(--color-parchment)' }}>{m.name}</span>
                  <span className="text-[10px] truncate flex-1" style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>— {m.detail}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}

window.VarC_AdventureLog = VarC_AdventureLog;
