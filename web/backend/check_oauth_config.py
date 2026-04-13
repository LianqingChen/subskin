#!/usr/bin/env python
"""
OAuth服务配置检查和验证脚本
检查所有必需的环境变量和配置
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_env_var(var_name, required=True):
    """检查环境变量"""
    value = os.getenv(var_name)
    if required and not value:
        print(f"❌ {var_name} - 缺失 (必需)")
        return False
    elif not value:
        print(f"ℹ️  {var_name} - 未配置 (可选)")
        return True
    else:
        # 隐藏敏感信息
        masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
        print(f"✅ {var_name} = {masked}")
        return True


def main():
    print("=" * 60)
    print("SubSkin OAuth服务配置检查")
    print("=" * 60)

    print("\n【必需配置】")
    all_required_ok = True
    all_required_ok &= check_env_var("SECRET_KEY", required=True)

    print("\n【微信开放平台配置】")
    wechat_ok = True
    wechat_ok &= check_env_var("WECHAT_APP_ID")
    wechat_ok &= check_env_var("WECHAT_APP_SECRET")
    wechat_ok &= check_env_var("WECHAT_REDIRECT_URI")

    if not wechat_ok:
        print("\n⚠️ 微信登录功能需要配置以上环境变量")

    print("\n【支付宝开放平台配置】")
    alipay_ok = True
    alipay_ok &= check_env_var("ALIPAY_APP_ID")
    alipay_ok &= check_env_var("ALIPAY_PRIVATE_KEY")
    alipay_ok &= check_env_var("ALIPAY_PUBLIC_KEY")
    alipay_ok &= check_env_var("ALIPAY_REDIRECT_URI")

    if not alipay_ok:
        print("\n⚠️ 支付宝登录功能需要配置以上环境变量")

    print("\n【短信服务配置】")
    sms_provider = os.getenv("SMS_PROVIDER", "log")
    print(f"短信服务商: {sms_provider}")

    if sms_provider == "aliyun":
        print("\n  阿里云配置:")
        check_env_var("SMS_ACCESS_KEY_ID")
        check_env_var("SMS_ACCESS_KEY_SECRET")
        check_env_var("SMS_SIGN_NAME")
        check_env_var("SMS_TEMPLATE_CODE")
    elif sms_provider == "tencent":
        print("\n  腾讯云配置:")
        check_env_var("SMS_ACCESS_KEY_ID")
        check_env_var("SMS_ACCESS_KEY_SECRET")
        check_env_var("SMS_SIGN_NAME")
        check_env_var("TENCENT_SMS_APP_ID")
        check_env_var("TENCENT_SMS_TEMPLATE_ID")
    elif sms_provider == "log":
        print("\n  开发模式: 验证码将打印到日志")
    else:
        print(f"\n  ⚠️ 未知的短信服务商: {sms_provider}")

    print("\n【数据库配置】")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/subskin.db")
    print(f"数据库URL: {database_url}")

    print("\n【JWT配置】")
    algorithm = os.getenv("ALGORITHM", "HS256")
    expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    print(f"JWT算法: {algorithm}")
    print(f"Token有效期: {expire_minutes}分钟")

    print("\n" + "=" * 60)
    print("【总结】")
    print("=" * 60)

    if all_required_ok:
        print("✅ 必需配置完整")
    else:
        print("❌ 请配置必需的环境变量")

    if wechat_ok:
        print("✅ 微信登录功能可用")
    else:
        print("ℹ️  微信登录功能待配置")

    if alipay_ok:
        print("✅ 支付宝登录功能可用")
    else:
        print("ℹ️  支付宝登录功能待配置")

    print("\n【快速开始】")
    print("=" * 60)

    if not all([os.getenv("WECHAT_APP_ID"), os.getenv("ALIPAY_APP_ID")]):
        print("建议配置步骤:")
        print("1. 复制 .env.example 为 .env")
        print("2. 根据需要配置微信/支付宝环境变量")
        print("3. 运行 python migrate_add_oauth_fields.py 迁移数据库")
        print("4. 启动服务: uvicorn快app.main:app --reload")

    print("=" * 60)


if __name__ == "__main__":
    main()
