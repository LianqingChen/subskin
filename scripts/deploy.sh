#!/bin/bash
#
# SubSkin 阿里云ECS全自动部署脚本
# Usage: ./scripts/deploy.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=========================================${NC}"
echo -e "${YELLOW}  SubSkin 部署到阿里云 ECS${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 未找到，请先安装 Python 3.9+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 检测通过${NC}"

# 获取项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "📁 项目目录: $PROJECT_DIR"

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo -e "🏗️  创建虚拟环境..."
    python3 -m venv .venv
else
    echo -e "${GREEN}✅ 虚拟环境已存在${NC}"
fi

# 激活虚拟环境
source .venv/bin/activate

# 升级pip
echo -e "🔝  升级 pip..."
pip install --upgrade pip

# 安装依赖
echo -e "📦  安装依赖..."
pip install -r requirements/dev.txt

# 检查.env文件是否存在
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env 文件不存在，从模板创建...${NC}"
    cp configs/.env.example .env
    echo -e "${YELLOW}⚠️  请现在编辑 .env 文件填入你的 API Key 和 QQ 配置${NC}"
    echo -e "${YELLOW}   vim .env${NC}"
    read -p "按回车继续..." -n 1 -r
fi

# 创建日志目录
echo -e "📝  创建日志目录..."
mkdir -p logs

# 创建数据目录
echo -e "🗄️  创建数据目录..."
mkdir -p data/raw data/processed data/exports data/weekly

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN} 🏁 依赖安装完成!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# 运行测试
echo -e "🧪 运行测试验证安装..."
python -m pytest tests/ -v --tb=short -q
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过!${NC}"
else
    echo -e "${YELLOW}⚠️  部分测试可能失败，请检查上面的输出${NC}"
fi

echo ""
echo -e "${YELLOW}=========================================${NC}"
echo -e "${YELLOW}  配置定时任务 (cron)${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""

# 显示当前crontab
echo -e "当前crontab内容:"
echo "----------------------------------------"
crontab -l
echo "----------------------------------------"
echo ""

# 生成cron条目
FULL_PATH=$(pwd)
CRON_ENTRY="0 9 * * * cd $FULL_PATH && source .venv/bin/activate && python -m src.cli update >> logs/cron-\$(date +\\%Y\\%m\\%d).log 2>&1"

echo -e "${YELLOW}要添加的定时任务:${NC}"
echo "  $CRON_ENTRY"
echo ""
echo -e "是否添加到crontab? [y/N]"
read -r add_cron

if [ "$add_cron" = "y" ] || [ "$add_cron" = "Y" ]; then
    # 添加到crontab
    (crontab -l ; echo "$CRON_ENTRY") | crontab -
    echo -e "${GREEN}✅ 定时任务已添加! 每天早上 9:00 自动运行${NC}"
else
    echo -e "${YELLOW}⚠️  跳过crontab配置，请手动添加${NC}"
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN} 🎉 部署完成!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "下一步:"
echo "  1. 确认编辑了 .env 文件，填入了正确的 API Key"
echo "  2. 确认 openclaw QQ机器人已经在服务器上运行并监听正确端口"
echo "  3. 手动测试运行: source .venv/bin/activate && python -m src.cli update"
echo "  4. 检查是否能收到 QQ 通知"
echo ""
echo "常用命令:"
echo "  - 查看状态: python -m src.cli status"
echo "  - 手动爬取 PubMed: python -m src.cli crawl-pubmed --query vitiligo --output data/raw/pubmed.json --limit 100"
echo "  - 查看日志: tail -f logs/cron-$(date +%Y%m%d).log"
echo ""
