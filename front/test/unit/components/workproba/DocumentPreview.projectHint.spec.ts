import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DocumentPreview from '@components/workproba/DocumentPreview.vue';

const openCapabilities = vi.fn();

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openCapabilities,
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  isDesktopApp: () => false,
  openLocalFile: vi.fn(),
}));

vi.mock('@services/aiSidecar', () => ({
  fetchDocumentPreview: vi.fn().mockResolvedValue({
    title: 'note.md',
    type: 'markdown',
    html: '<p>Contenu</p>',
  }),
  isSafeRelativePath: () => true,
}));

describe('DocumentPreview suggestion projet', () => {
  beforeEach(() => {
    sessionStorage.clear();
    openCapabilities.mockClear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('affiche une suggestion dismissible quand le plugin projet est inactif', async () => {
    const wrapper = mount(DocumentPreview, {
      props: {
        relativePath: 'docs/note.md',
        projectPath: '/tmp/projet',
        showPublish: false,
      },
      global: {
        stubs: {
          Lucide: true,
        },
      },
    });

    await flushPromises();

    const hint = wrapper.find('.doc-preview__project-hint');
    expect(hint.exists()).toBe(true);
    expect(hint.text()).toContain('Organiser ce document dans un projet');

    await wrapper.find('.doc-preview__project-hint-link').trigger('click');
    expect(openCapabilities).toHaveBeenCalledWith('projects');

    await wrapper.find('.doc-preview__project-hint-dismiss').trigger('click');
    expect(wrapper.find('.doc-preview__project-hint').exists()).toBe(false);
    expect(sessionStorage.getItem('workproba.ui.projectOrganizeHint.dismissed')).toBe('1');
  });

  it('n’affiche pas la suggestion quand la publication projet est disponible', async () => {
    const wrapper = mount(DocumentPreview, {
      props: {
        relativePath: 'docs/note.md',
        projectPath: '/tmp/projet',
        showPublish: true,
      },
      global: {
        stubs: {
          Lucide: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.doc-preview__project-hint').exists()).toBe(false);
  });
});
