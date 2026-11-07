import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Telegram Mini App'ni ochish uchun HTTPS tunnel (masalan ngrok) orqali kirish
    // zarur - Vite'ning Host header himoyasi bunday tashqi domenlarni rad etadi,
    // shuning uchun ngrok/localtunnel kabi bepul tunnel domenlariga ruxsat beramiz.
    allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io', '.loca.lt', '.trycloudflare.com'],
  },
});
