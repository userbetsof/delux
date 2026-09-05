<script setup lang="ts">
import type { MatchDetail } from '~/types/db'
import { sportLabel } from '~/types/db'

const route = useRoute()
const { dbQuery } = useAdminDb()
const matchId = computed(() => String(route.params.id))

const { data, pending, error, refresh } = await useFetch<MatchDetail>(
  () => `/api/matches/${matchId.value}`,
  { query: dbQuery, watch: [matchId, dbQuery] },
)

const m = computed(() => data.value?.match)

const predHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'ID', key: 'strategy_id' },
  { title: 'Прогноз', key: 'prediction' },
  { title: 'Кф', key: 'odds' },
  { title: 'Ставка', key: 'stake' },
  { title: 'Результат', key: 'result' },
  { title: 'Профит', key: 'profit' },
]

const outcomeHeaders = [
  { title: 'Стратегия', key: 'strategy_name' },
  { title: 'ID', key: 'strategy_id' },
  { title: 'П1 %', key: 'home_win_prob' },
  { title: 'X %', key: 'draw_prob' },
  { title: 'П2 %', key: 'away_win_prob' },
]

const oddsHeaders = [
  { title: 'Рынок', key: 'market_name' },
  { title: 'Исход', key: 'outcome' },
  { title: 'Сторона', key: 'side' },
  { title: 'Линия', key: 'line_value' },
  { title: 'Кф', key: 'odds_value' },
]

const goalRows = computed(() => {
  const g = data.value?.goals
  if (!g) return []
  return [0, 1, 2, 3, 4, 5].map((n) => ({
    goals: n,
    home: g[`home_goals_${n}` as keyof typeof g],
    away: g[`away_goals_${n}` as keyof typeof g],
  }))
})
</script>

<template>
  <div class="d-flex flex-column ga-4">
    <div class="d-flex align-center justify-space-between">
      <div class="d-flex align-center ga-3">
        <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/matches">К списку</v-btn>
        <div>
          <div class="text-h5 font-weight-bold">{{ matchId }}</div>
          <div v-if="m" class="text-body-2 text-medium-emphasis">
            {{ m.home_team || '—' }} — {{ m.away_team || '—' }}
          </div>
        </div>
      </div>
      <v-btn variant="outlined" :loading="pending" @click="refresh()">Обновить</v-btn>
    </div>

    <v-alert v-if="error" type="error" density="compact">{{ error.message || error }}</v-alert>

    <v-card v-if="m">
      <v-card-title>Карточка матча</v-card-title>
      <v-divider />
      <v-card-text>
        <v-row dense>
          <v-col cols="12" md="3"><strong>Дата:</strong> {{ m.match_date }}</v-col>
          <v-col cols="12" md="3">
            <strong>Лига:</strong>
            {{ [m.country_name, m.league_name].filter(Boolean).join(': ') || '—' }}
          </v-col>
          <v-col cols="12" md="3"><strong>Статус:</strong> {{ m.match_status }}</v-col>
          <v-col cols="12" md="3"><strong>Счёт:</strong> {{ m.score_home }} : {{ m.score_away }}</v-col>
          <v-col cols="12" md="3"><strong>Минута:</strong> {{ m.minute }}</v-col>
          <v-col cols="12" md="3"><strong>Прогноз:</strong> {{ m.prediction || '—' }}</v-col>
          <v-col cols="12" md="3"><strong>Профит:</strong> {{ m.profit }}</v-col>
          <v-col cols="12" md="3"><strong>Спорт:</strong> {{ sportLabel(m.sport as number) }}</v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card>
      <v-card-title>Прогнозы стратегий</v-card-title>
      <v-divider />
      <v-data-table
        :headers="predHeaders"
        :items="data?.predictions || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
      />
    </v-card>

    <v-card>
      <v-card-title>Вероятности исходов (10 стратегий)</v-card-title>
      <v-divider />
      <v-data-table
        :headers="outcomeHeaders"
        :items="data?.outcomes || []"
        :loading="pending"
        item-value="id"
        hide-default-footer
      />
    </v-card>

    <v-row dense>
      <v-col cols="12" md="7">
        <v-card>
          <v-card-title>Коэффициенты</v-card-title>
          <v-divider />
          <v-data-table
            :headers="oddsHeaders"
            :items="data?.odds || []"
            :loading="pending"
            item-value="id"
            hide-default-footer
          />
        </v-card>
      </v-col>
      <v-col cols="12" md="5">
        <v-card>
          <v-card-title>Вероятности голов</v-card-title>
          <v-divider />
          <v-data-table
            :headers="[
              { title: 'Голы', key: 'goals' },
              { title: 'Дома %', key: 'home' },
              { title: 'Гости %', key: 'away' },
            ]"
            :items="goalRows"
            item-value="goals"
            hide-default-footer
          />
          <v-card-text v-if="!data?.goals" class="text-medium-emphasis">Нет данных</v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
