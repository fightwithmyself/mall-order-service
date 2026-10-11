<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  userId: { type: Number, required: true },
  active: Boolean,
  notify: { type: Function, required: true },
})
const emit = defineEmits(['ordered'])

const products = ref([])
const loading = ref(false)
const qty = reactive({})        // 每个商品的购买数量
const submitting = reactive({}) // 每个商品的提交状态，防止重复点击

async function load() {
  loading.value = true
  try {
    products.value = await api.listProducts()
    products.value.forEach((p) => {
      if (!qty[p.id]) qty[p.id] = 1
    })
  } catch (e) {
    props.notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function changeQty(p, delta) {
  const next = (qty[p.id] || 1) + delta
  qty[p.id] = Math.min(Math.max(next, 1), Math.max(p.stock, 1), 99)
}

async function buy(p) {
  if (!props.userId || props.userId < 1) return props.notify('请先输入有效的用户ID', 'error')
  if (submitting[p.id]) return
  submitting[p.id] = true
  try {
    const data = await api.createOrder({
      user_id: props.userId,
      product_id: p.id,
      buy_num: qty[p.id] || 1,
    })
    props.notify(`下单成功，订单号 ${data.order_no}，请尽快支付`, 'success')
    emit('ordered', data.order_id)
  } catch (e) {
    props.notify(e.message, 'error')
  } finally {
    submitting[p.id] = false
    load()   // 无论成败都刷新库存
  }
}

onMounted(load)
watch(() => props.active, (v) => v && load())   // 切回商品页时刷新库存
</script>

<template>
  <section>
    <div class="section-title">
      <h2>商品列表</h2>
      <button class="btn ghost" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新库存' }}</button>
    </div>

    <p v-if="!loading && products.length === 0" class="empty">暂无商品，请先运行 create_tables.py 初始化数据</p>

    <div class="grid">
      <article v-for="p in products" :key="p.id" class="card product">
        <div class="product-img">{{ p.image || '📦' }}</div>
        <h3>{{ p.product_name }}</h3>
        <p class="desc">{{ p.description }}</p>
        <div class="price-row">
          <span class="price">¥{{ p.price.toFixed(2) }}</span>
          <span class="stock" :class="{ low: p.stock > 0 && p.stock <= 10, out: p.stock === 0 }">
            {{ p.stock === 0 ? '已售罄' : `库存 ${p.stock}` }}
          </span>
        </div>
        <div class="buy-row">
          <div class="stepper">
            <button :disabled="p.stock === 0" @click="changeQty(p, -1)">−</button>
            <span>{{ qty[p.id] || 1 }}</span>
            <button :disabled="p.stock === 0" @click="changeQty(p, 1)">+</button>
          </div>
          <button class="btn primary" :disabled="p.stock === 0 || submitting[p.id]" @click="buy(p)">
            {{ submitting[p.id] ? '提交中…' : '立即下单' }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
