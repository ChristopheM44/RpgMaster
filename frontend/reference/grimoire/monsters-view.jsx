/* ─── Vue Monstres : liste filtrable + détail complet avec bloc de stats ─── */

const MonstersView = (() => {
  const { useState, useMemo } = React;

  const CR_ORDER = ['0','1/8','1/4','1/2','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30'];
  function crToNum(cr) { if (cr.includes('/')) { const [a,b]=cr.split('/'); return parseInt(a)/parseInt(b); } return parseInt(cr); }

  /* ── Petit select stylé ── */
  function MiniSelect({ value, onChange, options, placeholder }) {
    return (
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{
          background:'rgba(0,0,0,0.35)', border:'1px solid var(--color-border-strong)',
          borderRadius:'var(--radius-md)', color:'var(--color-parchment)',
          padding:'5px 8px', fontSize:11, fontFamily:'var(--font-body)',
          outline:'none', cursor:'pointer', minWidth:0, flex:1,
        }}>
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }

  /* ── Item de liste ── */
  function MonsterListItem({ monster, selected, onClick }) {
    const typeColor = TYPE_COLORS[monster.type] || 'var(--color-parchment)';
    return (
      <button onClick={onClick} style={{
        display:'flex', alignItems:'center', gap:10, width:'100%',
        padding:'8px 12px', textAlign:'left', cursor:'pointer',
        background: selected ? 'var(--color-surface-raised)' : 'transparent',
        borderLeft: selected ? `3px solid ${typeColor}` : '3px solid transparent',
        borderTop:'none', borderRight:'none', borderBottom:'1px solid var(--color-border)',
        color:'var(--color-parchment)', transition:'all 120ms ease',
        boxShadow: selected ? 'var(--shadow-card-active)' : 'none',
      }}>
        <span style={{
          width:8, height:8, borderRadius:'50%', flexShrink:0,
          background:typeColor, boxShadow:`0 0 6px ${typeColor}50`,
        }} />
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{
            fontFamily:'var(--font-display)', fontSize:13, fontWeight:700,
            letterSpacing:'0.03em', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
          }}>{monster.name}</div>
          <div style={{ fontSize:10, color:'var(--color-text-muted)', display:'flex', gap:4, alignItems:'center', marginTop:1 }}>
            <span>{monster.type}</span>
            <span style={{ color:'var(--color-text-dim)' }}>·</span>
            <span>{monster.size}</span>
          </div>
        </div>
        <span style={{
          flexShrink:0, padding:'2px 8px', borderRadius:'var(--radius-sm)',
          fontSize:10, fontWeight:700, fontFamily:'var(--font-mono)',
          background:`color-mix(in srgb, ${typeColor} 12%, transparent)`,
          color:typeColor, border:`1px solid ${typeColor}40`,
        }}>FP {monster.challenge}</span>
      </button>
    );
  }

  /* ── Bloc de stats 6 caractéristiques ── */
  function AbilityBlock({ abilities }) {
    const keys = ['FOR','DEX','CON','INT','SAG','CHA'];
    return (
      <div style={{
        display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:1,
        background:'var(--color-border)', borderRadius:'var(--radius-md)',
        overflow:'hidden', marginBottom:20,
      }}>
        {keys.map(k => (
          <div key={k} style={{
            background:'var(--color-surface)', padding:'10px 0',
            display:'flex', flexDirection:'column', alignItems:'center', gap:2,
          }}>
            <div style={{
              fontFamily:'var(--font-display)', fontSize:9, fontWeight:700,
              letterSpacing:'0.15em', color:'var(--color-text-dim)',
            }}>{k}</div>
            <div style={{
              fontFamily:'var(--font-mono)', fontSize:18, fontWeight:700,
              color:'var(--color-parchment)',
            }}>{abilities[k].v}</div>
            <div style={{
              fontFamily:'var(--font-mono)', fontSize:11, fontWeight:500,
              color:'var(--color-text-muted)',
            }}>{abilities[k].m}</div>
          </div>
        ))}
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

  /* ── Trait / Action block ── */
  function TraitBlock({ items, label }) {
    if (!items || items.length === 0) return null;
    return (
      <React.Fragment>
        <SectionHeader label={label} />
        <div style={{ display:'flex', flexDirection:'column', gap:14, marginBottom:24 }}>
          {items.map((t, i) => (
            <div key={i}>
              <div style={{
                fontFamily:'var(--font-display)', fontSize:13, fontWeight:700,
                color:'var(--color-parchment)', marginBottom:4, letterSpacing:'0.02em',
              }}>
                {t.name}
                {t.name.includes('recharge') || t.name.includes('Recharge') ? '' : '.'}
              </div>
              <p style={{
                fontFamily:'var(--font-serif)', fontSize:13, lineHeight:1.65,
                color:'var(--color-parchment-dark)', margin:0, textWrap:'pretty',
              }}>{t.desc}</p>
            </div>
          ))}
        </div>
      </React.Fragment>
    );
  }

  /* ── Panneau de détail ── */
  function MonsterDetail({ monster }) {
    if (!monster) return (
      <div style={{
        flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
        color:'var(--color-text-dim)', gap:12,
      }}>
        <span style={{ fontSize:48, opacity:0.15 }}>◆</span>
        <span style={{ fontFamily:'var(--font-display)', fontSize:14, letterSpacing:'0.1em', textTransform:'uppercase' }}>
          Sélectionnez un monstre
        </span>
      </div>
    );

    const typeColor = TYPE_COLORS[monster.type] || 'var(--color-parchment)';

    return (
      <div style={{ flex:1, overflowY:'auto', padding:'32px 40px 40px' }}>
        {/* Header */}
        <div style={{ marginBottom:24 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:6 }}>
            <span style={{ color:typeColor, fontSize:18 }}>◆</span>
            <h1 style={{
              fontFamily:'var(--font-display)', fontSize:28, fontWeight:700,
              letterSpacing:'0.04em', color:'var(--color-parchment)', margin:0, lineHeight:1.2,
            }}>{monster.name.toUpperCase()}</h1>
          </div>
          <div style={{
            marginLeft:28, fontSize:13, color:'var(--color-parchment-dark)',
            fontFamily:'var(--font-serif)', fontStyle:'italic',
          }}>
            {monster.type}{monster.subtype ? ` (${monster.subtype})` : ''} de taille {monster.size.toLowerCase()}, {monster.alignment.toLowerCase()}
          </div>
        </div>

        {/* Stats principaux : CA, PV, Vitesse */}
        <div style={{
          display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:1,
          background:'var(--color-border)', borderRadius:'var(--radius-lg)',
          overflow:'hidden', marginBottom:20,
        }}>
          <div style={{ background:'var(--color-surface)', padding:'14px 16px' }}>
            <div style={{
              fontFamily:'var(--font-display)', fontSize:9, fontWeight:700,
              letterSpacing:'0.15em', textTransform:'uppercase',
              color:'var(--color-text-dim)', marginBottom:4,
            }}>Classe d'armure</div>
            <div style={{ display:'flex', alignItems:'baseline', gap:6 }}>
              <span style={{ fontFamily:'var(--font-mono)', fontSize:22, fontWeight:700, color:'var(--color-parchment)' }}>
                {monster.ac}
              </span>
              {monster.ac_type && (
                <span style={{ fontSize:10, color:'var(--color-text-muted)', fontFamily:'var(--font-body)' }}>
                  {monster.ac_type}
                </span>
              )}
            </div>
          </div>
          <div style={{ background:'var(--color-surface)', padding:'14px 16px' }}>
            <div style={{
              fontFamily:'var(--font-display)', fontSize:9, fontWeight:700,
              letterSpacing:'0.15em', textTransform:'uppercase',
              color:'var(--color-text-dim)', marginBottom:4,
            }}>Points de vie</div>
            <div style={{ display:'flex', alignItems:'baseline', gap:6 }}>
              <span style={{ fontFamily:'var(--font-mono)', fontSize:22, fontWeight:700, color:'var(--color-parchment)' }}>
                {monster.hp}
              </span>
              <span style={{ fontSize:10, color:'var(--color-text-muted)', fontFamily:'var(--font-mono)' }}>
                ({monster.hp_dice})
              </span>
            </div>
          </div>
          <div style={{ background:'var(--color-surface)', padding:'14px 16px' }}>
            <div style={{
              fontFamily:'var(--font-display)', fontSize:9, fontWeight:700,
              letterSpacing:'0.15em', textTransform:'uppercase',
              color:'var(--color-text-dim)', marginBottom:4,
            }}>Vitesse</div>
            <div style={{ fontSize:13, color:'var(--color-parchment)', fontFamily:'var(--font-body)' }}>
              {Object.entries(monster.speed).map(([k, v], i) => (
                <span key={k}>
                  {i > 0 && <span style={{ color:'var(--color-text-dim)' }}>, </span>}
                  {k !== 'marche' && <span style={{ color:'var(--color-text-muted)', fontSize:11 }}>{k} </span>}
                  <span style={{ fontFamily:'var(--font-mono)', fontWeight:600 }}>{v}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Caractéristiques */}
        <AbilityBlock abilities={monster.abilities} />

        {/* Jets de sauvegarde */}
        {monster.saving_throws && (
          <InfoLine label="Jets de sauvegarde"
            value={Object.entries(monster.saving_throws).map(([k,v]) => `${k} ${v}`).join(', ')} />
        )}

        {/* Compétences */}
        {monster.skills && Object.keys(monster.skills).length > 0 && (
          <InfoLine label="Compétences"
            value={Object.entries(monster.skills).map(([k,v]) => `${k} ${v}`).join(', ')} />
        )}

        {/* Résistances */}
        {monster.damage_resistances.length > 0 && (
          <InfoLine label="Résistances" value={monster.damage_resistances.join(', ')} />
        )}

        {/* Immunités dégâts */}
        {monster.damage_immunities.length > 0 && (
          <InfoLine label="Immunités (dégâts)" value={monster.damage_immunities.join(', ')} />
        )}

        {/* Immunités conditions */}
        {monster.condition_immunities.length > 0 && (
          <InfoLine label="Immunités (conditions)" value={monster.condition_immunities.join(', ')} />
        )}

        {/* Sens */}
        <InfoLine label="Sens" value={monster.senses} />

        {/* Langues */}
        <InfoLine label="Langues" value={monster.languages} />

        {/* FP */}
        <div style={{
          display:'flex', alignItems:'center', gap:10, padding:'10px 0',
          borderBottom:'1px solid var(--color-border)', marginBottom:20,
        }}>
          <span style={{
            fontFamily:'var(--font-body)', fontSize:11, fontWeight:600,
            color:'var(--color-text-muted)', textTransform:'uppercase',
            letterSpacing:'0.08em', width:140, flexShrink:0,
          }}>Facteur de puissance</span>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:14, fontWeight:700, color:'var(--color-parchment)' }}>
            {monster.challenge}
          </span>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--color-text-muted)' }}>
            ({monster.xp.toLocaleString('fr-FR')} XP)
          </span>
        </div>

        {/* Capacités */}
        <TraitBlock items={monster.traits} label="Capacités" />

        {/* Actions */}
        <TraitBlock items={monster.actions} label="Actions" />

        {/* Réactions */}
        {monster.reactions && <TraitBlock items={monster.reactions} label="Réactions" />}

        {/* Actions légendaires */}
        {monster.legendary_actions && <TraitBlock items={monster.legendary_actions} label="Actions légendaires" />}

        {/* Environnement */}
        {monster.environment && monster.environment.length > 0 && (
          <React.Fragment>
            <SectionHeader label="Environnement" />
            <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:24 }}>
              {monster.environment.map(e => (
                <span key={e} style={{
                  padding:'4px 12px', borderRadius:'var(--radius-sm)',
                  fontSize:11, fontWeight:600, fontFamily:'var(--font-body)',
                  background:'var(--color-surface)', color:'var(--color-parchment-dark)',
                  border:'1px solid var(--color-border)',
                }}>{e}</span>
              ))}
            </div>
          </React.Fragment>
        )}

        {/* Source */}
        <div style={{
          marginTop:16, paddingTop:16, borderTop:'1px solid var(--color-border)',
          fontSize:10, color:'var(--color-text-dim)', fontFamily:'var(--font-mono)',
        }}>Source : {monster.source}</div>
      </div>
    );
  }

  function InfoLine({ label, value }) {
    return (
      <div style={{
        display:'flex', alignItems:'baseline', gap:10, padding:'6px 0',
        borderBottom:'1px solid var(--color-border)',
      }}>
        <span style={{
          fontFamily:'var(--font-body)', fontSize:11, fontWeight:600,
          color:'var(--color-text-muted)', textTransform:'uppercase',
          letterSpacing:'0.08em', width:140, flexShrink:0,
        }}>{label}</span>
        <span style={{
          fontFamily:'var(--font-body)', fontSize:12, color:'var(--color-parchment-dark)',
        }}>{value}</span>
      </div>
    );
  }

  /* ── Vue principale ── */
  function MonstersViewComponent() {
    const [search, setSearch] = useState('');
    const [crFilter, setCrFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('');
    const [sizeFilter, setSizeFilter] = useState('');
    const [selectedId, setSelectedId] = useState(null);

    const crOptions = useMemo(() => {
      const crs = [...new Set(MONSTERS.map(m => m.challenge))];
      return crs.sort((a, b) => crToNum(a) - crToNum(b));
    }, []);

    const typeOptions = useMemo(() => {
      return [...new Set(MONSTERS.map(m => m.type))].sort();
    }, []);

    const sizeOptions = useMemo(() => {
      return MONSTER_SIZES.filter(s => MONSTERS.some(m => m.size === s));
    }, []);

    const filtered = useMemo(() => {
      return MONSTERS.filter(m => {
        if (search && !m.name.toLowerCase().includes(search.toLowerCase())) return false;
        if (crFilter && m.challenge !== crFilter) return false;
        if (typeFilter && m.type !== typeFilter) return false;
        if (sizeFilter && m.size !== sizeFilter) return false;
        return true;
      });
    }, [search, crFilter, typeFilter, sizeFilter]);

    // Grouper par CR
    const grouped = useMemo(() => {
      const map = {};
      filtered.forEach(m => {
        const key = m.challenge;
        if (!map[key]) map[key] = [];
        map[key].push(m);
      });
      return Object.keys(map).sort((a, b) => crToNum(a) - crToNum(b)).map(k => ({
        cr: k, label: `FP ${k}`, monsters: map[k],
      }));
    }, [filtered]);

    const selectedMonster = MONSTERS.find(m => m.id === selectedId) || null;

    const hasFilters = search || crFilter || typeFilter || sizeFilter;

    function clearFilters() {
      setSearch(''); setCrFilter(''); setTypeFilter(''); setSizeFilter('');
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
                placeholder="Rechercher un monstre…"
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
              <MiniSelect value={crFilter} onChange={setCrFilter}
                options={crOptions} placeholder="FP" />
              <MiniSelect value={typeFilter} onChange={setTypeFilter}
                options={typeOptions} placeholder="Type" />
              <MiniSelect value={sizeFilter} onChange={setSizeFilter}
                options={sizeOptions} placeholder="Taille" />
            </div>
            <div style={{ display:'flex', gap:6, alignItems:'center' }}>
              <div style={{ flex:1 }} />
              {hasFilters && (
                <button onClick={clearFilters} style={{
                  fontSize:10, color:'var(--color-text-dim)', background:'none',
                  border:'none', cursor:'pointer', textDecoration:'underline',
                }}>Effacer les filtres</button>
              )}
            </div>
          </div>

          {/* Compteur */}
          <div style={{
            padding:'6px 14px 8px', fontSize:10, color:'var(--color-text-dim)',
            fontFamily:'var(--font-mono)', borderBottom:'1px solid var(--color-border)',
          }}>
            {filtered.length} monstre{filtered.length > 1 ? 's' : ''} trouvé{filtered.length > 1 ? 's' : ''}
          </div>

          {/* Liste groupée */}
          <div style={{ flex:1, overflowY:'auto' }}>
            {grouped.length === 0 && (
              <div style={{
                padding:32, textAlign:'center', color:'var(--color-text-dim)',
                fontSize:13, fontFamily:'var(--font-serif)', fontStyle:'italic',
              }}>Aucun monstre ne correspond</div>
            )}
            {grouped.map(group => (
              <div key={group.cr}>
                <div style={{
                  padding:'10px 14px 6px', fontSize:10, fontWeight:700,
                  fontFamily:'var(--font-display)', letterSpacing:'0.15em',
                  textTransform:'uppercase', color:'var(--color-text-dim)',
                  background:'rgba(0,0,0,0.15)',
                  borderBottom:'1px solid var(--color-border)',
                }}>
                  {group.label}
                  <span style={{ marginLeft:8, fontFamily:'var(--font-mono)', fontSize:9 }}>
                    ({group.monsters.length})
                  </span>
                </div>
                {group.monsters.map(m => (
                  <MonsterListItem key={m.id} monster={m}
                    selected={m.id === selectedId}
                    onClick={() => setSelectedId(m.id)} />
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ── Detail ── */}
        <MonsterDetail monster={selectedMonster} />
      </div>
    );
  }

  return MonstersViewComponent;
})();

window.MonstersView = MonstersView;
