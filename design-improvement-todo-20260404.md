# TODO List: 根据cpt竞对分析调研结果优化社区网站

> 来源：`/root/competitor-analysis/reports/` 四份调研报告
> 生成时间：2026-04-04

---

## 一、板块导航结构优化

### 需要做：

- [ ] 将「情绪交流/心情驿站」放在导航更显眼的位置 → **用户一半需求是心理支持**
- [ ] 治疗经验板块按治疗方式拆分二级导航：
  - [ ] 口服外用药物
  - [ ] 光疗（308/UVB）
  - [ ] 手术移植
  - [ ] 中医中药
- [ ] 增加「医院/医生点评」板块，按城市分类 → 用户非常需要
- [ ] 保持「新手提问/新人报到」在顶部

**文件参考：** `/root/competitor-analysis/reports/bailing-wang-bbs-analysis.md`

---

## 二、AI问答界面优化

### 需要做：

- [ ] 确认「首页默认就是对话窗口」→ 我们已经做了，保持✅
- [ ] 确保对话气泡样式正确：
  - [ ] 用户消息 → 右对齐，蓝色气泡
  - [ ] AI回答 → 左对齐，白色/灰色气泡
  - [ ] 完整支持 markdown 渲染（标题、列表、表格）
- [ ] 确保输入框交互正确：
  - [ ] ✅ 自动增高
  - [ ] ✅ Enter 发送，Shift+Enter 换行 → 必须遵循用户习惯
  - [ ] 支持粘贴图片
- [ ] 空对话状态（还没发消息）增加**推荐问题标签**，点击直接提问，推荐问题包括：
  - 白癜风会传染吗？
  - 白癜风能根治吗？
  - 日常生活需要注意什么？
  - 308激光治疗疼吗？
  - 中医调理有用吗？
  - 白癜风会遗传吗？

**文件参考：** `/root/competitor-analysis/reports/llm-c端-ui-analysis.md`

---

## 三、内容策略优化

### 需要做：

内容优先级排序，确保百科全书覆盖：

- [ ] **高优先级 ✅** 覆盖最常见用户问题：
  - [ ] 白癜风会传染吗？
  - [ ] 白癜风能根治吗？
  - 白癜风会遗传吗？
  - [ ] 白癜风可以怀孕吗？
  - [ ] 吃什么需要忌口？
  - [ ] 白癜风怎么治疗省钱？
- [ ] **高优先级 ✅** 按治疗方式整理用户经验：
  - [ ] 308准分子激光经验
  - [ ] 他克莫司/卡泊三醇使用经验
  - [ ] 表皮移植手术经验
  - [ ] 中医调理经验
- [ ] **高优先级 ✅** 重视心理支持内容：
  - [ ] 得了白癜风怎么调整心态
  - [ ] 给新人的建议
- [ ] 内容写作原则：
  - [ ] ✅ 客观诚实 → 不说"包根治"，承认"目前无法根治但可以控制"
  - [ ] ✅ 鼓励为主 → 用户需要心理支持
  - [ ] ✅ 结论放最前面 → 用户没时间看长文
  - [ ] ✅ 有图有真相 → 支持对比配图

### 渠道策略：

- [ ] 网站做好核心功能（AI问答+百科）
- [ ] 未来引流可以从抖音/小红书发科普内容
- [ ] 如果做小程序包装方便移动端用户访问

**文件参考：**
- `/root/competitor-analysis/reports/ai-skin-communication-channels.md`
- `/root/competitor-analysis/reports/social-media-vitiligo-analysis.md`

---

## 四、社交媒体内容方向参考

如果未来做内容引流，遵循：

- [ ] **小红书**：发用户经验图文笔记 → 带对比图
- [ ] **抖音**：发医生一分钟科普短视频
- [ ] **今日头条**：发深度分析文章

---

## 文件位置

本TODO List：`/root/subskin/design-improvement-todo-20260404.md`

调研报告源文件：
- `/root/competitor-analysis/reports/bailing-wang-bbs-analysis.md`
- `/root/competitor-analysis/reports/llm-c端-ui-analysis.md`
- `/root/competitor-analysis/reports/ai-skin-communication-channels.md`
- `/root/competitor-analysis/reports/social-media-vitiligo-analysis.md`
