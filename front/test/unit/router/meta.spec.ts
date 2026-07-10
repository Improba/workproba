import { describe, expect, it } from 'vitest';
import { DESKTOP_META, HOME_ROUTE } from '../../../src/router/meta';

describe('router meta', () => {
  it('expose la meta bureau sans auth', () => {
    expect(DESKTOP_META).toEqual({ ssr: false });
  });

  it('expose le nom de route home', () => {
    expect(HOME_ROUTE).toBe('home');
  });
});
