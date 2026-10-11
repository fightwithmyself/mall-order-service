<script setup>
import { ref, watch } from 'vue'
import ProductList from './components/ProductList.vue'
import OrderList from './components/OrderList.vue'

const tab = ref('products')
const userId = ref(Number(localStorage.getItem('mall_user_id')) || 1)
watch(userId, (v) => localStorage.setItem('mall_user_id', String(v || 1)))

// 全局提示
const toast = ref(null)
let toastTimer = null
function notify(msg, type = 'info') {
  toast.value = { msg, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = null), 3000)
}

// 下单成功后跳转到订单页并定位到新订单
const focusOrderId = ref(null)
function onOrdered(orderId) {
  focusOrderId.value = orderId
  tab.value = 'orders'
}
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <div class="brand">🛒 Mall 商城</div>
      <nav class="tabs">
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">商品列表</button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">订单查询</button>
      </nav>
      <label class="user-box">
        用户ID
        <input v-model.number="userId" type="number" min="1" />
      </label>
    </div>
  </header>

  <main class="container">
    <ProductList v-show="tab === 'products'" :user-id="userId" :active="tab === 'products'" :notify="notify" @ordered="onOrdered" />
    <OrderList v-if="tab === 'orders'" :user-id="userId" :focus-id="focusOrderId" :notify="notify" />
  </main>

  <transition name="fade">
    <div v-if="toast" class="toast" :class="toast.type">{{ toast.msg }}</div>
  </transition>
</template>
