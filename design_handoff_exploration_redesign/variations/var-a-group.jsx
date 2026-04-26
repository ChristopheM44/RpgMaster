/* Variation A — Tableau de bord groupe
   Le panneau droit devient un dashboard détaillé du groupe :
   - en haut : 4 cartes joueur denses (PV, CA, Init, sorts dispo)
   - bas : zone "Mon perso" sélectionné en focus
   PartyBar du bas SUPPRIMÉE (déduplication).
*/

function VarA_GroupDashboard({ density = 'detailed', selectedId = 'thorvald' }) {
  const party = window.PARTY;
  const sel = party.find((p) => p.id === selectedId) ?? party[0];

  function hpColor(c) {
    const pct = c.hp_max > 0 ? (c.hp_current / c.hp_max) * 100 : 0;
    return pct > 50 ? 'var(--color-green)' : pct > 25 ? '#e5b93a' : 'var(--color-blood)';
  }

  return (
    <aside className="flex shrink-0 min-h-0 flex-col overflow-hidden" style={{ width: '380px', background: 'var(--color-bg-elev)' }}>
      {/* Section header */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-2.5" style={{ borderColor: 'var(--color-border)' }}>
        <span className="rpg-eyebrow">✦ Le groupe</span>
        <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>{party.length} aventuriers</span>
      </div>

      {/* Cartes joueur */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {party.map((c) => {
          const isSel = c.id === sel.id;
          const isMine = c.is_self;
          const pct = (c.hp_current / c.hp_max) * 100;
          return (
            <div
              key={c.id}
              className="rounded-lg border transition-all"
              style={{
                borderColor: isSel ? 'rgba(255,130,71,0.5)' : 'var(--color-border)',
                background: isSel ? 'linear-gradient(180deg, rgba(255,130,71,0.07), rgba(255,130,71,0.02))' : 'var(--color-surface)',
                boxShadow: isSel ? '0 0 16px rgba(255,130,71,0.10)' : 'none',
              }}
            >
              <div className="flex items-center gap-2.5 px-3 pt-2.5">
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
                    <span className="truncate font-display text-[13px] font-bold" style={{ color: isMine ? 'var(--color-gold)' : 'var(--color-parchment)' }}>{c.name}</span>
                    {c.is_ai && <span className="rpg-chip !py-0 !px-1.5 !text-[8px]" style={{ color: 'var(--color-arcane)', borderColor: 'rgba(192,144,255,0.4)' }}>IA</span>}
                    {isMine && <span className="rpg-chip !py-0 !px-1.5 !text-[8px]" style={{ color: 'var(--color-gold)', borderColor: 'rgba(240,199,100,0.4)' }}>Vous</span>}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                    Niv. {c.level} · {c.char_class} · {c.species}
                  </div>
                </div>
              </div>

              {/* Stats compactes */}
              <div className="px-3 pt-2 grid grid-cols-3 gap-1.5">
                {[
                  { l: 'PV', v: `${c.hp_current}/${c.hp_max}`, color: hpColor(c) },
                  { l: 'CA', v: c.ac },
                  { l: 'Init', v: c.init >= 0 ? `+${c.init}` : c.init },
                ].map((s) => (
                  <div key={s.l} className="flex flex-col items-center rounded-md py-1" style={{ background: 'rgba(0,0,0,0.3)' }}>
                    <span className="text-[8px] font-bold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-dim)' }}>{s.l}</span>
                    <span className="font-mono text-xs font-bold" style={{ color: s.color ?? 'var(--color-parchment)' }}>{s.v}</span>
                  </div>
                ))}
              </div>

              {/* HP bar */}
              <div className="px-3 pt-2">
                <div className="relative w-full overflow-hidden rounded-full" style={{ height: '4px', background: 'rgba(0,0,0,0.4)' }}>
                  <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: hpColor(c), boxShadow: `0 0 6px ${hpColor(c)}80` }} />
                </div>
              </div>

              {/* Détails (mode détaillé) */}
              {density === 'detailed' && (
                <div className="px-3 py-2 mt-1 border-t flex items-center justify-between gap-2 text-[10px]" style={{ borderColor: 'var(--color-border)' }}>
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span style={{ color: 'var(--color-text-dim)' }}>⚔</span>
                    <span className="truncate" style={{ color: 'var(--color-parchment-dark)' }}>{c.equipped}</span>
                  </div>
                  {c.spells_left ? (
                    <span className="font-mono shrink-0" style={{ color: 'var(--color-arcane)' }}>✦ {c.spells_left}</span>
                  ) : null}
                </div>
              )}

              {/* Actions ligne (uniquement carte sélectionnée) */}
              {isSel && (
                <div className="flex gap-1.5 px-3 pb-2.5 pt-1">
                  <button className="flex-1 rpg-btn-secondary !py-1 !text-[10px] justify-center">Fiche</button>
                  <button className="flex-1 rpg-btn-tonal tone-arcane !py-1 !text-[10px]">{c.is_ai ? 'Reprendre' : 'Confier IA'}</button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer focus perso actif */}
      <div className="shrink-0 border-t px-4 py-3" style={{ borderColor: 'var(--color-border)', background: 'rgba(0,0,0,0.2)' }}>
        <div className="flex items-center justify-between">
          <span className="rpg-eyebrow">✦ Votre tour</span>
          <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>en exploration</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md font-display text-sm font-bold" style={{ background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))', color: 'var(--color-bg)' }}>T</div>
          <div className="min-w-0 flex-1">
            <div className="font-display text-[13px] font-bold" style={{ color: 'var(--color-parchment)' }}>Thorvald</div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>Aucune contrainte de tour — agissez librement</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

window.VarA_GroupDashboard = VarA_GroupDashboard;
