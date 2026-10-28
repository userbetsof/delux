import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

export default defineNuxtPlugin((nuxtApp) => {
  const vuetify = createVuetify({
    components,
    directives,
    ssr: true,
    icons: {
      defaultSet: 'mdi',
      aliases,
      sets: { mdi },
    },
    theme: {
      defaultTheme: 'light',
      themes: {
        light: {
          colors: {
            primary: '#E87739',
            secondary: '#4A90E2',
            success: '#2ECC71',
            info: '#3498DB',
            warning: '#F39C12',
            error: '#E74C3C',
            dark: '#0D1117',
            darkHover: '#161B22',
            surface: '#F0EBE5',
            surfaceAlt: '#FFFFFF',
            text: '#1A1A2E',
            textSecondary: '#6B7280',
            border: '#E5E7EB',
          },
        },
        dark: {
          colors: {
            primary: '#E87739',
            secondary: '#4A90E2',
            success: '#2ECC71',
            info: '#3498DB',
            warning: '#F39C12',
            error: '#E74C3C',
            dark: '#0D1117',
            darkHover: '#161B22',
            surface: '#1C1C2E',
            surfaceAlt: '#2A2A3E',
            text: '#F0EBE5',
            textSecondary: '#9CA3AF',
            border: '#374151',
          },
        },
      },
    },
  })

  nuxtApp.vueApp.use(vuetify)
})
