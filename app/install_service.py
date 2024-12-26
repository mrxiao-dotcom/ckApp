import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import time

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app.price_updater import PriceUpdater, run_scheduler

class PriceUpdateService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PriceUpdateService"
    _svc_display_name_ = "Price Update Service"
    _svc_description_ = "Service for updating cryptocurrency price ranges"
    
    # 添加服务账户配置
    _svc_deps_ = ["EventLog"]  # 依赖的其他服务
    _exe_name_ = sys.executable  # Python解释器路径
    _exe_args_ = '"%s"' % os.path.abspath(sys.argv[0])  # 脚本路径
    
    # 添加自动启动配置
    _svc_start_type_ = win32service.SERVICE_AUTO_START  # 自动启动
    
    # 添加恢复选项
    _svc_reg_flags_ = win32service.SERVICE_WIN32_OWN_PROCESS
    _svc_recovery_actions_ = [
        (win32service.SC_ACTION_RESTART, 0),  # 立即重启
        (win32service.SC_ACTION_RESTART, 60000),  # 1分钟后重启
        (win32service.SC_ACTION_RESTART, 120000)  # 2分钟后重启
    ]
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True
        self.timeout = 30000  # 30 seconds timeout

    def SvcStop(self):
        """停止服务"""
        try:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.is_alive = False
        except Exception as e:
            servicemanager.LogErrorMsg(f"Error stopping service: {str(e)}")

    def SvcDoRun(self):
        """运行服务"""
        try:
            # 报告启动中状态
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            
            # 初始化服务
            try:
                # 设置工作目录
                os.chdir(project_dir)
                
                # 初始化日志
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTING,
                    (self._svc_name_, 'Initializing service...')
                )
                
                # 报告运行状态
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                
                # 运行主循环
                self.main()
                
            except Exception as e:
                servicemanager.LogErrorMsg(f"Service initialization failed: {str(e)}")
                self.SvcStop()
                return
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Service startup failed: {str(e)}")
            self.SvcStop()

    def main(self):
        """主要服务逻辑"""
        try:
            while self.is_alive:
                try:
                    # 检查停止事件
                    if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                        break
                    
                    # 运行调度器
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_INFORMATION_TYPE,
                        0,
                        "Running scheduler..."
                    )
                    run_scheduler()
                    
                except Exception as e:
                    servicemanager.LogErrorMsg(f"Error in scheduler: {str(e)}")
                    # 继续运行，不退出循环
                    time.sleep(60)  # 出错后等待1分钟再重试
                    
        except Exception as e:
            servicemanager.LogErrorMsg(f"Error in main loop: {str(e)}")
            self.SvcStop()

def get_service_status():
    """获取服务状态"""
    try:
        status = win32serviceutil.QueryServiceStatus(PriceUpdateService._svc_name_)
        status_map = {
            win32service.SERVICE_STOPPED: 'STOPPED',
            win32service.SERVICE_START_PENDING: 'STARTING',
            win32service.SERVICE_STOP_PENDING: 'STOPPING',
            win32service.SERVICE_RUNNING: 'RUNNING',
            win32service.SERVICE_CONTINUE_PENDING: 'CONTINUING',
            win32service.SERVICE_PAUSE_PENDING: 'PAUSING',
            win32service.SERVICE_PAUSED: 'PAUSED'
        }
        return status_map.get(status[1], 'UNKNOWN')
    except Exception as e:
        return f"ERROR: {str(e)}"

def print_usage():
    """打印使用说明"""
    print("Usage:")
    print("  install   - Install service")
    print("  remove    - Remove service")
    print("  start     - Start service")
    print("  stop      - Stop service")
    print("  restart   - Restart service")
    print("  status    - Show service status")
    print("  debug     - Run in debug mode")

def force_stop_service():
    """强制停止服务"""
    try:
        # 获取服务句柄
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        try:
            hs = win32service.OpenService(scm, PriceUpdateService._svc_name_, win32service.SERVICE_ALL_ACCESS)
            try:
                status = win32service.QueryServiceStatus(hs)[1]
                if status == win32service.SERVICE_STOPPED:
                    return True
                
                # 强制停止
                win32service.ControlService(hs, win32service.SERVICE_CONTROL_STOP)
                
                # 等待服务停止
                for _ in range(30):  # 最多等待30秒
                    status = win32service.QueryServiceStatus(hs)[1]
                    if status == win32service.SERVICE_STOPPED:
                        return True
                    time.sleep(1)
                
                return False
            finally:
                win32service.CloseServiceHandle(hs)
        finally:
            win32service.CloseServiceHandle(scm)
    except Exception as e:
        print(f"Error force stopping service: {str(e)}")
        return False

def clean_service():
    """清理服务"""
    try:
        # 尝试停止服务
        force_stop_service()
        
        # 尝试删除服务
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        try:
            hs = win32service.OpenService(scm, PriceUpdateService._svc_name_, win32service.SERVICE_ALL_ACCESS)
            try:
                win32service.DeleteService(hs)
                return True
            except Exception as e:
                print(f"Error deleting service: {str(e)}")
            finally:
                win32service.CloseServiceHandle(hs)
        finally:
            win32service.CloseServiceHandle(scm)
    except Exception as e:
        print(f"Error cleaning service: {str(e)}")
    return False

def install_service():
    """安装服务"""
    try:
        # 确保以管理员权限运行
        if not is_admin():
            print("Error: This command must be run as Administrator")
            return False
            
        # 清理现有服务
        clean_service()
        
        # 直接使用 win32serviceutil 安装服务
        win32serviceutil.InstallService(
            pythonClassString=f"{__name__}.PriceUpdateService",
            serviceName=PriceUpdateService._svc_name_,
            displayName=PriceUpdateService._svc_display_name_,
            description=PriceUpdateService._svc_description_,
            startType=win32service.SERVICE_AUTO_START,
            userName="LocalSystem",
            password=None
        )
        
        print("Service installed successfully")
        return True
            
    except Exception as e:
        print(f"Error during installation: {str(e)}")
        return False

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PriceUpdateService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        cmd = sys.argv[1].lower()
        try:
            if cmd == 'install':
                if install_service():
                    print("Service installation completed")
                    # 安装后自动启动服务
                    win32serviceutil.StartService(PriceUpdateService._svc_name_)
                    print("Service started")
                else:
                    sys.exit(1)
            elif cmd == 'status':
                status = get_service_status()
                print(f"Service Status: {status}")
            elif cmd == 'stop':
                print("Attempting to stop service...")
                if force_stop_service():
                    print("Service stopped successfully")
                else:
                    print("Failed to stop service")
            elif cmd == 'start':
                print("Starting service...")
                win32serviceutil.StartService(PriceUpdateService._svc_name_)
                print("Service started")
            elif cmd == 'restart':
                print("Restarting service...")
                win32serviceutil.RestartService(PriceUpdateService._svc_name_)
                print("Service restarted")
            elif cmd == 'remove':
                print("Removing service...")
                win32serviceutil.RemoveService(PriceUpdateService._svc_name_)
                print("Service removed")
            elif cmd == 'debug':
                print("Running in debug mode...")
                run_scheduler()
            else:
                print_usage()
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1) 