import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import MessageList from '@components/chat/MessageList.vue';
import type { ChatMessage } from '#types';

vi.mock('vue-virtual-scroller', () => ({
  DynamicScroller: {
    name: 'DynamicScroller',
    props: ['items'],
    template: '<div class="dynamic-scroller"><slot v-for="(item, index) in items" :item="item" :active="true" :index="index" /></div>',
  },
  DynamicScrollerItem: {
    name: 'DynamicScrollerItem',
    template: '<div class="dynamic-scroller-item"><slot /></div>',
  },
}));

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
});
