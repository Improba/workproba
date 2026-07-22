import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import PreviewChangeDialog from '@components/chat/PreviewChangeDialog.vue';

const fetchPreviewChange = vi.fn();

vi.mock('@services/aiSidecar', () => ({
  fetchPreviewChange: (...args: unknown[]) => fetchPreviewChange(...args),
}));

describe('PreviewChangeDialog write_pptx', () => {
  beforeEach(() => {
    fetchPreviewChange.mockReset();
  });

  it('charge un aperçu Office avec toolName/toolArgs pptx', async () => {
    fetchPreviewChange.mockResolvedValue({
      is_new: true,
      is_binary: false,
      diff_html: '<div class="wp-diff"><div class="wp-diff-add">Slide 1</div></div>',
      message: '',
      old_size: 0,
      new_size: 12,
    });

    const wrapper = mount(PreviewChangeDialog, {
      props: {
        open: true,
        workspaceDataDir: '/data',
        projectPath: '/project',
        filePath: 'pitch.pptx',
        toolName: 'write_pptx',
        toolArgs: {
          path: 'pitch.pptx',
          slides: [{ layout: 'title', title: 'Hello' }],
        },
      },
      global: {
        stubs: { Lucide: true, 'q-dialog': { template: '<div><slot /></div>' } },
      },
    });

    await flushPromises();

    expect(fetchPreviewChange).toHaveBeenCalledWith(
      expect.objectContaining({
        filePath: 'pitch.pptx',
        toolName: 'write_pptx',
        toolArgs: expect.objectContaining({ path: 'pitch.pptx' }),
      }),
    );
    expect(wrapper.text()).toContain('Slide 1');
    expect(wrapper.text()).toContain('Nouveau fichier');
    wrapper.unmount();
  });

  it('affiche preview_html wp-slide pour pptx', async () => {
    fetchPreviewChange.mockResolvedValue({
      is_new: true,
      is_binary: false,
      diff_html: '<div class="wp-diff"><div class="wp-diff-add">Slide 1</div></div>',
      preview_html:
        "<div class='wp-slide'><h1 class='wp-slide__title'>Hello</h1></div>",
      message: '',
      old_size: 0,
      new_size: 12,
    });

    const wrapper = mount(PreviewChangeDialog, {
      props: {
        open: true,
        workspaceDataDir: '/data',
        projectPath: '/project',
        filePath: 'pitch.pptx',
        toolName: 'write_pptx',
        toolArgs: {
          path: 'pitch.pptx',
          slides: [{ layout: 'title', title: 'Hello' }],
        },
      },
      global: {
        stubs: { Lucide: true, 'q-dialog': { template: '<div><slot /></div>' } },
      },
    });

    await flushPromises();
    expect(wrapper.find('.preview-change-dialog__slides').exists()).toBe(true);
    expect(wrapper.text()).toContain('Hello');
    wrapper.unmount();
  });

  it('affiche le message sidecar quand is_binary', async () => {
    fetchPreviewChange.mockResolvedValue({
      is_new: true,
      is_binary: true,
      diff_html: '',
      message: 'Aperçu non disponible pour ce format.',
      old_size: 0,
      new_size: 0,
    });

    const wrapper = mount(PreviewChangeDialog, {
      props: {
        open: true,
        workspaceDataDir: '/data',
        projectPath: '/project',
        filePath: 'pitch.pptx',
        toolName: 'write_pptx',
        toolArgs: { theme: 'neon', slides: [{ layout: 'title', title: 'X' }] },
      },
      global: {
        stubs: { Lucide: true, 'q-dialog': { template: '<div><slot /></div>' } },
      },
    });

    await flushPromises();
    expect(wrapper.text()).toContain('Aperçu non disponible pour ce format.');
    wrapper.unmount();
  });
});
