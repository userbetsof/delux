<script setup lang="ts">
const props = defineProps<{
  offset: number
  limit: number
  total: number
  pending?: boolean
}>()

const emit = defineEmits<{
  prev: []
  next: []
  'update:limit': [value: number]
}>()

const from = computed(() => (props.total === 0 ? 0 : props.offset + 1))
const to = computed(() => Math.min(props.offset + props.limit, props.total))
const canPrev = computed(() => !props.pending && props.offset > 0)
const canNext = computed(() => !props.pending && props.offset + props.limit < props.total)

const limitModel = computed({
  get: () => props.limit,
  set: (v: number) => emit('update:limit', Number(v) || 50),
})
</script>

<template>
  <div class="d-flex align-center justify-space-between pa-3 flex-wrap ga-2">
    <v-btn size="small" variant="outlined" :disabled="!canPrev" @click="emit('prev')">Назад</v-btn>
    <div class="d-flex align-center ga-3 flex-wrap">
      <v-text-field
        v-model.number="limitModel"
        label="На стр."
        type="number"
        density="compact"
        hide-details
        style="max-width: 90px"
        min="1"
        max="500"
      />
      <div class="text-caption text-medium-emphasis">
        {{ from }}–{{ to }} из {{ total || '—' }}
      </div>
    </div>
    <v-btn size="small" variant="outlined" :disabled="!canNext" @click="emit('next')">Далее</v-btn>
  </div>
</template>
