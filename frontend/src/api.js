// 统一请求封装：后端响应格式为 { code, msg, data }，code !== 0 视为失败
async function request(path, options = {}) {
  let res
  try {
    res = await fetch('/api' + path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (e) {
    throw new Error('网络异常，无法连接服务器')
  }
  let body = null
  try {
    body = await res.json()
  } catch (e) {
    throw new Error(`服务器响应异常（HTTP ${res.status}）`)
  }
  if (body.code !== 0) {
    const err = new Error(body.msg || '请求失败')
    err.code = body.code
    throw err
  }
  return body.data
}

export const api = {
  listProducts: () => request('/product/list'),
  createOrder: (payload) =>
    request('/order/create', { method: 'POST', body: JSON.stringify(payload) }),
  listOrders: (userId) => request(`/order/list?user_id=${encodeURIComponent(userId)}`),
  getOrder: (id) => request(`/order/${encodeURIComponent(id)}`),
  payOrder: (id) => request(`/order/${id}/pay`, { method: 'POST' }),
  cancelOrder: (id) => request(`/order/${id}/cancel`, { method: 'POST' }),
}
