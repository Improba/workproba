import { describe, expect, it } from 'vitest';
import fr from '../../../src/i18n/fr/index';
import en from '../../../src/i18n/en-US/index';

describe('space terminology i18n', () => {
  it('utilise le vocabulaire espace pour les actions principales (fr)', () => {
    expect(fr.common.openSpace).toMatch(/espace/i);
    expect(fr.common.openSpace).not.toMatch(/dossier/i);
    expect(fr.common.openSpaceEllipsis).toMatch(/espace/i);
    expect(fr.common.changeSpace).toMatch(/espace/i);
    expect(fr.errors.noSpaceOpen).toMatch(/espace/i);
    expect(fr.errors.noSpaceOpen).not.toMatch(/dossier/i);
    expect(fr.errors.openSpaceFailed).toMatch(/espace/i);
    expect(fr.home.openSpaceLead).toMatch(/espace/i);
    expect(fr.home.step1Title).toMatch(/espace/i);
    expect(fr.home.step3Text).toMatch(/espace/i);
  });

  it('utilise le vocabulaire space pour les actions principales (en)', () => {
    expect(en.common.openSpace).toMatch(/space/i);
    expect(en.common.openSpace).not.toMatch(/folder/i);
    expect(en.common.openSpaceEllipsis).toMatch(/space/i);
    expect(en.common.changeSpace).toMatch(/space/i);
    expect(en.errors.noSpaceOpen).toMatch(/space/i);
    expect(en.errors.noSpaceOpen).not.toMatch(/folder/i);
    expect(en.errors.openSpaceFailed).toMatch(/space/i);
    expect(en.home.openSpaceLead).toMatch(/space/i);
    expect(en.home.step1Title).toMatch(/space/i);
    expect(en.home.step3Text).toMatch(/space/i);
  });

  it('aligne le scope mémoire espace (fr/en)', () => {
    expect(fr.memory.scopeProject).toBe('Espace');
    expect(fr.memory.scopeProjectHint).toMatch(/espace/i);
    expect(en.memory.scopeProject).toBe('Space');
    expect(en.memory.scopeProjectHint).toMatch(/space/i);
  });

  it('expose les libellés de renommage d\'espace', () => {
    expect(fr.shell.renameSpace).toMatch(/espace/i);
    expect(fr.shell.renameSpaceTitle).toBeTruthy();
    expect(fr.shell.spacePathHint).toMatch(/Dossier/i);
    expect(en.shell.renameSpace).toMatch(/space/i);
    expect(en.shell.spacePathHint).toMatch(/Folder/i);
  });
});
