# fix_db.py
from sqlalchemy import select, func
from database.engine import get_db_session
from database.models import Project

def fix_duplicate_projects():
    print("正在检查数据库中的重复项目...")
    with get_db_session() as session:
        # 1. 查找所有重复的项目名称
        subq = (
            session.query(Project.name, func.count(Project.id).label('count'))
            .group_by(Project.name)
            .having(func.count(Project.id) > 1)
        ).all()

        if not subq:
            print("✅ 数据库正常，未发现重复项目。")
            return

        print(f"⚠️ 发现 {len(subq)} 组重复项目，开始清理...")

        for name, count in subq:
            print(f" -> 处理项目 '{name}' (共 {count} 条记录)...")
            
            # 查找该项目名的所有记录，按 ID 排序
            projects = session.execute(
                select(Project).where(Project.name == name).order_by(Project.id)
            ).scalars().all()

            # 保留第一个（ID最小的），删除其余的
            keep_project = projects[0]
            drop_projects = projects[1:]

            for p in drop_projects:
                print(f"    - 删除重复记录 ID: {p.id}")
                session.delete(p)
            
            print(f"    + 保留记录 ID: {keep_project.id}")

        try:
            session.commit()
            print("✅ 清理完成，数据库已恢复正常。")
        except Exception as e:
            session.rollback()
            print(f"❌ 清理失败: {str(e)}")

if __name__ == "__main__":
    fix_duplicate_projects()