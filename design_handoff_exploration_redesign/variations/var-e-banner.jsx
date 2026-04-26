/* Variation E — Layout pivoté : groupe au-dessus en bandeau riche
   Au lieu d'un panneau droit, on utilise tout le bandeau supérieur (sous le header)
   pour montrer le groupe en grand format horizontal "fiches d'équipe". Le récit
   prend toute la largeur en dessous. PartyBar du bas SUPPRIMÉE.
*/

function VarE_TopBanner({ density = 'detailed' }) {
  const party = window.PARTY;

  function hpColor(c) {
    const pct = c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0;
    return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)';
  }

  return (
    <div className="shrink-0 border-b" style={{ borderColor: 'var(--color-border)', background: 'linear-gradient(180deg, rgba(255,130,71,0.04), var(--color-bg-elev))' }}>
      <div className="flex items-stretch px-4 py-3 gap-2">
        <div className="flex shrink-0 items-center px-2">
          <span className="font-mono text-[9px] font-bold uppercase tracking-[0.25em]" style={{ color: 'var(--color-text-dim)', writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>Le groupe</span>
        </div>
        {party.map((c) => {
          const pct = (c.hp_current / c.hp_max) * 100;
          return (
            <div key={c.id} className="flex flex-1 items-stretch rounded-lg border overflow-hidden" style={{ borderColor: c.is_self ? 'rgba(240,199,100,0.4)' : 'var(--color-border)', background: c.is_self ? 'rgba(240,199,100,0.04)' : 'var(--color-surface)', minWidth: 0 }}>
              <div className="flex w-12 shrink-0 items-center justify-center font-display text-lg font-bold" style={{ background: c.is_ai ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)' : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))', color: 'var(--color-bg)' }}>{c.initial}</div>
              <div className="flex-1 min-w-0 px-2.5 py-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-display text-[12px] font-bold truncate" style={{ color: c.is_self ? 'var(--color-gold)' : 'var(--color-parchment)' }}>{c.name}</span>
                  {c.is_ai && <span className="text-[8px]" style={{ color: 'var(--color-arcane)' }}>IA</span>}
                </div>
                <div className="text-[9px] truncate" style={{ color: 'var(--color-text-muted)' }}>Niv. {c.level} {c.char_class}</div>
                <div className="mt-1 flex items-center gap-2 text-[9px] font-mono" style={{ color: 'var(--color-text-dim)' }}>
                  <span style={{ color: hpColor(c) }}>{c.hp_current}/{c.hp_max}</span>
                  <span>CA {c.ac}</span>
                  {c.spells_left && <span style={{ color: 'var(--color-arcane)' }}>✦{c.spells_left}</span>}
                </div>
                <div className="mt-1 relative w-full overflow-hidden rounded-full" style={{ height: '2px', background: 'rgba(0,0,0,0.4)' }}>
                  <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: hpColor(c) }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* Aside compact à droite : juste quêtes + mémoire (compagnons sont au-dessus) */
function VarE_RightSlim() {
  const quests = window.QUESTS;
  const memory = window.MEMORY;

  return (
    <aside className="flex shrink-0 min-h-0 flex-col overflow-hidden" style={{ width: '300px', background: 'var(--color-bg-elev)' }}>
      <div className="flex shrink-0 items-center border-b px-4 py-2.5" style={{ borderColor: 'var(--color-border)' }}>
        <span className="rpg-eyebrow">◈ Aventure en cours</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        <div>
          <div className="rpg-eyebrow mb-1.5" style={{ color: 'var(--color-gold)' }}>Quêtes</div>
          <div className="space-y-1.5">
            {quests.map((q) => {
              const tone = q.kind === 'principale' ? 'var(--color-ember)' : q.kind === 'secondaire' ? 'var(--color-gold)' : 'var(--color-arcane)';
              return (
                <div key={q.id} className="border-l-2 pl-2 py-0.5" style={{ borderColor: tone }}>
                  <div className="font-display text-[11px] font-bold" style={{ color: 'var(--color-parchment)' }}>{q.title}</div>
                  <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{q.kind}{q.steps ? ` · ${q.progress}/${q.steps}` : ''}</div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="border-t pt-2.5" style={{ borderColor: 'var(--color-border)' }}>
          <div className="rpg-eyebrow mb-1.5" style={{ color: 'var(--color-arcane)' }}>Mémoire</div>
          <div className="space-y-1">
            {memory.map((m, i) => (
              <div key={i} className="flex items-baseline gap-1.5 text-[10px]">
                <span className="font-mono text-[8px] uppercase shrink-0" style={{ color: m.kind === 'PNJ' ? 'var(--color-arcane)' : 'var(--color-teal)' }}>{m.kind}</span>
                <span className="font-display font-semibold" style={{ color: 'var(--color-parchment)' }}>{m.name}</span>
                <span className="truncate italic" style={{ color: 'var(--color-text-dim)', fontFamily: 'var(--font-serif)' }}>— {m.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

Object.assign(window, { VarE_TopBanner, VarE_RightSlim });
