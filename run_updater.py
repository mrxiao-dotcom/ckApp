import os
import sys

# 添加项目根目录到 Python 路径
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app.price_updater import PriceUpdater

if __name__ == "__main__":
    try:
        # 根据命令行参数决定运行模式
        if len(sys.argv) > 1:
            if sys.argv[1] == '--once':
                # 单次运行价格范围更新
                updater = PriceUpdater()
                updater.run()
            elif sys.argv[1] == '--tick':
                # 单次运行实时行情更新
                updater = PriceUpdater()
                updater.update_ticks()
            elif sys.argv[1] == '--update':
                # 单次运行实时行情更新
                updater = PriceUpdater()
                updater.update_price_range()
        else:
            # 调度器模式
            from app.price_updater import run_scheduler
            run_scheduler()
    except Exception as e:
        print(f"程序运行失败: {str(e)}")
        sys.exit(1) 