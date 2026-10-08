/**
 * 数据贡献的同意文案。版本号必须与后端 services/data_consent.py 的 CURRENT_TEXT_VERSION 一致：
 * 改任何一句话都要同时升级两处版本，后端会拒绝旧版本（409 STALE_TEXT），保证用户同意的就是看到的文案。
 *
 * 文案原则：只承诺现在能做到的；不写具体清理天数；不暗示有已上线但实际没有的审核环节。
 */
export const CONTRIBUTION_TEXT_VERSION = '2026-10-v1'

/** 目前只开放“帮助改进白斑识别”；公开、研究、医生查看等用途在对应功能上线前不向用户展示。 */
export const OPEN_PURPOSES = ['model_training'] as const

export const TRAINING_TEXT = {
  title: '帮助改进白斑识别',
  summary: '你的照片和你核对的范围，会经人工复核后，用于训练和评测白斑识别功能。',
  details: [
    '不会公开展示，不会出售你的联系方式。',
    '照片中可能含有能认出你的特征（如面部）。只有获授权的工作人员能在后台查看。',
    '这是一项长期授权：我们会在你撤回之前使用。你随时可以撤回，且不影响你使用任何功能。',
  ],
  scopeFuture: '只包含今后的记录',
  scopeAll: '同时包含已有的历史记录',
  withdrawNote:
    '撤回后，你的资料不会再用于新的训练和导出，并会进入清理流程。已经训练完成的模型无法完全“遗忘”，我们会记录受影响的版本，必要时重新训练。你的个人记录和对比不受影响。',
} as const

export const INVITE = {
  title: '想帮更多白友吗？',
  lead: '你已经记录并对比过变化。如果愿意，可以让你的照片帮助改进白斑识别。这完全自愿，不选也能继续使用全部功能。',
  agree: '同意',
  later: '先不用',
  footnote: '可随时在「我的 → 数据与贡献」查看和撤回。',
  /** 拒绝后的冷却天数 */
  cooldownDays: 30,
} as const
