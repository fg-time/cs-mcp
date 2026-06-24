# CS-MCP

让 Claude 替你操作 Cobalt Strike。

不用点 GUI，不用写 Sleep 脚本，直接用自然语言让 AI 帮你列 beacon、执行命令、生成 payload。基于 CS 自带的 agscript 无头客户端，不依赖 REST API，CS 4.8 破解版就能跑。

## 为啥要自己写一个

[MickeyDB/Cobalt-Strike-MCP](https://github.com/MickeyDB/Cobalt-Strike-MCP) 是目前最完善的 CS MCP 方案，200+ 工具，但它依赖 **CS 4.12 新增的 REST API**。4.12 之前的版本（包括 uCare@Pwn3rs 破解的 4.8）只有 agscript 命令行入口。

于是有了这个项目 — 绕开 REST API，直接搓 agscript：

- **动态 CNA 生成**：每次操作实时生成一个 Sleep 脚本，喂给 agscript 执行，结果写到临时文件再解析回来
- **artifact_payload 可用**：踩坑后发现 `artifact_payload()` 在 headless 模式下直接返回数据，不依赖 GUI 回调（`artifact_stageless()` 就不行，会在 headless 卡死）
- **payload 生成打通**：证明 headless 也能生成 exe/dll/raw/powershell/python 全格式
- **HTTP Hosts 字段问题**：发现 `listener_create` 只设了 Stager Host，beacon 回连实际用的是 `beacons` 字段（HTTP Hosts），headless 下得用 GUI 补设

## 接入 Claude Code

```bash
git clone https://github.com/fg-time/Cobalt-Strike-4.8-MCP.git && cd cs-mcp && pip install mcp && python cs_mcp_server.py test
```

加到 `.claude/settings.json` 里：

```json
{
  "mcpServers": {
    "cs-mcp": {
      "command": "python",
      "args": ["D:/ct gongji/cs-mcp/cs_mcp_server.py"]
    }
  }
}
```

或者用环境变量配 TeamServer 地址和密码：

```bash
export CS_DIR="D:/ct gongji/cs"
export CS_HOST="127.0.0.1"
export CS_PORT="50050"
export CS_PASS="123"
python cs_mcp_server.py
```

## 能干什么

接入后直接跟 Claude 说话就行，比如：

- "列一下现在有几个 beacon"
- "对 xxx beacon 执行 whoami"
- "给 http 监听器生成个 x64 exe 存到 payloads 目录"
- "把 beacon 的 sleep 改成 3 秒"

一共 11 个工具：

| 工具 | 干什么的 |
|------|---------|
| `cs_list_beacons` | 列出所有在线 beacon，包含用户名、机器名、内外网 IP |
| `cs_list_listeners` | 列出所有监听器，包含回连地址和端口 |
| `cs_get_beacon` | 查某个 beacon 的详细信息 |
| `cs_get_listener_detail` | 查监听器完整配置，包括 HTTP Hosts 和 Stager Host |
| `cs_exec_beacon` | 在 beacon 上执行 shell 命令 |
| `cs_beacon_sleep` | 调整 beacon 回连间隔和抖动 |
| `cs_beacon_note` | 给 beacon 加备注 |
| `cs_beacon_kill` | 干掉某个 beacon |
| `cs_create_listener` | 新建监听器（HTTP/HTTPS/DNS/SMB/TCP 都行） |
| `cs_delete_listener` | 删监听器（CS 4.8 只能在 GUI 删，这个会提示你） |
| `cs_generate_payload` | 生成 payload，支持 raw/exe/dll/powershell/python，x64/x86 |

## 怎么工作的

```
你说话 → Claude → MCP → Python 动态生成 CNA → agscript → TeamServer
                                                        ↓
                                                 结果写进临时文件
                                                        ↓
你看到结果 ← Claude ← JSON ← Python 解析 ←────────────┘
```

每次操作会启动一个新的 agscript 进程（JVM 冷启动大概 5 秒），执行完就退出。没有长连接，不用担心占着坑导致 GUI 登不上。

## 跟同类项目的区别

| | CS-MCP | MickeyDB MCP | sleep_python_bridge |
|---|---|---|---|
| 支持版本 | CS 4.8 | CS 4.12+ | CS 4.8 |
| 通信方式 | agscript 动态 CNA | CS REST API | agscript + pexpect |
| Windows 能用 | ✅ | ✅ | ❌ pexpect 不兼容 |
| 工具数量 | 11 | 200+ | Python 函数库 |
| payload 生成 | ✅ artifact_payload | ✅ REST API | ✅ |
| 创建监听器 | ⚠️ stager host OK，HTTP Hosts 建议 GUI 确认 | ✅ API 完整 | ✅ |

简单来说：**MickeyDB 功能最全但要 CS 4.12+，sleep_python_bridge 在 Windows 跑不了，CS-MCP 是 CS 4.8 破解版在 Windows 上唯一能用的 LLM 控制方案。**

## CS 4.8 的坑

| 情况 | 状态 | 说明 |
|------|------|------|
| `artifact_payload()` | ✅ 能用 | 直接返回数据，不卡 |
| `artifact_stageless()` | ❌ 卡死 | 依赖 GUI 异步回调，headless 模式必挂 |
| `listener_create()` | ⚠️ 半残 | 能设 Stager Host，但 HTTP Hosts（beacons 字段）没设上，payload 生成的回连地址可能是错的。建议创建后用 `cs_get_listener_detail` 验证 |
| `listener_remove()` | ❌ 没有 | CS 4.8 headless API 不支持，去 GUI 删 |
| 多监听器同端口 | ❌ 冲突 | 后面创建的会静默失败，日志里能看到 `Another Beacon listener exists on port XXXX` |

## License

MIT
