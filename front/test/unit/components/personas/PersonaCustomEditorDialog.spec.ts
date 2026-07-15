import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import PersonaCustomEditorDialog from '@components/personas/PersonaCustomEditorDialog.vue';

describe('PersonaCustomEditorDialog', () => {
  it('émet save avec les champs du formulaire', async () => {
    const wrapper = mount(PersonaCustomEditorDialog, {
      props: { open: true },
      global: {
        stubs: { 'q-dialog': { template: '<div><slot /></div>' } },
      },
    });

    const inputs = wrapper.findAll('input[type="text"]');
    await inputs[0].setValue('Coach');
    await inputs[1].setValue('Mentor');
    await wrapper.find('textarea').setValue('Tu es un coach bienveillant.');

    await wrapper.find('form').trigger('submit.prevent');

    expect(wrapper.emitted('save')?.[0]?.[0]).toEqual({
      name: 'Coach',
      role: 'Mentor',
      systemPrompt: 'Tu es un coach bienveillant.',
    });
    wrapper.unmount();
  });
});
