/* ─── Vue Sorts : liste filtrable + détail complet ─── */

const SpellsView = (() => {
  const { useState, useMemo } = React;

  const LEVEL_LABELS = { 0:'Cantrip', 1:'Niveau 1', 2:'Niveau 2', 3:'Niveau 3', 4:'Niveau 4', 5:'Niveau 5', 6:'Niveau 6', 7:'Niveau 7', 8:'Niveau 8', 9:'Niveau 9' };

  /* ── Petit select stylé ── */
  function MiniSelect({ value, onChange, options, placeholder, style }) {
    return (
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{
          background:'rgba(0,0,0,0.35)', border:'1px solid var(--color-border-strong)',
          borderRadius:'var(--radius-md)', color:'var(--color-parchment)',
          padding:'5px 8px', fontSize:11, fontFamily:'var(--font-body)',
          outline:'none', cursor:'pointer', minWidth:0, flex:1, ...style,
        }}>
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }

  /* ── Chip toggle ── */
  function ToggleChip({ label, active, onClick, color }) {
    const c = color || 'var(--color-gold)';
    return (
      <button onClick={onClick} style={{
        padding:'3px 10px', borderRadius:'var(--radius-sm)',
        fontSize:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.05em',
        border: active ? `1px solid ${c}` : '1px solid var(--color-border)',
        background: active ? `color-mix(in srgb, ${c} 12%, transparent)` : 'transparent',
        color: active ? c : 'var(--color-text-muted)',
        cursor:'pointer', transition:'all 120ms ease',
      }}>{label}</button>
    );
  }

  /* ── Item de liste ── */
  function SpellListItem({ spell, selected, onClick }) {
    const schoolColor = SCHOOL_COLORS[spell.school] || 'var(--color-parchment)';
    return (
      <button onClick={onClick} style={{
        display:'flex', alignItems:'center', gap:10, width:'100%',
        padding:'8px 12px', textAlign:'left', cursor:'pointer',
        background: selected ? 'var(--color-surface-raised)' : 'transparent',
        borderLeft: selected ? `3px solid ${schoolColor}` : '3px solid transparent',
        borderTop:'none', borderRight:'none', borderBottom:'1px solid var(--color-border)',
        color:'var(--color-parchment)', transition:'all 120ms ease',
        boxShadow: selected ? 'var(--shadow-card-active)' : 'none',
      }}>
        {/* Dot école */}
        <span style={{
          width:8, height:8, borderRadius:'50%', flexShrink:0,
          background:schoolColor, boxShadow:`0 0 6px ${schoolColor}50`,
        }} />

        {/* Infos */}
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{
            fontFamily:'var(--font-display)', fontSize:13, fontWeight:700,
            letterSpacing:'0.03em', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
          }}>{spell.name}</div>
          <div style={{ fontSize:10, color:'var(--color-text-muted)', display:'flex', gap:6, alignItems:'center', marginTop:1 }}>
            <span>{spell.school}</span>
            {spell.concentration && <span style={{ color:'var(--color-gold)', fontWeight:600 }}>◉ C</span>}
            {spell.ritual && <span style={{ color:'var(--color-arcane)', fontWeight:600 }}>◈ R</span>}
          </div>
        </div>

        {/* Badge niveau */}
        <span style={{
          flexShrink:0, padding:'2px 8px', borderRadius:'var(--radius-sm)',
          fontSize:10, fontWeight:700, fontFamily:'var(--font-mono)',
          background: spell.level === 0 ? 'rgba(247,236,208,0.06)' : `color-mix(in srgb, ${schoolColor} 12%, transparent)`,
          color: spell.level === 0 ? 'var(--color-text-muted)' : schoolColor,
          border: `1px solid ${spell.level === 0 ? 'var(--color-border)' : schoolColor + '40'}`,
        }}>
          {spell.level === 0 ? 'C' : `Niv.${spell.level}`}
        </span>
      </button>
    );
  }

  /* ── Composants tag ── */
  function CompChip({ letter, label, active }) {
    return (
      <span style={{
        display:'inline-flex', alignItems:'center', gap:3,
        padding:'2px 7px', borderRadius:'var(--radius-sm)',
        fontSize:10, fontWeight:600, fontFamily:'var(--font-mono)',
        background: active ? 'rgba(247,236,208,0.08)' : 'rgba(247,236,208,0.03)',
        color: active ? 'var(--color-parchment)' : 'var(--color-text-dim)',
        border:'1px solid var(--color-border)',
      }}>
        <span style={{ fontWeight:700 }}>{letter}</span>
        {label && <span style={{ fontSize:9, fontFamily:'var(--font-body)' }}>{label}</span>}
      </span>
    );
  }

  /* ── Panneau de détail ── */
  function SpellDetail({ spell }) {
    if (!spell) return (
      <div style={{
        flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
        color:'var(--color-text-dim)', gap:12,
      }}>
        <span style={{ fontSize:48, opacity:0.15 }}>✦</span>
        <span style={{ fontFamily:'var(--font-display)', fontSize:14, letterSpacing:'0.1em', textTransform:'uppercase' }}>
          Sélectionnez un sort
        </span>
      </div>
    );

    const schoolColor = SCHOOL_COLORS[spell.school] || 'var(--color-parchment)';
    const comps = [spell.components.V && 'V', spell.components.S && 'S', spell.components.M && 'M'].filter(Boolean).join(', ');

    return (
      <div style={{ flex:1, overflowY:'auto', padding:'32px 40px 40px' }}>
        {/* Header */}
        <div style={{ marginBottom:24 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:6 }}>
            <span style={{ color:schoolColor, fontSize:18 }}>✦</span>
            <h1 style={{
              fontFamily:'var(--font-display)', fontSize:28, fontWeight:700,
              letterSpacing:'0.04em', color:'var(--color-parchment)', margin:0, lineHeight:1.2,
            }}>{spell.name.toUpperCase()}</h1>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginLeft:28 }}>
            <span style={{
              padding:'3px 10px', borderRadius:'var(--radius-sm)',
              fontSize:10, fontWeight:700, textTransform:'uppercase',
              background:`color-mix(in srgb, ${schoolColor} 15%, transparent)`,
              color:schoolColor, border:`1px solid ${schoolColor}30`,
            }}>{spell.school}</span>
            <span style={{ color:'var(--color-text-muted)', fontSize:13 }}>·</span>
            <span style={{
              fontFamily:'var(--font-display)', fontSize:13, fontWeight:700,
              color:'var(--color-parchment-dark)', letterSpacing:'0.05em',
            }}>{LEVEL_LABELS[spell.level]}</span>
          </div>
        </div>

        {/* Grille de stats */}
        <div style={{
          display:'grid', gridTemplateColumns:'1fr 1fr', gap:1,
          background:'var(--color-border)', borderRadius:'var(--radius-lg)',
          overflow:'hidden', marginBottom:20,
        }}>
          {[
            ['INCANTATION', spell.casting_time],
            ['PORTÉE', spell.range],
            ['COMPOSANTES', comps],
            ['DURÉE', spell.duration],
          ].map(([label, val]) => (
            <div key={label} style={{ background:'var(--color-surface)', padding:'12px 16px' }}>
              <div style={{
                fontFamily:'var(--font-display)', fontSize:9, fontWeight:700,
                letterSpacing:'0.15em', textTransform:'uppercase',
                color:'var(--color-text-dim)', marginBottom:4,
              }}>{label}</div>
              <div style={{
                fontFamily:'var(--font-body)', fontSize:13, fontWeight:500,
                color:'var(--color-parchment)',
              }}>{val}</div>
            </div>
          ))}
        </div>

        {/* Composante matérielle */}
        {spell.components.M && (
          <div style={{
            padding:'10px 14px', borderRadius:'var(--radius-md)',
            background:'rgba(0,0,0,0.2)', border:'1px solid var(--color-border)',
            fontSize:12, color:'var(--color-text-muted)', marginBottom:20,
            fontFamily:'var(--font-serif)', fontStyle:'italic',
          }}>
            <span style={{ color:'var(--color-parchment-dark)', fontWeight:600, fontStyle:'normal', fontFamily:'var(--font-body)', fontSize:10, textTransform:'uppercase', letterSpacing:'0.08em' }}>
              Matériel :</span> {spell.components.M}
          </div>
        )}

        {/* Tags concentration / rituel / dégâts */}
        <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:24 }}>
          {spell.concentration && (
            <span style={{
              padding:'4px 10px', borderRadius:'var(--radius-sm)',
              fontSize:10, fontWeight:700, textTransform:'uppercase',
              background:'rgba(240,199,100,0.10)', color:'var(--color-gold)',
              border:'1px solid rgba(240,199,100,0.25)',
            }}>◉ Concentration</span>
          )}
          {spell.ritual && (
            <span style={{
              padding:'4px 10px', borderRadius:'var(--radius-sm)',
              fontSize:10, fontWeight:700, textTransform:'uppercase',
              background:'rgba(192,144,255,0.10)', color:'var(--color-arcane)',
              border:'1px solid rgba(192,144,255,0.25)',
            }}>◈ Rituel</span>
          )}
          {spell.damage_type && (
            <span style={{
              padding:'4px 10px', borderRadius:'var(--radius-sm)',
              fontSize:10, fontWeight:700, textTransform:'uppercase',
              background:'rgba(255,130,71,0.10)', color:'var(--color-ember)',
              border:'1px solid rgba(255,130,71,0.25)',
            }}>◆ {spell.damage_type}</span>
          )}
        </div>

        {/* Séparateur + Description */}
        <SectionHeader label="Description" />
        <p style={{
          fontFamily:'var(--font-serif)', fontSize:15, lineHeight:1.7,
          color:'var(--color-parchment-dark)', textWrap:'pretty', margin:'0 0 24px',
        }}>{spell.description}</p>

        {/* Niveaux supérieurs */}
        {spell.higher_levels && (
          <React.Fragment>
            <SectionHeader label="Aux niveaux supérieurs" />
            <p style={{
              fontFamily:'var(--font-serif)', fontSize:14, lineHeight:1.65,
              color:'var(--color-parchment-dark)', textWrap:'pretty', margin:'0 0 24px',
              fontStyle:'italic',
            }}>{spell.higher_levels}</p>
          </React.Fragment>
        )}

        {/* Classes */}
        <SectionHeader label="Classes" />
        <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:24 }}>
          {spell.classes.map(c => (
            <span key={c} style={{
              padding:'4px 12px', borderRadius:'var(--radius-sm)',
              fontSize:11, fontWeight:600, fontFamily:'var(--font-body)',
              background:'var(--color-surface)', color:'var(--color-parchment-dark)',
              border:'1px solid var(--color-border)',
            }}>{c}</span>
          ))}
        </div>

        {/* Source */}
        <div style={{
          marginTop:16, paddingTop:16, borderTop:'1px solid var(--color-border)',
          fontSize:10, color:'var(--color-text-dim)', fontFamily:'var(--font-mono)',
        }}>Source : {spell.source}</div>
      </div>
    );
  }

  function SectionHeader({ label }) {
    return (
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10 }}>
        <span style={{
          fontFamily:'var(--font-display)', fontSize:11, fontWeight:700,
          letterSpacing:'0.12em', textTransform:'uppercase', color:'var(--color-text-muted)',
          whiteSpace:'nowrap',
        }}>{label}</span>
        <div style={{ flex:1, height:1, background:'linear-gradient(90deg, var(--color-border-strong), transparent)' }} />
      </div>
    );
  }

  /* ── Vue principale ── */
  function SpellsViewComponent() {
    const [search, setSearch] = useState('');
    const [levelFilter, setLevelFilter] = useState('');
    const [schoolFilter, setSchoolFilter] = useState('');
    const [classFilter, setClassFilter] = useState('');
    const [concOnly, setConcOnly] = useState(false);
    const [ritualOnly, setRitualOnly] = useState(false);
    const [selectedId, setSelectedId] = useState(null);

    const filtered = useMemo(() => {
      return SPELLS.filter(s => {
        if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false;
        if (levelFilter !== '' && String(s.level) !== levelFilter) return false;
        if (schoolFilter && s.school !== schoolFilter) return false;
        if (classFilter && !s.classes.includes(classFilter)) return false;
        if (concOnly && !s.concentration) return false;
        if (ritualOnly && !s.ritual) return false;
        return true;
      });
    }, [search, levelFilter, schoolFilter, classFilter, concOnly, ritualOnly]);

    // Grouper par niveau
    const grouped = useMemo(() => {
      const map = {};
      filtered.forEach(s => {
        const key = s.level;
        if (!map[key]) map[key] = [];
        map[key].push(s);
      });
      return Object.keys(map).sort((a, b) => a - b).map(k => ({
        level: parseInt(k), label: LEVEL_LABELS[parseInt(k)], spells: map[k],
      }));
    }, [filtered]);

    const selectedSpell = SPELLS.find(s => s.id === selectedId) || null;

    const levelOptions = [...new Set(SPELLS.map(s => s.level))].sort((a,b) => a-b).map(l => String(l));
    const levelLabels = { '0':'Cantrip','1':'Niv. 1','2':'Niv. 2','3':'Niv. 3','4':'Niv. 4','5':'Niv. 5','6':'Niv. 6' };

    const hasFilters = search || levelFilter !== '' || schoolFilter || classFilter || concOnly || ritualOnly;

    function clearFilters() {
      setSearch(''); setLevelFilter(''); setSchoolFilter(''); setClassFilter('');
      setConcOnly(false); setRitualOnly(false);
    }

    return (
      <div style={{ display:'flex', flex:1, minHeight:0 }}>
        {/* ── Sidebar ── */}
        <div style={{
          width:360, flexShrink:0, display:'flex', flexDirection:'column',
          borderRight:'1px solid var(--color-border)', background:'var(--color-bg-elev)',
        }}>
          {/* Search */}
          <div style={{ padding:'16px 14px 0' }}>
            <div style={{ position:'relative' }}>
              <span style={{
                position:'absolute', left:10, top:'50%', transform:'translateY(-50%)',
                color:'var(--color-text-dim)', fontSize:13, pointerEvents:'none',
              }}>◉</span>
              <input
                type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Rechercher un sort…"
                style={{
                  width:'100%', padding:'8px 12px 8px 30px',
                  background:'rgba(0,0,0,0.35)', border:'1px solid var(--color-border-strong)',
                  borderRadius:'var(--radius-md)', color:'var(--color-parchment)',
                  fontSize:13, fontFamily:'var(--font-body)', outline:'none',
                  boxSizing:'border-box',
                }}
              />
            </div>
          </div>

          {/* Filtres */}
          <div style={{ padding:'10px 14px', display:'flex', flexDirection:'column', gap:8 }}>
            <div style={{ display:'flex', gap:6 }}>
              <MiniSelect value={levelFilter} onChange={setLevelFilter}
                options={levelOptions} placeholder="Niveau" />
              <MiniSelect value={schoolFilter} onChange={setSchoolFilter}
                options={SPELL_SCHOOLS} placeholder="École" />
              <MiniSelect value={classFilter} onChange={setClassFilter}
                options={SPELL_CLASSES} placeholder="Classe" />
            </div>
            <div style={{ display:'flex', gap:6, alignItems:'center' }}>
              <ToggleChip label="◉ Concentration" active={concOnly} onClick={() => setConcOnly(!concOnly)} color="var(--color-gold)" />
              <ToggleChip label="◈ Rituel" active={ritualOnly} onClick={() => setRitualOnly(!ritualOnly)} color="var(--color-arcane)" />
              <div style={{ flex:1 }} />
              {hasFilters && (
                <button onClick={clearFilters} style={{
                  fontSize:10, color:'var(--color-text-dim)', background:'none',
                  border:'none', cursor:'pointer', textDecoration:'underline',
                }}>Effacer</button>
              )}
            </div>
          </div>

          {/* Compteur */}
          <div style={{
            padding:'6px 14px 8px', fontSize:10, color:'var(--color-text-dim)',
            fontFamily:'var(--font-mono)', borderBottom:'1px solid var(--color-border)',
          }}>
            {filtered.length} sort{filtered.length > 1 ? 's' : ''} trouvé{filtered.length > 1 ? 's' : ''}
          </div>

          {/* Liste groupée */}
          <div style={{ flex:1, overflowY:'auto' }}>
            {grouped.length === 0 && (
              <div style={{
                padding:32, textAlign:'center', color:'var(--color-text-dim)',
                fontSize:13, fontFamily:'var(--font-serif)', fontStyle:'italic',
              }}>Aucun sort ne correspond</div>
            )}
            {grouped.map(group => (
              <div key={group.level}>
                <div style={{
                  padding:'10px 14px 6px', fontSize:10, fontWeight:700,
                  fontFamily:'var(--font-display)', letterSpacing:'0.15em',
                  textTransform:'uppercase', color:'var(--color-text-dim)',
                  background:'rgba(0,0,0,0.15)',
                  borderBottom:'1px solid var(--color-border)',
                }}>
                  {group.label}
                  <span style={{ marginLeft:8, fontFamily:'var(--font-mono)', fontSize:9, color:'var(--color-text-dim)' }}>
                    ({group.spells.length})
                  </span>
                </div>
                {group.spells.map(s => (
                  <SpellListItem key={s.id} spell={s}
                    selected={s.id === selectedId}
                    onClick={() => setSelectedId(s.id)} />
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ── Detail ── */}
        <SpellDetail spell={selectedSpell} />
      </div>
    );
  }

  return SpellsViewComponent;
})();

window.SpellsView = SpellsView;
