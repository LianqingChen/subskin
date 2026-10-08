# Findings

主导航从site-modules派生；页面名另有page-names JSON与TS映射；App/海报/微信/PWA/条款品牌介绍存在旧名称。后端site模块和统计映射均导入时缓存，修改shared源码不会主动刷新当前服务；需重启同步。导航埋点ID随label变化，新增记录ID必须保留手帐ID历史兼容。旧名称只保留为搜索别名/禁止展示旧名清单。
