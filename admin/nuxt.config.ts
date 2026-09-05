export default defineNuxtConfig({
  compatibilityDate: '2025-03-01',
  srcDir: 'app/',
  serverDir: 'server',
  devtools: { enabled: true },
  typescript: {
    strict: true,
    typeCheck: false,
  },
  build: {
    transpile: ['vuetify'],
  },
  vite: {
    ssr: {
      noExternal: ['vuetify'],
    },
  },
  css: ['vuetify/styles', '@mdi/font/css/materialdesignicons.css'],
  app: {
    head: {
      title: 'DeluX Admin',
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    },
  },
  nitro: {
    // node:sqlite
    esbuild: {
      options: {
        target: 'esnext',
      },
    },
  },
})
