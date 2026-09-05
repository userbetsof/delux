<script setup lang="ts">
import { useTheme } from 'vuetify'

const theme = useTheme()
const route = useRoute()
const { db } = useAdminDb()
const drawer = ref(true)

const links = [
  { to: '/', title: 'Обзор', icon: 'mdi-view-dashboard-outline' },
  { to: '/matches', title: 'Матчи', icon: 'mdi-soccer' },
  { to: '/queue', title: 'Очередь', icon: 'mdi-format-list-bulleted' },
  { to: '/predictions', title: 'Прогнозы', icon: 'mdi-crystal-ball' },
  { to: '/moneyway', title: 'Moneyway', icon: 'mdi-chart-timeline-variant' },
  { to: '/outcomes', title: 'Стратегии %', icon: 'mdi-percent-outline' },
  { to: '/odds', title: 'Коэффициенты', icon: 'mdi-cash-multiple' },
  { to: '/goals', title: 'Голы %', icon: 'mdi-soccer-field' },
  { to: '/leagues', title: 'Лиги', icon: 'mdi-trophy-outline' },
  { to: '/teams', title: 'Команды', icon: 'mdi-shield-outline' },
  { to: '/countries', title: 'Страны', icon: 'mdi-earth' },
  { to: '/strategies', title: 'Справочник стратегий', icon: 'mdi-puzzle-outline' },
  { to: '/sub-strategies', title: 'Подстратегии', icon: 'mdi-sitemap' },
]

const dbItems = [
  { title: 'matches.db (боевая)', value: 'matches' },
  { title: 'parity_excel.db', value: 'parity_excel' },
  { title: 'parity_python.db', value: 'parity_python' },
]

const isDark = computed(() => theme.global.name.value === 'dark')

function toggleTheme() {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}
</script>

<template>
  <v-app>
    <v-navigation-drawer v-model="drawer" permanent :rail="false" width="260">
      <div class="pa-4">
        <div class="text-h6 font-weight-bold">DeluX</div>
        <div class="text-caption text-medium-emphasis">Просмотр SQLite</div>
      </div>
      <v-divider />
      <v-list nav density="compact">
        <v-list-item
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          :prepend-icon="link.icon"
          :title="link.title"
          :active="route.path === link.to || (link.to !== '/' && route.path.startsWith(link.to))"
          color="primary"
          rounded="lg"
        />
      </v-list>
    </v-navigation-drawer>

    <v-app-bar flat border>
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title class="text-body-1">Админка БД</v-app-bar-title>
      <v-spacer />
      <v-select
        v-model="db"
        :items="dbItems"
        density="compact"
        hide-details
        variant="outlined"
        style="max-width: 280px"
        class="mr-3"
      />
      <v-btn
        :icon="isDark ? 'mdi-weather-night' : 'mdi-white-balance-sunny'"
        variant="text"
        @click="toggleTheme"
      />
    </v-app-bar>

    <v-main>
      <v-container class="py-6" fluid>
        <slot />
      </v-container>
    </v-main>
  </v-app>
</template>
