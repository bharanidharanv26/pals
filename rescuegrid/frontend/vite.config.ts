import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],worker:{format:'es'},server:{port:5173,proxy:{'/api':'http://127.0.0.1:8000','/geography':'http://127.0.0.1:8000'}},build:{chunkSizeWarningLimit:1600,rollupOptions:{output:{manualChunks:{maps:['maplibre-gl'],charts:['recharts'],ui:['react','react-dom','@radix-ui/react-dialog','sonner','react-i18next','i18next']}}}}});
