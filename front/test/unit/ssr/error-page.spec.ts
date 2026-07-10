import { afterEach, describe, expect, it } from 'vitest';
import { brandedErrorHtml } from '../../../src-ssr/middlewares/error-page';

describe('error-page', () => {
  const originalSiteUrl = process.env.SITE_URL;

  afterEach(() => {
    if (originalSiteUrl === undefined) {
      delete process.env.SITE_URL;
    } else {
      process.env.SITE_URL = originalSiteUrl;
    }
  });

  it("marque les pages d'erreur comme noindex", () => {
    const html = brandedErrorHtml('not-found');
    expect(html).toContain('<meta name="robots" content="noindex"');
  });

  it('utilise SITE_URL pour le canonical quand il est défini', () => {
    process.env.SITE_URL = 'https://example.com';
    const html = brandedErrorHtml('server');
    expect(html).toContain('<link rel="canonical" href="https://example.com/"');
  });

  it('échappe les caractères dangereux de SITE_URL', () => {
    process.env.SITE_URL = 'https://example.com"><script>';
    const html = brandedErrorHtml('server');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('retombe sur un canonical relatif sans SITE_URL', () => {
    delete process.env.SITE_URL;
    const html = brandedErrorHtml('not-found');
    expect(html).toContain('<link rel="canonical" href="/"');
  });

  it('rend un code 404/500 et un HTML complet', () => {
    expect(brandedErrorHtml('not-found')).toContain('404');
    expect(brandedErrorHtml('server')).toContain('500');
  });
});
