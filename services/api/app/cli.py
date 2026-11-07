import argparse
import getpass
import secrets

from sqlalchemy import select

from .auth import create_user
from .db import DATA_DIR, SessionLocal
from .models import ServicePlan, User


def main():
    parser = argparse.ArgumentParser(description='CreatorOS 本地初始化工具')
    parser.add_argument('command', choices=['init-admin'])
    parser.add_argument('--email', default='owner@creatoros.local')
    parser.add_argument('--name', default='CreatorOS 老板')
    parser.add_argument('--generate', action='store_true', help='随机生成密码写入仅本地 data/admin-credentials.txt')
    args = parser.parse_args()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.role == 'OWNER_ADMIN'))
        if existing:
            print('管理员已存在；未更改现有账号或密码。')
            return
        password = secrets.token_urlsafe(24) if args.generate else getpass.getpass('设置管理员密码（至少 10 位，不回显）: ')
        if len(password) < 10:
            raise SystemExit('密码至少 10 位')
        user = create_user(db, args.email, password, args.name, role='OWNER_ADMIN')
        for name, price, description in [('简版内容诊断', 0, '本地基础分析与研究流程体验'), ('单次深度诊断', 99, '一次 MiMo 内容诊断与改进脚本'), ('持续账号顾问', 499, '账号数据复盘、创作实验和策略建议')]:
            db.add(ServicePlan(organization_id=user.organization_id, name=name, price=price, data={'description': description, 'pricing_status': '试运营报价，非实际收款'}))
        db.commit()
        if args.generate:
            credential_file = DATA_DIR / 'admin-credentials.txt'
            credential_file.write_text(f'仅本地开发管理员凭证，请妥善保管。\n邮箱: {args.email}\n密码: {password}\n', encoding='utf-8')
            print(f'已生成随机管理员凭证，保存在 {credential_file}（Git 忽略，不在日志显示）。')
        else:
            print('管理员创建成功。')


if __name__ == '__main__':
    main()
