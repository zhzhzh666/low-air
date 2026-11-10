# SZU Yuehai HTML Simulation

交互式 WebGL 三维回放，数据来自 `SZU_Yuehai_Simulation/data` 与重新运行生成的 `results`。页面会在浏览器中生成 2,106 栋建筑体块、道路表面以及卡车/无人机三维轨迹，并显示八方向风场、节点天气分类、20% 电量阈值和换电记录。

## 运行

在本目录执行：

```powershell
python -m http.server 8765 --directory dist
```

然后访问 `http://127.0.0.1:8765/`。

页面不依赖外部 CDN，可离线运行。支持拖动旋转、滚轮缩放、全景复位与跟随卡车。卡车每到一个节点重新读取天气，0–8 m/s 为常规风况，8–14 m/s 为强风，达到 14 m/s 时仅派卡车。由于浏览器安全策略，不能直接双击 `index.html` 后通过 `file://` 加载 JSON 数据。
