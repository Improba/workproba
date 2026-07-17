import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import DocumentPreview from '@components/workproba/DocumentPreview.vue';

const fetchDocumentPreview = vi.fn();
const listFileVersions = vi.fn();

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openCapabilities: vi.fn(),
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  isDesktopApp: () => false,
  openLocalFile: vi.fn(),
}));

vi.mock('@services/aiSidecar', () => ({
  fetchDocumentPreview: (...args: unknown[]) => fetchDocumentPreview(...args),
  isSafeRelativePath: () => true,
  listFileVersions: (...args: unknown[]) => listFileVersions(...args),
  restoreFileVersion: vi.fn(),
}));

describe('DocumentPreview réponses obsolètes', () => {
  it('ignore une preview async devenue obsolète', async () => {
    let resolveFirst: ((value: unknown) => void) | null = null;
    fetchDocumentPreview
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValueOnce({
        title: 'current.md',
        type: 'markdown',
        html: '<p>Courant</p>',
      });
    listFileVersions.mockResolvedValue([]);

    const wrapper = mount(DocumentPreview, {
      props: {
        relativePath: 'old.md',
        projectPath: '/tmp/projet',
        workspaceDataDir: '/data/ws-1',
      },
      global: {
        stubs: { Lucide: true },
      },
    });

    await flushPromises();
    expect(wrapper.find('.doc-preview__spinner').exists()).toBe(true);

    await wrapper.setProps({ relativePath: 'current.md' });
    await flushPromises();

    resolveFirst?.({
      title: 'old.md',
      type: 'markdown',
      html: '<p>Ancien</p>',
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Courant');
    expect(wrapper.text()).not.toContain('Ancien');
  });

  it('ignore des versions async devenues obsolètes', async () => {
    let resolveVersions: ((value: unknown) => void) | null = null;
    fetchDocumentPreview.mockResolvedValue({
      title: 'current.md',
      type: 'markdown',
      html: '<p>Courant</p>',
    });
    listFileVersions
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveVersions = resolve;
          }),
      )
      .mockResolvedValueOnce([{ version_id: 'v-current', created_at: '2026-01-02' }]);

    const wrapper = mount(DocumentPreview, {
      props: {
        relativePath: 'old.md',
        projectPath: '/tmp/projet',
        workspaceDataDir: '/data/ws-1',
      },
      global: {
        stubs: { Lucide: true },
      },
    });

    await flushPromises();
    expect(wrapper.find('.doc-preview__restore').exists()).toBe(false);

    await wrapper.setProps({ relativePath: 'current.md' });
    await flushPromises();
    expect(wrapper.find('.doc-preview__restore').exists()).toBe(false);

    resolveVersions?.([
      { version_id: 'v-old-current', created_at: '2026-01-02' },
      { version_id: 'v-old-previous', created_at: '2026-01-01' },
    ]);
    await flushPromises();

    expect(wrapper.find('.doc-preview__restore').exists()).toBe(false);
  });
});
