# 电化学工作站复现

低成本 CV / OCPT 电化学工作站的硬件设计、固件和上位机调试软件。

## 目录

- `hardware/board/`: PCB 工程、原理图 PDF 和 BOM
- `software/adc_debugger/`: ESP32-C3 / ADS1115 调试上位机、MicroPython 固件和构建脚本
- `archive/`: 本地归档资料，不纳入 Git

## 上位机

进入 `software/adc_debugger/` 后，安装依赖并运行：

```bash
python -m pip install -r requirements.txt
./run_linux.sh
```

Linux 和 Windows 的打包脚本分别是 `build_linux.sh` 和 `build_windows.bat`。`build/`、`dist/` 等构建结果不会提交到 Git。

## 协作约定

- 功能开发使用独立分支，合并前提交清晰的变更说明。
- 硬件工程修改后，同时更新对应的 BOM 或导出文件。
- 实验数据、会议材料和临时导出文件放入本地 `archive/`，不要直接提交到源码仓库。
