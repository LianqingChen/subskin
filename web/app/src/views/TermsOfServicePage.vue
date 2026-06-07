<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const sections = [
  { id: 'acceptance', title: '接受条款' },
  { id: 'account', title: '账户注册' },
  { id: 'services', title: '服务说明' },
  { id: 'content', title: '内容规范' },
  { id: 'community-rules', title: '社区行为规范' },
  { id: 'privacy-data', title: '隐私与数据' },
  { id: 'sharing', title: '信息分享授权' },
  { id: 'ip', title: '知识产权' },
  { id: 'disclaimer', title: '免责声明' },
  { id: 'termination', title: '服务终止' },
  { id: 'dispute', title: '争议解决' },
  { id: 'changes', title: '条款变更' },
  { id: 'contact', title: '联系我们' },
]

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA]">
    <!-- Header -->
    <div class="sticky top-0 z-10 bg-[#F5F7FA]/80  backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
        <button
          class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600"
          @click="router.back()"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 class="text-lg font-semibold text-gray-900">服务条款</h1>
      </div>
    </div>

    <div class="max-w-6xl mx-auto px-4 py-6 flex gap-6">
      <!-- Sidebar TOC (desktop) -->
      <nav class="hidden lg:block w-48 shrink-0">
        <div class="sticky top-20 space-y-1">
          <p class="text-xs font-medium text-gray-400  uppercase tracking-wider mb-2">目录</p>
          <button
            v-for="s in sections"
            :key="s.id"
            class="block w-full text-left text-sm px-3 py-1.5 rounded-md text-gray-600  hover:text-primary-600 dark:hover:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition"
            @click="scrollTo(s.id)"
          >
            {{ s.title }}
          </button>
        </div>
      </nav>

      <!-- Content -->
      <article class="flex-1 min-w-0 prose prose-sm dark:prose-invert max-w-none">
          <p class="text-sm text-gray-500 ">最近更新日期：2026年4月25日 &nbsp;|&nbsp; 生效日期：2026年4月25日</p>

        <div id="acceptance" class="pt-4">
          <h2>一、接受条款</h2>
          <p>欢迎使用 SubSkin（以下简称"本平台"）。在注册、登录或使用本平台服务之前，请您仔细阅读并充分理解本服务条款（以下简称"本条款"）。</p>
          <p><strong>您一旦注册、登录或使用本平台服务，即视为您已阅读并同意受本条款约束。</strong>如果您不同意本条款的任何内容，请立即停止使用本平台服务。</p>
          <p>本条款由 SubSkin 运营团队（以下简称"我们"）与注册用户（以下简称"您"）之间签订。</p>
        </div>

        <div id="account" class="pt-4">
          <h2>二、账户注册</h2>
          <h3>2.1 注册资格</h3>
          <p>您确认您具备完全民事行为能力。如果您是未满14周岁的未成年人，请在监护人的陪同和同意下使用本平台。</p>

          <h3>2.2 账户信息</h3>
          <ul>
            <li>您应提供真实、准确、完整的注册信息</li>
            <li>您应及时更新因时间推移导致变化的注册信息</li>
            <li>您对账户安全负全部责任，不得将账户转让或出借给他人</li>
            <li>如发现账户被非法使用，请立即通知我们</li>
          </ul>

          <h3>2.3 注册方式</h3>
          <p>本平台支持以下注册方式：</p>
          <ul>
            <li>手机号码 + 短信验证码</li>
            <li>电子邮箱 + 邮箱验证码</li>
            <li>第三方账号授权登录（微信、支付宝）</li>
          </ul>

          <h3>2.4 账户安全</h3>
          <p>您应妥善保管账户凭证，因您的原因导致账户被盗用，我们不承担任何责任。我们采取以下措施保护您的账户安全：</p>
          <ul>
            <li>密码使用 bcrypt 加密存储，不以明文形式保存</li>
            <li>登录使用 JWT Token 机制，访问令牌30分钟自动过期</li>
            <li>所有通信强制使用 HTTPS/TLS 加密</li>
          </ul>
        </div>

        <div id="services" class="pt-4">
          <h2>三、服务说明</h2>
          <h3>3.1 服务内容</h3>
          <p>SubSkin 是一个面向白癜风白友及家属的知识社区平台，提供以下核心服务：</p>
          <ul>
            <li><strong>AI助手</strong>：基于 AI 的智能问答服务</li>
            <li><strong>手账</strong>：VASI评估及病情记录</li>
            <li><strong>发现</strong>：白友交流与经验分享社区</li>
          </ul>

          <h3>3.2 服务性质</h3>
          <div class="not-prose my-4 p-4 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
            <p class="text-sm font-semibold text-amber-800 dark:text-amber-300"><i class="ri-error-warning-line mr-1"></i>重要声明</p>
            <p class="text-sm text-amber-700 dark:text-amber-400 mt-1">本平台提供的所有内容仅供参考和知识分享，<strong>不构成任何医疗建议、诊断或治疗方案</strong>。所有健康问题请务必咨询执业医师。</p>
          </div>

          <h3>3.3 服务变更</h3>
          <p>我们保留随时修改、暂停或终止部分或全部服务的权利。重大变更将提前通知用户。</p>
        </div>

        <div id="content" class="pt-4">
          <h2>四、内容规范</h2>
          <h3>4.1 您的内容</h3>
          <p>您在社区发布的帖子、评论等内容（以下简称"用户内容"），您保留原始著作权。</p>
          <p>通过在本平台发布内容，您授予我们以下非独家许可：</p>
          <ul>
            <li>在平台内展示、传播您的用户内容</li>
            <li>为改善服务对用户内容进行必要的格式调整</li>
            <li>为保护平台安全对违反规则的内容进行处理</li>
          </ul>

          <h3>4.2 内容审核</h3>
          <p>我们有权但不负有义务对用户内容进行审核。以下内容严禁发布：</p>
          <ul>
            <li>违反法律法规的内容</li>
            <li>虚假或误导性的医疗信息</li>
            <li>未经授权的他人隐私信息</li>
            <li>广告、垃圾信息或恶意代码</li>
            <li>歧视、仇恨或人身攻击的内容</li>
            <li>任何违反公序良俗的内容</li>
          </ul>

          <h3>4.3 医疗内容免责</h3>
          <p>用户在社区分享的病情经验、治疗心得等属于个人经验，不代表平台立场。我们不对用户内容的医学准确性和有效性做任何保证。</p>
        </div>

        <div id="community-rules" class="pt-4">
          <h2>五、社区行为规范</h2>

          <h3>5.1 风险内容风控</h3>
          <p>为维护社区健康环境，我们采用AI+人工双重审核机制，对所有用户内容（包括帖子、评论、昵称、头像等）进行实时风险检测。以下类别的内容将被自动识别并处理：</p>
          <div class="not-prose space-y-2 my-4">
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">严重</span>
              <span class="text-gray-700">涉政、暴恐、色情、赌博、诈骗、毒品、枪支</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300">高危</span>
              <span class="text-gray-700">自残教唆、辱骂歧视、人身攻击</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300">中危</span>
              <span class="text-gray-700">引流广告、违反公序良俗</span>
            </div>
          </div>

          <h3>5.2 自动处理机制</h3>
          <p>当AI检测到风险内容时，系统将根据风险等级自动采取以下措施：</p>
          <ul>
            <li><strong>严重风险</strong>：立即屏蔽内容，自动封禁账号</li>
            <li><strong>高危风险</strong>：立即屏蔽内容，自动禁言7天；累计2次禁言30天</li>
            <li><strong>中危风险</strong>：标记内容待人工审核，首次警告；累计3次禁言7天</li>
            <li><strong>低危风险</strong>：标记内容待人工审核</li>
          </ul>

          <h3>5.3 人工审核</h3>
          <p>所有被AI标记的内容将进入管理员审核队列，管理员可做出以下决定：</p>
          <ul>
            <li><strong>通过</strong>：恢复内容正常展示，通知用户审核通过</li>
            <li><strong>拒绝</strong>：维持内容屏蔽，可附加禁言或封号处罚，通知用户违规原因</li>
            <li><strong>升级</strong>：提交更高级别审核</li>
          </ul>

          <h3>5.4 用户处罚</h3>
          <p>对于违规用户，我们采取分级处罚措施：</p>
          <div class="not-prose my-4 overflow-x-auto">
            <table class="w-full text-sm border-collapse">
              <thead>
                <tr class="border-b border-gray-200 dark:border-gray-700">
                  <th class="text-left py-2 pr-4 font-medium">处罚类型</th>
                  <th class="text-left py-2 font-medium">适用条件</th>
                  <th class="text-left py-2 font-medium">措施</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                <tr><td class="py-2 pr-4">警告</td><td class="py-2">首次中危违规</td><td class="py-2">站内通知提醒</td></tr>
                <tr><td class="py-2 pr-4">禁言</td><td class="py-2">多次违规</td><td class="py-2">限制发言3天/7天/30天</td></tr>
                <tr><td class="py-2 pr-4">封号</td><td class="py-2">严重或屡次违规</td><td class="py-2">永久禁止登录和使用</td></tr>
              </tbody>
            </table>
          </div>

          <h3>5.5 通知机制</h3>
          <p>当您的内容被确认违规时，我们将通过以下方式通知您：</p>
          <ul>
            <li>站内通知：在App内推送违规处理通知</li>
            <li>短信通知：对确认违规的内容，发送短信提醒（如预留手机号）</li>
          </ul>

          <h3>5.6 申诉</h3>
          <p>如您对审核结果有异议，可通过站内通知中的联系方式向我们申诉。我们将在3个工作日内处理您的申诉。</p>
        </div>

        <div id="privacy-data" class="pt-4">
          <h2>六、隐私与数据保护</h2>
          <p>我们高度重视您的个人信息保护。详细信息请参阅我们的 <router-link to="/privacy" class="text-primary-600 dark:text-primary-400 hover:underline font-medium">隐私政策</router-link>。</p>
          <p>以下为本条款中的隐私要点：</p>

          <h3>5.1 数据分级</h3>
          <p>我们实行四级数据分类管理：</p>
          <div class="not-prose space-y-2 my-4">
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-500 text-white">🔴 L4</span>
              <span class="text-gray-700">密码、Token — 绝不在任何场合暴露</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-orange-500 text-white">🟠 L3</span>
              <span class="text-gray-700">手机号、邮箱、病情图片 — 严格脱敏、仅本人可见</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-yellow-500 text-white">🟡 L2</span>
              <span class="text-gray-700">昵称、公开内容 — 用户自主控制公开范围</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-green-500 text-white">🟢 L1</span>
              <span class="text-gray-700">百科内容、匿名统计 — 公开可见</span>
            </div>
          </div>

          <h3>5.2 安全承诺</h3>
          <ul>
            <li>全站 HTTPS 加密，所有 API 强制 TLS</li>
            <li>密码 bcrypt 加密存储，永不明文保存</li>
            <li>敏感数据最小化收集，仅保留功能必需信息</li>
            <li>严格的访问控制，用户 A 无法访问用户 B 的 L3 数据</li>
          </ul>
        </div>

        <div id="sharing" class="pt-4">
          <h2>七、信息分享授权</h2>
          <p>我们不会主动将您的个人信息分享给任何第三方。当您选择分享时：</p>

          <h3>6.1 您的分享权</h3>
          <p>您可以在平台内以下场景主动分享信息：</p>
          <ul>
            <li>社区帖子：发布经验、心得、问答</li>
            <li>评估结果：分享脱敏后的病情评估摘要</li>
            <li>收藏公开：将收藏夹设为公开可见</li>
          </ul>

          <h3>6.2 审计追踪</h3>
          <p><strong>所有用户授权的分享、公开操作均会记录不可篡改的审计日志</strong>，包含：</p>
          <div class="not-prose my-4 overflow-x-auto">
            <table class="w-full text-sm border-collapse">
              <thead>
                <tr class="border-b border-gray-200 dark:border-gray-700">
                  <th class="text-left py-2 pr-4 font-medium">字段</th>
                  <th class="text-left py-2 font-medium">说明</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                <tr><td class="py-2 pr-4">who</td><td class="py-2">操作人</td></tr>
                <tr><td class="py-2 pr-4">what</td><td class="py-2">操作对象及类型</td></tr>
                <tr><td class="py-2 pr-4">when</td><td class="py-2">操作时间戳</td></tr>
                <tr><td class="py-2 pr-4">scope</td><td class="py-2">分享范围（公开/仅粉丝/指定用户）</td></tr>
                <tr><td class="py-2 pr-4">revokeable</td><td class="py-2">是否可撤销</td></tr>
              </tbody>
            </table>
          </div>
          <p>审计日志<strong>不可修改、不可删除</strong>，确保用户授权行为可追溯。</p>
        </div>

        <div id="ip" class="pt-4">
          <h2>八、知识产权</h2>
          <h3>7.1 平台内容</h3>
          <p>本平台的百科内容、AI模型、界面设计、商标等知识产权归我们所有或经合法授权使用。</p>

          <h3>7.2 用户内容</h3>
          <p>用户保留其原创内容的著作权。发布内容即授予我们非独家、不可撤销的许可，允许我们在平台内展示和传播该内容。</p>

          <h3>7.3 开源许可</h3>
          <p>SubSkin 的源代码遵循 MIT 许可证开源。社区贡献内容遵循 CC BY-NC-SA 4.0 协议。</p>
        </div>

        <div id="disclaimer" class="pt-4">
          <h2>九、免责声明</h2>

          <div class="not-prose my-4 p-4 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800">
            <p class="text-sm font-semibold text-red-800 dark:text-red-300"><i class="ri-error-warning-line mr-1"></i>医疗免责声明</p>
            <p class="text-sm text-red-700 dark:text-red-400 mt-1">SubSkin 提供的所有内容（包括但不限于百科文章、AI问答结果、病情评估数据）均<strong>不构成医疗建议、诊断或治疗方案</strong>。所有健康问题请务必咨询执业医师，并遵医嘱执行。</p>
          </div>

          <ul>
            <li><strong>AI 问答</strong>：AI 生成的回答基于公开论文和知识库，可能存在过时或错误信息，不作为医疗诊断依据</li>
            <li><strong>病情评估</strong>：VASI 评分仅供参考，实际诊断需由专业皮肤科医生进行</li>
            <li><strong>社区内容</strong>：用户分享的个人经验不代表平台观点和立场</li>
            <li><strong>服务可用性</strong>：我们尽力保证服务稳定，但不对因不可抗力导致的服务中断承担责任</li>
            <li><strong>第三方链接</strong>：本平台可能包含指向第三方网站的链接，我们不对这些网站内容负责</li>
          </ul>
        </div>

        <div id="termination" class="pt-4">
          <h2>十、服务终止</h2>
          <h3>9.1 用户主动注销</h3>
          <p>您有权随时注销您的账户。注销后：</p>
          <ul>
            <li>L4 数据（密码、Token）：即时删除</li>
            <li>L3 数据（手机号、邮箱、图片等）：30天内彻底删除</li>
            <li>L2 数据（昵称、内容等）：30天内删除或根据您的选择匿名化</li>
            <li>L1 数据（匿名统计数据）：保留，不再关联任何个人身份</li>
          </ul>

          <h3>10.2 我们的权利</h3>
          <p>在以下情况下，我们有权暂停或终止您的服务：</p>
          <ul>
            <li>违反本服务条款或社区行为规范</li>
            <li>发布违法或有害内容</li>
            <li>恶意攻击平台或侵害他人权益</li>
            <li>长期未登录（超过12个月，会提前30天通知）</li>
          </ul>
        </div>

        <div id="dispute" class="pt-4">
          <h2>十一、争议解决</h2>
          <p>本条款适用中华人民共和国法律。如发生争议：</p>
          <ol>
            <li>优先通过友好协商解决</li>
            <li>协商不成时，任何一方可向我们所在地有管辖权的人民法院提起诉讼</li>
          </ol>
        </div>

        <div id="changes" class="pt-4">
          <h2>十二、条款变更</h2>
          <p>我们可能会不时修订本服务条款。修订后，我们将：</p>
          <ol>
            <li>在本页面发布修订后的条款</li>
            <li>对重大变更通过站内通知或邮件告知您</li>
            <li>如您在修订后继续使用服务，视为接受修订后的条款</li>
            <li>如您不同意修订后的条款，有权选择注销账户</li>
          </ol>
        </div>

        <div id="contact" class="pt-4">
          <h2>十三、联系我们</h2>
          <p>如您对本服务条款有任何疑问或建议，请通过以下方式联系我们：</p>
          <ul>
            <li>邮箱地址：<a href="mailto:lianqing_chan@126.com" class="text-primary-600 dark:text-primary-400 hover:underline">lianqing_chan@126.com</a></li>
            <li>GitHub：<a href="https://github.com/LianqingChen/subskin" target="_blank" rel="noopener noreferrer" class="text-primary-600 dark:text-primary-400 hover:underline">LianqingChen/subskin</a></li>
          </ul>
        </div>

        <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-400  text-center">
          <p>版本 v1.1 &nbsp;|&nbsp; 生效日期：2026年4月25日 &nbsp;|&nbsp; SubSkin 服务条款</p>
        </div>
      </article>
    </div>

    <!-- Mobile TOC (bottom bar) -->
    <div class="lg:hidden fixed bottom-0 left-0 right-0 bg-[#F5F7FA]/90  backdrop-blur-md border-t border-gray-200 dark:border-gray-700 px-4 py-2 z-20 safe-bottom">
      <div class="flex overflow-x-auto gap-2 scrollbar-hide">
        <button
          v-for="s in sections"
          :key="s.id"
          class="shrink-0 text-xs px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-primary-100 dark:hover:bg-primary-900 hover:text-primary-600 dark:hover:text-primary-400 transition"
          @click="scrollTo(s.id)"
        >
          {{ s.title }}
        </button>
      </div>
    </div>
  </div>
</template>
