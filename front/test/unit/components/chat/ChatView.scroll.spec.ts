import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { defineComponent, nextTick, ref } from 'vue';
import ChatView from '@components/chat/ChatView.vue';

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    activeSet: ref(null),
    effectiveActiveSet: ref(null),
    effectiveActiveSetId: ref(null),
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    isEnrolled: ref(false),
    init: vi.fn(),
    refreshQuota: vi.fn(),
  }),
}));

vi.mock('@components/cloud/EnrollCloudModal.vue', () => ({
  default: { template: '<div />' },
}));

vi.mock('@components/cloud/CloudLoginModal.vue', () => ({
  default: { template: '<div />' },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@vueuse/core', () => ({
  useScroll: () => ({
    arrivedState: ref({ top: false, bottom: true, left: false, right: false }),
  }),
}));

type ScrollState = {
  mode: string;
  spacerHeight: number;
  isPinned: boolean;
  userDetached: boolean;
  anchorUserIndex: number | null;
};

const scrollToItem = vi.fn();
const mockSizes: Record<number, number> = { 0: 120 };
const scrollEl = {
  clientHeight: 600,
  scrollHeight: 2000,
  scrollTop: 0,
  scrollTo: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
};

const MessageListStub = defineComponent({
  name: 'MessageList',
  props: {
    messages: { type: Array, default: () => [] },
    streaming: { type: Boolean, default: false },
    spacerHeight: { type: Number, default: 0 },
  },
  setup(_props, { expose }) {
    expose({
      getScrollTarget: () => scrollEl,
      scrollToItem,
      getItemSize: (index: number) => mockSizes[index] ?? 0,
      getItemOffset: (index: number) => index * 200,
      getScroller: () => null,
      scrollToBottom: vi.fn(),
      scrollToPosition: vi.fn(),
    });
    return {};
  },
  template:
    '<div class="message-list-stub" :data-spacer="spacerHeight"></div>',
});

function mountChat(messages: unknown[], streaming = false) {
  return mount(ChatView, {
    props: {
      messages,
      streaming,
    },
    global: {
      stubs: {
        Lucide: true,
        ChatModelMenuContent: true,
        StartPrompts: true,
        EnrollCloudModal: true,
        CloudLoginModal: true,
        ChatComposerAttachments: true,
        MessageList: MessageListStub,
        QInput: true,
        QMenu: true,
      },
    },
  });
}

function scrollState(wrapper: ReturnType<typeof mountChat>): ScrollState {
  return (
    wrapper.vm as unknown as { getScrollState: () => ScrollState }
  ).getScrollState();
}

async function settle(): Promise<void> {
  await flushPromises();
  await nextTick();
  vi.runAllTimers();
  await flushPromises();
  await nextTick();
}

describe('ChatView scroll behavior', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    scrollToItem.mockClear();
    Object.keys(mockSizes).forEach((k) => delete mockSizes[Number(k)]);
    mockSizes[0] = 120;
    scrollEl.scrollTop = 0;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('entre en mode anchor au nouveau message user et appelle scrollToItem', async () => {
    const wrapper = mountChat([]);
    await settle();

    await wrapper.setProps({
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Question',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('anchor');
    expect(state.anchorUserIndex).toBe(0);
    expect(scrollToItem).toHaveBeenCalled();
    expect(scrollToItem.mock.calls.some((c) => c[0] === 0)).toBe(true);
    expect(state.spacerHeight).toBeGreaterThan(0);
    wrapper.unmount();
  });

  it('promouvoit sticky quand la réponse remplit le viewport', async () => {
    const wrapper = mountChat([]);
    await settle();

    await wrapper.setProps({
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });
    await settle();
    expect(scrollState(wrapper).mode).toBe('anchor');

    mockSizes[1] = 800;
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: 'long'.repeat(200),
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
          _contentRev: 1,
        },
      ],
    });
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('sticky');
    expect(state.spacerHeight).toBe(0);
    expect(state.isPinned).toBe(true);
    wrapper.unmount();
  });

  it('le FAB repasse en sticky pinné sans réserve', async () => {
    const wrapper = mountChat([]);
    await settle();

    mockSizes[1] = 900;
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: 'A'.repeat(2000),
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
          _contentRev: 1,
        },
      ],
    });
    await settle();
    expect(scrollState(wrapper).mode).toBe('sticky');

    const vm = wrapper.vm as unknown as {
      detachFromBottomForTest: () => void;
      handleScrollDownClickForTest: () => void;
    };
    vm.detachFromBottomForTest();
    await settle();
    expect(scrollState(wrapper).userDetached).toBe(true);
    expect(scrollState(wrapper).mode).toBe('detached');
    expect(wrapper.find('.chat-view__scroll-down').exists()).toBe(true);

    vm.handleScrollDownClickForTest();
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('sticky');
    expect(state.isPinned).toBe(true);
    expect(state.userDetached).toBe(false);
    expect(state.spacerHeight).toBe(0);
    wrapper.unmount();
  });

  it('utilise un offset de peek sur scrollToItem pour messages user longs', async () => {
    mockSizes[0] = 400;
    const wrapper = mountChat([]);
    await settle();

    await wrapper.setProps({
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'long question'.repeat(40),
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });
    await settle();

    expect(scrollState(wrapper).mode).toBe('anchor');
    const peekCall = scrollToItem.mock.calls.find(
      (c) => c[1] && typeof c[1] === 'object' && 'offset' in c[1],
    );
    expect(peekCall).toBeTruthy();
    expect(peekCall?.[1]).toMatchObject({
      align: 'start',
      offset: 400 - 96,
    });
    wrapper.unmount();
  });

  it('ancre même si user+assistant arrivent dans le même lot', async () => {
    const wrapper = mountChat([]);
    await settle();

    mockSizes[0] = 80;
    mockSizes[1] = 64;
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'raconte une histoire',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: '',
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
        },
      ],
    });
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('anchor');
    expect(state.anchorUserIndex).toBe(0);
    expect(state.spacerHeight).toBeGreaterThan(0);
    expect(scrollToItem).toHaveBeenCalled();
    expect(scrollToItem.mock.calls.some((c) => c[0] === 0)).toBe(true);
    wrapper.unmount();
  });

  it('garde la réserve pendant thinking replié (header compté dans responseHeight)', async () => {
    const wrapper = mountChat([]);
    await settle();

    await wrapper.setProps({
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });
    await settle();

    mockSizes[1] = 64; // header ThinkingCard seul
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: '',
          thinking: 'long reasoning…'.repeat(40),
          parts: [
            {
              type: 'thinking',
              id: 'a1__think',
              thinkingId: 't1',
              content: 'long reasoning…'.repeat(40),
              done: false,
            },
          ],
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
        },
      ],
    });
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('anchor');
    // viewport 600 - peek(min(120,96)=96) - header 64
    expect(state.spacerHeight).toBe(600 - 96 - 64);
    wrapper.unmount();
  });

  it('promouvoit sticky et suit le bas quand la réponse remplit après thinking', async () => {
    const wrapper = mountChat([]);
    await settle();

    mockSizes[0] = 80;
    await wrapper.setProps({
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    });
    await settle();
    expect(scrollState(wrapper).mode).toBe('anchor');

    mockSizes[1] = 64;
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: '',
          thinking: 'r',
          parts: [
            {
              type: 'thinking',
              id: 'a1__think',
              thinkingId: 't1',
              content: 'r',
              done: true,
            },
          ],
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
        },
      ],
    });
    await settle();
    expect(scrollState(wrapper).mode).toBe('anchor');

    mockSizes[1] = 800;
    await wrapper.setProps({
      streaming: true,
      messages: [
        {
          id: 'u1',
          role: 'user',
          content: 'Q',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'a1',
          role: 'assistant',
          content: 'Voici la longue réponse.'.repeat(80),
          thinking: 'r',
          parts: [
            {
              type: 'thinking',
              id: 'a1__think',
              thinkingId: 't1',
              content: 'r',
              done: true,
            },
            {
              type: 'text',
              id: 'a1__text',
              content: 'Voici la longue réponse.'.repeat(80),
            },
          ],
          createdAt: '2026-01-01T00:00:01.000Z',
          streaming: true,
          _contentRev: 2,
        },
      ],
    });
    await settle();

    const state = scrollState(wrapper);
    expect(state.mode).toBe('sticky');
    expect(state.spacerHeight).toBe(0);
    expect(state.isPinned).toBe(true);
    wrapper.unmount();
  });
});
