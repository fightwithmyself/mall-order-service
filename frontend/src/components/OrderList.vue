<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import OrderCard from './OrderCard.vue'

const props = defineProps({
  userId: { type: Number, required: true },
  focusId: { type: Number, default: null },
  notify: { type: Function, required: true },
})

const orders = ref([])
const loading = ref(false)
const busy = reactive({})
const now = ref(Date.now())
const searchId = ref('')
const searched = ref(null)      // 按订单号查询的结果
const searchError = ref('')

// 给待支付订单记录截止时间，前端据此本地倒计时
function decorate(o) {
  o._deadline = Date.now() + o.remaining_seconds * 1000
  return o
}

async function load() {
  if (!props.userId || props.userId < 1) return
  loading.value = true
  try {
    orders.value = (await api.listOrders(props.userId)).map(decorate)
  } catch (e) {
    props.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}

async function search() {
  searchError.value = ''
  searched.value = null
  if (!searchId.value) return
  try {
    searched.value = decorate(await api.getOrder(searchId.value))
  } catch (e) {
    searchError.value = e.message
  }
}

function replace(updated) {
  decorate(updated)
  const i = orders.value.findIndex((o) => o.id === updated.id)
  if (i >= 0) orders.value[i] = updated
  if (searched.value && searched.value.id === updated.id) searched.value = updated
}

async function act(order, action, okMsg) {
  busy[order.id] = true
  try {
    replace(await action(order.id))
    props.notify(okMsg, 'success')
  } catch (e) {
    props.notify(e.message, 'error')
    load()      // 状态可能已变化（如已超时关闭），刷新一下
  } finally {
    busy[order.id] = false
  }
}
const pay = (o) => act(o, api.payOrder, '支付成功')
const cancel = (o) => act(o, api.cancelOrder, '订单已取消')

// 每秒刷新时钟；待支付订单倒计时归零后，等消费者处理完再刷新状态
let timer = null
const refreshed = new Set()
onMounted(() => {
  load()
  timer = setInterval(() => {
    now.value = Date.now()
    const expired = [...orders.value, searched.value].find(
      (o) => o && o.status === 0 && o._deadline <= now.value && !refreshed.has(o.id),
    )
    if (expired) {
      refreshed.add(expired.id)
      setTimeout(() => {
        load()
        if (searched.value) search()
      }, 3000)
    }
  }, 1000)
})
onBeforeUnmount(() => clearInterval(timer))
watch(() => props.userId, load)
</script>

<template>
  <section>
    <div class="section-title">
      <h2>订单查询</h2>
    </div>

    <div class="card search-box">
      <input v-model="searchId" type="number" min="1" placeholder="输入订单ID查询单个订单" @keyup.enter="search" />
      <button class="btn primary" @click="search">查询</button>
      <span v-if="searchError" class="error-text">{{ searchError }}</span>
    </div>
    <OrderCard
      v-if="searched"
      :order="searched"
      :now="now"
      :busy="!!busy[searched.id]"
      @pay="pay"
      @cancel="cancel"
    />

    <div class="section-title sub">
      <h3>用户 {{ userId }} 的订单</h3>
      <button class="btn ghost" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新' }}</button>
    </div>
    <p v-if="!loading && orders.length === 0" class="empty">还没有订单，去商品列表下单吧</p>
    <OrderCard
      v-for="o in orders"
      :key="o.id"
      :order="o"
      :now="now"
      :busy="!!busy[o.id]"
      :highlight="o.id === focusId"
      @pay="pay"
      @cancel="cancel"
    />
  </section>
</template>
