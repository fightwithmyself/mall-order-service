<script setup>
import { computed } from 'vue'

const props = defineProps({
  order: { type: Object, required: true },
  now: { type: Number, required: true },   // 父组件每秒更新的当前时间戳（ms），用于倒计时
  busy: Boolean,
  highlight: Boolean,
})
defineEmits(['pay', 'cancel'])

const statusClass = computed(() => ['pending', 'paid', 'closed', 'closed'][props.order.status] || 'closed')

const remaining = computed(() => {
  if (props.order.status !== 0) return 0
  return Math.max(0, Math.ceil((props.order._deadline - props.now) / 1000))
})

const countdown = computed(() => {
  const s = remaining.value
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  return `${m}:${String(s % 60).padStart(2, '0')}`
})

const fmt = (t) => (t ? t.replace('T', ' ').slice(0, 19) : '-')
</script>

<template>
  <article class="card order" :class="{ highlight }">
    <div class="order-head">
      <span class="order-no">订单号 {{ order.order_no }}</span>
      <span class="tag" :class="statusClass">{{ order.status_text }}</span>
    </div>
    <div class="order-body">
      <div>
        <div class="order-name">{{ order.product_name || `商品#${order.product_id}` }} × {{ order.buy_num }}</div>
        <div class="muted">下单时间 {{ fmt(order.create_time) }}</div>
        <div v-if="order.pay_time" class="muted">支付时间 {{ fmt(order.pay_time) }}</div>
        <div class="muted">用户 {{ order.user_id }} · 订单ID {{ order.id }}</div>
      </div>
      <div class="order-side">
        <div class="price">¥{{ order.total_price.toFixed(2) }}</div>
        <div v-if="order.status === 0" class="countdown">
          {{ remaining > 0 ? `${countdown} 后自动关闭` : '正在关闭…' }}
        </div>
      </div>
    </div>
    <div v-if="order.status === 0" class="order-actions">
      <button class="btn ghost" :disabled="busy" @click="$emit('cancel', order)">取消订单</button>
      <button class="btn primary" :disabled="busy || remaining === 0" @click="$emit('pay', order)">立即支付</button>
    </div>
  </article>
</template>
