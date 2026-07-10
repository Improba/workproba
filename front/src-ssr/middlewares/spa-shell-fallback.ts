import { type Request, type Response } from 'express';
import { defineSsrMiddleware } from '#q-app/wrappers';
import routes from '@router/routes';
import { collectSsrPaths, matchesPathSet } from '@router/ssr-paths';
import { brandedErrorHtml } from './error-page';

// Matches the Quasar mount point, tolerating extra attributes Vue/Quasar may
// inject at runtime (data-v-app, data-*, etc.). Without this, an attribute on
// #q-app would silently defeat the shell-emptying step and leak rendered HTML.
const Q_APP_RE = /<div id="q-app"[^>]*>[\s\S]*?<\/div>/;

// Static, public (non-auth) routes that should be server-side rendered.
// Everything else (auth routes, dynamic routes, unknown paths) is served as
// a CSR shell and rendered in the browser.
const SSR_PATHS = collectSsrPaths(routes);

function renderCsrShell(
  req: Request,
  res: Response,
  render: (opts: { req: Request; res: Response }) => Promise<string>,
): void {
  const originalUrl = req.url;
  req.url = '/__spa_shell__';
  res.setHeader('Content-Type', 'text/html');

  // Restore req.url no matter how render resolves (sync throw, rejected promise,
  // or success). Mutating req without restoring leaks the internal shell path
  // into any downstream middleware/error handler.
  const restoreUrl = (): void => {
    req.url = originalUrl;
  };

  Promise.resolve()
    .then(() => render({ req, res }))
    .then((html: string) => {
      restoreUrl();
      const shell = html.replace(Q_APP_RE, '<div id="q-app"></div>');
      res.send(shell);
    })
    .catch((err: unknown) => {
      restoreUrl();
      if (process.env.DEV) {
        console.error('[spa-shell-fallback] render error:', err);
      }
      res.status(500).send(brandedErrorHtml('server'));
    });
}

export default defineSsrMiddleware(({ app, resolve, render }) => {
  app.get(resolve.urlPath('*'), (req: Request, res: Response, next) => {
    const pathName = new URL(req.url, `http://${req.headers.host || 'localhost'}`).pathname;

    // Known SSR route → let the render middleware handle it.
    if (matchesPathSet(pathName, SSR_PATHS)) {
      next();
      return;
    }

    // CSR route, dynamic route or unknown path → serve the SPA shell.
    renderCsrShell(req, res, render);
  });
});
