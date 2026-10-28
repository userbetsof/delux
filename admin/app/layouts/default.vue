<script setup lang="ts">
import { useTheme } from 'vuetify'

const theme = useTheme()
const route = useRoute()
const { db } = useAdminDb()
const drawer = ref(true)
const collapsed = ref(false)

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
  { to: '/strategies', title: 'Стратегии', icon: 'mdi-puzzle-outline' },
  { to: '/sub-strategies', title: 'Подстратегии', icon: 'mdi-sitemap' },
  { to: '/elo', title: 'ELO', icon: 'mdi-chart-bar' },
  { to: '/glicko2', title: 'Glicko-2', icon: 'mdi-chart-line' },
  { to: '/openskill', title: 'OpenSkill', icon: 'mdi-chart-scatter-plot' },
]

const dbItems = [
  { title: 'matches.db', value: 'matches' },
  { title: 'parity_excel.db', value: 'parity_excel' },
  { title: 'parity_python.db', value: 'parity_python' },
]

const isDark = computed(() => theme.global.name.value === 'dark')

function toggleTheme() {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}

function toggleDrawer() {
  collapsed.value = !collapsed.value
  drawer.value = !collapsed.value
}
</script>

<template>
  <v-app>
    <!-- Sidebar -->
    <v-navigation-drawer
      v-model="drawer"
      :width="260"
      permanent
      class="sidebar"
      :class="{ 'sidebar--collapsed': collapsed }"
    >
      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="logo-icon">D</div>
        <span class="logo-text">DeluX</span>
      </div>

      <!-- Navigation -->
      <div class="sidebar-content">
        <v-list nav density="compact" class="pt-2">
          <v-list-item
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            :prepend-icon="link.icon"
            :title="link.title"
            :active="route.path === link.to || (link.to !== '/' && route.path.startsWith(link.to))"
            color="primary"
            rounded="lg"
            class="mb-1"
          >
            <template #prepend="{ active }">
              <v-icon :color="active ? 'primary' : 'rgba(255,255,255,0.7)'" size="small">
                {{ link.icon }}
              </v-icon>
            </template>
            <template #title>
              <span class="font-weight-medium">{{ link.title }}</span>
            </template>
          </v-list-item>
        </v-list>
      </div>

      <!-- Bottom Actions -->
      <div class="sidebar-footer">
        <v-divider class="mb-2" />
        <div class="pa-3">
          <v-select
            v-model="db"
            :items="dbItems"
            density="compact"
            hide-details
            variant="outlined"
            size="small"
          />
        </div>
      </div>
    </v-navigation-drawer>

    <!-- Top Bar -->
    <v-app-bar class="topbar" flat>
      <v-app-bar-nav-icon @click="toggleDrawer" />
      
      <v-spacer />

      <!-- Theme Toggle -->
      <v-btn
        :icon="isDark ? 'mdi-weather-night' : 'mdi-white-balance-sunny'"
        variant="text"
        size="small"
        @click="toggleTheme"
      />
    </v-app-bar>

    <!-- Main Content -->
    <v-main class="main-content">
      <v-container fluid class="px-4 px-md-6 py-6">
        <slot />
      </v-container>
    </v-main>
  </v-app>
</template>

<style scoped>
.sidebar {
  background-color: #0D1117 !important;
  border-right: none !important;
}

.sidebar--collapsed {
  width: 72px !important;
}

.sidebar--collapsed .sidebar-logo,
.sidebar--collapsed .sidebar-content,
.sidebar--collapsed .sidebar-footer {
  display: none;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #E87739 0%, #D35400 100%);
  color: white;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: white;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #E87739;
  font-weight: 900;
  font-size: 20px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.5px;
  white-space: nowrap;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.sidebar-footer {
  background-color: rgba(0, 0, 0, 0.2);
}

.topbar {
  background-color: white !important;
  border-bottom: 1px solid #E5E7EB !important;
}

.v-theme--dark .topbar {
  background-color: #1C1C2E !important;
  border-bottom-color: #374151 !important;
}

.main-content {
  background-color: #F0EBE5;
}

.v-theme--dark .main-content {
  background-color: #0F172A !important;
}

.v-list-item {
  color: rgba(255,255,255);
}
</style>
