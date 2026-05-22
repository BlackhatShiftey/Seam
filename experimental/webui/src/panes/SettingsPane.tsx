import React from 'react';

const BASE_KEY = 'seam-webui-api-url';
const TOKEN_KEY = 'seam-webui-api-token';

export default function SettingsPane() {
  const [baseUrl, setBaseUrl] = React.useState(localStorage.getItem(BASE_KEY) || 'http://127.0.0.1:8765');
  const [token, setToken] = React.useState(sessionStorage.getItem(TOKEN_KEY) || '');
  const [saved, setSaved] = React.useState(false);

  function handleSave() {
    localStorage.setItem(BASE_KEY, baseUrl);
    localStorage.removeItem(TOKEN_KEY);
    if (token.trim()) {
      sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div style={{ padding: 16, overflowY: 'auto', flex: 1, maxWidth: 640 }}>
      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#4f8cfb', marginBottom: 12 }}>Settings</div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ color: '#7fe0ff', fontSize: 11 }}>API Base URL</span>
          <span style={{ color: '#274063', fontSize: 10, fontStyle: 'italic' }}>REST API address</span>
        </div>
        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          style={{
            width: '100%',
            background: '#030d20',
            border: '1px solid rgba(47,99,255,0.2)',
            borderRadius: 5,
            padding: '8px 10px',
            color: '#bfefff',
            fontSize: 12,
            fontFamily: 'var(--font)',
            outline: 'none',
          }}
        />
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ color: '#7fe0ff', fontSize: 11 }}>Bearer Token</span>
          <span style={{ color: '#274063', fontSize: 10, fontStyle: 'italic' }}>Only when SEAM_API_TOKEN is set</span>
        </div>
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          type="password"
          placeholder="********"
          style={{
            width: '100%',
            background: '#030d20',
            border: '1px solid rgba(47,99,255,0.2)',
            borderRadius: 5,
            padding: '8px 10px',
            color: '#bfefff',
            fontSize: 12,
            fontFamily: 'var(--font)',
            outline: 'none',
          }}
        />
      </div>

      <button
        onClick={handleSave}
        style={{
          padding: '7px 18px',
          background: 'rgba(79,140,251,0.15)',
          border: '1px solid rgba(79,140,251,0.3)',
          borderRadius: 5,
          color: '#7fe0ff',
          fontSize: 12,
          fontFamily: 'var(--font)',
          cursor: 'pointer',
        }}
      >
        Save changes
      </button>
      {saved && (
        <span style={{ marginLeft: 10, fontSize: 11, color: '#7efdb9' }}>Saved</span>
      )}
    </div>
  );
}
