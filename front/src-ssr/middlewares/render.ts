import { type Request, type Response } from 'express';
import { type RenderError } from '#q-app';
import { defineSsrMiddleware } from '#q-app/wrappers';
import { brandedErrorHtml } from './error-page';

// This middleware should execute as last one
// since it captures everything and tries to
// render the page with Vue

export default defineSsrMiddleware(({ app, resolve, render, serve }) => {
  // we capture any other Express route and hand it
  // over to Vue and Vue Router to render our page
  app.get(resolve.urlPath('*'), (req: Request, res: Response) => {
    res.setHeader('Content-Type', 'text/html');

    // Wrap render() so a synchronous throw is caught the same way as a
    // rejected promise — otherwise it would escape Express' reach and surface
    // as an unhandled exception instead of a branded 500 page.
    Promise.resolve()
      .then(() => render(/* the ssrContext: */ { req, res }))
      .then((html) => {
        // now let's send the rendered html to the client
        res.send(html);
      })
      .catch((err: RenderError) => {
        console.error('[render] error for', req.url, err && err.stack ? err.stack : err);

        // we were told to redirect to another URL
        if (err.url) {
          if (err.code) {
            res.redirect(err.code, err.url);
          } else {
            res.redirect(err.url);
          }
        } else if (err.code === 404) {
          // Vue Router could not find the requested route
          // (only reached if no catch-all route is defined in /src/router/routes)
          res.status(404).send(brandedErrorHtml('not-found'));
        } else if (process.env.DEV) {
          // in dev mode, Quasar CLI can display a nice error page with the stack
          // serve.error is available on dev only
          serve.error({ err, req, res });
        } else {
          // production: render a branded, dependency-free error page
          // (no Vue / i18n) so it still works when the renderer itself failed.
          res.status(500).send(brandedErrorHtml('server'));

          if (process.env.DEBUGGING) {
            console.error(err.stack);
          }
        }
      });
  });
});
