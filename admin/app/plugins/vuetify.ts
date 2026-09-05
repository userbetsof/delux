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
            primary: '#1B4D3E',
            secondary: '#C4A35A',
            surface: '#F7F4EF',
          },
        },
        dark: {
          colors: {
            primary: '#3D8B6E',
            secondary: '#D4B56A',
          },
        },
      },
    },
  })

  nuxtApp.vueApp.use(vuetify)
})
