/* ─── App principale : shell + navigation Grimoire / Bestiaire ─── */

const GrimoireApp = (() => {
  const { useState, useEffect } = React;

  function AppShell() {
    const [view, setView] = useState('spells');
    const [showTweaks, setShowTweaks] = useState(false);

    const TWEAK_DEFAULTS = window.__GRIMOIRE_TWEAKS;
    const [tweaks, setTweakState] = useState(TWEAK_DEFAULTS);

    function setTweak(keyOrObj, val) {
      setTweakState(prev => {
        const next = typeof keyOrObj === 'string' ? { ...prev, [keyOrObj]: val } : { ...prev, ...keyOrObj };
        try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits: typeof keyOrObj === 'string' ? { [keyOrObj]: val } : keyOrObj }, '*'); } catch {}
        return next;
      });
    }

    useEffect(() => {
      const onMsg = (e) => {
        if (e.data?.type === '__activate_edit_mode') setShowTweaks(true);
        if (e.data?.type === '__deactivate_edit_mode') setShowTweaks(false);
      };
      window.addEventListener('message', onMsg);
      try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch {}
      return () => window.removeEventListener('message', onMsg);
    }, []);

    const views = [
      { id: 'spells', label: '✦ Grimoire', icon: '✦' },
      { id: 'monsters', label: '◆ Bestiaire', icon: '◆' },
    ];

    return (
      <div style={{
        height: '100vh', display: 'flex', flexDirection: 'column',
        background: 'radial-gradient(ellipse at top, #1a1630 0%, var(--color-bg) 60%)',
        color: 'var(--color-parchment)', fontFamily: 'var(--font-body)',
        fontSize: 14, overflow: 'hidden', position: 'relative',
      }}>
        {/* Grid dust */}
        <div style={{
          position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)',
          backgroundSize: '24px 24px',
        }} />

        {/* ── Header ── */}
        <header style={{
          height: 56, display: 'flex', alignItems: 'center',
          padding: '0 24px', gap: 18, flexShrink: 0,
          borderBottom: '1px solid var(--color-border)',
          background: 'linear-gradient(180deg, var(--color-bg-elev), rgba(24,22,35,0.9))',
          position: 'relative', zIndex: 2,
        }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--grad-primary)',
              color: 'var(--color-bg)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, fontWeight: 700,
              boxShadow: '0 0 18px rgba(255,130,71,0.25)',
            }}>⚔</div>
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 700, letterSpacing: '0.1em' }}>
                RPGMASTER
              </div>
              <div style={{ fontSize: 9, color: 'var(--color-text-dim)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
                Bibliothèque
              </div>
            </div>
          </div>

          {/* Breadcrumb separator */}
          <div style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>›</div>

          {/* Nav pills */}
          <nav style={{ display: 'flex', gap: 4 }}>
            {views.map(v => {
              const active = view === v.id;
              return (
                <button key={v.id} onClick={() => setView(v.id)} style={{
                  padding: '6px 16px', borderRadius: 999,
                  fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  border: active ? '1px solid rgba(240,199,100,0.30)' : '1px solid transparent',
                  background: active ? 'rgba(240,199,100,0.10)' : 'transparent',
                  color: active ? 'var(--color-gold)' : 'var(--color-text-muted)',
                  cursor: 'pointer', transition: 'all 120ms ease',
                }}>{v.label}</button>
              );
            })}
          </nav>

          <div style={{ flex: 1 }} />

          {/* Online indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, fontWeight: 600, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-green)', boxShadow: '0 0 6px var(--color-green)' }} />
            En ligne
          </div>

          <div style={{ width: 1, height: 20, background: 'var(--color-border-strong)' }} />

          <button style={{
            padding: '5px 14px', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-strong)',
            background: 'transparent', color: 'var(--color-parchment)',
            fontSize: 11, fontWeight: 600, cursor: 'pointer',
          }}>Lobby →</button>
        </header>

        {/* ── Content ── */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative', zIndex: 1 }}>
          {view === 'spells' ? <SpellsView /> : <MonstersView />}
        </div>

        {/* ── Tweaks Panel ── */}
        {showTweaks && (
          <TweaksPanel title="Tweaks" onClose={() => {
            setShowTweaks(false);
            try { window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); } catch {}
          }}>
            <TweakSection label="Affichage">
              <TweakRadio label="Vue active" value={view}
                options={[
                  { label: 'Grimoire', value: 'spells' },
                  { label: 'Bestiaire', value: 'monsters' },
                ]}
                onChange={v => setView(v)} />
            </TweakSection>
          </TweaksPanel>
        )}
      </div>
    );
  }

  return AppShell;
})();

window.GrimoireApp = GrimoireApp;
