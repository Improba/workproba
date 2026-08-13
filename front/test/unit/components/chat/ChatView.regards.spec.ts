import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ChatView from '@components/chat/ChatView.vue';

function mountChatView(personasEnabled: boolean, streaming = false) {
  return mount(ChatView, {
    props: {
      messages: [],
      streaming,
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

describe('ChatView Regards (chip composer)', () => {
  it('n’affiche pas le chip Regards quand personas est désactivé', () => {
    const wrapper = mountChatView(false);

    expect(wrapper.find('.chat-composer__regards').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Demander un regard');
    expect(wrapper.text()).not.toContain('Croiser plusieurs regards');
  });

  it('affiche le chip Regards hors du menu +', () => {
    const wrapper = mountChatView(true);

    expect(wrapper.find('.chat-composer__regards').exists()).toBe(true);
    expect(wrapper.find('.chat-composer__regards-menu').exists()).toBe(true);
    expect(wrapper.text()).toContain('Regards');
    expect(wrapper.text()).toContain('Demander un regard');
    expect(wrapper.text()).toContain('Croiser plusieurs regards');
    const addItems = wrapper.findAll('.chat-composer__add-item');
    const regardsInPlus = addItems.filter(
      (item) =>
        !item.classes().includes('chat-composer__regards-item') &&
        (item.text().includes('Demander un regard') ||
          item.text().includes('Croiser plusieurs regards')),
    );
    expect(regardsInPlus).toHaveLength(0);
  });

  it('émet personas-open, personas-meeting et personas-discuss depuis le chip', async () => {
    const wrapper = mountChatView(true);

    const regardsItems = wrapper.findAll('.chat-composer__regards-item');
    expect(regardsItems).toHaveLength(3);

    await regardsItems[0]!.trigger('click');
    await regardsItems[1]!.trigger('click');
    await regardsItems[2]!.trigger('click');

    expect(wrapper.emitted('personas-open')).toHaveLength(1);
    expect(wrapper.emitted('personas-meeting')).toHaveLength(1);
    expect(wrapper.emitted('personas-discuss')).toHaveLength(1);
  });

  it('n’ouvre pas une réunion pendant un échange en cours', async () => {
    const wrapper = mountChatView(true, true);

    const regardsItems = wrapper.findAll('.chat-composer__regards-item');
    expect(regardsItems).toHaveLength(3);

    await regardsItems[1]!.trigger('click');
    expect(wrapper.emitted('personas-meeting')).toBeUndefined();

    await regardsItems[0]!.trigger('click');
    expect(wrapper.emitted('personas-open')).toHaveLength(1);
  });
});
