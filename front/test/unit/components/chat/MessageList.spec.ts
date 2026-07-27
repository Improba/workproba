import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import MessageList from '@components/chat/MessageList.vue';
import type { ChatMessage } from '#types';

const sampleMessages: ChatMessage[] = [
  {
    id: 'u1',
    role: 'user',
    content: 'Bonjour',
    createdAt: '2026-01-01T00:00:00.000Z',
  },
  {
    id: 'a1',
    role: 'assistant',
    content: 'Salut',
    createdAt: '2026-01-01T00:00:01.000Z',
  },
];

describe('MessageList', () => {
  it('désactive aria-live pendant le streaming', () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
        streaming: true,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    const log = wrapper.find('.message-list__scroller');
    expect(log.attributes('aria-live')).toBe('off');
    wrapper.unmount();
  });

  it('utilise aria-live polite hors streaming', () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    const log = wrapper.find('.message-list__scroller');
    expect(log.attributes('aria-live')).toBe('polite');
    wrapper.unmount();
  });

  it('annonce la fin du streaming aux lecteurs d\'écran', async () => {
    vi.useFakeTimers();
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
        streaming: true,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    await wrapper.setProps({ streaming: false });
    await flushPromises();

    const status = wrapper.find('.message-list__sr-status');
    expect(status.text()).toContain('terminée');

    vi.advanceTimersByTime(1600);
    await flushPromises();
    expect(status.text()).toBe('');

    vi.useRealTimers();
    wrapper.unmount();
  });

  it('expose scrollToBottom via ref', async () => {
    const scrollTo = vi.fn();

    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template:
              '<div class="q-scroll-area"><div class="q-scrollarea__container"><slot /></div></div>',
            mounted() {
              const container = (this.$el as HTMLElement).querySelector(
                '.q-scrollarea__container',
              ) as HTMLElement;
              Object.defineProperty(container, 'scrollHeight', {
                value: 400,
                configurable: true,
              });
              Object.defineProperty(container, 'clientHeight', {
                value: 100,
                configurable: true,
              });
              container.scrollTo = scrollTo;
            },
            methods: {
              getScrollTarget() {
                return (this.$el as HTMLElement).querySelector(
                  '.q-scrollarea__container',
                );
              },
            },
          },
        },
      },
    });

    const list = wrapper.vm as { scrollToBottom: (smooth?: boolean) => void };
    list.scrollToBottom(true);

    expect(scrollTo).toHaveBeenCalledWith({
      top: 400,
      behavior: 'smooth',
    });

    wrapper.unmount();
  });

  it('rend la réserve turn-anchor seulement si spacerHeight > 0', async () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
        spacerHeight: 240,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    const spacer = wrapper.find('.message-list__reply-spacer');
    expect(spacer.exists()).toBe(true);
    expect(spacer.attributes('style')).toContain('height: 240px');

    await wrapper.setProps({ spacerHeight: 0 });
    expect(wrapper.find('.message-list__reply-spacer').exists()).toBe(false);
    wrapper.unmount();
  });

  it('rend les messages en liste plate avec data-index', () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: true,
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    const items = wrapper.findAll('[data-index]');
    expect(items).toHaveLength(2);
    expect(items[0].attributes('data-index')).toBe('0');
    expect(items[1].attributes('data-index')).toBe('1');
    wrapper.unmount();
  });

  it('mesure getItemSize et getItemOffset via le DOM', async () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: sampleMessages,
      },
      global: {
        stubs: {
          Lucide: true,
          Message: {
            template: '<div class="message-stub" :style="{ height: message.role === \'user\' ? \'80px\' : \'120px\' }" />',
            props: ['message'],
          },
          QScrollArea: {
            template: '<div class="q-scroll-area"><slot /></div>',
          },
        },
      },
    });

    await flushPromises();

    const list = wrapper.vm as {
      getItemSize: (index: number) => number;
      getItemOffset: (index: number) => number;
    };

    const first = wrapper.find('[data-index="0"]').element as HTMLElement;
    const second = wrapper.find('[data-index="1"]').element as HTMLElement;

    expect(list.getItemSize(0)).toBe(first.offsetHeight);
    expect(list.getItemSize(1)).toBe(second.offsetHeight);
    expect(list.getItemOffset(0)).toBe(first.offsetTop);
    expect(list.getItemOffset(1)).toBe(second.offsetTop);

    wrapper.unmount();
  });
});
