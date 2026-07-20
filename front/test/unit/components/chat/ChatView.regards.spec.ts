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
        ChatModelMenuContent: true,
        MessageList: true,
        StartPrompts: true,
        ChatComposerAttachments: true,
      },
    },
  });
}

describe('ChatView Regards (menu +)', () => {
  it('n’affiche pas la section Regards quand personas est désactivé', () => {
    const wrapper = mountChatView(false);

    expect(wrapper.find('.chat-view__regards').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Demander un avis');
    expect(wrapper.text()).not.toContain('Croiser plusieurs regards');
  });

  it('n’affiche pas le chip Regards visible et place les entrées dans le menu +', () => {
    const wrapper = mountChatView(true);

    expect(wrapper.find('.chat-view__regards').exists()).toBe(false);
    expect(wrapper.text()).toContain('Regards');
    expect(wrapper.text()).toContain('Demander un avis');
    expect(wrapper.text()).toContain('Croiser plusieurs regards');
  });

  it('émet personas-open, personas-meeting et personas-discuss depuis le menu +', async () => {
    const wrapper = mountChatView(true);

    const items = wrapper.findAll('.chat-view__add-item');
    const regardsItems = items.filter(
      (item) =>
        item.text().includes('Demander un avis') ||
        item.text().includes('Croiser plusieurs regards') ||
        item.text().includes('Discuter avec un regard'),
    );
    expect(regardsItems).toHaveLength(3);

    await regardsItems[0]!.trigger('click');
    await regardsItems[1]!.trigger('click');
    await regardsItems[2]!.trigger('click');

    expect(wrapper.emitted('personas-open')).toHaveLength(1);
    expect(wrapper.emitted('personas-meeting')).toHaveLength(1);
    expect(wrapper.emitted('personas-discuss')).toHaveLength(1);
  });
});
