/* Variation D — Vue immersive éditoriale
   Le panneau droit est minimal et cinématographique :
   - "Le moment" en haut : lieu, ambiance, jour de jeu (mood)
   - Carrousel groupe vertical en grandes "tuiles photo"
   - Pas d'onglets, scroll discret. Plus de respiration / typo serif.
*/

function VarD_Editorial({ density = 'detailed' }) {
  const party = window.PARTY;
  const quests = window.QUESTS.filter(q => q.kind === 'principale').slice(0, 1);

  function hpColor(c) {
    const pct = c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0;
    return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)';
  }

  return (
    <aside className="flex shrink-0 min-h-0 flex-col overflow-hidden" style={{ width: '380px', background: 'var(--color-bg-elev)' }}>
      {/* Hero "moment" */}
      <div className="shrink-0 relative overflow-hidden">
        <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at top, rgba(255,130,71,0.18), transparent 70%)' }} />
        <div className="relative px-5 pt-5 pb-4">
          <div className="rpg-eyebrow mb-2" style={{ color: 'var(--color-ember)' }}>Le moment</div>
          <div className="font-display text-[18px] font-bold leading-tight" style={{ color: 'var(--color-parchment)' }}>
            L'aube à Phandalin
          </div>
          <div className="mt-1 font-serif text-[12px] italic leading-snug" style={{ color: 'var(--color-parchment-dark)' }}>
            « Les premiers rayons traversent les volets. Le groupe partage un dernier repas avant la route. »
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-dim)' }}>
            <span>☀ Aube</span><span>·</span><span>Jour 3</span><span>·</span><span>Calme</span>
          </div>
        </div>
      </div>

      {/* Bandeau quête principale */}
      {quests.length > 0 && (
        <div className="shrink-0 mx-4 my-2 rounded-lg border px-3 py-2" style={{ borderColor: 'rgba(255,130,71,0.3)', background: 'rgba(255,130,71,0.05)' }}>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[8px] font-bold uppercase tracking-[0.15em]" style={{ color: 'var(--color-ember)' }}>◈ Quête principale</span>
            {quests[0].due && <span className="text-[9px]" style={{ color: 'var(--color-blood)' }}>⏳ {quests[0].due}</span>}
          </div>
          <div className="font-display text-[12px] font-bold" style={{ color: 'var(--color-parchment)' }}>{quests[0].title}</div>
          <div className="mt-1.5 flex items-center gap-1">
            {Array.from({ length: quests[0].steps }).map((_, i) => (
              <div key={i} className="h-0.5 flex-1 rounded-full" style={{ background: i < quests[0].progress ? 'var(--color-ember)' : 'rgba(255,255,255,0.08)' }} />
            ))}
          </div>
        </div>
      )}

      {/* Groupe — tuiles verticales éditoriales */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <div className="flex items-center justify-between mb-2 pt-1">
          <span className="rpg-eyebrow">✦ Compagnons</span>
          <button className="text-[9px] font-bold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-dim)' }}>Voir tout →</button>
        </div>

        <div className="space-y-2">
          {party.map((c) => {
            const pct = (c.hp_current / c.hp_max) * 100;
            const accent = c.is_self ? 'var(--color-gold)' : c.is_ai ? 'var(--color-arcane)' : 'var(--color-parchment)';
            return (
              <div key={c.id} className="rounded-lg border overflow-hidden" style={{ borderColor: c.is_self ? 'rgba(240,199,100,0.35)' : 'var(--color-border)', background: 'var(--color-surface)' }}>
                <div className="flex items-stretch">
                  <div className="flex w-[68px] shrink-0 items-center justify-center font-display text-[28px] font-bold" style={{ background: c.is_ai ? 'linear-gradient(135deg, var(--color-arcane), #7050b0)' : 'linear-gradient(135deg, var(--color-ember), var(--color-gold))', color: 'var(--color-bg)' }}>{c.initial}</div>
                  <div className="flex-1 px-3 py-2 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-display text-[13px] font-bold truncate" style={{ color: accent }}>{c.name}</span>
                      {c.is_ai && <span className="text-[8px]" style={{ color: 'var(--color-arcane)' }}>· IA</span>}
                      {c.is_self && <span className="text-[8px]" style={{ color: 'var(--color-gold)' }}>· vous</span>}
                    </div>
                    <div className="text-[10px]" style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>{c.char_class} · {c.species}</div>

                    <div className="mt-2 flex items-center gap-2.5">
                      <div className="flex items-baseline gap-1">
                        <span className="font-mono text-[11px] font-bold" style={{ color: hpColor(c) }}>{c.hp_current}</span>
                        <span className="text-[9px]" style={{ color: 'var(--color-text-dim)' }}>/{c.hp_max} pv</span>
                      </div>
                      <span className="text-[9px] font-mono" style={{ color: 'var(--color-text-dim)' }}>CA {c.ac}</span>
                      {c.spells_left && <span className="text-[9px] font-mono" style={{ color: 'var(--color-arcane)' }}>✦ {c.spells_left}</span>}
                    </div>
                    <div className="mt-1 relative w-full overflow-hidden rounded-full" style={{ height: '2px', background: 'rgba(0,0,0,0.4)' }}>
                      <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: hpColor(c) }} />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

window.VarD_Editorial = VarD_Editorial;
