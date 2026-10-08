# 首页问答流式中断修复（完成）
根因：answer_question_stream读取空chunk.choices[0]产生IndexError，导致SSE中断。
修复：跳过统计/无正文片段，空回答友好处理，关闭上游连接。
验证：5项新增SDK流式回归通过；共享后端已部署；真实问答HTTP200，8个token事件与done完整返回，5.7秒，正式/测试健康检查正常。
既有旧RAG测试两项失败记录在progress.md，相关业务函数本次未变更。
