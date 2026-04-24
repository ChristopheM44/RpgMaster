// Direction 3 — Confirm Dialog previews
// Montre 4 tonalités du dialog : danger, warning, arcane, info
// + un cas "avec contenu custom" (liste).

const { useState: useStateD3C } = React;

const D3C = {
  bg: "#0e0d14",
  bgElev: "#181623",
  surface: "#1f1c2e",
  border: "rgba(255, 235, 180, 0.07)",
  borderStrong: "rgba(255, 235, 180, 0.18)",
  text: "#f7ecd0",
  textSoft: "rgba(247, 236, 208, 0.75)",
  textMuted: "rgba(247, 236, 208, 0.5)",
  textDim: "rgba(247, 236, 208, 0.32)",
  gold: "#f0c764",
  ember: "#ff8247",
  blood: "#e84545",
  arcane: "#c090ff",
  teal: "#4fd8c0",
};

const TONES_C = {
  danger: { color: D3C.blood, glow: "rgba(232,69,69,0.35)", bg: "rgba(232,69,69,0.10)", icon: "⚠" },
  warning: { color: D3C.gold, glow: "rgba(240,199,100,0.35)", bg: "rgba(240,199,100,0.10)", icon: "⚔" },
  arcane: { color: D3C.arcane, glow: "rgba(192,144,255,0.35)", bg: "rgba(192,144,255,0.10)", icon: "✦" },
  info: { color: D3C.teal, glow: "rgba(79,216,192,0.30)", bg: "rgba(79,216,192,0.10)", icon: "?" },
};

function ConfirmDialogShell({
  width = 620, height = 560, sceneBg, children,
}) {
  return (
    <div style={{
      width, height,
      background: sceneBg || `radial-gradient(ellipse at top, #1a1630 0%, ${D3C.bg} 60%)`,
      color: D3C.text,
      fontFamily: "'Inter', system-ui, sans-serif",
      position: "relative", overflow: "hidden",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {/* grid dust */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)",
        backgroundSize: "24px 24px",
      }} />
      {/* backdrop blur */}
      <div style={{
        position: "absolute", inset: 0,
        background: "rgba(7, 6, 12, 0.72)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
      }} />
      {children}
    </div>
  );
}

function ConfirmDialog({ tone = "danger", title, message, confirmLabel, cancelLabel, children, loading }) {
  const preset = TONES_C[tone];
  return (
    <div style={{
      position: "relative",
      width: 420,
      background: `linear-gradient(180deg, ${D3C.bgElev}, ${D3C.bg})`,
      border: `1px solid ${D3C.borderStrong}`,
      borderRadius: 14,
      overflow: "hidden",
      boxShadow: `0 24px 60px rgba(0,0,0,0.65), 0 0 0 1px ${preset.glow}, 0 0 40px ${preset.glow}`,
    }}>
      {/* Top ribbon */}
      <div style={{
        height: 3, width: "100%",
        background: `linear-gradient(90deg, transparent, ${preset.color}, transparent)`,
      }} />

      {/* Glow behind icon */}
      <div style={{
        position: "absolute", top: -60, left: "50%", transform: "translateX(-50%)",
        width: 220, height: 220, borderRadius: 110,
        background: `radial-gradient(circle, ${preset.glow}, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative", padding: "28px 32px 24px" }}>
        {/* Icon medallion */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 28,
            background: preset.bg,
            border: `1px solid ${preset.color}50`,
            color: preset.color,
            fontSize: 26, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 0 24px ${preset.glow}, inset 0 0 12px ${preset.glow}`,
          }}>{preset.icon}</div>
        </div>

        {/* Eyebrow */}
        <div style={{
          textAlign: "center", marginBottom: 8,
          fontSize: 10, fontWeight: 700, letterSpacing: "0.25em",
          textTransform: "uppercase", color: preset.color,
        }}>
          <span style={{ marginRight: 6 }}>✦</span>
          Confirmation requise
        </div>

        {/* Title */}
        <h2 style={{
          margin: "0 0 8px",
          textAlign: "center",
          fontFamily: "'Cinzel', serif",
          fontSize: 22, fontWeight: 700,
          lineHeight: 1.15, letterSpacing: 0.8,
          color: D3C.text,
        }}>{title}</h2>

        {/* Message */}
        {message && (
          <p style={{
            margin: "0 auto 24px", maxWidth: 320,
            textAlign: "center",
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 14, fontStyle: "italic",
            lineHeight: 1.55, color: D3C.textSoft, textWrap: "pretty",
          }}>{message}</p>
        )}

        {/* Custom content */}
        {children && <div style={{ marginBottom: 20 }}>{children}</div>}

        {/* Divider */}
        <div style={{
          margin: "0 auto 20px",
          height: 1, width: 96,
          background: `linear-gradient(90deg, transparent, ${preset.color}50, transparent)`,
        }} />

        {/* Actions */}
        <div style={{ display: "flex", gap: 12 }}>
          <button style={{
            flex: 1, padding: "10px 16px",
            background: "transparent",
            border: `1px solid ${D3C.borderStrong}`,
            borderRadius: 6, color: D3C.gold,
            fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
            cursor: "pointer",
          }}>{cancelLabel || "Annuler"}</button>

          <button style={{
            flex: 1, padding: "10px 16px",
            display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
            ...(tone === "warning" ? {
              background: `linear-gradient(135deg, ${D3C.ember}, ${D3C.gold})`,
              color: D3C.bg, border: "none",
              boxShadow: `0 2px 12px rgba(255,130,71,0.3)`,
            } : {
              background: `${preset.color}14`,
              color: preset.color,
              border: `1px solid ${preset.color}40`,
            }),
            borderRadius: 6,
            fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
            cursor: "pointer",
          }}>
            {loading ? "…" : (
              <>
                <span>{confirmLabel || "Confirmer"}</span>
                <span>→</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Four preview scenes
// ═══════════════════════════════════════════════════════════════════════

function DlgDanger() {
  return (
    <ConfirmDialogShell>
      <ConfirmDialog
        tone="danger"
        title="Lâcher cet objet ?"
        message="Cette action est irréversible. Le Carquois sera retiré de votre inventaire et ne pourra plus être récupéré."
        confirmLabel="Lâcher"
        cancelLabel="Annuler"
      />
    </ConfirmDialogShell>
  );
}

function DlgWarning() {
  return (
    <ConfirmDialogShell>
      <ConfirmDialog
        tone="warning"
        title="Lancer le combat ?"
        message="Les combattants seront rangés en initiative. Vous ne pourrez plus revenir à la phase d'exploration sans fuir ou vaincre vos ennemis."
        confirmLabel="Engager"
      />
    </ConfirmDialogShell>
  );
}

function DlgArcane() {
  return (
    <ConfirmDialogShell>
      <ConfirmDialog
        tone="arcane"
        title="Prendre un repos long ?"
        message="Votre groupe dormira huit heures. Les PV et emplacements de sorts seront restaurés, mais huit heures s'écouleront dans le monde."
        confirmLabel="Se reposer"
        cancelLabel="Pas encore"
      />
    </ConfirmDialogShell>
  );
}

function DlgWithContent() {
  return (
    <ConfirmDialogShell>
      <ConfirmDialog
        tone="danger"
        title="Supprimer cette session ?"
        message="Cette campagne sera définitivement perdue. Les personnages et l'historique seront effacés."
        confirmLabel="Supprimer"
      >
        <div style={{
          padding: "10px 14px",
          background: "rgba(232,69,69,0.06)",
          border: "1px solid rgba(232,69,69,0.25)",
          borderRadius: 6,
          fontSize: 12,
          color: D3C.textSoft,
          fontFamily: "'Fraunces', serif",
        }}>
          <div style={{
            fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase",
            color: D3C.blood, fontWeight: 700, marginBottom: 6, fontFamily: "'Inter', sans-serif",
          }}>Contenu de la session</div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
            <span>Les Brumes du Hinterland</span>
            <span style={{ color: D3C.textMuted, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>5 persos</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
            <span>Chapitre I</span>
            <span style={{ color: D3C.textMuted, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>128 tours</span>
          </div>
        </div>
      </ConfirmDialog>
    </ConfirmDialogShell>
  );
}

window.DlgDanger = DlgDanger;
window.DlgWarning = DlgWarning;
window.DlgArcane = DlgArcane;
window.DlgWithContent = DlgWithContent;
