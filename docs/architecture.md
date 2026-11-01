# 当前架构：所有权、候选与证据边界

![OpenBound 架构：一个任务负责人；私人源生成公共候选；检查和验证产生私人证据；仅候选通过宿主授权边界交付。](architecture.png)

这张图回答：谁负责完整成果、哪些材料进入候选、什么证据可以复用、什么动作需要 Host 的实际授权与观察？

顶部是任务控制关系。OpenBound 持有完整委托；references 因具体阻碍被读取，结束后回到同一任务。持久化上下文只是恢复手段，普通任务不必创建额外文件。

中部是当前已实现的本地工具与数据。私人材料经过 Agent 编辑和显式投影，形成有身份的公共候选。检查器观察选择的文件和 Git 表面；验证工具在临时副本执行已审查的检查。回执始终是私人控制材料，绑定内容、规则与执行输入，不能成为安全或授权证书。虚线表示证据观察/返回，实线表示任务控制或候选数据流；节点文字也明确区分，颜色不是唯一编码。

底部属于 Host。实际用户授权决定提交、push、visibility、Release、包发布和部署；工程包没有自行授予这些权限，也没有执行这些外部动作。已观察外部状态与本地准备是不同的完成声明。

## 编辑和复现

- [architecture-model.json](architecture-model.json)：节点、关系、区域、几何与源码证据的中立模型。
- [architecture.excalidraw](architecture.excalidraw)：可编辑原生形状和已绑定的连接器。
- [architecture.svg](architecture.svg)：本地矢量导出，包含等价无障碍说明。
- [architecture.png](architecture.png)：同一几何的实际栅格渲染。

运行 `python3 tools/render_architecture.py` 重新生成 SVG 和 Excalidraw。PNG 可由任一可信本地 SVG 渲染器导出；本次使用 Sharp/libvips 并实际打开 PNG 检查。原生 Excalidraw Host 导入交互尚未作为命名 Host 验收。修改时保持模型、原生源及导出一致，重新检查实际图片。

图中的 implemented 表示交付源码存在且相应工具有本地测试，不代表所有真实项目或 Host 的运行保证。图不引入新的进程、服务、授权代理或固定流水线。
