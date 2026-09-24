<template>
  <div class="home-container">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="icon-wrapper">
        <span class="icon">✈️</span>
      </div>
      <h1 class="page-title">智能旅行助手</h1>
      <p class="page-subtitle">基于AI的个性化旅行规划,让每一次出行都完美无忧</p>
    </div>

    <a-card class="form-card" :bordered="false">
      <a-form
        :model="formData"
        layout="vertical"
        @finish="handleSubmit"
      >
        <!-- 第一步:目的地和日期 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">📍</span>
            <span class="section-title">目的地与日期</span>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="city" :rules="[{ required: true, message: '请输入目的地城市' }]">
                <template #label>
                  <span class="form-label">目的地城市</span>
                </template>
                <a-input
                  v-model:value="formData.city"
                  placeholder="例如: 北京"
                  size="large"
                  class="custom-input"
                >
                  <template #prefix>
                    <span style="color: #1890ff;">🏙️</span>
                  </template>
                </a-input>
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择开始日期' }]">
                <template #label>
                  <span class="form-label">开始日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="end_date" :rules="[{ required: true, message: '请选择结束日期' }]">
                <template #label>
                  <span class="form-label">结束日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.end_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="4">
              <a-form-item>
                <template #label>
                  <span class="form-label">旅行天数</span>
                </template>
                <div class="days-display-compact">
                  <span class="days-value">{{ formData.travel_days }}</span>
                  <span class="days-unit">天</span>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- 第二步:偏好设置 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">⚙️</span>
            <span class="section-title">偏好设置</span>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="transportation">
                <template #label>
                  <span class="form-label">交通方式</span>
                </template>
                <a-select v-model:value="formData.transportation" size="large" class="custom-select">
                  <a-select-option value="公共交通">🚇 公共交通</a-select-option>
                  <a-select-option value="自驾">🚗 自驾</a-select-option>
                  <a-select-option value="步行">🚶 步行</a-select-option>
                  <a-select-option value="混合">🔀 混合</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="accommodation">
                <template #label>
                  <span class="form-label">住宿偏好</span>
                </template>
                <a-select v-model:value="formData.accommodation" size="large" class="custom-select">
                  <a-select-option value="经济型酒店">💰 经济型酒店</a-select-option>
                  <a-select-option value="舒适型酒店">🏨 舒适型酒店</a-select-option>
                  <a-select-option value="豪华酒店">⭐ 豪华酒店</a-select-option>
                  <a-select-option value="民宿">🏡 民宿</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="preferences">
                <template #label>
                  <span class="form-label">旅行偏好</span>
                </template>
                <div class="preference-tags">
                  <a-checkbox-group v-model:value="formData.preferences" class="custom-checkbox-group">
                    <a-checkbox value="历史文化" class="preference-tag">🏛️ 历史文化</a-checkbox>
                    <a-checkbox value="自然风光" class="preference-tag">🏞️ 自然风光</a-checkbox>
                    <a-checkbox value="美食" class="preference-tag">🍜 美食</a-checkbox>
                    <a-checkbox value="购物" class="preference-tag">🛍️ 购物</a-checkbox>
                    <a-checkbox value="艺术" class="preference-tag">🎨 艺术</a-checkbox>
                    <a-checkbox value="休闲" class="preference-tag">☕ 休闲</a-checkbox>
                  </a-checkbox-group>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- 第三步:额外要求 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">💬</span>
            <span class="section-title">额外要求</span>
          </div>

          <a-form-item name="free_text_input">
            <a-textarea
              v-model:value="formData.free_text_input"
              placeholder="请输入您的额外要求,例如:想去看升旗、需要无障碍设施、对海鲜过敏等..."
              :rows="3"
              size="large"
              class="custom-textarea"
            />
          </a-form-item>
        </div>

        <!-- 提交按钮 -->
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            :loading="loading"
            size="large"
            block
            class="submit-button"
          >
            <template v-if="!loading">
              <span class="button-icon">🚀</span>
              <span>开始规划我的旅行</span>
            </template>
            <template v-else>
              <span>正在生成中...</span>
            </template>
          </a-button>
        </a-form-item>

        <!-- 真实运行进度：由 SSE step_started/tool_call/tool_result 事件驱动 -->
        <a-form-item v-if="loading">
          <div class="loading-container">
            <a-steps direction="vertical" :current="currentStepIndex" :items="stepItems" />
            <p v-if="toolActivity" class="loading-status">{{ toolActivity }}</p>
            <p v-else class="loading-status">{{ loadingStatus }}</p>
          </div>
        </a-form-item>

        <!-- 失败/降级告警：常驻显示（不随 loading 隐藏），用户可重试 -->
        <a-form-item v-if="runError || runWarnings.length > 0">
          <div class="loading-container">
            <a-alert v-if="runError" type="error" show-icon :message="runError" />
            <a-alert
              v-for="warning in runWarnings"
              :key="warning"
              type="warning"
              show-icon
              :message="warning"
            />
          </div>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { generateTripPlan, subscribeRunEvents } from '@/services/api'
import { clearTripRunResult, saveTripRunResult } from '@/services/runStorage'
import type { RunCompletedPayload, RunEvent, TripFormData, TripRunResult } from '@/types'
import type { Dayjs } from 'dayjs'

const router = useRouter()
const loading = ref(false)
const loadingStatus = ref('')
const currentStep = ref<string | null>(null)
const finishedSteps = ref<string[]>([])
const toolActivity = ref('')
const runError = ref('')
const runWarnings = ref<string[]>([])
let unsubscribeRun: (() => void) | null = null
// 当前 run 的 id：只接受属于它的事件，旧订阅的迟到回调无法影响新 run
let activeRunId: string | null = null

// 编排四步（与后端 step_started 事件中的 step 键一一对应）
const RUN_STEPS = [
  { key: 'attractions', label: '搜索景点', icon: '🔍' },
  { key: 'weather', label: '查询天气', icon: '🌤️' },
  { key: 'hotels', label: '推荐酒店', icon: '🏨' },
  { key: 'plan', label: '生成行程计划', icon: '📋' }
]

const currentStepIndex = computed<number | undefined>(() => {
  if (!currentStep.value) return undefined
  const index = RUN_STEPS.findIndex((step) => step.key === currentStep.value)
  return index < 0 ? undefined : index
})

// 真实步骤状态驱动 a-steps：完成 / 进行中 / 等待
const stepItems = computed(() =>
  RUN_STEPS.map((step) => {
    const isFinished = finishedSteps.value.includes(step.key)
    const isCurrent = currentStep.value === step.key
    return {
      title: `${step.icon} ${step.label}`,
      status: isFinished ? 'finish' : isCurrent ? 'process' : 'wait'
    }
  })
)

type TripFormState = Omit<TripFormData, 'start_date' | 'end_date'> & {
  start_date: Dayjs | null
  end_date: Dayjs | null
}

const formData = reactive<TripFormState>({
  city: '',
  start_date: null,
  end_date: null,
  travel_days: 1,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: ''
})

// 监听日期变化,自动计算旅行天数
watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (start && end) {
    const days = end.diff(start, 'day') + 1
    if (days > 0 && days <= 30) {
      formData.travel_days = days
    } else if (days > 30) {
      message.warning('旅行天数不能超过30天')
      formData.end_date = null
    } else {
      message.warning('结束日期不能早于开始日期')
      formData.end_date = null
    }
  }
})

const resetProgress = () => {
  currentStep.value = null
  finishedSteps.value = []
  toolActivity.value = ''
  runError.value = ''
  runWarnings.value = []
  activeRunId = null
}

const handleRunEvent = (event: RunEvent) => {
  // 旧订阅的迟到回调不能影响新 run：只处理当前 run 的事件
  if (activeRunId !== event.run_id) return
  switch (event.type) {
    case 'run_started':
      loadingStatus.value = '运行已开始，正在执行多智能体编排...'
      break
    case 'step_started': {
      const step = String(event.data.step || '')
      const label = String(event.data.label || step)
      const nextIndex = RUN_STEPS.findIndex((item) => item.key === step)
      if (nextIndex < 0) break
      const currentKey = currentStep.value
      const currentIndex = currentKey ? RUN_STEPS.findIndex((item) => item.key === currentKey) : -1
      // 重放幂等 + 单调前进：只接受严格晚于当前步骤的推进；重放/回退事件一律忽略，
      // 既不把当前步骤误标为已完成，也不允许进度回退
      if (nextIndex > currentIndex) {
        if (currentKey && currentIndex >= 0 && !finishedSteps.value.includes(currentKey)) {
          finishedSteps.value.push(currentKey)
        }
        currentStep.value = step
        toolActivity.value = ''
        loadingStatus.value = `正在${label}...`
      }
      break
    }
    case 'tool_call':
      toolActivity.value = `🔧 正在调用 ${event.data.tool_name} 获取数据...`
      break
    case 'tool_result': {
      const toolName = String(event.data.tool_name || '工具')
      // 工具调用失败时后端在 data 里带 error 字段：如实显示失败，不打成功勾
      toolActivity.value = event.data.error
        ? `⚠️ ${toolName} 调用失败：${String(event.data.error)}`
        : `✅ 已获取 ${toolName} 数据`
      break
    }
    case 'validation_error': {
      const validationMessage = event.data.error || event.data.message || '输出校验未通过'
      toolActivity.value = `⚠️ ${String(validationMessage)}`
      break
    }
    case 'run_completed':
      handleRunCompleted(event.run_id, event.data as unknown as RunCompletedPayload)
      break
  }
}

// 校验 run_completed 终态载荷与后端终态契约的一致性：
// success/degraded 必须携带非空 result；degraded/failed 必须携带非空 warnings。
// 非法终态视作异常：不跳转、不渲染，防止把不完整/自相矛盾的结果伪装成成功。
const validateTerminalPayload = (data: RunCompletedPayload): string | null => {
  const warnings = Array.isArray(data.warnings) ? data.warnings : []
  const hasResult = data.result !== null && data.result !== undefined
  switch (data.status) {
    case 'success':
      return hasResult ? null : '运行终态不完整：success 必须携带行程结果'
    case 'degraded':
      if (!hasResult) return '运行终态不完整：degraded 必须携带行程结果'
      return warnings.length > 0 ? null : '运行终态不完整：degraded 必须携带降级告警清单'
    case 'failed':
      return warnings.length > 0 ? null : '运行终态不完整：failed 必须携带失败告警清单'
    default:
      return '收到无法识别的运行终态'
  }
}

const handleRunCompleted = (runId: string, data: RunCompletedPayload) => {
  // 先校验终态载荷：非法终态直接停止（不跳转、清残留存储、如实报错），
  // 同时关闭订阅并清空活动 run 引用，迟到回调无法再触达 UI
  const validationError = validateTerminalPayload(data)
  if (validationError) {
    unsubscribeRun?.()
    unsubscribeRun = null
    activeRunId = null
    loading.value = false
    loadingStatus.value = '运行已结束'
    toolActivity.value = ''
    clearTripRunResult()
    runError.value = validationError
    runWarnings.value = []
    message.error(validationError)
    return
  }

  // warnings 在终态契约中必然存在；对缺失做空数组兜底，避免旧事件形状导致渲染异常
  const warnings: string[] = Array.isArray(data.warnings) ? data.warnings : []
  const envelope: TripRunResult = {
    run_id: runId,
    status: data.status,
    warnings,
    result: data.result ?? null,
    error: data.error ?? null
  }
  // 先捕获 run_id 到信封，再关闭 SSE 订阅、清空活动 run 引用；
  // 此后任何迟到回调都无法改写属于本次运行的终态
  unsubscribeRun?.()
  unsubscribeRun = null
  activeRunId = null
  loadingStatus.value = '运行已结束'
  toolActivity.value = ''

  // 完整终态信封落 sessionStorage：success/degraded/failed 一律保存，交由结果页如实渲染
  let storageError = ''
  try {
    saveTripRunResult(envelope)
  } catch (error: unknown) {
    storageError = error instanceof Error
      ? `运行已结束，但结果保存失败：${error.message}`
      : '运行已结束，但结果保存失败，请重试'
  }
  if (storageError) {
    // 存储失败时保持诚实：不跳转，并清除可能残留的旧 run 信封，防止误读过期结果
    clearTripRunResult()
    loading.value = false
    runError.value = storageError
    runWarnings.value = []
    message.error(storageError)
    return
  }

  if (data.status === 'success') {
    message.success('旅行计划生成成功!')
  } else if (data.status === 'degraded') {
    message.warning(warnings.length > 0 ? `行程已降级生成：${warnings[0]}` : '行程已降级生成，部分数据可能缺失')
  } else {
    message.error(data.error || '运行失败，请稍后重试')
  }
  runError.value = ''
  runWarnings.value = []
  // 所有合法终态（success / degraded / failed）都跳转结果页，由结果页三态如实呈现
  handleSuccess()
}

const handleSuccess = () => {
  loading.value = false
  setTimeout(() => {
    router.push('/result')
  }, 500)
}

const handleSubmit = async () => {
  if (!formData.start_date || !formData.end_date) {
    message.error('请选择日期')
    return
  }

  loading.value = true
  // 关闭上一个 run 的订阅，旧回调不得残留到新 run
  unsubscribeRun?.()
  unsubscribeRun = null
  resetProgress()
  loadingStatus.value = '正在提交请求...'

  try {
    const requestData: TripFormData = {
      city: formData.city,
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: formData.end_date.format('YYYY-MM-DD'),
      travel_days: formData.travel_days,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: formData.preferences,
      free_text_input: formData.free_text_input
    }

    // 受理即回（202 + run_id），不再长等待
    const acceptance = await generateTripPlan(requestData)
    const acceptedRunId = acceptance.run_id
    activeRunId = acceptedRunId

    // 订阅 SSE 真实进度事件流；run_completed 后由 handleRunCompleted 关闭
    unsubscribeRun = subscribeRunEvents(acceptedRunId, handleRunEvent, () => {
      // 排队的 error 回调只影响其所属 run：旧订阅不得覆盖新 run 的连接状态
      if (loading.value && activeRunId === acceptedRunId) {
        loadingStatus.value = '进度连接中断，正在重连...'
      }
    })
  } catch (error: unknown) {
    unsubscribeRun?.()
    unsubscribeRun = null
    activeRunId = null
    loading.value = false
    message.error(error instanceof Error ? error.message : '受理旅行计划失败,请稍后重试')
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 60px 20px;
  position: relative;
  overflow: hidden;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: hidden;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 20s infinite ease-in-out;
}

.circle-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.circle-2 {
  width: 200px;
  height: 200px;
  top: 50%;
  right: -50px;
  animation-delay: 5s;
}

.circle-3 {
  width: 150px;
  height: 150px;
  bottom: -50px;
  left: 30%;
  animation-delay: 10s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-30px) rotate(180deg);
  }
}

/* 页面标题 */
.page-header {
  text-align: center;
  margin-bottom: 50px;
  animation: fadeInDown 0.8s ease-out;
  position: relative;
  z-index: 1;
}

.icon-wrapper {
  margin-bottom: 20px;
}

.icon {
  font-size: 80px;
  display: inline-block;
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

.page-title {
  font-size: 56px;
  font-weight: 800;
  color: #ffffff;
  margin-bottom: 16px;
  text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
  letter-spacing: 2px;
}

.page-subtitle {
  font-size: 20px;
  color: rgba(255, 255, 255, 0.95);
  margin: 0;
  font-weight: 300;
}

/* 表单卡片 */
.form-card {
  max-width: 1400px;
  margin: 0 auto;
  border-radius: 24px;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.4);
  animation: fadeInUp 0.8s ease-out;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.98) !important;
}

/* 表单分区 */
.form-section {
  margin-bottom: 32px;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 16px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
}

.form-section:hover {
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
  transform: translateY(-2px);
}

.section-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #667eea;
}

.section-icon {
  font-size: 24px;
  margin-right: 12px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

/* 表单标签 */
.form-label {
  font-size: 15px;
  font-weight: 500;
  color: #555;
}

/* 自定义输入框 */
.custom-input :deep(.ant-input),
.custom-input :deep(.ant-picker) {
  border-radius: 12px;
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.custom-input :deep(.ant-input:hover),
.custom-input :deep(.ant-picker:hover) {
  border-color: #667eea;
}

.custom-input :deep(.ant-input:focus),
.custom-input :deep(.ant-picker-focused) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 自定义选择框 */
.custom-select :deep(.ant-select-selector) {
  border-radius: 12px !important;
  border: 2px solid #e8e8e8 !important;
  transition: all 0.3s ease;
}

.custom-select:hover :deep(.ant-select-selector) {
  border-color: #667eea !important;
}

.custom-select :deep(.ant-select-focused .ant-select-selector) {
  border-color: #667eea !important;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

/* 天数显示 - 紧凑版 */
.days-display-compact {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.days-display-compact .days-value {
  font-size: 24px;
  font-weight: 700;
  margin-right: 4px;
}

.days-display-compact .days-unit {
  font-size: 14px;
}

/* 偏好标签 */
.preference-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.custom-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.preference-tag :deep(.ant-checkbox-wrapper) {
  margin: 0 !important;
  padding: 8px 16px;
  border: 2px solid #e8e8e8;
  border-radius: 20px;
  transition: all 0.3s ease;
  background: white;
  font-size: 14px;
}

.preference-tag :deep(.ant-checkbox-wrapper:hover) {
  border-color: #667eea;
  background: #f5f7ff;
}

.preference-tag :deep(.ant-checkbox-wrapper-checked) {
  border-color: #667eea;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 自定义文本域 */
.custom-textarea :deep(.ant-input) {
  border-radius: 12px;
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.custom-textarea :deep(.ant-input:hover) {
  border-color: #667eea;
}

.custom-textarea :deep(.ant-input:focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 提交按钮 */
.submit-button {
  height: 56px;
  border-radius: 28px;
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.submit-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.5);
}

.submit-button:active {
  transform: translateY(0);
}

.button-icon {
  margin-right: 8px;
  font-size: 20px;
}

/* 加载容器 */
.loading-container {
  text-align: center;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 16px;
  border: 2px dashed #667eea;
}

.loading-status {
  margin-top: 16px;
  color: #667eea;
  font-size: 18px;
  font-weight: 500;
}

/* 动画 */
@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

