import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ChatView from '@components/chat/ChatView.vue';

function mountChatView(personasEnabled: boolean) {
  return mount(ChatView, {
    props: {
      messages: [],
      streaming: false,
      personasEnabled,
    },
    global: {
      stubs: {
        Lucide: true,
        ChatModelControl: true,
        MessageList: true,
        StartPrompts: true,
        ChatComposerAttachments: true,
      },
    },
  });
}

describe('ChatView Regards (PR3)', () => {
  it('n’affiche pas le chip Regards quand personas est désactivé', () => {
    const wrapper = mountChatView(false);

    expect(wrapper.find('.chat-view__regards').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Consulter des experts');
    expect(wrapper.text()).not.toContain('Simuler une réunion');
  });

  it('affiche le chip Regards et retire les entrées personas du menu +', () => {
    const wrapper = mountChatView(true);

    expect(wrapper.find('.chat-view__regards').exists()).toBe(true);
    expect(wrapper.text()).toContain('Regards');
    expect(wrapper.text()).not.toContain('Consulter des experts');
    expect(wrapper.text()).not.toContain('Simuler une réunion');
  });

  it('émet personas-open, personas-meeting et personas-discuss depuis le menu Regards', async () => {
    const wrapper = mountChatView(true);

    const items = wrapper.findAll('.chat-view__regards-item');
    expect(items).toHaveLength(3);

    await items[0]!.trigger('click');
    await items[1]!.trigger('click');
    await items[2]!.trigger('click');

    expect(wrapper.emitted('personas-open')).toHaveLength(1);
    expect(wrapper.emitted('personas-meeting')).toHaveLength(1);
    expect(wrapper.emitted('personas-discuss')).toHaveLength(1);
  });
});
