/* Variation B — Onglets : Groupe / Quêtes / Mémoire
   Le panneau droit présente trois onglets pour réunir tous les sujets
   pertinents en exploration. PartyBar du bas SUPPRIMÉE.
*/

function VarB_TabbedCompanion({ density = 'compact', initialTab = 'group' }) {
  const [tab, setTab] = React.useState(initialTab);
  const party = window.PARTY;
  const quests = window.QUESTS;
  const memory = window.MEMORY;

  function hpColor(c) {
    const pct = c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0;
    return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)';
  }

  const TABS = [
    { id: 'group', label: 'Groupe', icon: '✦', count: party.length },
    { id: 'quest', label: 'Quêtes', icon: '◈', count: quests.length },
    { id: 'memo',  label: 'Mémoire', icon: '◉', count: memory.length },
  ];

  return (
    <aside className="flex shrink-0 min-h-0 flex-col overflow-hidden" style={{ width: '380px', background: 'var(--color-bg-elev)' }}>
      {/* Tabs header */}
      <div className="flex shrink-0 border-b" style={{ borderColor: 'var(--color-border)' }}>
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="flex flex-1 items-center justify-center gap-1.5 px-3 py-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-all"
              style={{
                color: active ? 'var(--color-ember)' : 'var(--color-text-muted)',
                background: active ? 'rgba(255,130,71,0.06)' : 'transparent',
                borderBottom: active ? '2px solid var(--color-ember)' : '2px solid transparent',
              }}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
              <span className="text-[9px] font-mono opacity-70">{t.count}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'group' && (
          <div className="p-3 space-y-2">
            {party.map((c) => {
              const pct = (c.hp_current / c.hp_max) * 100;
              return (
                <div key={c.id} className="rounded-lg border px-3 py-2.5" style={{ borderColor: c.is_self ? 'rgba(240,199,100,0.4)' : 'var(--color-border)', background: c.is_self ? 'rgba(240,199,100,0.04)' : 'var(--color-surface)' }}>
                  <div className="flex items-center gap-2.5">
                    <div
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-display text-base font-bold"
                      style={{
                        background: c.is_ai
                          ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)'
                          : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
                        color: 'var(--color-bg)',
                      }}
                    >{c.initial}</div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-display text-[13px] font-bold" style={{ color: c.is_self ? 'var(--color-gold)' : 'var(--color-parchment)' }}>{c.name}</span>
                        {c.is_ai && <span className="text-[8px] font-bold" style={{ color: 'var(--color-arcane)' }}>IA</span>}
                      </div>
                      <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>Niv. {c.level} {c.char_class}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-[11px] font-bold" style={{ color: hpColor(c) }}>{c.hp_current}/{c.hp_max}</div>
                      <div className="text-[9px]" style={{ color: 'var(--color-text-dim)' }}>CA {c.ac}</div>
                    </div>
                  </div>
                  <div className="mt-2 relative w-full overflow-hidden rounded-full" style={{ height: '3px', background: 'rgba(0,0,0,0.4)' }}>
                    <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: hpColor(c) }} />
                  </div>
                  {density === 'detailed' && (
                    <div className="mt-2 flex items-center justify-between text-[10px]">
                      <span style={{ color: 'var(--color-parchment-dark)' }}>⚔ {c.equipped}</span>
                      {c.spells_left && <span className="font-mono" style={{ color: 'var(--color-arcane)' }}>✦ {c.spells_left}</span>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {tab === 'quest' && (
          <div className="p-3 space-y-2.5">
            {quests.map((q) => {
              const tone = q.kind === 'principale' ? 'var(--color-ember)' : q.kind === 'secondaire' ? 'var(--color-gold)' : 'var(--color-arcane)';
              return (
                <div key={q.id} className="rounded-lg border px-3 py-2.5" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="rpg-chip !py-0 !px-1.5 !text-[8px]" style={{ color: tone, borderColor: tone, opacity: 0.85 }}>
                      {q.kind}
                    </span>
                    {q.due && <span className="text-[9px]" style={{ color: 'var(--color-blood)' }}>⏳ {q.due}</span>}
                  </div>
                  <div className="font-display text-[13px] font-bold" style={{ color: 'var(--color-parchment)' }}>{q.title}</div>
                  <div className="mt-1 text-[11px] leading-snug" style={{ color: 'var(--color-parchment-dark)' }}>{q.desc}</div>
                  {q.steps && (
                    <div className="mt-2 flex items-center gap-2">
                      <div className="relative flex-1 overflow-hidden rounded-full" style={{ height: '3px', background: 'rgba(0,0,0,0.4)' }}>
                        <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${(q.progress / q.steps) * 100}%`, background: tone }} />
                      </div>
                      <span className="font-mono text-[9px]" style={{ color: 'var(--color-text-dim)' }}>{q.progress}/{q.steps}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {tab === 'memo' && (
          <div className="p-3 space-y-1.5">
            {memory.map((m, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border px-2.5 py-2" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
                <span className="rpg-chip !py-0 !px-1.5 !text-[8px] shrink-0 mt-0.5" style={{ color: m.kind === 'PNJ' ? 'var(--color-arcane)' : 'var(--color-teal)', borderColor: 'var(--color-border-strong)' }}>{m.kind}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-display text-[12px] font-semibold" style={{ color: 'var(--color-parchment)' }}>{m.name}</div>
                  <div className="text-[10px] leading-snug" style={{ color: 'var(--color-text-muted)' }}>{m.detail}</div>
                </div>
                <span className="text-[9px] shrink-0 italic" style={{ color: m.tag === 'danger' ? 'var(--color-blood)' : m.tag === 'allié' ? 'var(--color-green)' : 'var(--color-text-dim)' }}>{m.tag}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

window.VarB_TabbedCompanion = VarB_TabbedCompanion;
