<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-header">
        <h1>SubSkin 管理后台</h1>
        <p>请登录您的管理员账户</p>
      </div>
      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-placement="left"
        label-width="auto"
        size="large"
      >
        <n-form-item path="username">
          <n-input
            v-model:value="form.username"
            placeholder="手机号 / 邮箱 / 用户名"
            :input-props="{ autocomplete: 'username' }"
          >
            <template #prefix>
              <i class="ri-user-line" />
            </template>
          </n-input>
        </n-form-item>
        <n-form-item path="password">
          <n-input
            v-model:value="form.password"
            type="password"
            placeholder="密码"
            show-password-on="click"
            :input-props="{ autocomplete: 'current-password' }"
            @keydown.enter="handleLogin"
          >
            <template #prefix>
              <i class="ri-lock-line" />
            </template>
          </n-input>
        </n-form-item>
        <n-button
          type="primary"
          size="large"
          :loading="loading"
          block
          @click="handleLogin"
        >
          登录
        </n-button>
      </n-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const message = useMessage()
const authStore = useAuthStore()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: { required: true, message: '请输入账号', trigger: 'blur' },
  password: { required: true, message: '请输入密码', trigger: 'blur' }
}

const formRef = ref<any>(null)

async function handleLogin() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    if (!authStore.user?.is_admin) {
      message.error('需要管理员权限')
      authStore.logout()
      return
    }
    message.success('登录成功')
    router.push('/')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  width: 100vw;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
}

.login-box {
  width: 400px;
  max-width: 92vw;
  padding: 40px;
  border-radius: 16px;
  background: rgba(30, 41, 59, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}

@media (max-width: 768px) {
  .login-box {
    padding: 28px 20px;
  }

  .login-header h1 {
    font-size: 20px;
  }
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 600;
  color: #f8fafc;
}

.login-header p {
  margin: 0;
  color: #94a3b8;
  font-size: 14px;
}

i {
  font-size: 18px;
  color: #94a3b8;
}
</style>
