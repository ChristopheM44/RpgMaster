/* Shell partagé : header + narratif + cadre commun pour les variations Exploration */

const SHELL_TONE_TO_COLOR = {
  ember: 'var(--color-ember)',
  gold: 'var(--color-gold)',
  arcane: 'var(--color-arcane)',
  green: 'var(--color-green)',
  blood: 'var(--color-blood)',
  teal: 'var(--color-teal)',
};

/* ---------- Header (top bar) ---------- */
function ExplorationHeader({ phase = 'Exploration' }) {
  return (
    <header
      className="flex h-14 shrink-0 items-center gap-6 border-b px-6"
      style={{
        borderColor: 'var(--color-border)',
        background: 'linear-gradient(180deg, var(--color-bg-elev), rgba(24,22,35,0.9))',
      }}
    >
      <div className="flex shrink-0 items-center gap-3">
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold"
          style={{
            background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))',
            color: 'var(--color-bg)',
            boxShadow: '0 0 18px rgba(255,130,71,0.25)',
          }}
        >⚔</div>
        <div>
          <div className="font-display text-[15px] font-bold tracking-[0.1em]">RPGMASTER</div>
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.2em] leading-none"
            style={{ color: 'var(--color-text-dim)' }}
          >Lancement</div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center gap-2">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
          <span>Phase</span>
          <span className="font-display font-bold" style={{ color: 'var(--color-green)' }}>{phase}</span>
        </div>
        <div className="h-4 w-px mx-1" style={{ background: 'var(--color-border-strong)' }} />
        <button className="rpg-btn-tonal tone-blood !py-1.5 !text-[11px]">⚔ Combat</button>
        <button className="rpg-btn-tonal tone-arcane !py-1.5 !text-[11px]">☽ Repos</button>
        <button className="rpg-btn-tonal tone-arcane !py-1.5 !text-[11px]" title="Demander aux compagnons IA de réagir maintenant">🤖 IA réagit</button>
        <button className="rpg-btn-secondary !py-1.5 !px-4 !text-[11px]">💾 Sauvegarder</button>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
          <span className="h-2 w-2 rounded-full" style={{ background: 'var(--color-green)', boxShadow: '0 0 6px var(--color-green)' }} />
          <span>En ligne</span>
        </div>
        <div className="h-4 w-px" style={{ background: 'var(--color-border-strong)' }} />
        <button className="rpg-btn-secondary !py-1 !px-3 !text-[11px] shrink-0">Lobby →</button>
      </div>
    </header>
  );
}

/* ---------- Narratif central ---------- */
function NarrativeColumn() {
  const items = window.NARRATIVE;
  return (
    <section className="flex flex-1 min-h-0 min-w-0 flex-col overflow-hidden border-r" style={{ borderColor: 'var(--color-border)' }}>
      <div className="flex shrink-0 items-baseline gap-4 px-10 pt-8 pb-4">
        <h2 className="font-display text-[32px] font-bold tracking-[0.05em] leading-none" style={{ color: 'var(--color-parchment)' }}>
          <span style={{ color: 'var(--color-ember)' }}>✦</span> Récit
        </h2>
        <div className="flex-1 h-px" style={{ background: 'linear-gradient(90deg, var(--color-border-strong), transparent)' }} />
      </div>

      <div className="flex-1 overflow-y-auto px-10 pb-6 space-y-6">
        {items.map((entry, idx) => {
          if (entry.type === 'gm-recap' || entry.type === 'gm') {
            return (
              <div key={idx} className="space-y-3">
                {entry.type === 'gm' && (
                  <div className="rpg-eyebrow" style={{ color: 'var(--color-ember)' }}>✦ Maître du Jeu</div>
                )}
                <p className="font-serif leading-[1.8] text-pretty" style={{ fontSize: '17px', color: 'var(--color-parchment-dark)' }}>
                  {entry.text}
                </p>
              </div>
            );
          }
          if (entry.type === 'player') {
            return (
              <div
                key={idx}
                className="flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
                style={{ borderColor: 'rgba(192,144,255,0.5)', background: 'rgba(192,144,255,0.05)' }}
              >
                <div className="min-w-0 flex-1">
                  <span className="mr-2 text-sm font-display font-semibold" style={{ color: 'var(--color-arcane)' }}>{entry.who}</span>
                  <span className="text-sm" style={{ color: 'var(--color-parchment)' }}>{entry.text}</span>
                </div>
              </div>
            );
          }
          return null;
        })}
      </div>
    </section>
  );
}

/* ---------- Barre du bas : input + actions exploration ---------- */
function ExplorationActionBar({ density = 'normal', actionSet = 'contextual' }) {
  // density: 'normal' | 'compact'
  // actionSet: 'minimal' | 'utility' | 'contextual' | 'classic'
  const utility = [
    { icon: '✦', label: 'Sort utilitaire', tone: 'tone-arcane' },
    { icon: '🎒', label: 'Objet', tone: 'tone-gold' },
    { icon: '☽', label: 'Repos court', tone: 'tone-arcane' },
  ];
  const contextual = window.SUGGESTIONS;
  const classic = [
    { icon: '⚔', label: 'Attaquer', tone: 'tone-blood' },
    { icon: '✦', label: 'Sort', tone: 'tone-arcane' },
    { icon: '🎒', label: 'Objet', tone: 'tone-gold' },
    { icon: '💨', label: 'Foncer', tone: 'tone-teal' },
    { icon: '⏭', label: 'Fin du tour', tone: 'tone-gold' },
  ];

  return (
    <div
      className="shrink-0 border-t px-5"
      style={{
        borderColor: 'var(--color-border)',
        background: 'var(--color-bg-elev)',
        paddingTop: density === 'compact' ? '10px' : '16px',
        paddingBottom: density === 'compact' ? '10px' : '16px',
      }}
    >
      <div className="mb-3 flex items-center gap-2.5">
        <div
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-display text-xs font-bold"
          style={{ background: 'linear-gradient(135deg, var(--color-ember), var(--color-gold))', color: 'var(--color-bg)' }}
        >T</div>
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Vous incarnez <strong className="font-display" style={{ color: 'var(--color-parchment)' }}>Thorvald</strong>
        </span>
      </div>

      <div className="flex items-end gap-3">
        <textarea
          rows={2}
          placeholder="Décrivez votre action, parlez, ou posez une question au MJ…"
          className="rpg-input flex-1 resize-none"
          style={{ fontFamily: 'inherit', fontSize: '14px' }}
        />
        <button className="rpg-btn-primary shrink-0 self-end !px-5 !py-3">Envoyer ↵</button>
      </div>

      {actionSet === 'minimal' && null}

      {actionSet === 'utility' && (
        <div className="mt-2.5 flex items-center gap-2 flex-wrap">
          {utility.map((a) => (
            <button key={a.label} className={`rpg-btn-tonal !py-1 !text-[11px] ${a.tone}`}>
              {a.icon} {a.label}
            </button>
          ))}
        </div>
      )}

      {actionSet === 'contextual' && (
        <div className="mt-2.5 flex items-center gap-2 flex-wrap">
          <span className="rpg-eyebrow" style={{ color: 'var(--color-text-dim)' }}>Suggestions</span>
          {contextual.map((s) => (
            <button
              key={s.label}
              className="flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold transition-all hover:bg-[rgba(255,130,71,0.06)]"
              style={{
                borderColor: 'var(--color-border-strong)',
                color: 'var(--color-parchment)',
                background: 'rgba(0,0,0,0.2)',
              }}
            >
              <span style={{ filter: 'grayscale(0.2)' }}>{s.icon}</span>
              <span>{s.label}</span>
              <span className="ml-1 text-[9px] font-normal" style={{ color: 'var(--color-text-dim)' }}>{s.hint}</span>
            </button>
          ))}
          <span className="ml-auto rpg-eyebrow" style={{ color: 'var(--color-text-dim)', cursor: 'pointer' }}>+ Sort · Objet · Repos</span>
        </div>
      )}

      {actionSet === 'classic' && (
        <div className="mt-2.5 flex items-center gap-2 flex-wrap">
          {classic.map((a) => (
            <button key={a.label} className={`rpg-btn-tonal !py-1 !text-[11px] ${a.tone}`}>
              {a.icon} {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Exporte au global pour les autres scripts ---------- */
Object.assign(window, {
  ExplorationHeader,
  NarrativeColumn,
  ExplorationActionBar,
  SHELL_TONE_TO_COLOR,
});
