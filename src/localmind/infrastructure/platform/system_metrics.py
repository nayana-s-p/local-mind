"""Local, sampled psutil metrics; no network requests."""

import platform
import time
from datetime import datetime

import psutil

from localmind.domain.tasks import TaskResult
from localmind.infrastructure.filesystem.inspection import size_text


class SystemMetrics:
    def execute(self, request, scope, event, progress):
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(scope or "/")
        cpu = psutil.cpu_percent(interval=0.15)
        data = {"sampled_at": datetime.now().astimezone().isoformat(timespec="seconds"), "cpu_percent": cpu,
                "memory_available": memory.available, "memory_total": memory.total, "memory_percent": memory.percent,
                "disk_free": disk.free, "disk_total": disk.total, "os": platform.platform(), "machine": platform.machine(),
                "logical_cpus": psutil.cpu_count(), "uptime_seconds": max(0, time.time() - psutil.boot_time())}
        lines = [f"Sampled: {data['sampled_at']}", f"CPU: {cpu:.1f}% (150 ms sample), {data['logical_cpus']} logical cores",
                 f"RAM: {size_text(memory.available)} available of {size_text(memory.total)} ({memory.percent:.1f}% used)",
                 f"Disk ({scope or '/'}): {size_text(disk.free)} free of {size_text(disk.total)}", f"OS: {data['os']} · {data['machine']}",
                 f"Uptime: {data['uptime_seconds'] / 3600:.1f} hours"]
        if request.task_id == "S08":
            battery = psutil.sensors_battery()
            data["battery_percent"] = battery.percent if battery else None
            lines.append(f"Battery: {battery.percent:.0f}% · plugged in: {battery.power_plugged}" if battery else "Battery readings are unavailable on this computer.")
        if request.task_id == "S06":
            processes = []
            for process in psutil.process_iter(["pid", "name", "memory_info"]):
                if event.is_set():
                    break
                try:
                    info = process.info
                    if info["memory_info"]:
                        processes.append((info["memory_info"].rss, info["pid"], info["name"]))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            data["processes"] = [{"rss": rss, "pid": pid, "name": name} for rss, pid, name in sorted(processes, reverse=True)[:10]]
            lines.extend(f"{item['name']} (PID {item['pid']}): {size_text(item['rss'])} RSS" for item in data["processes"])
        return TaskResult(request.task_id, True, "\n".join(lines), data, suggestions=("Update system stats",))
