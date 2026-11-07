declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

export const tg = {
  get isAvailable(): boolean {
    return typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp);
  },

  get webApp() {
    return window.Telegram?.WebApp;
  },

  get initData(): string {
    return window.Telegram?.WebApp?.initData || '';
  },

  get initDataUnsafe(): any {
    return window.Telegram?.WebApp?.initDataUnsafe || {};
  },

  expand() {
    window.Telegram?.WebApp?.expand?.();
  },

  ready() {
    window.Telegram?.WebApp?.ready?.();
  },

  close() {
    window.Telegram?.WebApp?.close?.();
  },

  haptic(style: 'light' | 'medium' | 'heavy' = 'light') {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.(style);
    } catch {
      // ignore
    }
  },
};
