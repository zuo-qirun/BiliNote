<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getCaptcha, getCurrentAccount, loginAccount, logoutAccount, registerAccount } from '~/logic/api'
import { syncTaskHistory } from '~/logic/account-sync'
import { authReady, authSession } from '~/logic/storage'

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const email = ref('')
const phone = ref('')
const captchaId = ref('')
const captchaImage = ref('')
const captchaCode = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')
const loggedIn = computed(() => !!authSession.value?.token)

async function refreshCaptcha() {
  const captcha = await getCaptcha()
  captchaId.value = captcha.captcha_id
  captchaImage.value = captcha.image
  captchaCode.value = ''
}

async function submit() {
  loading.value = true
  message.value = ''
  error.value = ''
  try {
    const session = mode.value === 'login'
      ? await loginAccount(username.value.trim(), password.value)
      : await registerAccount({
          username: username.value.trim(),
          password: password.value,
          email: email.value.trim(),
          phone: phone.value.trim() || undefined,
          captcha_id: captchaId.value,
          captcha_code: captchaCode.value.trim(),
        })
    authSession.value = session
    password.value = ''
    await syncTaskHistory()
    message.value = mode.value === 'login' ? '登录成功，历史已同步' : '账号创建成功，历史已同步'
  }
  catch (e) {
    error.value = (e as Error).message
    if (mode.value === 'register')
      await refreshCaptcha().catch(() => undefined)
  }
  finally {
    loading.value = false
  }
}

async function logout() {
  await logoutAccount().catch(() => undefined)
  authSession.value = { token: '', user: null }
  message.value = '已退出账号，本机历史仍然保留'
}

async function syncNow() {
  loading.value = true
  error.value = ''
  try {
    await syncTaskHistory()
    message.value = '生成历史已同步'
  }
  catch (e) {
    error.value = (e as Error).message
  }
  finally {
    loading.value = false
  }
}

onMounted(async () => {
  await authReady
  if (authSession.value?.token) {
    try {
      const user = await getCurrentAccount()
      authSession.value = { ...authSession.value, user }
    }
    catch {
      authSession.value = { token: '', user: null }
    }
  }
})
</script>

<template>
  <div class="p-6 max-w-2xl">
    <h1 class="text-xl font-bold mb-1">账号与同步</h1>
    <p class="text-sm text-gray-500 mb-5">
      网页、不同电脑和浏览器插件使用同一账号时，共享全部生成历史。
    </p>

    <section v-if="loggedIn" class="section-card">
      <div class="flex items-center justify-between gap-4">
        <div>
          <div class="text-xs text-gray-500">当前账号</div>
          <div class="mt-1 text-lg font-semibold">{{ authSession.user?.username }}</div>
          <div class="mt-1 text-xs text-gray-500">{{ authSession.user?.role_label }}</div>
        </div>
        <span class="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">自动同步</span>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary" :disabled="loading" @click="syncNow">
          {{ loading ? '同步中…' : '立即同步' }}
        </button>
        <button class="btn-secondary" @click="logout">退出账号</button>
      </div>
      <div class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <div class="font-medium">今日生成额度</div>
        <div class="mt-1 text-lg font-semibold">
          {{ authSession.user?.quota.limit == null ? '无限制' : `${authSession.user?.quota.remaining} / ${authSession.user?.quota.limit}` }}
        </div>
      </div>
    </section>

    <section v-else class="section-card">
      <div class="grid grid-cols-2 rounded bg-gray-100 p-1 text-sm">
        <button
          class="rounded px-3 py-2"
          :class="mode === 'login' ? 'bg-white font-medium shadow-sm' : 'text-gray-500'"
          @click="mode = 'login'"
        >登录</button>
        <button
          class="rounded px-3 py-2"
          :class="mode === 'register' ? 'bg-white font-medium shadow-sm' : 'text-gray-500'"
          @click="mode = 'register'; refreshCaptcha()"
        >注册</button>
      </div>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">账号</span>
        <input v-model="username" class="input" minlength="3" maxlength="32" autocomplete="username" placeholder="3-32 位字母、数字、点或下划线">
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">密码</span>
        <input v-model="password" class="input" type="password" minlength="8" maxlength="128" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" placeholder="至少 8 位">
      </label>
      <template v-if="mode === 'register'">
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-gray-600">邮箱（必填）</span>
          <input v-model="email" class="input" type="email" maxlength="254" autocomplete="email" placeholder="name@example.com">
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-gray-600">手机号（选填）</span>
          <input v-model="phone" class="input" type="tel" maxlength="30" autocomplete="tel">
        </label>
        <label class="flex flex-col gap-1 text-sm">
          <span class="text-gray-600">图形验证码</span>
          <div class="flex gap-2">
            <input v-model="captchaCode" class="input flex-1 uppercase" maxlength="10" placeholder="输入图中字符">
            <button class="h-10 w-36 overflow-hidden rounded border bg-stone-50" type="button" @click="refreshCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="图形验证码" class="h-full w-auto">
              <span v-else class="text-xs text-gray-500">点击刷新</span>
            </button>
          </div>
        </label>
        <p class="text-xs text-gray-500">免费用户每日 5 篇，特权用户每日 50 篇。</p>
      </template>
      <button
        class="btn-primary"
        :disabled="loading || username.length < 3 || password.length < 8 || (mode === 'register' && (!email || !captchaCode || !captchaId))"
        @click="submit"
      >
        {{ loading ? '处理中…' : mode === 'login' ? '登录并同步历史' : '注册并同步历史' }}
      </button>
      <p class="text-xs text-gray-500">模型 API Key 不会作为生成历史上传。</p>
    </section>

    <p v-if="message" class="text-sm text-green-700">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600 break-words">{{ error }}</p>
  </div>
</template>
