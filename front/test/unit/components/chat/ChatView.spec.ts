import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import ChatView from '@components/chat/ChatView.vue';
import MessageList from '@components/chat/MessageList.vue';

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

describe('ChatView accessibilité', () => {
  it('délègue role=log et aria-live au conteneur scrollable des messages', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          MessageList: false,
        },
      },
    });

    const list = wrapper.findComponent(MessageList);
    const scroller = list.find('.message-list__scroller');
    expect(scroller.attributes('role')).toBe('log');
    expect(scroller.attributes('aria-live')).toBe('polite');
    expect(scroller.attributes('aria-relevant')).toBe('additions');
  });

  it('affiche une bannière moteur quand aucun set effectif', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [],
        streaming: false,
        settingsLocked: false,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          StartPrompts: true,
          EnrollCloudModal: true,
        },
      },
    });

    expect(wrapper.find('.chat-view__engine-banner').exists()).toBe(true);
    expect(wrapper.find('.chat-view__engine-banner-action').exists()).toBe(true);
  });

  it('masque la bannière moteur si settings verrouillés', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [],
        streaming: false,
        settingsLocked: true,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          StartPrompts: true,
          EnrollCloudModal: true,
        },
      },
    });

    expect(wrapper.find('.chat-view__engine-banner').exists()).toBe(false);
  });
});

describe('ChatView erreurs stream', () => {
  const messageListStub = {
    template: '<div class="message-list-stub" />',
    methods: {
      getScrollTarget: () => null,
      getItemSize: () => 0,
      scrollToItem: () => {},
    },
  };

  const defaultStubs = {
    Lucide: true,
    ChatModelMenuContent: true,
    MessageList: messageListStub,
    StartPrompts: true,
    EnrollCloudModal: true,
    CloudLoginModal: true,
    'q-input': true,
    'q-menu': true,
    'q-list': true,
    'q-item': true,
    'q-item-section': true,
    'q-item-label': true,
    'q-separator': true,
  };

  const retryableError = {
    message: 'Erreur réseau',
    code: 'network_error' as const,
    retryable: true,
  };

  it('affiche le bandeau stream error et émet stream-error-retry au clic Retry', async () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
        streamError: retryableError,
      },
      global: { stubs: defaultStubs },
    });

    const banner = wrapper.find('.chat-view__stream-error');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('Erreur réseau');

    const retryBtn = banner
      .findAll('button')
      .find((btn) => btn.text().includes('Réessayer'));
    expect(retryBtn).toBeTruthy();
    await retryBtn!.trigger('click');

    expect(wrapper.emitted('stream-error-retry')).toHaveLength(1);
    wrapper.unmount();
  });

  it('émet stream-error-report au clic Report', async () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
        streamError: retryableError,
      },
      global: { stubs: defaultStubs },
    });

    const banner = wrapper.find('.chat-view__stream-error');
    const reportBtn = banner
      .findAll('button')
      .find((btn) => btn.text().includes('Voir le rapport'));
    expect(reportBtn).toBeTruthy();
    await reportBtn!.trigger('click');

    expect(wrapper.emitted('stream-error-report')).toHaveLength(1);
    wrapper.unmount();
  });

  it('affiche reconnect sans bouton Réessayer quand reconnect proposé', async () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
        streamError: {
          message: 'Session expirée',
          code: 'invalid_user_jwt' as const,
          retryable: true,
        },
        streamErrorReconnect: 'login',
      },
      global: { stubs: defaultStubs },
    });

    const banner = wrapper.find('.chat-view__stream-error');
    const reconnectBtn = banner
      .findAll('button')
      .find((btn) => btn.text().includes('Se reconnecter'));
    expect(reconnectBtn).toBeTruthy();
    const retryBtn = banner
      .findAll('button')
      .find((btn) => btn.text().includes('Réessayer'));
    expect(retryBtn).toBeUndefined();
    await reconnectBtn!.trigger('click');

    expect(wrapper.emitted('stream-error-reconnect')).toHaveLength(1);
    wrapper.unmount();
  });

  it('affiche le bandeau sans bouton Réessayer pour une erreur non-retryable', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
        streamError: {
          message: 'Erreur fatale',
          code: 'unknown' as const,
          retryable: false,
        },
      },
      global: { stubs: defaultStubs },
    });

    const banner = wrapper.find('.chat-view__stream-error');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('Erreur fatale');
    const retryBtn = banner
      .findAll('button')
      .find((btn) => btn.text().includes('Réessayer'));
    expect(retryBtn).toBeUndefined();
    wrapper.unmount();
  });

  it('masque le bandeau stream error si le dernier assistant a une erreur inline du même tour', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
          {
            id: 'm2',
            role: 'assistant',
            content: '',
            error: {
              message: 'Échec',
              code: 'unknown',
              retryable: true,
              turnId: 'turn-a',
            },
            createdAt: '2026-01-01T00:00:01.000Z',
          },
        ],
        streaming: false,
        streamError: { ...retryableError, turnId: 'turn-a' },
      },
      global: { stubs: defaultStubs },
    });

    expect(wrapper.find('.chat-view__stream-error').exists()).toBe(false);
    wrapper.unmount();
  });

  it('affiche le bandeau si assistant erreur turn différent ou streamError sans turnId', () => {
    const messages = [
      {
        id: 'm1',
        role: 'user' as const,
        content: 'Bonjour',
        createdAt: '2026-01-01T00:00:00.000Z',
      },
      {
        id: 'm2',
        role: 'assistant' as const,
        content: '',
        error: {
          message: 'Échec',
          code: 'unknown',
          retryable: true,
          turnId: 'turn-a',
        },
        createdAt: '2026-01-01T00:00:01.000Z',
      },
    ];

    const differentTurn = mount(ChatView, {
      props: {
        messages,
        streaming: false,
        streamError: { ...retryableError, turnId: 'turn-b' },
      },
      global: { stubs: defaultStubs },
    });
    expect(differentTurn.find('.chat-view__stream-error').exists()).toBe(true);
    differentTurn.unmount();

    const noStreamTurnId = mount(ChatView, {
      props: {
        messages,
        streaming: false,
        streamError: retryableError,
      },
      global: { stubs: defaultStubs },
    });
    expect(noStreamTurnId.find('.chat-view__stream-error').exists()).toBe(true);
    noStreamTurnId.unmount();
  });
});
