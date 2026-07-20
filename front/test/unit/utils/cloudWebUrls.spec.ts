import { describe, expect, it } from 'vitest';
import {
  cloudAuthLoginUrl,
  cloudAuthRegisterUrl,
  resolveCloudWebOrigin,
} from '@utils/cloudWebUrls';

describe('cloudWebUrls', () => {
  it('utilise localhost:8482 par défaut', () => {
    expect(resolveCloudWebOrigin()).toBe('http://localhost:8482');
    expect(cloudAuthLoginUrl()).toBe('http://localhost:8482/auth/login');
    expect(cloudAuthRegisterUrl()).toBe('http://localhost:8482/auth/register');
  });
});
