<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const sections = [
  { id: 'overview', title: '概述' },
  { id: 'collection', title: '信息收集' },
  { id: 'classification', title: '数据分级' },
  { id: 'usage', title: '信息使用' },
  { id: 'storage', title: '存储与保护' },
  { id: 'sharing', title: '信息共享' },
  { id: 'rights', title: '用户权利' },
  { id: 'cookies', title: 'Cookie 政策' },
  { id: 'children', title: '未成年人保护' },
  { id: 'changes', title: '政策变更' },
  { id: 'contact', title: '联系我们' },
]

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA] ">
    <!-- Header -->
    <div class="sticky top-0 z-10 bg-[#F5F7FA]/80  backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
        <button
          class="p-2 -ml-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 "
          @click="router.back()"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 class="text-lg font-semibold text-gray-900 ">隐私政策</h1>
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
        <p class="text-sm text-gray-500 ">最近更新日期：2026年4月18日 &nbsp;|&nbsp; 生效日期：2026年4月18日</p>

        <div id="overview" class="pt-4">
          <h2>概述</h2>
          <p>SubSkin（以下简称"我们"）深知个人隐私的重要性。本隐私政策旨在帮助您了解我们收集哪些信息、为什么收集这些信息，以及您如何更新、管理和导出您的个人信息。</p>
          <p>我们承诺：您个人信息的隐私和安全是我们的<strong>第一优先级</strong>。违反本政策的任何行为在我们团队内部都是零容忍的。</p>
          <p>使用 SubSkin 服务即表示您同意本隐私政策。如果您不同意本政策，请停止使用我们的服务。</p>
        </div>

        <div id="collection" class="pt-4">
          <h2>信息收集</h2>
          <h3>我们收集的信息</h3>
          <p>我们仅收集为提供核心功能所必需的信息，遵循<strong>最小化数据收集</strong>原则：</p>

          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="text-left py-2 pr-4">信息类型</th>
                <th class="text-left py-2 pr-4">示例</th>
                <th class="text-left py-2">用途</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr>
                <td class="py-2 pr-4 font-medium">注册信息</td>
                <td class="py-2 pr-4">手机号、邮箱、用户名</td>
                <td class="py-2">账户创建与登录验证</td>
              </tr>
              <tr>
                <td class="py-2 pr-4 font-medium">健康数据</td>
                <td class="py-2 pr-4">白斑照片、评估部位、VASI评分</td>
                <td class="py-2">VASI测评</td>
              </tr>
              <tr>
                <td class="py-2 pr-4 font-medium">社区内容</td>
                <td class="py-2 pr-4">帖子、评论、收藏</td>
                <td class="py-2">社区交流</td>
              </tr>
              <tr>
                <td class="py-2 pr-4 font-medium">设备信息</td>
                <td class="py-2 pr-4">浏览器类型、屏幕尺寸</td>
                <td class="py-2">体验优化</td>
              </tr>
            </tbody>
          </table>

          <h3>我们不会收集的信息</h3>
          <ul>
            <li>身份证号</li>
            <li>银行卡号</li>
            <li>家庭住址</li>
            <li>紧急联系人信息</li>
            <li>任何与核心功能无关的个人信息</li>
          </ul>
        </div>

        <div id="classification" class="pt-4">
          <h2>数据分级</h2>
          <p>我们对所有用户数据实行四级分类管理，确保不同敏感级别的信息获得对应等级的保护：</p>

          <div class="not-prose space-y-3 my-4">
            <!-- L4 -->
            <div class="rounded-lg border-2 border-red-500/30 bg-red-50 dark:bg-red-950/30 p-4">
              <div class="flex items-center gap-2 mb-1">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-500 text-white">🔴 L4 极高</span>
                <span class="font-semibold text-red-700 dark:text-red-400">绝密级</span>
              </div>
              <p class="text-sm text-red-800 dark:text-red-300">密码（bcrypt 哈希存储）、JWT Token、银行卡号</p>
              <p class="text-xs text-red-600 dark:text-red-400 mt-1">⚡ 任何情况下不得出现在 API 响应、日志、前端代码、公开页面或 Git 仓库中</p>
            </div>

            <!-- L3 -->
            <div class="rounded-lg border-2 border-orange-500/30 bg-orange-50 dark:bg-orange-950/30 p-4">
              <div class="flex items-center gap-2 mb-1">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-orange-500 text-white">🟠 L3 高</span>
                <span class="font-semibold text-orange-700 dark:text-orange-400">机密级</span>
              </div>
              <p class="text-sm text-orange-800 dark:text-orange-300">手机号、邮箱、病情图片、个人照片、音频、视频、体检报告、真实姓名、家庭住址</p>
              <p class="text-xs text-orange-600 dark:text-orange-400 mt-1"><i class="ri-lock-line mr-1"></i>API 返回时脱敏（手机号 138****1234、邮箱 li***@example.com），病情图片仅所有者可访问</p>
            </div>

            <!-- L2 -->
            <div class="rounded-lg border-2 border-yellow-500/30 bg-yellow-50 dark:bg-yellow-950/30 p-4">
              <div class="flex items-center gap-2 mb-1">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-yellow-500 text-white">🟡 L2 中</span>
                <span class="font-semibold text-yellow-700 dark:text-yellow-400">内部级</span>
              </div>
              <p class="text-sm text-yellow-800 dark:text-yellow-300">用户昵称、头像、发表内容、收藏、评估历史摘要</p>
              <p class="text-xs text-yellow-600 dark:text-yellow-400 mt-1"><i class="ri-eye-line mr-1"></i>用户自主选择是否公开，社区分享由用户主动授权，所有授权操作留有不可篡改的审计记录</p>
            </div>

            <!-- L1 -->
            <div class="rounded-lg border-2 border-green-500/30 bg-green-50 dark:bg-green-950/30 p-4">
              <div class="flex items-center gap-2 mb-1">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-green-500 text-white">🟢 L1 低</span>
                <span class="font-semibold text-green-700 dark:text-green-400">公开级</span>
              </div>
              <p class="text-sm text-green-800 dark:text-green-300">百科内容、公开帖子、匿名统计数据</p>
              <p class="text-xs text-green-600 dark:text-green-400 mt-1">🌐 可公开访问，但数据采集需注明来源</p>
            </div>
          </div>
        </div>

        <div id="usage" class="pt-4">
          <h2>信息使用</h2>
          <p>我们收集的信息仅用于以下目的：</p>
          <ol>
            <li><strong>提供核心服务</strong>：账户管理、VASI测评、AI问答、社区交流</li>
            <li><strong>改善体验</strong>：产品功能优化、个性化内容推荐</li>
            <li><strong>安全保障</strong>：身份验证、安全防护、欺诈检测</li>
            <li><strong>法律合规</strong>：遵守适用的法律法规要求</li>
          </ol>
          <p>我们<strong>不会</strong>将您的个人信息用于：</p>
          <ul>
            <li>向第三方出售或出租</li>
            <li>与广告商共享用于精准投放广告</li>
            <li>任何与核心功能无关的目的</li>
          </ul>
        </div>

        <div id="storage" class="pt-4">
          <h2>存储与保护</h2>
          <h3>数据存储</h3>
          <ul>
            <li>服务器位于中国大陆，符合数据本地化要求</li>
            <li>所有数据传输使用 TLS/HTTPS 加密</li>
            <li>数据库访问受网络隔离和访问控制保护</li>
          </ul>

          <h3>技术保障</h3>
          <ul>
            <li><strong>密码安全</strong>：使用 bcrypt 算法哈希存储，绝不明文保存</li>
            <li><strong>传输加密</strong>：全站 HTTPS，API 强制 TLS</li>
            <li><strong>Token 机制</strong>：JWT 访问令牌短时效（30分钟），刷新令牌7天有效</li>
            <li><strong>访问控制</strong>：基于角色的权限管理，最小权限原则</li>
            <li><strong>日志脱敏</strong>：生产环境日志自动脱敏手机号、邮箱等敏感字段</li>
          </ul>

          <h3>数据保留</h3>
          <p>在您使用服务期间，我们将保留您的个人信息。当您注销账户后：</p>
          <ul>
            <li>L4（密码、Token）：即时删除</li>
            <li>L3（手机号、邮箱、图片等）：30天内彻底删除</li>
            <li>L2（昵称、内容等）：30天内删除，或根据您的选择匿名化</li>
            <li>L1（匿名统计数据）：予以保留，不再关联任何个人身份</li>
          </ul>
        </div>

        <div id="sharing" class="pt-4">
          <h2>信息共享与公开</h2>
          <h3>我们不会主动共享</h3>
          <p>我们<strong>不会主动</strong>将您的个人信息共享给任何第三方，除非：</p>
          <ol>
            <li>获得您的<strong>明确授权</strong></li>
            <li>法律法规要求</li>
            <li>涉及重大公共利益且符合法律程序</li>
          </ol>

          <h3>用户主动分享</h3>
          <p>您可以通过以下功能主动分享内容：</p>
          <ul>
            <li>在社区发布帖子、评论</li>
            <li>分享评估结果（仅展示脱敏后的摘要数据）</li>
            <li>将个人经验分享至社区</li>
          </ul>
          <p><strong>所有分享操作均会记录不可篡改的审计日志</strong>，包括：</p>
          <ul>
            <li>操作人（谁操作的）</li>
            <li>操作内容（分享了什么）</li>
            <li>操作时间（什么时候操作的）</li>
            <li>分享范围（对谁可见）</li>
            <li>是否可撤销</li>
          </ul>

          <h3>服务提供商</h3>
          <p>我们可能委托以下类型的服务提供商处理数据：</p>
          <ul>
            <li>云存储服务商（用于图片存储）</li>
            <li>短信/邮件服务商（用于验证码发送）</li>
          </ul>
          <p>所有服务提供商均签署严格的数据保护协议，仅可在提供服务所必需的范围内处理数据。</p>
        </div>

        <div id="rights" class="pt-4">
          <h2>您的权利</h2>
          <p>根据相关法律法规，您享有以下权利：</p>

          <div class="not-prose space-y-3 my-4">
            <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 ">
              <span class="text-xl"><i class="ri-search-line"></i></span>
              <div>
                <p class="font-medium text-gray-900 ">查阅权</p>
                <p class="text-sm text-gray-600 ">随时查看您的个人信息和使用记录</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 ">
              <span class="text-xl"><i class="ri-edit-line"></i></span>
              <div>
                <p class="font-medium text-gray-900 ">更正权</p>
                <p class="text-sm text-gray-600 ">更正不准确的信息</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 ">
              <span class="text-xl"><i class="ri-delete-bin-line"></i></span>
              <div>
                <p class="font-medium text-gray-900 ">删除权（被遗忘权）</p>
                <p class="text-sm text-gray-600 ">请求删除您的个人信息，我们将在30天内完成。注销账户后所有个人数据（L2-L4）将被彻底删除</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 ">
              <span class="text-xl">📥</span>
              <div>
                <p class="font-medium text-gray-900 ">数据可携带权</p>
                <p class="text-sm text-gray-600 ">导出您的个人数据（JSON格式）</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 ">
              <span class="text-xl"><i class="ri-forbid-line"></i></span>
              <div>
                <p class="font-medium text-gray-900 ">撤回同意权</p>
                <p class="text-sm text-gray-600 ">随时撤回对信息处理的同意</p>
              </div>
            </div>
          </div>

          <p>行使上述权利，请前往<strong>个人中心 → 隐私设置</strong>，或联系 <a href="mailto:lianqing_chan@126.com" class="text-primary-600 dark:text-primary-400 hover:underline">lianqing_chan@126.com</a>。</p>
        </div>

        <div id="cookies" class="pt-4">
          <h2>Cookie 政策</h2>
          <p>SubSkin 使用以下 Cookie：</p>
          <ul>
            <li><strong>认证 Token</strong>：用于维持登录状态（存储于 localStorage，非 Cookie）</li>
            <li><strong>主题偏好</strong>：记录您的深色/浅色模式选择</li>
            <li><strong>分析统计</strong>：匿名的页面访问统计（不关联个人身份）</li>
          </ul>
          <p>我们不使用第三方跟踪 Cookie 或广告 Cookie。</p>
        </div>

        <div id="children" class="pt-4">
          <h2>未成年人保护</h2>
          <p>SubSkin 高度重视未成年人个人信息保护：</p>
          <ul>
            <li>如果您是未满14周岁的未成年人，请在监护人的陪同下阅读本政策，并在取得监护人同意后使用我们的服务</li>
            <li>我们不会在明知用户为未成年人的情况下，收集超出必要范围的个人信息</li>
            <li>如发现未成年人未经授权使用我们服务的，我们将及时删除相关信息</li>
          </ul>
        </div>

        <div id="changes" class="pt-4">
          <h2>政策变更</h2>
          <p>我们可能会不时更新本隐私政策。更新后，我们将：</p>
          <ol>
            <li>在本页面公布修订后的政策</li>
            <li>对重大变更通过站内通知或邮件方式告知您</li>
            <li>继续使用服务即表示同意修订后的政策</li>
          </ol>
          <p>版本历史将在此页面底部记录。</p>
        </div>

        <div id="contact" class="pt-4">
          <h2>联系我们</h2>
          <p>如果您对本隐私政策有任何疑问、建议或投诉，请通过以下方式联系我们：</p>
          <ul>
            <li>邮箱：<a href="mailto:lianqing_chan@126.com" class="text-primary-600 dark:text-primary-400 hover:underline">lianqing_chan@126.com</a></li>
            <li>GitHub：<a href="https://github.com/LianqingChen/subskin" target="_blank" rel="noopener noreferrer" class="text-primary-600 dark:text-primary-400 hover:underline">LianqingChen/subskin</a></li>
          </ul>
        </div>

        <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-400  text-center">
          <p>版本 v1.0 &nbsp;|&nbsp; 生效日期：2026年4月18日 &nbsp;|&nbsp; SubSkin 隐私政策</p>
        </div>
      </article>
    </div>

    <!-- Mobile TOC (bottom bar) -->
    <div class="lg:hidden fixed bottom-0 left-0 right-0 bg-[#F5F7FA]/90  backdrop-blur-md border-t border-gray-200 dark:border-gray-700 px-4 py-2 z-20 safe-bottom">
      <div class="flex overflow-x-auto gap-2 scrollbar-hide">
        <button
          v-for="s in sections"
          :key="s.id"
          class="shrink-0 text-xs px-3 py-1.5 rounded-full bg-gray-100  text-gray-600  hover:bg-primary-100 dark:hover:bg-primary-900 hover:text-primary-600 dark:hover:text-primary-400 transition"
          @click="scrollTo(s.id)"
        >
          {{ s.title }}
        </button>
      </div>
    </div>
  </div>
</template>
