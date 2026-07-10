/**
 * Branded, dependency-free error pages for the SSR webserver.
 *
 * These are plain HTML (no Vue / no i18n) so they still render when the
 * renderer itself is what failed. Adapt the copy / brand to your project.
 */
type ErrorKind = 'server' | 'not-found';

interface ErrorCopy {
  code: string;
  title: string;
  subtitle: string;
  backHome: string;
}

const HOME_HREF = '/';

function escapeAttr(value: string): string {
  return value.replace(/["'<>&]/g, (ch) =>
    ch === '"' ? '&quot;' :
    ch === '<' ? '&lt;' :
    ch === '>' ? '&gt;' :
    ch === '&' ? '&amp;' : '&#39;',
  );
}

function copy(kind: ErrorKind): ErrorCopy {
  if (kind === 'not-found') {
    return {
      code: '404',
      title: "Cette page n'existe pas",
      subtitle:
        "La page que vous cherchez a peut-être été déplacée, supprimée, ou n'a jamais existé.",
      backHome: "Retour à l'accueil",
    };
  }
  return {
    code: '500',
    title: 'Une erreur est survenue',
    subtitle:
      "Notre équipe a été notifiée. Merci de réessayer dans quelques instants.",
    backHome: "Retour à l'accueil",
  };
}

// Absolute canonical URL for SEO. Falls back to a relative href when SITE_URL
// is not configured (e.g. local dev without .env), so the link stays valid.
function canonicalHref(): string {
  const site = process.env.SITE_URL?.trim().replace(/\/+$/, '');
  return site ? escapeAttr(`${site}${HOME_HREF}`) : HOME_HREF;
}

export function brandedErrorHtml(kind: ErrorKind = 'server'): string {
  const c = copy(kind);
  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex" />
<link rel="canonical" href="${canonicalHref()}" />
<title>${c.code} · ${c.title}</title>
<link rel="icon" type="image/png" href="/icons/favicon-128x128.png" />
<style>
  :root { --azure:#0f84cb; --azure-deep:#094a7a; --orange:#ff7a18; }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#062b48;color:#fff;min-height:100vh;display:flex;flex-direction:column}
  a{text-decoration:none}
  .bar{display:flex;align-items:center;justify-content:space-between;padding:18px 24px;max-width:1180px;margin:0 auto;width:100%}
  .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;color:#fff}
  .ghost{padding:12px 22px;border-radius:999px;border:1px solid rgba(255,255,255,.3);color:#fff;font-weight:600;font-size:14px;background:rgba(255,255,255,.08)}
  .hero{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:48px 24px;position:relative;overflow:hidden}
  .hero::before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.08) 1px,transparent 1px);background-size:56px 56px;-webkit-mask-image:radial-gradient(ellipse 70% 60% at 50% 40%,#000 25%,transparent 75%);mask-image:radial-gradient(ellipse 70% 60% at 50% 40%,#000 25%,transparent 75%);pointer-events:none}
  .hero::after{content:"";position:absolute;top:-160px;right:-120px;width:480px;height:480px;border-radius:50%;background:radial-gradient(circle,rgba(255,122,24,.35) 0%,transparent 65%);pointer-events:none}
  .code{font-weight:700;font-size:clamp(6rem,18vw,12rem);line-height:1;background:linear-gradient(120deg,#fff 0%,#b3d9ff 60%,var(--orange) 130%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;position:relative;z-index:1}
  h1{font-weight:700;font-size:clamp(1.5rem,3.5vw,2.2rem);margin:8px 0 14px;position:relative;z-index:1}
  p{opacity:.86;max-width:520px;font-size:1.05rem;line-height:1.6;margin:0 auto 28px;position:relative;z-index:1}
  .cta{display:inline-flex;align-items:center;gap:10px;padding:14px 26px;border-radius:999px;font-weight:600;font-size:15px;color:#fff;background:linear-gradient(135deg,var(--orange) 0%,#ff5e7e 100%);box-shadow:0 18px 40px -14px rgba(255,122,24,.55);position:relative;z-index:1}
  .foot{padding:18px 24px;color:#94a3b8;font-size:14px;max-width:1180px;margin:0 auto;width:100%}
</style>
</head>
<body>
  <div class="bar">
    <a class="brand" href="${HOME_HREF}">App</a>
    <a class="ghost" href="${HOME_HREF}">${c.backHome}</a>
  </div>
  <main class="hero">
    <div class="code">${c.code}</div>
    <h1>${c.title}</h1>
    <p>${c.subtitle}</p>
    <a class="cta" href="${HOME_HREF}">${c.backHome} →</a>
  </main>
  <div class="foot">© ${new Date().getFullYear()}</div>
</body>
</html>`;
}
